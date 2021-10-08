﻿# Imports
from disnake import Intents
from disnake.ext import commands

from EnvVariables import TOKEN, OWNERID

from os import listdir

# Client
intents = Intents.all()
client = commands.Bot(command_prefix = commands.when_mentioned_or('.'), intents = intents, help_command=None, case_insensitive=True, test_guilds=[821758346054467584])
client.description = "Andrew's Assistant"

# Load Extention
@client.command(hidden=True)
async def load(ctx: commands.Context, extention):
    if ctx.message.author.id != OWNERID: return await ctx.send('🚫 You can\'t do that.')
    try: client.load_extension(f'cogs.{extension}')
    except Exception as e:
        await ctx.message.add_reaction('☠️')
        await ctx.send(f'{type(e).__name__}: {e}')
    else: await ctx.message.add_reaction('✔️')

# Unload Extention
@client.command(hidden=True)
async def unload(ctx: commands.Context, extention):
    if ctx.message.author.id != OWNERID: return await ctx.send('🚫 You can\'t do that.')
    try: client.unload_extension(f'cogs.{extension}')
    except Exception as e:
        await ctx.message.add_reaction('☠️')
        await ctx.send(f'{type(e).__name__}: {e}')
    else: await ctx.message.add_reaction('✔️')

# Reload Extention
@client.command(hidden=True)
async def reload(ctx: commands.Context, extention):
    if ctx.message.author.id != OWNERID: return await ctx.send('🚫 You can\'t do that.')
    try:
        client.unload_extension(f'cogs.{extension}')
        client.load_extension(f'cogs.{extension}')
    except Exception as e:
        await ctx.message.add_reaction('☠️')
        await ctx.send(f'{type(e).__name__}: {e}')
    else: await ctx.message.add_reaction('✔️')

for filename in listdir('./cogs'):
    if filename.endswith('.py'):
        client.load_extension(f'cogs.{filename[:-3]}')

client.run(TOKEN)