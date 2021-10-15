# Imports
from disnake.ext import commands
from disnake.utils import get
from disnake import FFmpegOpusAudio, Embed, Activity, ActivityType, Status, Client
from disnake import Button, ButtonStyle, Interaction
from disnake.ui import View, button

import time, asyncio, re, math
from datetime import datetime
import yt_dlp.YoutubeDL as YDL
from enum import Enum
from pyyoutube import Api

from EnvVariables import YT_TOKEN

api = Api(api_key=YT_TOKEN)

ydl_opts = {
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'format': 'bestaudio/best',
}
FFMPEG_OPTIONS={'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -multiple_requests 1', 'options': '-vn'}

vid_url_regex = re.compile(r"^(https?\:\/\/)?(www\.)?(youtube\.com|youtu\.?be)\/.+$", re.IGNORECASE)
playlist_url_regex = re.compile(r"^(https?\:\/\/)?(www\.)?(youtube\.com)\/(playlist).+$", re.IGNORECASE)

def human_format(num):
    num = float('{:.3g}'.format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return '{}{}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'K', 'M', 'B', 'T'][magnitude])

class video_info:
    def __init__(self, YT_extract, author:str):
            self.Title:str = (YT_extract.get("title", None))
            self.pURL:str = (YT_extract.get("webpage_url"))
            self.URL:str = (YT_extract["formats"][0]["url"])
            self.Thumbnail:str = (YT_extract.get("thumbnail"))
            self.Rating:float = (round(YT_extract.get("average_rating"),2))
            self.Views:int = (YT_extract.get("view_count"))
            self.Likes:int = (YT_extract.get("like_count"))
            self.UploadDate:str = (datetime.strptime(YT_extract.get('upload_date'), '%Y%m%d').strftime('%d-%m-%Y'))
            self.Duration:int = (YT_extract.get("duration"))
            self.FDuration:str = (time.strftime('%M:%S', time.gmtime(YT_extract.get("duration"))))
            self.SongIn:int = (YT_extract.get("duration"))
            self.Author:str = author

class InputType(Enum):
    Search = 0
    URL = 1
    Playlist = 2

class Music(commands.Cog):
    def __init__(self, client: Client):
        self.client = client
        self.looper: bool = False
        self.dict_obj: dict = {}

    def YTDl(self, url: str, inputtype: InputType ):
        with YDL(ydl_opts) as ydl:
            match inputtype:
                case InputType.Search:
                    song_info = ydl.extract_info(f'ytsearch:{url}', download=False)['entries']
                case _:
                    song_info = []
                    song_info.append(ydl.extract_info(url, download=False))
        return song_info

    def FindInputType(query:str):
        if re.match(playlist_url_regex, query) is not None:
            return InputType.Playlist
        elif re.match(vid_url_regex, query) is not None:
            return InputType.URL
        else: return InputType.Search

    def Playlist_urls(playlist:str):
        playlist_id = playlist.replace('https://www.youtube.com/playlist?list=','')
        playlistResponse = api.get_playlist_items(playlist_id=playlist_id, count=None)
        playlist_URLS = []
        for i in range(0, len(playlistResponse.items)):
            playlist_URLS.append(f'https://www.youtube.com/watch?v={playlistResponse.items[i].contentDetails.videoId}')
        return playlist_URLS

    async def AddtoQueue(self, ctx: commands.Context, playlist:list):
        loop = asyncio.get_event_loop()
        for i in range(0, len(playlist)):
            song_info = await loop.run_in_executor(None, Music.YTDl, self, playlist[i], InputType.Playlist)
            self.dict_obj[ctx.guild.id].append(video_info(song_info[0], ctx.message.author.display_name))

    #Play
    @commands.command(pass_context=True, aliases=['p'])
    async def play(self, ctx: commands.Context, *, query:str=None):

        # create Dictionary
        if not self.dict_obj:
            for guild in self.client.guilds:
                self.dict_obj[guild.id] = []

        # If player is_paused resume...
        if query is None:
            if self.dict_obj[ctx.guild.id] !=[] and ctx.voice_client.is_paused() is True:
                return await Music.pause(self, ctx)
            else: return await ctx.send('Queue is Empty.', delete_after = 60)

        async with ctx.typing():
            inputType = Music.FindInputType(query)
            loop = asyncio.get_event_loop()
            match inputType:
                case InputType.Playlist:
                    playlist = Music.Playlist_urls(query)
                    song_info = await loop.run_in_executor(None, Music.YTDl, self, playlist[0], inputType)
                    playlist.pop(0)
                    self.dict_obj[ctx.guild.id].append(video_info(song_info[0], ctx.message.author.display_name))
                    asyncio.create_task(Music.AddtoQueue(self, ctx, playlist))
                case _:
                    song_info = await loop.run_in_executor(None, Music.YTDl, self, query, inputType)
                    self.dict_obj[ctx.guild.id].append(video_info(song_info[0], ctx.message.author.display_name))
        
        if inputType == InputType.Playlist: await ctx.send(f"Adding Playlist to Queue...")
        else: await ctx.send(f'Adding `{self.dict_obj[ctx.guild.id][len(self.dict_obj[ctx.guild.id])-1].Title}` to Queue.')

        # Join VC
        voice = get(self.client.voice_clients, guild=ctx.guild)
        if voice and voice.is_connected():
            pass
        elif voice==None:
            voiceChannel = ctx.message.author.voice.channel
            voice = await voiceChannel.connect()
        if self.dict_obj[ctx.guild.id][0] and ctx.voice_client.is_paused() is False and ctx.voice_client.is_playing() is False:
            await Music.player(self, ctx)
            

    #Queue
    class QueuePages(View):
        def __init__(self, obj):
            super().__init__()
            self.page_no = 1
            self.obj = obj

        def page_index(obj, pgno):
            first = (pgno*4)-3
            if (pgno*4)+1 <= len(obj): last = (pgno*4)+1
            else: last = len(obj)
            return [i for i in range(first, last)]

        def embed_gen(obj, page_no):
            embed=Embed(title="Now Playing", description = f"[{obj[0].Title}]({obj[0].pURL}) (Requested by {obj[0].Author})", colour=0xffa31a)
            if len(obj)>1:
                song_index = Music.QueuePages.page_index(obj, page_no)
                next_songs = "\u200b"
                max_page = math.ceil((len(obj)-1)/4)
                for i in song_index:
                    next_songs += f"{i}. [{obj[i].Title}]({obj[i].pURL}) (Requested by {obj[i].Author})\n"
                embed.add_field(name=f'Next Up ({page_no}/{max_page})', value=next_songs, inline=False)
            return embed

        @button(label='◀️', style=ButtonStyle.blurple)
        async def prev_page(self, button: Button, interaction: Interaction):
            if self.page_no > 1: self.page_no -= 1
            else: self.page_no = math.ceil((len(self.obj)-1)/4)
            await interaction.response.edit_message(embed=Music.QueuePages.embed_gen(self.obj, self.page_no), view=self)

        @button(label='▶️', style=ButtonStyle.blurple)
        async def next_page(self, button: Button, interaction: Interaction):
            if self.page_no < math.ceil((len(self.obj)-1)/4): self.page_no += 1
            else: self.page_no = 1
            await interaction.response.edit_message(embed=Music.QueuePages.embed_gen(self.obj, self.page_no), view=self)

    @commands.command(aliases=['q'])
    async def queue(self, ctx):
        await ctx.send(embed = Music.QueuePages.embed_gen(self.dict_obj[ctx.guild.id], 1), view=Music.QueuePages(self.dict_obj[ctx.guild.id]), delete_after=300)

    #Play from Queue
    async def player(self, ctx: commands.Context):
        voice = get(self.client.voice_clients, guild=ctx.guild)
        await Music.StatusUpdate(self, ctx)
        if len(self.dict_obj[ctx.guild.id]):
            embed=Embed(title="", color=0xff0000)
            embed.set_thumbnail(url=f'{self.dict_obj[ctx.guild.id][0].Thumbnail}')
            embed.set_author(name=f'Playing: {self.dict_obj[ctx.guild.id][0].Title}', url=self.dict_obj[ctx.guild.id][0].pURL, icon_url='')
            embed.add_field(name="Duration:", value=self.dict_obj[ctx.guild.id][0].FDuration, inline=True)
            embed.add_field(name="Requested by:", value=self.dict_obj[ctx.guild.id][0].Author, inline=True)
            embed.add_field(name="Song Rating:", value=f'{self.dict_obj[ctx.guild.id][0].Rating}/5', inline=True)
            await ctx.send(embed=embed, delete_after=self.dict_obj[ctx.guild.id][0].Duration)
            voice.play(FFmpegOpusAudio(self.dict_obj[ctx.guild.id][0].URL, bitrate=192, **FFMPEG_OPTIONS),
                       after=lambda e: print(f'Player error: {e}') if e else None)
            if self.dict_obj[ctx.guild.id][0]:
                while self.dict_obj[ctx.guild.id][0].SongIn>0:
                    await asyncio.sleep(1)
                    self.dict_obj[ctx.guild.id][0].SongIn-=1
            ctx.voice_client.stop()
            # song ends here
            if self.dict_obj[ctx.guild.id] and self.looper:
                self.dict_obj[ctx.guild.id].append(self.dict_obj[ctx.guild.id][0])
                self.dict_obj[ctx.guild.id].pop(0)
                # Temp Fix
                self.dict_obj[ctx.guild.id][0].SongIn = self.dict_obj[ctx.guild.id][0].Duration
            elif self.dict_obj[ctx.guild.id] and not self.looper:
                self.dict_obj[ctx.guild.id].pop(0)
            await Music.player(self, ctx)

    # Update client's status
    #Cuz why not ?
    async def StatusUpdate(self, ctx: commands.Context):
        if ctx.voice_client is not None and len(self.dict_obj[ctx.guild.id]):
            await self.client.change_presence(activity=Activity(type=ActivityType.listening, name=self.dict_obj[ctx.guild.id][0].Title))
        else: await self.client.change_presence(status=Status.online, activity=Activity(type=ActivityType.watching, name="yall Homies."))

    #Skip
    @commands.command()
    async def skip(self, ctx: commands.Context, arg=0):
        if ctx.voice_client is not None and ctx.voice_client.is_playing() is True or ctx.voice_client.is_paused() is True:
            embed=Embed(title='Removed',colour=0xff7f50)
            embed.add_field(name=f'{self.dict_obj[ctx.guild.id][arg].Title} from Queue.',value=f'by {ctx.message.author.display_name}')
            if arg>0 and arg<len(self.dict_obj[ctx.guild.id]):
                await ctx.send(embed=embed, delete_after=60)
                self.dict_obj[ctx.guild.id].pop(arg)
            elif arg==0:
                ctx.voice_client.stop()
                self.dict_obj[ctx.guild.id][0].SongIn = 0
                await asyncio.sleep(1)
                await ctx.send(embed=embed, delete_after=60)
            else:
                embed.add_field(name='Nothing',value=':p')
                await ctx.send(embed=embed, delete_after=30)

    #Stop
    @commands.command(aliases=['dc', 'kelambu'])
    async def stop(self, ctx: commands.Context):
        if ctx.voice_client is not None:
            if ctx.voice_client.is_playing() is True or ctx.voice_client.is_paused() is True:
                ctx.voice_client.stop()
                # clean list
                self.dict_obj[ctx.guild.id][0].SongIn = 0
                await asyncio.sleep(2)
                self.dict_obj[ctx.guild.id].clear()
            await ctx.message.add_reaction('👋'), await ctx.voice_client.disconnect()
            self.looper=False

    #Pause
    @commands.command()
    async def pause(self, ctx: commands.Context):
        if ctx.voice_client is not None and ctx.voice_client.is_paused() is False:
            ctx.voice_client.pause()
            embed=Embed(title='Paused:',colour=0x4169e1)
            embed.add_field(name=self.dict_obj[ctx.guild.id][0].Title,value='\u200b')
            await ctx.send(embed=embed, delete_after=180)
            # we addin 1 every second to wait :p
            while ctx.voice_client.is_paused():
                self.dict_obj[ctx.guild.id][0].SongIn+=1
                await asyncio.sleep(1)
        else:
            ctx.voice_client.resume()
            embed=Embed(title='Resumed:',colour=0x4169e1)
            embed.add_field(name=self.dict_obj[ctx.guild.id][0].Title,value='\u200b')
            return await ctx.send(embed=embed, delete_after=self.dict_obj[ctx.guild.id][0].SongIn)

    #Loop
    @commands.command(aliases=['repeat'])
    async def loop(self, ctx: commands.Context):
        if self.looper:
            self.looper=False
            embed=Embed(title='Loop Disabled.',colour=0x1abc9c)
        else:
            self.looper=True
            embed=Embed(title='Loop Enabled.',colour=0x800080)
        await ctx.send(embed=embed, delete_after=300)

    #Now Playing
    @commands.command(aliases=['nowplaying'])
    async def np(self, ctx: commands.Context):
        if self.dict_obj[ctx.guild.id]:
            percentile=20-round((self.dict_obj[ctx.guild.id][0].SongIn/self.dict_obj[ctx.guild.id][0].Duration)*20)
            bar='────────────────────'
            progbar=bar[:percentile]+'⚪'+bar[percentile+1:]
            song_on = time.strftime('%M:%S', time.gmtime(self.dict_obj[ctx.guild.id][0].Duration-self.dict_obj[ctx.guild.id][0].SongIn))
            embed=Embed(color=0xeb459e)
            embed.set_thumbnail(url=f'{self.dict_obj[ctx.guild.id][0].Thumbnail}')
            embed.set_author(name=f'{self.dict_obj[ctx.guild.id][0].Title}', url=self.dict_obj[ctx.guild.id][0].pURL, icon_url='')
            embed.add_field(name=f'{song_on} {progbar} {self.dict_obj[ctx.guild.id][0].FDuration}',value='\u200b',inline=False)
            embed.add_field(name="Views:", value=f'{human_format(self.dict_obj[ctx.guild.id][0].Views)}', inline=True)
            embed.add_field(name="Likes:", value=f'{human_format(self.dict_obj[ctx.guild.id][0].Likes)}', inline=True)
            embed.add_field(name="Uploaded on:", value=f'{self.dict_obj[ctx.guild.id][0].UploadDate}', inline=True)
            await ctx.send(embed=embed, delete_after=self.dict_obj[ctx.guild.id][0].SongIn)
        else:
            await ctx.reply('Queue is Empty', delete_after=30)
            await ctx.message.delete()

    #Jump
    @commands.command(aliases=['skipto'])
    async def jump(self, ctx: commands.Context, song_index: int=1):
        if ctx.voice_client is not None and ctx.voice_client.is_playing() is True or ctx.voice_client.is_paused() is True and song_index >1:
            if song_index >=2: del self.dict_obj[ctx.guild.id][1:song_index]
            self.dict_obj[ctx.guild.id][0].SongIn = 1
            await asyncio.sleep(2)
            await ctx.send("Skipped", delete_after=6)

    # Check Bot in VC
    @queue.before_invoke
    @skip.before_invoke
    @stop.before_invoke
    @pause.before_invoke
    @loop.before_invoke
    @np.before_invoke
    @jump.before_invoke
    async def check_voice(self, ctx: commands.Context):
        if ctx.voice_client is None or not ctx.voice_client.is_connected():
            raise commands.CommandError('Bot is not connect to VC.')
        if ctx.author.voice is None:
            raise commands.CommandError('You are not connected to a voice channel.')
        if ctx.voice_client is not None and ctx.author.voice is not None:
            if ctx.voice_client.channel.id != ctx.author.voice.channel.id:
                raise commands.CommandError('You must be in same VC as Bot.') 

    # Play Checks
    @play.before_invoke
    async def check_play(self, ctx: commands.Context):
        if ctx.author.voice is None:
            raise commands.CommandError('You are not connected to a voice channel.')
        if ctx.voice_client is not None and ctx.author.voice is not None:
            if ctx.voice_client.channel.id != ctx.author.voice.channel.id:
                raise commands.CommandError('You must be in same VC as Bot.') 

def setup(client):
	client.add_cog(Music(client))