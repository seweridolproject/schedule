import sqlite3

DB_PATH = "bot.db"

DEFAULT_GROUP_NAME = "06-25.РИУПО.ОФ.9"
DEFAULT_GROUP_URL = "https://site.mstimetables.ru/01a00f53d32773b5b396bf3eb6f57ce2/groups/309"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # строки доступны по имени столбца
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS groups (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                url  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                group_id    INTEGER REFERENCES groups(id)
            );
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO groups (name, url) VALUES (?, ?)",
            (DEFAULT_GROUP_NAME, DEFAULT_GROUP_URL),
        )


def get_groups():
    with get_conn() as conn:
        return conn.execute("SELECT id, name FROM groups ORDER BY name").fetchall()


def set_user_group(telegram_id, group_id):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (telegram_id, group_id) VALUES (?, ?) "
            "ON CONFLICT(telegram_id) DO UPDATE SET group_id = excluded.group_id",
            (telegram_id, group_id),
        )


def get_user_group(telegram_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT group_id FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return row["group_id"] if row else None


def get_group_name(group_id):
    with get_conn() as conn:
        row = conn.execute("SELECT name FROM groups WHERE id = ?", (group_id,)).fetchone()
        return row["name"] if row else "?"


def get_group_url(group_id):
    with get_conn() as conn:
        row = conn.execute("SELECT url FROM groups WHERE id = ?", (group_id,)).fetchone()
        return row["url"] if row else None
