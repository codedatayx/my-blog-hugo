import sqlite3
import gzip
import json
from datetime import datetime
from config import DB_PATH


class SQLiteMemory:
    def __init__(self):
        self.db_path = DB_PATH
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                session_id TEXT PRIMARY KEY,
                first_seen TEXT,
                last_seen TEXT,
                interests TEXT DEFAULT '',
                topics_discussed TEXT DEFAULT '',
                message_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS conversation_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                date TEXT,
                summary TEXT,
                key_topics TEXT DEFAULT '',
                compressed_data BLOB,
                turn_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS knowledge_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact TEXT,
                source_session TEXT,
                created_at TEXT
            );
        """)
        conn.commit()
        conn.close()

    def _conn(self):
        return sqlite3.connect(self.db_path)

    # ---- User Profile ----
    def save_profile(self, session_id: str, interests: str = "", topics: str = ""):
        conn = self._conn()
        now = datetime.now().isoformat()
        conn.execute("""
            INSERT INTO user_profiles (session_id, first_seen, last_seen, interests, topics_discussed, message_count)
            VALUES (?, ?, ?, ?, ?, 1)
            ON CONFLICT(session_id) DO UPDATE SET
                last_seen = ?,
                interests = CASE WHEN ? != '' THEN ? ELSE interests END,
                topics_discussed = CASE WHEN ? != '' THEN ? ELSE topics_discussed END,
                message_count = message_count + 1
        """, (session_id, now, now, interests, topics, now, interests, interests, topics, topics))
        conn.commit()
        conn.close()

    def get_profile(self, session_id: str) -> dict:
        conn = self._conn()
        row = conn.execute(
            "SELECT interests, topics_discussed, message_count FROM user_profiles WHERE session_id = ?",
            (session_id,)
        ).fetchone()
        conn.close()
        if row:
            return {"interests": row[0], "topics": row[1], "message_count": row[2]}
        return {}

    # ---- Conversation Summaries ----
    def save_summary(self, session_id: str, summary: str, topics: str, compressed_data: bytes, turn_count: int):
        conn = self._conn()
        conn.execute("""
            INSERT INTO conversation_summaries (session_id, date, summary, key_topics, compressed_data, turn_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session_id, datetime.now().isoformat(), summary, topics, compressed_data, turn_count))
        conn.commit()
        conn.close()

    def get_recent_summaries(self, session_id: str, limit: int = 5) -> list:
        conn = self._conn()
        rows = conn.execute("""
            SELECT summary, key_topics, date FROM conversation_summaries
            WHERE session_id = ?
            ORDER BY id DESC LIMIT ?
        """, (session_id, limit)).fetchall()
        conn.close()
        return [{"summary": r[0], "topics": r[1], "date": r[2]} for r in rows]

    def decompress_conversation(self, compressed_data: bytes) -> list:
        try:
            return json.loads(gzip.decompress(compressed_data))
        except Exception:
            return []

    # ---- Knowledge Facts ----
    def save_fact(self, fact: str, source_session: str):
        conn = self._conn()
        conn.execute(
            "INSERT INTO knowledge_facts (fact, source_session, created_at) VALUES (?, ?, ?)",
            (fact, source_session, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

    def get_facts(self, session_id: str, limit: int = 20) -> list:
        conn = self._conn()
        rows = conn.execute("""
            SELECT fact FROM knowledge_facts
            WHERE source_session = ?
            ORDER BY id DESC LIMIT ?
        """, (session_id, limit)).fetchall()
        conn.close()
        return [r[0] for r in rows]

    def get_all_facts(self, limit: int = 50) -> list:
        conn = self._conn()
        rows = conn.execute(
            "SELECT fact FROM knowledge_facts ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]
