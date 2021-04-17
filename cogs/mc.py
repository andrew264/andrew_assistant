import discord.ext.commands as commands
from urllib.request import urlopen
from os import remove, system
from shutil import copyfile, rmtree

from oldefs import checkIfProcessRunning

class mc(commands.Cog):

	def __init__(self,client):
		self.client = client

	# IP
	@commands.command(pass_context=True)
	@commands.has_permissions(manage_messages=True)
	async def mcip(self, ctx):
		if checkIfProcessRunning():
			external_ip = urlopen('https://ident.me').read().decode('utf8')
			await ctx.send(f'{external_ip}:42069')
		else: return await ctx.send('Server isn\'t Running.')
	@commands.command(hidden=True)
	@mcip.error
	async def mcip_error(self, ctx, error):
		if isinstance(error, commands.MissingPermissions):
			await ctx.send('You have no Permission(s).')

	# check server is running
	@commands.command(pass_context=True)
	async def mcstatus(self,ctx):
		if checkIfProcessRunning():
			await ctx.send('Server is Running.')
		else:
			await ctx.send('Server isn\'t Running.')

	# startup server
	@commands.command(pass_context=True)
	@commands.has_permissions(manage_messages=True)
	async def mcstart(self,ctx):
		if checkIfProcessRunning():
			return await ctx.send('A Server is already running.')
		else:
			system("start cmd /K vikki.bat")
			return await ctx.send('Server will start in 20 secs...')

	# startup server
	@commands.command(pass_context=True)
	@commands.has_permissions(manage_messages=True)
	async def mcnew(self,ctx,arg):
		if checkIfProcessRunning():
			return await ctx.send('A Server is already running.')
		try: 
			rmtree('C:\\Users\\Andrew\\MCServer\\Speed\\world')
			remove('C:\\Users\\Andrew\\MCServer\\Speed\\server.properties')
		except OSError as error: 
			print('World folder doesn\'t exist.')
		copyfile('C:\\Users\\Andrew\\MCServer\\Speed\\server.properties.bak','C:\\Users\\Andrew\\MCServer\\Speed\\server.properties')
		props= open("C:\\Users\\Andrew\\MCServer\\Speed\\server.properties", "a")
		props.write(f'\nlevel-seed={arg}')
		props.close()
		system("start cmd /K newworld.bat")
		return await ctx.send(f'Creating new world with seed: `{arg}`')


def setup(client):
	client.add_cog(mc(client))