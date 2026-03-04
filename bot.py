import os
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

from admin_panel import AdminPanelServer

# Load environment variables from .env file
load_dotenv()


@dataclass
class RuntimeState:
    bot_instance_name: str
    pid: int
    start_time: float
    connected: bool = False
    guild_count: int = 0
    commands_handled: int = 0
    last_ready_at: Optional[float] = None
    last_error: Optional[str] = None
    last_admin_action: Optional[str] = None

    def snapshot(self) -> Dict:
        return {
            'bot_instance_name': self.bot_instance_name,
            'pid': self.pid,
            'start_time': self.start_time,
            'connected': self.connected,
            'guild_count': self.guild_count,
            'commands_handled': self.commands_handled,
            'last_ready_at': self.last_ready_at,
            'last_error': self.last_error,
            'last_admin_action': self.last_admin_action,
        }

    def set_last_error(self, error_message: str) -> None:
        self.last_error = error_message

    def register_admin_action(self, action_name: str) -> None:
        self.last_admin_action = action_name


# Get the bot token from environment variables
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
BOT_INSTANCE_NAME = os.getenv('BOT_INSTANCE_NAME', 'default-instance')
LOCK_FILE_PATH = os.getenv('BOT_LOCK_FILE_PATH', '/tmp/discord_bot_single_instance.lock')
ENABLE_SINGLE_INSTANCE_LOCK = os.getenv('ENABLE_SINGLE_INSTANCE_LOCK', 'false').strip().lower() == 'true'
WEB_ADMIN_ENABLED = os.getenv('ENABLE_WEB_ADMIN_PANEL', 'true').strip().lower() == 'true'
WEB_ADMIN_HOST = os.getenv('WEB_ADMIN_HOST', '0.0.0.0')
WEB_ADMIN_PORT = int(os.getenv('WEB_ADMIN_PORT', '8080'))

runtime_state = RuntimeState(
    bot_instance_name=BOT_INSTANCE_NAME,
    pid=os.getpid(),
    start_time=time.time(),
)
admin_panel_server = None

lock_file_handle = None

if not TOKEN:
    print("Error: DISCORD_BOT_TOKEN not found in environment variables.")
    print("Please create a .env file with your bot token.")
    exit(1)

PROXY_ENV_PRIORITY = ('PROXY_URL', 'HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY')


def resolve_proxy_url_from_env() -> Tuple[Optional[str], Optional[str]]:
    """Return the first configured proxy env var and its value."""
    for env_var in PROXY_ENV_PRIORITY:
        value = os.getenv(env_var)
        if value:
            return env_var, value
    return None, None


def is_containerized_environment() -> bool:
    """Best-effort container detection for Docker/Kubernetes style environments."""
    if os.path.exists('/.dockerenv'):
        return True
    return os.getenv('KUBERNETES_SERVICE_HOST') is not None


def is_loopback_host(hostname: Optional[str]) -> bool:
    """Return True when hostname points to local loopback within this network namespace."""
    if not hostname:
        return False
    return hostname.lower() in {'127.0.0.1', 'localhost', '::1'}


# Get proxy settings from environment variables
PROXY_ENV_SOURCE, PROXY_URL = resolve_proxy_url_from_env()


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
        from aiohttp_socks import ProxyConnector

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
    print(f"Proxy source env var: {PROXY_ENV_SOURCE}")
    print(f"Using proxy: {proxy_options['proxy_display']}")

    parsed_proxy = urlsplit(PROXY_URL or '')
    if is_containerized_environment() and is_loopback_host(parsed_proxy.hostname):
        warning_message = (
            "\n"
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
            "WARNING: Proxy host is set to localhost/127.0.0.1 in a containerized environment.\n"
            "In Docker, loopback points to THIS container, not your host machine.\n"
            "Use a reachable host/IP (for example host.docker.internal on Docker Desktop)\n"
            "or run the proxy in the same container/network namespace.\n"
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        )
        print(warning_message)

        if os.getenv('STRICT_PROXY_CHECK', '').strip().lower() == 'true':
            raise RuntimeError(
                "STRICT_PROXY_CHECK=true and loopback proxy detected in container. "
                "Update PROXY_URL to a non-loopback host (e.g. host.docker.internal)."
            )
else:
    print("No proxy configured")

bot_options = {k: v for k, v in proxy_options.items() if k != 'proxy_display'}
bot = commands.Bot(command_prefix='/', intents=intents, **bot_options)


def acquire_single_instance_lock() -> None:
    """Acquire a non-blocking file lock to prevent duplicate bot instances."""
    global lock_file_handle

    if not ENABLE_SINGLE_INSTANCE_LOCK:
        return

    import fcntl

    lock_file_handle = open(LOCK_FILE_PATH, 'a+', encoding='utf-8')

    try:
        fcntl.flock(lock_file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(
            f"[{BOT_INSTANCE_NAME}] Another bot instance is already running for lock '{LOCK_FILE_PATH}'. "
            "Exiting to avoid duplicate replies."
        )
        exit(1)

    lock_file_handle.seek(0)
    lock_file_handle.truncate()
    lock_file_handle.write(f"pid={os.getpid()} instance={BOT_INSTANCE_NAME} started_at={int(time.time())}\n")
    lock_file_handle.flush()


async def start_web_admin() -> None:
    global admin_panel_server

    if not WEB_ADMIN_ENABLED or admin_panel_server is not None:
        return

    admin_panel_server = AdminPanelServer(
        bot=bot,
        runtime_state=runtime_state,
        username=os.getenv('ADMIN_USERNAME', 'admin'),
        password=os.getenv('ADMIN_PASSWORD', 'admin'),
        host=WEB_ADMIN_HOST,
        port=WEB_ADMIN_PORT,
    )
    await admin_panel_server.start()
    print(f"Web admin panel available on http://{WEB_ADMIN_HOST}:{WEB_ADMIN_PORT}")


acquire_single_instance_lock()
print(f"Starting bot instance '{BOT_INSTANCE_NAME}' with PID {os.getpid()}")


@bot.event
async def on_ready():
    """Event handler for when the bot connects to Discord"""
    ready_time = time.strftime('%Y-%m-%d %H:%M:%S %z')
    bot_user_id = bot.user.id if bot.user else 'unknown'

    runtime_state.connected = True
    await start_web_admin()
    runtime_state.guild_count = len(bot.guilds)
    runtime_state.last_ready_at = time.time()

    print(
        f"[{BOT_INSTANCE_NAME}] on_ready at {ready_time}: "
        f"pid={os.getpid()} bot_user_id={bot_user_id} guild_count={len(bot.guilds)}"
    )
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guild(s)')


@bot.event
async def on_command(ctx):
    runtime_state.commands_handled += 1


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
    runtime_state.set_last_error(str(error))
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Sorry, I didn't understand that command. Try `/hello` or `/ping`.")
    else:
        print(f"Error: {error}")
        await ctx.send("An error occurred. Please try again.")


if __name__ == "__main__":
    bot.run(TOKEN)
