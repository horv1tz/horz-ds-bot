import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv('BOT_DB_PATH', 'family_bot.db')


def init_db(db_path: str = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        '''
    )

    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS form_fields (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            form_type TEXT NOT NULL,
            field_key TEXT NOT NULL,
            label TEXT NOT NULL,
            field_type TEXT NOT NULL DEFAULT 'text',
            required INTEGER NOT NULL DEFAULT 1,
            max_length INTEGER NOT NULL DEFAULT 100,
            sort_order INTEGER NOT NULL DEFAULT 0
        )
        '''
    )

    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            submitted_at INTEGER NOT NULL,
            reviewed_at INTEGER,
            reviewer_id INTEGER,
            reject_reason TEXT,
            data_json TEXT NOT NULL,
            message_id INTEGER,
            cooldown_until INTEGER
        )
        '''
    )

    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS promotion_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            submitted_at INTEGER NOT NULL,
            reviewed_at INTEGER,
            reviewer_id INTEGER,
            reject_reason TEXT,
            data_json TEXT NOT NULL,
            target_rank TEXT,
            message_id INTEGER
        )
        '''
    )

    conn.commit()
    conn.close()


@contextmanager
def get_conn(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.commit()
        conn.close()
