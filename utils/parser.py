from telethon.sync import TelegramClient
from telethon.errors import ChannelInvalidError, ChannelPrivateError
from utils.config import API_ID, API_HASH, SESSION_NAME
import asyncio
import re

# Простая регулярка для поиска большинства эмодзи
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F700-\U0001F77F"  # alchemical symbols
    "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
    "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
    "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
    "\U0001FA00-\U0001FA6F"  # Chess Symbols
    "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
    "\U00002702-\U000027B0"  # Dingbats
    "\U000024C2-\U0001F251" 
    "]+",
    flags=re.UNICODE,
)

async def parse_channel(channel_url, post_limit=50):
    """
    Парсит последние посты из публичного Telegram-канала.
    Возвращает список словарей, каждый из которых содержит текст поста и количество эмодзи.
    """
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
             return "Ошибка: Клиент Telethon не авторизован."

        entity = await client.get_entity(channel_url)
        
        # ИЗМЕНЕНИЕ: Будем собирать не просто текст, а структурированные данные
        parsed_posts = []
        
        messages = await client.get_messages(entity, limit=post_limit)
        for message in messages:
            if message.text:
                # Считаем эмодзи в тексте поста
                emoji_count = len(EMOJI_PATTERN.findall(message.text))
                
                # Сохраняем и текст, и количество эмодзи
                parsed_posts.append({
                    "text": message.text,
                    "emoji_count": emoji_count
                })
        
        # Возвращаем список словарей вместо одной строки
        if not parsed_posts:
            return "Ошибка: Не удалось найти текстовые посты в канале."
            
        return parsed_posts

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

def run_parser(channel_url):
    return asyncio.run(parse_channel(channel_url))
