import asyncio
import re
from collections import defaultdict
from typing import Optional, Dict, List

import discord
import wavelink
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient
from thefuzz import process
from wavelink.ext import spotify

from assistant import AssistantBot
from config import LavaConfig, HOME_GUILD_ID, STATUS, ACTIVITY_TYPE, ACTIVITY_TEXT
from utils import check_vc, remove_brackets, YTTrack, YTPlaylist, clickable_song

url_rx = re.compile(r'https?://(?:www\.)?.+')
yt_video_rx = r'^(?:https?://(?:www\.)?youtube\.com/watch\?(?=.*v=\w+)(?:\S+)?|https?://youtu\.be/\w+)$'
yt_playlist_rx = r'^https?://(?:www\.)?youtube\.com/playlist\?(?=.*list=\w+)(?:\S+)?$'
spotify_rx = r'https?://(?:open\.)?spotify\.com/(?:track|playlist)/[^\s?/]+'


class Play(commands.Cog):
    def __init__(self, bot: AssistantBot):
        self.bot = bot
        self._mongo_client: Optional[AsyncIOMotorClient] = None  # type: ignore
        self._cache: Dict[int, List[Dict[str, str]]] = defaultdict(list)

    @property
    def mongo_client(self) -> AsyncIOMotorClient:  # type: ignore
        if not self._mongo_client:
            self._mongo_client = self.bot.connect_to_mongo()
        return self._mongo_client

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.Node) -> None:
        self.bot.logger.info(f"[LAVALINK] Node {node.id} is ready.")

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackEventPayload) -> None:
        assert payload.player.guild is not None
        self.bot.logger.info(f"[LAVALINK] Playing {payload.track.title} on {payload.player.guild}")
        await self._add_track_to_db(payload.player)
        if payload.player.guild.id == HOME_GUILD_ID:
            await self.bot.change_presence(status=STATUS,
                                           activity=discord.Activity(type=discord.ActivityType.listening,
                                                                     name=remove_brackets(payload.track.title)))

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEventPayload) -> None:
        assert payload.player.guild is not None
        self.bot.logger.info(f"[LAVALINK] Finished playing {payload.track.title} on {payload.player.guild}")
        if payload.player.queue.count or payload.player.queue.loop:
            await payload.player.play(payload.player.queue.get())
            await asyncio.sleep(1)
        if not payload.player.current:
            if payload.player.guild.id == HOME_GUILD_ID:
                await self.bot.change_presence(status=STATUS,
                                               activity=discord.Activity(type=ACTIVITY_TYPE, name=ACTIVITY_TEXT), )

    async def _fill_cache(self, guild_id: int):
        db = self.mongo_client["assistant"]
        collection = db["songHistory"]
        history = await collection.find_one({"_id": guild_id})
        self._cache[guild_id].extend({song['title']: song['uri']} for song in history['songs'])

    async def _add_track_to_db(self, player: wavelink.Player):
        assert player.guild is not None
        assert player.current is not None
        guild_id = player.guild.id
        track = player.current
        if not isinstance(track, wavelink.YouTubeTrack):
            return
        uri = f"https://www.youtube.com/watch?v={track.identifier}"
        title = track.title
        if not self._cache[guild_id]:
            await self._fill_cache(guild_id)
        self._cache[guild_id].append({title: uri})
        db = self.mongo_client["assistant"]
        collection = db["songHistory"]
        await collection.update_one(
            {"_id": guild_id},
            {"$addToSet": {"songs": dict(title=title, uri=uri)}},
            upsert=True
        )

    @commands.hybrid_command(name="play", aliases=["p"], description="Play a song")
    @app_commands.describe(query="Title/URL of the song to play")
    @commands.guild_only()
    @check_vc()
    async def play(self, ctx: commands.Context, *, query: Optional[str] = None):
        assert isinstance(ctx.author, discord.Member)
        if not ctx.voice_client:
            vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player(),  # type: ignore
                                                                         self_deaf=True)
        else:
            vc: wavelink.Player = ctx.voice_client  # type: ignore

        if not query:
            if not vc.is_playing() or not vc.current:
                await ctx.send("I am not playing anything right now.")
                return
            if vc.is_paused():
                await vc.resume()
                await ctx.send(f"Resuming: {clickable_song(vc.current)}", suppress_embeds=True)
            else:
                await vc.pause()
                await ctx.send(f"Paused: {clickable_song(vc.current)}", suppress_embeds=True)
            return

        await ctx.defer()

        if re.match(yt_video_rx, query) or not re.match(url_rx, query):  # single video
            track: YTTrack = await YTTrack.search(query)
            track.requested_by = ctx.author
            vc.queue.put(track)
            await ctx.send(f"Added {clickable_song(track)} to queue", suppress_embeds=True)
        elif re.match(yt_playlist_rx, query):  # yt playlist
            tracks: YTPlaylist = await YTPlaylist.search(query)  # type: ignore
            assert isinstance(tracks, YTPlaylist)
            tracks.requested_by = ctx.author
            for t in tracks.tracks:
                vc.queue.put(t)
            await ctx.send(f"Added {len(tracks.tracks)} songs to queue")
        elif re.match(spotify_rx, query):  # spotify track
            decoded = spotify.decode_url(query)
            if not decoded:
                await ctx.send("Invalid Spotify URL")
                return
            if decoded.type == spotify.SpotifySearchType.track:
                tracks: list[spotify.SpotifyTrack] = await spotify.SpotifyTrack.search(query)
                vc.queue.put(tracks[0])
                await ctx.send(f"Added {clickable_song(tracks[0])} to queue")
            elif decoded.type == spotify.SpotifySearchType.playlist:
                tracks: list[spotify.SpotifyTrack] = await spotify.SpotifyTrack.search(query)
                for t in tracks:
                    vc.queue.put(t)
                await ctx.send(f"Added {len(tracks)} songs to queue")
        else:
            await ctx.send("Invalid URL or query")
            return  # invalid url

        if not vc.is_playing():
            await vc.play(track=vc.queue.get())
            await vc.set_volume(100)

    @play.autocomplete('query')
    async def play_autocomplete(self, ctx: discord.Interaction, query: str):
        assert ctx.guild is not None
        if query == "":
            return [Choice(name="Enter a song name or URL", value="https://youtu.be/dQw4w9WgXcQ")]
        result = {"Search: " + query: query} if query else {}
        guild_id = ctx.guild.id
        if guild_id not in self._cache:
            await self._fill_cache(guild_id)
        search = [s[0] for s in process.extractBests(query, self._cache[guild_id], limit=24, score_cutoff=70)]
        for s in search:
            result |= s

        return [Choice(name=k, value=v) for k, v in result.items()]


async def setup(bot: AssistantBot):
    lc = LavaConfig()
    if not lc:
        return
    await bot.add_cog(Play(bot))
