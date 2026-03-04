import base64
import os
from typing import Dict, Tuple

from aiohttp import web

from config import get_setting, set_setting, seed_defaults
from database import get_conn, init_db


def _get_web_panel_credentials() -> Tuple[str, str]:
    username = os.getenv('ADMIN_PANEL_USER') or os.getenv('ADMIN_USERNAME') or 'admin'
    password = os.getenv('ADMIN_PANEL_PASS') or os.getenv('ADMIN_PASSWORD') or 'admin'
    return username, password


def get_web_panel_bind() -> Tuple[str, int]:
    host = os.getenv('ADMIN_PANEL_HOST') or os.getenv('WEB_ADMIN_HOST') or '0.0.0.0'
    port = int(os.getenv('ADMIN_PANEL_PORT') or os.getenv('WEB_ADMIN_PORT') or '5000')
    return host, port


def is_web_panel_enabled() -> bool:
    raw = (os.getenv('ENABLE_WEB_ADMIN_PANEL') or 'true').strip().lower()
    return raw in {'1', 'true', 'yes', 'on'}


class SettingsPanel:
    def __init__(self):
        self.username, self.password = _get_web_panel_credentials()

    def _authorized(self, request: web.Request) -> bool:
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Basic '):
            return False
        try:
            token = auth_header.split(' ', 1)[1]
            decoded = base64.b64decode(token).decode('utf-8')
            username, password = decoded.split(':', 1)
            return username == self.username and password == self.password
        except Exception:
            return False

    def _auth_required(self) -> web.Response:
        return web.Response(status=401, headers={'WWW-Authenticate': 'Basic realm="Family Bot Admin"'})

    def _settings_html(self, settings: Dict[str, str]) -> str:
        def row(key: str, title: str) -> str:
            return f'<label>{title}<br><input name="{key}" value="{settings.get(key, "")}" style="width:100%"></label><br><br>'

        return f'''
<!doctype html><html><head><meta charset="utf-8"><title>Family Bot Admin</title></head>
<body style="font-family:sans-serif;max-width:900px;margin:20px auto">
<h1>Family Bot — Web UI</h1>
<form method="post" action="/save">
<h2>Основные</h2>
{row('guild_id', 'Guild ID')}
<h2>Заявки</h2>
{row('applications_submit_channel_id', 'Канал #подать-заявку')}
{row('applications_review_channel_id', 'Канал #рассмотрение-заявок')}
{row('applications_recruiter_role_id', 'Роль рекрутёра')}
{row('applications_newbie_role_id', 'Роль новобранца')}
{row('applications_cooldown_hours', 'Кулдаун (часы)')}
{row('applications_call_voice_channel_ids', 'Голосовые каналы обзвона JSON')} 
<h2>Отчёты</h2>
{row('reports_submit_channel_id', 'Канал подачи отчётов')}
{row('reports_review_channel_id', 'Канал рассмотрения отчётов')}
{row('reports_reviewer_role_id', 'Роль для рассмотрения')}
<h2>Логирование</h2>
{row('logs_channel_id', 'Канал логов')}
{row('log_level', 'Уровень логов (all/errors)')}
<button type="submit">Сохранить</button>
</form></body></html>
'''

    async def index(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._auth_required()
        settings = {
            k: get_setting(k, '')
            for k in [
                'guild_id',
                'applications_submit_channel_id',
                'applications_review_channel_id',
                'applications_recruiter_role_id',
                'applications_newbie_role_id',
                'applications_cooldown_hours',
                'applications_call_voice_channel_ids',
                'reports_submit_channel_id',
                'reports_review_channel_id',
                'reports_reviewer_role_id',
                'logs_channel_id',
                'log_level',
            ]
        }
        return web.Response(text=self._settings_html(settings), content_type='text/html')

    async def save(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._auth_required()
        data = await request.post()
        for key, value in data.items():
            set_setting(key, value)
        raise web.HTTPFound('/')


def create_app() -> web.Application:
    app = web.Application()
    panel = SettingsPanel()
    app.router.add_get('/', panel.index)
    app.router.add_post('/save', panel.save)
    return app


async def start_background_web_panel() -> web.AppRunner:
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    host, port = get_web_panel_bind()
    site = web.TCPSite(runner, host=host, port=port)
    await site.start()
    return runner


def main():
    init_db()
    seed_defaults()
    app = create_app()
    host, port = get_web_panel_bind()
    web.run_app(app, host=host, port=port)


if __name__ == '__main__':
    main()
