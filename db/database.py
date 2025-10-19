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
    def add_user(user_id: int, username: str = None, first_name: str = None):
        """Add or update user"""
        with Database.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (id, username, first_name, last_active)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE
                    SET username = EXCLUDED.username,
                        first_name = EXCLUDED.first_name,
                        last_active = CURRENT_TIMESTAMP
                    """,
                    (user_id, username, first_name)
                )

    @staticmethod
    def save_channel_style(user_id: int, channel_url: str, channel_title: str, style_summary: Dict) -> int:
        """Save channel style analysis"""
        with Database.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO channels (user_id, channel_url, channel_title, style_summary, analyzed_at)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id, channel_url) DO UPDATE
                    SET channel_title = EXCLUDED.channel_title,
                        style_summary = EXCLUDED.style_summary,
                        analyzed_at = CURRENT_TIMESTAMP
                    RETURNING id
                    """,
                    (user_id, channel_url, channel_title, Json(style_summary))
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
    def get_user_channels(user_id: int) -> List[Dict]:
        """Get all channels analyzed by user"""
        with Database.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, channel_url, channel_title, analyzed_at
                    FROM channels
                    WHERE user_id = %s
                    ORDER BY analyzed_at DESC
                    """,
                    (user_id,)
                )
                return [dict(row) for row in cur.fetchall()]

    @staticmethod
    def get_channel_by_id(channel_id: int) -> Optional[Dict]:
        """Get channel by ID"""
        with Database.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, user_id, channel_url, channel_title, style_summary, analyzed_at
                    FROM channels
                    WHERE id = %s
                    """,
                    (channel_id,)
                )
                result = cur.fetchone()
                if result:
                    result_dict = dict(result)
                    result_dict['style_summary'] = dict(result_dict['style_summary'])
                    return result_dict
                return None

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
