import psycopg2
import json
from utils.config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

def get_db_connection():
    """Устанавливает соединение с базой данных."""
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname=DB_NAME
    )
    return conn

def add_user_if_not_exists(user_id, username):
    """Добавляет нового пользователя, если его еще нет в базе."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO users (id, username) VALUES (%s, %s)",
            (user_id, username)
        )
        conn.commit()
    cur.close()
    conn.close()

def save_channel_style(user_id, channel_url, style_summary):
    """Сохраняет или обновляет анализ стиля канала."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Проверяем, есть ли уже такой канал
    cur.execute("SELECT id FROM channels WHERE channel_url = %s", (channel_url,))
    channel_row = cur.fetchone()
    
    style_summary_json = json.dumps(style_summary, ensure_ascii=False)

    if channel_row:
        # Обновляем существующий
        channel_id = channel_row[0]
        cur.execute(
            "UPDATE channels SET style_summary = %s, user_id = %s WHERE id = %s",
            (style_summary_json, user_id, channel_id)
        )
    else:
        # Создаем новый
        cur.execute(
            "INSERT INTO channels (user_id, channel_url, style_summary) VALUES (%s, %s, %s) RETURNING id",
            (user_id, channel_url, style_summary_json)
        )
        channel_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()
    return channel_id

def get_channel_style_by_user(user_id):
    """Получает последний проанализированный стиль для пользователя."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT style_summary FROM channels 
        WHERE user_id = %s 
        ORDER BY created_at DESC 
        LIMIT 1
        """,
        (user_id,)
    )
    result = cur.fetchone()
    cur.close()
    conn.close()
    
    if result and result[0]:
        return result[0]
    return None

# Другие функции для подписок и контент-плана будут добавлены по мере необходимости