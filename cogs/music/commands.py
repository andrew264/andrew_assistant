﻿# Imports
import lavalink
from disnake import (
    Activity,
    ActivityType,
    Client,
    Status,
)
from disnake.ext import commands

from cogs.music.misc import AddTagstoJSON

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -multiple_requests 1",
    "options": "-vn",
}


class Music(commands.Cog):
    def __init__(self, client: Client):
        self.client = client

        lavalink.add_event_hook(self.track_hook)

    def cog_unload(self):
        """ Cog unload handler. This removes any event hooks that were registered. """
        self.client.lavalink._event_hooks.clear()

    async def track_hook(self, event):
        # Update client's status
        # Cuz why not ?
        if isinstance(event, lavalink.events.TrackStartEvent):
            song = event.player.current
            if song:
                await self.client.change_presence(activity=Activity(type=ActivityType.listening,
                                                                    name=song.Title, ))
        if isinstance(event, lavalink.events.QueueEndEvent):
            await self.client.change_presence(status=Status.online, activity=Activity(type=ActivityType.watching,
                                                                                      name="yall Homies."), )

    # Skip
    @commands.command()
    @commands.guild_only()
    async def skip(self, ctx: commands.Context, arg: int = 0) -> None:
        player = self.client.lavalink.player_manager.get(ctx.guild.id)
        await ctx.message.delete()
        if not player.is_playing or arg > len(player.queue):
            return
        if 0 < arg <= len(player.queue):
            await ctx.send(f"{ctx.author.display_name} removed `{player.queue[arg - 1].Title}` from Queue.",
                           delete_after=30)
            player.queue.pop(arg - 1)
        elif arg == 0:
            await ctx.send(f"{ctx.author.display_name} removed `{player.current.Title}` from Queue.",
                           delete_after=30)
            await player.skip()

    # Stop
    @commands.command(aliases=["dc", "kelambu"])
    @commands.guild_only()
    async def stop(self, ctx: commands.Context) -> None:
        player = self.client.lavalink.player_manager.get(ctx.guild.id)
        if player.is_playing or player.paused:
            # Clear the queue to ensure old tracks don't start playing
            # when someone else queues something.
            player.queue.clear()
            # Stop the current track so Lavalink consumes less resources.
            await player.stop()
            # Disconnect from the voice channel.
            await ctx.voice_client.disconnect(force=True)
        await ctx.message.add_reaction("👋")
        await ctx.message.delete(delay=30)

    # Pause
    @commands.command()
    @commands.guild_only()
    async def pause(self, ctx: commands.Context) -> None:
        player = self.client.lavalink.player_manager.get(ctx.guild.id)
        await ctx.message.delete()
        if player.paused is False:
            await player.set_pause(pause=True)
            await ctx.send(f"{ctx.author.display_name} paused `{player.current.Title}`", delete_after=30)
        else:
            await player.set_pause(pause=False)
            await ctx.send(f"{ctx.author.display_name} resumed `{player.current.Title}`", delete_after=30)

    # Loop
    @commands.command(aliases=["repeat"])
    @commands.guild_only()
    async def loop(self, ctx: commands.Context) -> None:
        player = self.client.lavalink.player_manager.get(ctx.guild.id)
        await ctx.message.delete()
        if player.repeat:
            player.set_repeat(False)
            await ctx.send("Loop Disabled", delete_after=30)
        else:
            player.set_repeat(True)
            await ctx.send("Loop Enabled", delete_after=30)

    # Jump
    @commands.command(aliases=["skipto"])
    @commands.guild_only()
    async def jump(self, ctx: commands.Context, song_index: int = 1) -> None:
        player = self.client.lavalink.player_manager.get(ctx.guild.id)
        await ctx.message.delete()
        if ctx.voice_client and player.is_playing and song_index >= 1:
            del player.queue[0:song_index - 1]
        await ctx.send("Skipped", delete_after=30)
        await player.play()

    # Volume
    @commands.command(aliases=["vol", "v"])
    @commands.guild_only()
    async def volume(self, ctx: commands.Context, volume_int: int = None) -> None:
        player = self.client.lavalink.player_manager.get(ctx.guild.id)
        await ctx.message.delete()
        if volume_int is None:
            await ctx.send(f"Volume: {player.volume}%", delete_after=15)
        elif 0 < volume_int <= 100:
            try:
                await player.set_volume(round(volume_int))
                await ctx.send(f"Volume is set to `{round(volume_int)}%`", delete_after=15)
            except AttributeError:
                pass
        else:
            await ctx.send("Set Volume between `1 and 100`.", delete_after=10)

    # Add Tags to Current Song
    @commands.is_owner()
    @commands.guild_only()
    @commands.command(aliases=["tag"])
    async def addtag(self, ctx: commands.Context, *, tag: str) -> None:
        player = self.client.lavalink.player_manager.get(ctx.guild.id)
        await ctx.message.delete()
        AddTagstoJSON(player.current.identifier, tag)
        await ctx.reply(f"TAG: **{tag}** added to **{player.current.Title}**", delete_after=15)

    # Check Bot in VC
    @skip.before_invoke
    @stop.before_invoke
    @pause.before_invoke
    @loop.before_invoke
    @jump.before_invoke
    @addtag.before_invoke
    @volume.before_invoke
    async def check_voice(self, ctx: commands.Context) -> None:
        player = self.client.lavalink.player_manager.get(ctx.guild.id)
        if ctx.voice_client is None or not player.is_connected:
            raise commands.CheckFailure("Bot is not connect to VC.")
        if ctx.author.voice is None:
            raise commands.CheckFailure("You are not connected to a voice channel.")
        if ctx.voice_client is not None and ctx.author.voice is not None:
            if ctx.voice_client.channel != ctx.author.voice.channel:
                raise commands.CheckFailure("You must be in same VC as Bot.")


def setup(client):
    client.add_cog(Music(client))
