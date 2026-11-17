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

    conn.execute("""
        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)

    # status: queued -> extracting -> transcribing -> summarizing -> translating -> done | failed
    conn.execute("""
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            folder_id INTEGER,
            title TEXT NOT NULL,
            source_type TEXT NOT NULL DEFAULT 'video',
            source_url TEXT,
            summary_type TEXT NOT NULL DEFAULT 'bullet_points',
            transcript TEXT NOT NULL,
            summary TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'done',
            error TEXT,
            target_lang TEXT NOT NULL DEFAULT 'en',
            media_filename TEXT,
            subject TEXT,
            subject_confidence REAL,
            subject_reasons TEXT,
            transcript_original TEXT,
            language TEXT NOT NULL DEFAULT 'en',
            language_name TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (folder_id) REFERENCES folders (id) ON DELETE SET NULL
        )
    """)

    # Databases created before background processing lack these columns.
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(summaries)")}
    for column, ddl in (
        ("status", "TEXT NOT NULL DEFAULT 'done'"),
        ("error", "TEXT"),
        ("target_lang", "TEXT NOT NULL DEFAULT 'en'"),
        ("media_filename", "TEXT"),
        ("subject", "TEXT"),
        ("subject_confidence", "REAL"),
        ("subject_reasons", "TEXT"),
        ("transcript_original", "TEXT"),
        ("language", "TEXT NOT NULL DEFAULT 'en'"),
        ("language_name", "TEXT"),
    ):
        if column not in existing:
            conn.execute(f"ALTER TABLE summaries ADD COLUMN {column} {ddl}")

    # Jobs run in a thread of this process, so any job still "in progress" at
    # startup was cut off when the server last stopped.
    conn.execute("""
        UPDATE summaries
        SET status = 'failed',
            error = 'Processing stopped because the server was restarted. Delete this and add the lecture again.'
        WHERE status NOT IN ('done', 'failed')
    """)

    conn.commit()
    conn.close()


def update_summary(summary_id, **fields):
    if not fields:
        return
    columns = ", ".join(f"{name} = ?" for name in fields)
    conn = get_db()
    conn.execute(
        f"UPDATE summaries SET {columns} WHERE id = ?",
        (*fields.values(), summary_id),
    )
    conn.commit()
    conn.close()
