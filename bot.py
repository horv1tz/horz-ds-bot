import os
from typing import Dict, Optional
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import aiohttp
import discord
from discord.ext import commands
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
PROXY_URL = (
    os.getenv('PROXY_URL')
    or os.getenv('HTTPS_PROXY')
    or os.getenv('HTTP_PROXY')
    or os.getenv('ALL_PROXY')
)


HTTP_PROXY_SCHEMES = {'http', 'https'}
SOCKS_PROXY_SCHEMES = {'socks4', 'socks5', 'socks5h'}


def build_proxy_url_with_optional_auth(proxy_url: str, username: Optional[str], password: Optional[str]) -> str:
    """Return a proxy URL with injected credentials when explicitly provided."""
    parsed_proxy = urlsplit(proxy_url)

    if not username or not password:
        return proxy_url

    hostname = parsed_proxy.hostname or ''
    netloc = f"{quote(username, safe='')}:{quote(password, safe='')}@{hostname}"
    if parsed_proxy.port is not None:
        netloc = f"{netloc}:{parsed_proxy.port}"

    return urlunsplit((parsed_proxy.scheme, netloc, parsed_proxy.path, parsed_proxy.query, parsed_proxy.fragment))


def strip_credentials_from_url(proxy_url: str) -> str:
    """Return URL without embedded credentials for safe logging/usage."""
    parsed_proxy = urlsplit(proxy_url)
    if not parsed_proxy.username and not parsed_proxy.password:
        return proxy_url

    hostname = parsed_proxy.hostname or ''
    netloc = hostname if parsed_proxy.port is None else f"{hostname}:{parsed_proxy.port}"
    return urlunsplit((parsed_proxy.scheme, netloc, parsed_proxy.path, parsed_proxy.query, parsed_proxy.fragment))


def get_proxy_options(proxy_url: Optional[str]) -> Dict:
    """Build discord.py proxy options from environment variables and URL."""
    if not proxy_url:
        return {}

    parsed_proxy = urlsplit(proxy_url)
    scheme = parsed_proxy.scheme.lower()

    if scheme not in HTTP_PROXY_SCHEMES and scheme not in SOCKS_PROXY_SCHEMES:
        raise ValueError(
            f"Unsupported proxy scheme '{parsed_proxy.scheme}'. "
            "Use http://, https://, socks4://, socks5:// or socks5h:// proxy URL."
        )

    env_username = os.getenv('PROXY_USERNAME')
    env_password = os.getenv('PROXY_PASSWORD')

    username = env_username
    password = env_password
    if parsed_proxy.username and username is None:
        username = unquote(parsed_proxy.username)
    if parsed_proxy.password and password is None:
        password = unquote(parsed_proxy.password)

    normalized_proxy_url = build_proxy_url_with_optional_auth(
        strip_credentials_from_url(proxy_url),
        username,
        password,
    )

    if scheme in SOCKS_PROXY_SCHEMES:
        try:
            from aiohttp_socks import ProxyConnector
        except ImportError as exc:
            raise RuntimeError(
                "SOCKS proxy configured but 'aiohttp-socks' is not installed. "
                "Install dependencies again with `pip install -r requirements.txt`."
            ) from exc

        return {
            'connector': ProxyConnector.from_url(normalized_proxy_url),
            'proxy_display': strip_credentials_from_url(normalized_proxy_url),
        }

    proxy_options = {
        'proxy': strip_credentials_from_url(normalized_proxy_url),
        'proxy_display': strip_credentials_from_url(normalized_proxy_url),
    }
    if username and password:
        proxy_options['proxy_auth'] = aiohttp.BasicAuth(login=username, password=password)

    return proxy_options


# Create a bot instance with command prefix and message content intent
intents = discord.Intents.default()
intents.message_content = True

proxy_options = get_proxy_options(PROXY_URL)
if proxy_options:
    print(f"Using proxy: {proxy_options['proxy_display']}")
else:
    print("No proxy configured")

bot_options = {k: v for k, v in proxy_options.items() if k != 'proxy_display'}
bot = commands.Bot(command_prefix='/', intents=intents, **bot_options)


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
