from typing import cast, Optional

import wavelink
from discord import app_commands
from discord.ext import commands

from assistant import AssistantBot
from config import LAVA_CONFIG, OWNER_ID
from utils import check_same_vc, check_vc, clickable_song


class MusicCommands(commands.Cog):
    def __init__(self, bot: AssistantBot):
        self.bot = bot

    def get_voice_client(self, ctx: commands.Context) -> wavelink.Player:
        vc = ctx.guild.voice_client
        if not vc:
            self.bot.logger.debug("[MUSIC] Creating a new voice client. idk why?")
            vc = ctx.author.voice.channel.connect(cls=wavelink.Player, self_deaf=True)
        return cast(wavelink.Player, vc)

    @commands.hybrid_command(name="skip", aliases=["s", "next"], description="Skip songs that are in queue")
    @commands.guild_only()
    @check_vc()
    @check_same_vc()
    @app_commands.describe(index="Index of the song to skip")
    async def skip(self, ctx: commands.Context, index: int = 0):
        vc = self.get_voice_client(ctx)
        if vc.current is None and vc.queue.is_empty:
            await ctx.send("I am not playing anything right now.")
            return
        if index == 0:
            await ctx.send(f"Skipping {clickable_song(vc.current)}", suppress_embeds=True)
            await vc.stop()
            return
        if index > vc.queue.count or index < 0:
            await ctx.send("Invalid index")
            return
        else:
            await ctx.send(f"Skipping {clickable_song(vc.queue[index - 1])}", suppress_embeds=True)
            vc.queue.delete(index - 1)

    @commands.hybrid_command(name="loop", aliases=["l"], description="Loop the current song")
    @commands.guild_only()
    @check_vc()
    @check_same_vc()
    async def loop(self, ctx: commands.Context):
        vc = self.get_voice_client(ctx)
        if vc.current is None and vc.queue.is_empty:
            await ctx.send("I am not playing anything right now.")
            return
        if vc.queue.mode is wavelink.QueueMode.normal:
            vc.queue.mode = wavelink.QueueMode.loop_all
            await ctx.send("Looping is now enabled.")
        else:
            vc.queue.mode = wavelink.QueueMode.normal
            await ctx.send("Looping is now disabled.")

    @commands.hybrid_command(name="volume", aliases=["v", "vol"], description="Change the volume")
    @commands.guild_only()
    @check_vc()
    @check_same_vc()
    @app_commands.describe(volume="Volume to set [0 - 100]")
    async def volume(self, ctx: commands.Context, volume: int):
        vc = self.get_voice_client(ctx)
        if vc.current is None and vc.queue.is_empty:
            await ctx.send("I am not playing anything right now.")
            return
        if ctx.author.id == OWNER_ID:
            await vc.set_volume(volume)
            await ctx.send(f"Volume set to `{volume} %`")
            return
        if volume < 0 or volume > 100:
            await ctx.send("Invalid volume")
            return
        await vc.set_volume(volume)
        await ctx.send(f"Volume set to `{volume} %`")

    @commands.hybrid_command(name="stop", aliases=["leave", "disconnect", "dc"], description="Stops the music and disconnects the bot from the voice channel")
    @commands.guild_only()
    @check_vc()
    @check_same_vc()
    async def stop(self, ctx: commands.Context):
        assert ctx.guild
        vc = self.get_voice_client(ctx)
        if not vc or not vc.connected or not ctx.guild.voice_client:
            return await ctx.send("I am not connected to a voice channel", ephemeral=True)
        vc.queue.clear()
        await vc.stop()
        await ctx.guild.voice_client.disconnect(force=True)
        await ctx.send("Thanks for Listening")

    @commands.hybrid_command(name="skipto", aliases=["st"], description="Skip to a specific song in the queue")
    @commands.guild_only()
    @check_vc()
    @check_same_vc()
    @app_commands.describe(index="Index of the song to skip to")
    async def skipto(self, ctx: commands.Context, index: int = 0):
        vc = self.get_voice_client(ctx)
        if vc.current is None:
            await ctx.send("I am not playing anything right now.")
            return
        if index == 0:
            await ctx.send(f"Skipping {clickable_song(vc.current)}", suppress_embeds=True)
            await vc.stop()
            return
        if index > vc.queue.count or index < 0:
            await ctx.send("Invalid index")
            return
        else:
            await ctx.send(f"Skipping to {clickable_song(vc.queue[index - 1])}", suppress_embeds=True)
            vc.queue.swap(0, index - 1)
            vc.queue.put_at(index, vc.current)
            await vc.stop()

    @commands.hybrid_command(name="seek", description="Seek to a specific time in the song")
    @commands.guild_only()
    @check_vc()
    @check_same_vc()
    @app_commands.describe(time="Time to seek to in MM:SS format")
    async def seek(self, ctx: commands.Context, time: Optional[str] = None):
        vc = self.get_voice_client(ctx)
        if vc.current is None:
            await ctx.send("I am not playing anything right now.")
            return

        def time_in_seconds(timestamp: str) -> int:
            """
            Converts a timestamp string to seconds.
            """
            time_components = timestamp.split(':') if ':' in timestamp else timestamp.split('.')
            time_components = [int(comp) for comp in time_components]

            if any(comp < 0 or comp >= 60 for comp in time_components):
                return 0

            seconds = sum(comp * 60 ** (len(time_components) - idx - 1) for idx, comp in enumerate(time_components))
            return seconds

        if not time:
            await vc.seek(0)
            await ctx.send("Seeked to Beginning")
        else:
            await vc.seek(time_in_seconds(time) * 1000)
            await ctx.send(f"Seeked to {time}")


async def setup(bot: AssistantBot):
    if LAVA_CONFIG:
        await bot.add_cog(MusicCommands(bot))
