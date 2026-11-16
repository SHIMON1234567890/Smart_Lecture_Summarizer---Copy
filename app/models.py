import sqlite3

DATABASE = "database.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # status: queued -> extracting -> transcribing -> summarizing -> done | failed
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lectures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            video_filename TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            transcript TEXT,
            summary TEXT,
            error TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    conn.commit()
    conn.close()


def update_lecture(lecture_id, **fields):
    if not fields:
        return
    columns = ", ".join(f"{name} = ?" for name in fields)
    conn = get_db()
    conn.execute(
        f"UPDATE lectures SET {columns} WHERE id = ?",
        (*fields.values(), lecture_id),
    )
    conn.commit()
    conn.close()
