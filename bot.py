import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the bot token from environment variables
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

if not TOKEN:
    print("Error: DISCORD_BOT_TOKEN not found in environment variables.")
    print("Please create a .env file with your bot token.")
    exit(1)

# Get proxy settings from environment variables
PROXY_URL = os.getenv('PROXY_URL')

# Create a bot instance with command prefix and message content intent
intents = discord.Intents.default()
intents.message_content = True

# Configure bot with proxy if provided
if PROXY_URL:
    print(f"Using proxy: {PROXY_URL}")
    bot = commands.Bot(command_prefix='/', intents=intents, proxy=PROXY_URL)
else:
    print("No proxy configured")
    bot = commands.Bot(command_prefix='/', intents=intents)

@bot.event
async def on_ready():
    """Event handler for when the bot connects to Discord"""
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guild(s)')

@bot.command(name='hello')
async def hello_command(ctx):
    """
    Responds with "Hello World" when the /hello command is used.
    
    Usage: /hello
    """
    await ctx.send('Hello World!')

@bot.command(name='ping')
async def ping_command(ctx):
    """
    Simple ping command to test bot responsiveness.
    
    Usage: /ping
    """
    await ctx.send('Pong! The bot is working correctly.')

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors gracefully"""
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Sorry, I didn't understand that command. Try `/hello` or `/ping`.")
    else:
        print(f"Error: {error}")
        await ctx.send("An error occurred. Please try again.")

if __name__ == "__main__":
    bot.run(TOKEN)