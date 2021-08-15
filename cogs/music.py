from discord.ext import commands, tasks
from discord.utils import get
from discord import FFmpegPCMAudio, PCMVolumeTransformer, Activity, ActivityType, Status, Embed
import time
from datetime import datetime
import asyncio
import youtube_dl.YoutubeDL as YDL
ydl_opts = {
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'format': 'bestaudio/best',
}
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

def human_format(num):
    num = float('{:.3g}'.format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return '{}{}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'K', 'M', 'B', 'T'][magnitude])

class music(commands.Cog):
    def __init__(self,client):
        self.client = client
        self.fvol=0.25
        self.looper=False
        self.song_webpage_urls = []
        self.song_titles=[]
        self.song_urls=[]
        self.song_thumbnails=[]
        self.song_ratings=[]
        self.song_views=[]
        self.song_likes=[]
        self.song_dates=[]
        self.song_insec=[]
        self.song_lengths=[]
        self.song_reqby=[]
        self.master_list=[self.song_webpage_urls,self.song_titles,self.song_urls,self.song_thumbnails,self.song_ratings,self.song_views,self.song_likes,self.song_dates,self.song_insec,self.song_lengths,self.song_reqby]


    #Play
    @commands.command(pass_context=True, aliases=['p','P'])
    async def play(self, ctx,*,url:str=''):

        # Check if author in VC
        if ctx.author.voice is None or ctx.author.voice.channel is None:
            return await ctx.send("You are not connected to a voice channel.")

        # If player is_paused resume...
        if url=='' and ctx.voice_client.is_paused() is True:
            embed=Embed(title='Resumed:',colour=0x4169e1)
            embed.add_field(name=self.song_titles[0],value='\u200b')
            await ctx.send(embed=embed, delete_after=30)
            await music.status_set(self, ctx)
            await ctx.message.delete()
            return ctx.voice_client.resume()

        async with ctx.typing():
            #find vid url and add to list
            with YDL(ydl_opts) as ydl:
                song_info = ydl.extract_info(f'ytsearch:{url}', download=False)['entries'][0]
                self.song_webpage_urls.append(song_info.get("webpage_url"))
                self.song_titles.append(song_info.get('title', None))
                self.song_urls.append(song_info["formats"][0]["url"])
                self.song_thumbnails.append(song_info.get("thumbnail"))
                self.song_ratings.append(round(song_info.get("average_rating"),2))
                self.song_views.append(song_info.get('view_count'))
                self.song_likes.append(song_info.get('like_count'))
                self.song_dates.append(datetime.strptime(song_info.get('upload_date'), '%Y%m%d').strftime('%d-%m-%Y'))
                self.song_insec.append(song_info.get("duration"))
                self.song_lengths.append(time.strftime('%M:%S', time.gmtime(song_info.get("duration"))))
                self.song_reqby.append(ctx.message.author.display_name)
            # Join VC
            voice = get(self.client.voice_clients, guild=ctx.guild)
            if voice and voice.is_connected():
                pass
            elif voice==None:
                voiceChannel = ctx.message.author.voice.channel
                voice = await voiceChannel.connect()
            # add to queue
            await ctx.send(f'Adding `{self.song_titles[len(self.song_titles)-1]}` to Queue.', delete_after=30)
        if music.play_from_queue.is_running() is False:
            music.play_from_queue.start(self, ctx)
        await asyncio.sleep(25)
        await ctx.message.delete()

    #Status Update
    async def status_set(self, ctx):
        if ctx.voice_client is not None and self.song_titles:
            await self.client.change_presence(activity=Activity(type=ActivityType.streaming, name=self.song_titles[0], details=self.song_lengths[0], platform='YouTube', url=self.song_webpage_urls[0]))
        else:
            await self.client.change_presence(status=Status.idle, activity=Activity(type=ActivityType.watching, name="my Homies."))

    #Queue
    @commands.command(aliases=['q'])
    async def queue(self, ctx):
        if len(self.song_titles)==0:
            await ctx.send('Queue is Empty.')
        else:
            embed=Embed(title="Songs in Queue",colour=0xffa31a)
            embed.add_field(name='Now Playing',value=f'{self.song_titles[0]} (Requested by {self.song_reqby[0]})', inline=False)
            if len(self.song_titles)>1:
                embed.add_field(name='Next in Queue',value=f'1. {self.song_titles[1]} (Requested by {self.song_reqby[1]})', inline=False)
                for i in range(2,len(self.song_titles)):
                    embed.add_field(name='\u200b',value=f'{i}. {self.song_titles[i]} (Requested by {self.song_reqby[i]})', inline=False)
            await ctx.message.delete()
            await ctx.send(embed=embed, delete_after=180)

    #Play from Queue
    @tasks.loop(seconds = 1)
    async def play_from_queue(self, ctx):
        # Embed
        if self.song_titles:
            embed=Embed(title="", color=0xff0000)
            embed.set_thumbnail(url=f'{self.song_thumbnails[0]}')
            embed.set_author(name=f'Playing: {self.song_titles[0]}', url=self.song_webpage_urls[0], icon_url='')
            embed.add_field(name="Duration:", value=self.song_lengths[0], inline=True)
            embed.add_field(name="Requested by:", value=self.song_reqby[0], inline=True)
            embed.add_field(name="Song Rating:", value=f'{self.song_ratings[0]}/5', inline=True)
            await ctx.send(embed=embed, delete_after=self.song_insec[0])
            await music.status_set(self, ctx)
            voice = get(self.client.voice_clients, guild=ctx.guild)
            voice.play(FFmpegPCMAudio(self.song_urls[0], **FFMPEG_OPTIONS))
            voice.source=PCMVolumeTransformer(voice.source)
            voice.source.volume = self.fvol
            self.duration = self.song_insec[0]
            while self.duration>0:
                await asyncio.sleep(1)
                self.duration=self.duration-1
            # list deletus
            if self.song_titles and self.looper:
                for i in self.master_list:
                    i.append(i[0])
                    i.pop(0)
            elif self.song_titles and not self.looper:
                for i in self.master_list:
                    i.pop(0)
        else: 
            self.fvol=0.25
            await music.status_set(self, ctx)
            await asyncio.sleep(9)
            await ctx.voice_client.disconnect()
            music.play_from_queue.cancel()

    #Skip
    @commands.command()
    async def skip(self, ctx, arg=0):
        if ctx.message.author.voice is None:
            return await ctx.send('You must be is same VC as the bot.')
        if ctx.voice_client is None:
            return await ctx.send('Bot is not connect to VC.')
        if ctx.message.author.voice is not None and ctx.voice_client is not None:
            if ctx.voice_client.is_playing() is True or ctx.voice_client.is_paused() is True or ctx.voice_client is not None:
                embed=Embed(title='Removed',colour=0xff7f50)
                await ctx.message.delete()
                if arg>0 and arg<len(self.song_titles):
                    embed.add_field(name=f'{self.song_titles[arg]} from Queue.',value=f'by {ctx.message.author.display_name}')
                    await ctx.send(embed=embed, delete_after=60)
                    for i in self.master_list:
                        i.pop(arg)
                elif arg==0:
                    if len(self.song_titles):
                        embed.add_field(name=f'{self.song_titles[arg]} from Queue.',value=f'by {ctx.message.author.display_name}')
                        ctx.voice_client.stop()
                        self.duration = 0
                        await ctx.send(embed=embed, delete_after=60)
                        await music.status_set(self, ctx)
                    else:
                        embed.add_field(name='Nothing',value=':p')
                        await ctx.send(embed=embed, delete_after=30)
        else: await ctx.send('Queue is Empty')

    #Stop
    @commands.command(aliases=['dc', 'kelambu'])
    async def stop(self, ctx):
        if ctx.message.author.voice is None:
            return await ctx.send('You must be is same VC as the bot.')
        if ctx.voice_client is None:
            return await ctx.send('Bot is not connect to VC.')
        if ctx.message.author.voice is not None and ctx.voice_client is not None:
            if ctx.voice_client.is_playing() is True or ctx.voice_client.is_paused() is True or ctx.voice_client is not None:
                ctx.voice_client.stop()
                # clean all lists
                for i in self.master_list:
                    i.clear()
                if music.play_from_queue.is_running() is True:
                    music.play_from_queue.cancel()
                await ctx.message.add_reaction('👋') ,await ctx.voice_client.disconnect()
                await music.status_set(self, ctx)
                self.looper=False
                self.fvol=0.25
            return await ctx.send('Thanks for Listening btw.')

    #Pause
    @commands.command()
    async def pause(self, ctx):
        if ctx.message.author.voice is None:
            return await ctx.send('You must be is same VC as the bot.')
        if ctx.voice_client is None:
            return await ctx.send('Bot is not connect to VC.')
        if ctx.message.author.voice is not None and ctx.voice_client is not None:
            if ctx.voice_client.is_paused() is False:
                ctx.voice_client.pause()
                embed=Embed(title='Paused:',colour=0x4169e1)
                embed.add_field(name=self.song_titles[0],value='\u200b')
                await ctx.send(embed=embed, delete_after=60)
                await ctx.message.delete()
                # we addin 1 every second to wait :p
                while ctx.voice_client.is_paused():
                    self.duration=self.duration+1
                    await asyncio.sleep(1)

    #Loop
    @commands.command()
    async def loop(self, ctx):
        if ctx.message.author.voice is None:
            return await ctx.send('You must be is same VC as the bot.')
        if ctx.voice_client is None:
            return await ctx.send('Bot is not connect to VC.')
        if ctx.message.author.voice is not None and ctx.voice_client is not None:
            global looper
            if self.looper:
                self.looper=False
                embed=Embed(title='Loop Disabled.',colour=0x1abc9c)
            else:
                self.looper=True
                embed=Embed(title='Loop Enabled.',colour=0x800080)
            await ctx.send(embed=embed, delete_after=60)
            await asyncio.sleep(30)
            await ctx.message.delete()

    #Now PLaying
    @commands.command()
    async def np(self, ctx):
        if self.song_titles:
            percentile=30-round((self.duration/self.song_insec[0])*30)
            bar='──────────────────────────────'
            progbar=bar[:percentile]+'⚪'+bar[percentile+1:]
            song_on = time.strftime('%M:%S', time.gmtime(self.song_insec[0]-self.duration))
            await ctx.message.delete()
            embed=Embed(color=0xeb459e)
            embed.set_thumbnail(url=f'{self.song_thumbnails[0]}')
            embed.set_author(name=f'{self.song_titles[0]}', url=self.song_webpage_urls[0], icon_url='')
            embed.add_field(name=f'{song_on} {progbar} {self.song_lengths[0]}',value='\u200b',inline=False)
            embed.add_field(name="Views:", value=f'{human_format(self.song_views[0])}', inline=True)
            embed.add_field(name="Likes:", value=f'{human_format(self.song_likes[0])}', inline=True)
            embed.add_field(name="Uploaded on:", value=f'{self.song_dates[0]}', inline=True)
            await ctx.send(embed=embed, delete_after=self.duration)
            await ctx.message.delete()
        else:
            await ctx.reply('Queue is Empty', delete_after=30)
            await ctx.message.delete()

    #Volume
    @commands.command(aliases=['vol','v'])
    async def volume(self, ctx, volu:int=None):
        if ctx.voice_client is None or ctx.message.author.voice is None:
            return await ctx.send('BRUH no.')
        if volu is None:
            await ctx.send(f'Volume: {round(self.fvol*100)}%', delete_after=30)
            await asyncio.sleep(5)
            return await ctx.message.delete()
        elif volu>0 and volu<=100:
            self.fvol=round(volu)/100
            ctx.voice_client.source.volume=self.fvol
            await ctx.send(f'Volume is set to {round(self.fvol*100)}%', delete_after=30)
            await asyncio.sleep(5)
            return await ctx.message.delete()
        else: await ctx.send("Set Volume between 1 and 100.", delete_after=30)

def setup(client):
	client.add_cog(music(client))
