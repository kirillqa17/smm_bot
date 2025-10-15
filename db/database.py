"""Database manager"""
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import json
from typing import Optional, Dict, List
from contextlib import contextmanager
from core.config import DATABASE_URL, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME


class Database:
    """Database connection manager"""

    @staticmethod
    @contextmanager
    def get_connection():
        """Get database connection with context manager"""
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            dbname=DB_NAME
        )
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def add_user(user_id: int, username: str = None, first_name: str = None, language: str = 'en'):
        """Add or update user"""
        with Database.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (id, username, first_name, language, last_active)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE
                    SET username = EXCLUDED.username,
                        first_name = EXCLUDED.first_name,
                        last_active = CURRENT_TIMESTAMP
                    """,
                    (user_id, username, first_name, language)
                )

    @staticmethod
    def set_user_language(user_id: int, language: str):
        """Set user language"""
        with Database.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE users SET language = %s WHERE id = %s
                    """,
                    (language, user_id)
                )

    @staticmethod
    def get_user_language(user_id: int) -> str:
        """Get user language"""
        with Database.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT language FROM users WHERE id = %s
                    """,
                    (user_id,)
                )
                result = cur.fetchone()
                return result[0] if result else 'en'

    @staticmethod
    def save_channel_style(user_id: int, channel_url: str, style_summary: Dict) -> int:
        """Save channel style analysis"""
        with Database.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO channels (user_id, channel_url, style_summary, analyzed_at)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id, channel_url) DO UPDATE
                    SET style_summary = EXCLUDED.style_summary,
                        analyzed_at = CURRENT_TIMESTAMP
                    RETURNING id
                    """,
                    (user_id, channel_url, Json(style_summary))
                )
                return cur.fetchone()[0]

    @staticmethod
    def get_channel_style(user_id: int) -> Optional[Dict]:
        """Get latest channel style for user"""
        with Database.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT style_summary
                    FROM channels
                    WHERE user_id = %s
                    ORDER BY analyzed_at DESC
                    LIMIT 1
                    """,
                    (user_id,)
                )
                result = cur.fetchone()
                return dict(result['style_summary']) if result else None

    @staticmethod
    def save_post(user_id: int, content: str, channel_id: int = None) -> int:
        """Save generated post"""
        with Database.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO posts (user_id, channel_id, content)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (user_id, channel_id, content)
                )
                return cur.fetchone()[0]

    @staticmethod
    def save_image(user_id: int, file_id: str, prompt: str = None, provider: str = None) -> int:
        """Save image metadata"""
        with Database.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO images (user_id, file_id, prompt, provider)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (user_id, file_id, prompt, provider)
                )
                return cur.fetchone()[0]

    @staticmethod
    def get_user_stats(user_id: int) -> Dict:
        """Get user statistics"""
        with Database.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                        (SELECT COUNT(*) FROM channels WHERE user_id = %s) as channels_analyzed,
                        (SELECT COUNT(*) FROM posts WHERE user_id = %s) as posts_generated,
                        (SELECT COUNT(*) FROM images WHERE user_id = %s) as images_created
                    """,
                    (user_id, user_id, user_id)
                )
                return dict(cur.fetchone())


db = Database()
