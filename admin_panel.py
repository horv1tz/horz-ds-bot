import asyncio
import base64
from pathlib import Path
from typing import Any, Dict

import discord
from aiohttp import web


class AdminPanelServer:
    def __init__(self, bot, runtime_state, username: str, password: str, host: str, port: int):
        self.bot = bot
        self.runtime_state = runtime_state
        self.username = username
        self.password = password
        self.host = host
        self.port = port
        self.runner: web.AppRunner | None = None

    def _authorized(self, request: web.Request) -> bool:
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Basic '):
            return False

        try:
            raw = base64.b64decode(auth.split(' ', 1)[1]).decode('utf-8')
            username, password = raw.split(':', 1)
        except Exception:
            return False

        return username == self.username and password == self.password

    def _auth_required(self) -> web.Response:
        return web.Response(
            status=401,
            text='Authentication required',
            headers={'WWW-Authenticate': 'Basic realm="Web Admin"'},
        )

    async def _dashboard(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._auth_required()

        html = Path('templates/admin.html').read_text(encoding='utf-8')
        data = self.runtime_state.snapshot()
        for key, value in data.items():
            html = html.replace('{{ ' + key + ' }}', str(value if value is not None else '—'))
        return web.Response(text=html, content_type='text/html')

    async def _status(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._auth_required()
        return web.json_response(self.runtime_state.snapshot())

    async def _send_message(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._auth_required()

        payload: Dict[str, Any] = await request.json()
        channel_id = payload.get('channel_id')
        message = (payload.get('message') or '').strip()

        if not channel_id or not message:
            return web.json_response({'ok': False, 'error': 'channel_id and message are required'}, status=400)

        channel = self.bot.get_channel(int(channel_id)) or await self.bot.fetch_channel(int(channel_id))
        await channel.send(message)

        self.runtime_state.register_admin_action('send_message')
        return web.json_response({'ok': True})

    async def _presence(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._auth_required()

        payload: Dict[str, Any] = await request.json()
        status_text = (payload.get('status_text') or '').strip()
        if not status_text:
            return web.json_response({'ok': False, 'error': 'status_text is required'}, status=400)

        await self.bot.change_presence(activity=discord.Game(name=status_text))
        self.runtime_state.register_admin_action('change_presence')
        return web.json_response({'ok': True})

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get('/', self._dashboard)
        app.router.add_get('/api/status', self._status)
        app.router.add_post('/api/send-message', self._send_message)
        app.router.add_post('/api/presence', self._presence)

        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.host, self.port)
        await site.start()

    async def stop(self) -> None:
        if self.runner:
            await self.runner.cleanup()
