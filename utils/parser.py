from telethon.sync import TelegramClient
from telethon.errors import ChannelInvalidError, ChannelPrivateError
from utils.config import API_ID, API_HASH, SESSION_NAME
import asyncio

async def parse_channel(channel_url, post_limit=100):
    """
    Парсит последние посты из публичного Telegram-канала.
    Возвращает строку с объединенным текстом постов.
    """
    # Создаем клиента внутри асинхронной функции
    # Имя сессии лучше делать уникальным для избежания конфликтов
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    
    try:
        await client.connect()
        # Проверяем, авторизован ли клиент
        if not await client.is_user_authorized():
             # В реальном приложении здесь нужна обработка входа (например, через код)
             # Для простоты предполагаем, что сессия уже авторизована
             return "Ошибка: Клиент Telethon не авторизован. Запустите скрипт в интерактивном режиме один раз."

        entity = await client.get_entity(channel_url)
        posts_text = []
        
        # Получаем сообщения
        messages = await client.get_messages(entity, limit=post_limit)
        for message in messages:
            if message.text:
                posts_text.append(message.text)
        
        return "\n\n---РАЗДЕЛИТЕЛЬ ПОСТОВ---\n\n".join(posts_text)

    except (ChannelInvalidError, ValueError):
        return "Ошибка: Неверная ссылка на канал. Убедитесь, что она имеет формат @channel_name."
    except ChannelPrivateError:
        return "Ошибка: Канал является приватным. Я могу анализировать только публичные каналы."
    except Exception as e:
        print(f"Неожиданная ошибка в парсере: {e}")
        return f"Произошла внутренняя ошибка при анализе канала: {e}"
    finally:
        if client.is_connected():
            await client.disconnect()

# Функция-обертка для запуска асинхронного кода из синхронного
def run_parser(channel_url):
    return asyncio.run(parse_channel(channel_url))