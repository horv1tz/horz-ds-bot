import base64
import os
from typing import Dict

from aiohttp import web

from config import get_setting, set_setting, seed_defaults
from database import get_conn, init_db


class SettingsPanel:
    def __init__(self):
        self.username = os.getenv('ADMIN_PANEL_USER', 'admin')
        self.password = os.getenv('ADMIN_PANEL_PASS', 'admin')

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


def main():
    init_db()
    seed_defaults()
    app = web.Application()
    panel = SettingsPanel()
    app.router.add_get('/', panel.index)
    app.router.add_post('/save', panel.save)
    web.run_app(
        app,
        host=os.getenv('ADMIN_PANEL_HOST', '0.0.0.0'),
        port=int(os.getenv('ADMIN_PANEL_PORT', '5000')),
    )


if __name__ == '__main__':
    main()
