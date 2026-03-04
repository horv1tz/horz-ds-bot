import json
from typing import Any

from database import get_conn


DEFAULT_SETTINGS = {
    'guild_id': '',
    'applications_submit_channel_id': '',
    'applications_review_channel_id': '',
    'applications_recruiter_role_id': '',
    'applications_newbie_role_id': '',
    'applications_cooldown_hours': '24',
    'applications_call_voice_channel_ids': '[]',
    'reports_submit_channel_id': '',
    'reports_review_channel_id': '',
    'reports_reviewer_role_id': '',
    'logs_channel_id': '',
    'log_level': 'all',
}


def seed_defaults() -> None:
    with get_conn() as conn:
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                'INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)',
                (key, value),
            )


def get_setting(key: str, default: Any = None) -> str:
    with get_conn() as conn:
        row = conn.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
    if not row:
        return default
    return row['value']


def set_setting(key: str, value: Any) -> None:
    with get_conn() as conn:
        conn.execute(
            'INSERT INTO settings(key, value) VALUES(?, ?) '
            'ON CONFLICT(key) DO UPDATE SET value = excluded.value',
            (key, str(value)),
        )


def get_json_setting(key: str, default: Any):
    raw = get_setting(key, None)
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def set_json_setting(key: str, value: Any) -> None:
    set_setting(key, json.dumps(value, ensure_ascii=False))
