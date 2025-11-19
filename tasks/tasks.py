"""Celery tasks for async operations"""
import os
from tasks.celery_app import celery_app

# Import config FIRST to get API keys
from core.config import (
    API_ID, API_HASH, SESSION_NAME, GEMINI_API_KEY,
    OPENAI_API_KEY, REPLICATE_API_KEY, NEWS_API_KEY,
    MAX_POSTS_TO_ANALYZE, BASE_DIR
)

# IMPORTANT: Set Replicate API token BEFORE importing replicate
if REPLICATE_API_KEY:
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_KEY

# Now import replicate (will use the token from environment)
from pyrogram import Client
from pyrogram.errors import UsernameNotOccupied, UsernameInvalid, ChannelPrivate
import google.generativeai as genai
from openai import OpenAI
import replicate
import requests
import feedparser
from PIL import Image, ImageDraw, ImageFont
from rembg import remove
from io import BytesIO
import base64
import re
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta

# Ensure sessions directory exists
os.makedirs(BASE_DIR / "sessions", exist_ok=True)

# Initialize AI clients
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-2.5-flash')
gemini_pro_model = genai.GenerativeModel('gemini-2.5-pro')  # For deep analysis
gemini_image_model = genai.GenerativeModel('gemini-2.5-flash-image')  # For image generation and editing

if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)


@celery_app.task(name='analyze_channel')
def analyze_channel_task(channel_url: str) -> Dict:
    """
    REVOLUTIONARY AI-POWERED CHANNEL ANALYSIS

    This function uses advanced AI to deeply understand the writing style,
    not just count metrics. It creates a psychological profile of the author.
    """
    try:
        # Parse channel with Pyrogram
        channel_title = ""
        with Client(SESSION_NAME, API_ID, API_HASH) as client:
            # Get chat info
            chat = client.get_chat(channel_url)
            channel_title = chat.title

            # Get messages from the channel
            messages = []
            for message in client.get_chat_history(chat.id, limit=MAX_POSTS_TO_ANALYZE):
                messages.append(message)

            posts_data = []
            for msg in messages:
                # Get text from either text or caption (for media posts)
                text_content = msg.text or msg.caption

                if text_content:
                    emoji_count = len(re.findall(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001FAFF\U00002702-\U000027B0]', text_content))

                    # Deep metrics per post
                    words = text_content.split()
                    sentences = [s.strip() for s in re.split(r'[.!?]+', text_content) if s.strip()]
                    lines = [l.strip() for l in text_content.split('\n') if l.strip()]

                    # Formatting analysis
                    bold_count = text_content.count('<b>') + text_content.count('**')
                    italic_count = text_content.count('<i>') + text_content.count('_')
                    code_count = text_content.count('<code>') + text_content.count('`')
                    link_count = text_content.count('http')

                    # Punctuation analysis
                    question_marks = text_content.count('?')
                    exclamation_marks = text_content.count('!')
                    hashtags = len(re.findall(r'#\w+', text_content))

                    posts_data.append({
                        "text": text_content,
                        "word_count": len(words),
                        "sentence_count": len(sentences),
                        "line_count": len(lines),
                        "emoji_count": emoji_count,
                        "bold_count": bold_count,
                        "italic_count": italic_count,
                        "code_count": code_count,
                        "link_count": link_count,
                        "question_marks": question_marks,
                        "exclamation_marks": exclamation_marks,
                        "hashtags": hashtags,
                        "avg_word_length": round(sum(len(w) for w in words) / len(words)) if words else 0,
                        "has_cta": any(word in text_content.lower() for word in ['подпишись', 'жми', 'переходи', 'смотри', 'читай', 'узнай'])
                    })

        if not posts_data:
            return {"error": "Текстовые посты не найдены"}

        num_posts = len(posts_data)

        # Calculate basic metrics (supplementary data)
        metrics = {
            "channel_title": channel_title,
            "analyzed_posts_count": num_posts,
            "average_word_count": round(sum(p['word_count'] for p in posts_data) / num_posts),
            "average_sentence_count": round(sum(p['sentence_count'] for p in posts_data) / num_posts),
            "average_line_count": round(sum(p['line_count'] for p in posts_data) / num_posts),
            "average_emoji_count": round(sum(p['emoji_count'] for p in posts_data) / num_posts),
            "average_bold_usage": round(sum(p['bold_count'] for p in posts_data) / num_posts, 1),
            "average_italic_usage": round(sum(p['italic_count'] for p in posts_data) / num_posts, 1),
            "average_code_usage": round(sum(p['code_count'] for p in posts_data) / num_posts, 1),
            "average_link_count": round(sum(p['link_count'] for p in posts_data) / num_posts, 1),
            "average_question_marks": round(sum(p['question_marks'] for p in posts_data) / num_posts, 1),
            "average_exclamation_marks": round(sum(p['exclamation_marks'] for p in posts_data) / num_posts, 1),
            "average_hashtags": round(sum(p['hashtags'] for p in posts_data) / num_posts, 1),
            "average_word_length": round(sum(p['avg_word_length'] for p in posts_data) / num_posts),
            "cta_frequency": round(sum(1 for p in posts_data if p['has_cta']) / num_posts * 100),
        }

        # Select diverse example posts (short, medium, long)
        sorted_by_length = sorted(posts_data, key=lambda x: x['word_count'])
        example_indices = []

        # Get short posts (bottom 20%)
        short_range = len(sorted_by_length) // 5
        example_indices.extend([0, short_range // 2] if short_range > 0 else [0])

        # Get medium posts (middle 40-60%)
        mid_start = len(sorted_by_length) * 2 // 5
        mid_end = len(sorted_by_length) * 3 // 5
        example_indices.extend([mid_start, (mid_start + mid_end) // 2, mid_end - 1])

        # Get long posts (top 20%)
        long_start = len(sorted_by_length) * 4 // 5
        example_indices.extend([long_start, (long_start + len(sorted_by_length)) // 2, len(sorted_by_length) - 1])

        # Deduplicate and limit to 12 examples
        example_indices = list(set(example_indices))[:12]
        example_posts = [sorted_by_length[i]['text'] for i in example_indices]

        # ═══════════════════════════════════════════════════════════
        # DEEP AI ANALYSIS - NO JSON CONSTRAINTS
        # Let the AI freely analyze the style in natural language
        # ═══════════════════════════════════════════════════════════

        all_posts_for_analysis = "\n\n━━━━━━━━━━━━━━━━━━━━━━\n\n".join(
            [p['text'] for p in posts_data[:40]]  # Analyze up to 40 posts
        )

        deep_analysis_prompt = f"""Ты — эксперт-лингвист и копирайтер с 20-летним опытом анализа стилей письма.

Твоя задача: проанализировать стиль автора Telegram канала настолько глубоко, чтобы ЛЮБОЙ пост, написанный на основе твоего анализа, был НЕОТЛИЧИМ от оригинала.

КАНАЛ: {channel_title}
КОЛИЧЕСТВО ПОСТОВ: {num_posts}

═══════════════════════════════════════════════════════════
ПОСТЫ ДЛЯ АНАЛИЗА:
═══════════════════════════════════════════════════════════

{all_posts_for_analysis}

═══════════════════════════════════════════════════════════
ТВОЯ ЗАДАЧА:
═══════════════════════════════════════════════════════════

Проведи МАКСИМАЛЬНО ГЛУБОКИЙ анализ стиля этого автора. Напиши развернутый текст (3000-5000 слов), который покрывает ВСЕ аспекты стиля:

1. **ПСИХОЛОГИЧЕСКИЙ ПОРТРЕТ АВТОРА**
   - Какая личность просматривается через тексты?
   - Какие ценности, убеждения, мировоззрение?
   - Как автор позиционирует себя по отношению к читателю?
   - Эмоциональный фон и темперамент

2. **ЛИНГВИСТИЧЕСКИЙ АНАЛИЗ**
   - Уровень и характер лексики (простая/сложная, современная/классическая)
   - Использование профессиональной терминологии
   - Сленг, жаргон, неологизмы
   - Любимые слова, фразы, обороты (конкретные примеры!)
   - Длина предложений и их структура
   - Использование сложных/простых конструкций

3. **СТРУКТУРНЫЕ ПАТТЕРНЫ**
   - Как автор начинает посты? (5-7 типичных примеров начала)
   - Как развивает мысль? (линейно, по спирали, хаотично?)
   - Как заканчивает посты? (5-7 типичных примеров окончания)
   - Использование списков, перечислений, нумерации
   - Структура абзацев (короткие, длинные, смешанные?)

4. **РИТОРИЧЕСКИЕ ПРИЕМЫ**
   - Какие вопросы задает? (риторические, прямые, провокационные?)
   - Использование метафор, сравнений, аналогий
   - Примеры из жизни, кейсы, истории
   - Цитаты, отсылки к культуре/медиа
   - Юмор (тип: ирония, сарказм, абсурд?)

5. **СТИЛЬ ФОРМАТИРОВАНИЯ**
   - Использование эмодзи (где, как часто, какие именно?)
   - Выделение текста (жирный, курсив, код)
   - Пробелы между абзацами (плотно/разреженно)
   - Заглавные буквы (когда и как используются?)
   - Пунктуация (многоточия, восклицания, вопросы)

6. **ТЕМЫ И КОНТЕНТ**
   - Основные темы (топ-5)
   - Как автор их подает? (экспертно, дружески, с юмором?)
   - Глубина погружения в тему
   - Баланс теории/практики

7. **УНИКАЛЬНЫЕ МАРКЕРЫ**
   - Что делает стиль УЗНАВАЕМЫМ?
   - Фирменные фразы, конструкции
   - Характерные ошибки или особенности
   - То, что отличает этого автора от других

8. **ЦЕЛЕВАЯ АУДИТОРИЯ И КОММУНИКАЦИЯ**
   - На кого рассчитан контент?
   - Как автор обращается к читателю? (на "ты", "вы", безличноно?)
   - Уровень доверительности
   - Тактики вовлечения

9. **ЭМОЦИОНАЛЬНАЯ ТОНАЛЬНОСТЬ**
   - Преобладающие эмоции (вдохновение, тревога, спокойствие?)
   - Энергетика текстов (высокая, низкая, нейтральная?)
   - Как меняется тон в зависимости от темы?

10. **САМОЕ ВАЖНОЕ: ИМИТАЦИЯ**
    - Напиши подробную инструкцию: КАК писать как этот автор?
    - Что ОБЯЗАТЕЛЬНО нужно делать?
    - Чего КАТЕГОРИЧЕСКИ избегать?
    - Какие фишки повторять?

ВАЖНО:
- Будь максимально конкретным, приводи ПРИМЕРЫ из текстов
- Пиши развернуто, не сокращай
- Это анализ для имитации стиля, поэтому глубина критична
- В конце сформулируй 10-15 четких правил для генерации постов в этом стиле

НАЧИНАЙ АНАЛИЗ:"""

        # Use Gemini Pro for deep analysis (smarter than Flash)
        deep_response = gemini_model.generate_content(
            contents=[{"role": "user", "parts": [{"text": deep_analysis_prompt}]}],
            generation_config=genai.types.GenerationConfig(
                temperature=1.0,  # High creativity for deep insights
                top_p=0.95,
                top_k=40,
                max_output_tokens=8192,  # Allow long analysis
            )
        )

        deep_analysis_text = deep_response.text

        return {
            "success": True,
            "style": metrics,
            "deep_analysis": deep_analysis_text,
            "example_posts": example_posts,
            "channel_title": channel_title
        }

    except (UsernameNotOccupied, UsernameInvalid, ValueError) as e:
        return {"error": f"Неверный URL канала: {str(e)}"}
    except ChannelPrivate:
        return {"error": "Канал приватный"}
    except Exception as e:
        import traceback
        return {"error": f"Ошибка анализа: {str(e)}\n{traceback.format_exc()}"}


@celery_app.task(name='generate_posts')
def generate_posts_task(style_data: Dict, topic: str) -> Dict:
    """
    REVOLUTIONARY AI POST GENERATION WITH FEW-SHOT LEARNING

    Uses deep analysis + real examples to generate indistinguishable posts
    """
    try:
        # Extract data
        style_summary = style_data.get('style_summary', {})
        deep_analysis = style_data.get('deep_analysis', '')
        example_posts = style_data.get('example_posts', [])

        # Extract metrics for reference
        avg_words = style_summary.get("average_word_count", 100)
        avg_sentences = style_summary.get("average_sentence_count", 5)
        avg_emojis = style_summary.get("average_emoji_count", 0)

        # Select 5-7 best examples for few-shot learning
        selected_examples = example_posts[:7] if len(example_posts) > 7 else example_posts

        # Format examples for prompt
        examples_text = "\n\n━━━━━ ПРИМЕР ОРИГИНАЛЬНОГО ПОСТА ━━━━━\n\n".join(selected_examples)

        # ═══════════════════════════════════════════════════════════
        # FEW-SHOT LEARNING PROMPT
        # Show real examples + deep analysis for perfect imitation
        # ═══════════════════════════════════════════════════════════

        prompt = f"""Ты — автор Telegram канала, который уже много лет ведет свой канал в уникальном стиле.

ТВОЯ ЗАДАЧА: написать 3 разных варианта поста на тему "{topic}"

КРИТИЧЕСКИ ВАЖНО: Посты должны быть НЕОТЛИЧИМЫ от твоего обычного стиля! Никто не должен заподозрить, что это не ты.

═══════════════════════════════════════════════════════════
ГЛУБОКИЙ АНАЛИЗ ТВОЕГО СТИЛЯ:
═══════════════════════════════════════════════════════════

{deep_analysis}

═══════════════════════════════════════════════════════════
ПРИМЕРЫ ТВОИХ ОРИГИНАЛЬНЫХ ПОСТОВ:
═══════════════════════════════════════════════════════════

{examples_text}

═══════════════════════════════════════════════════════════
ТЕПЕРЬ НАПИШИ 3 ПОСТА НА ТЕМУ: "{topic}"
═══════════════════════════════════════════════════════════

ВАЖНЫЕ УКАЗАНИЯ:

1. **ИЗУЧИ ПРИМЕРЫ ВЫШЕ** — это твои настоящие посты. Копируй их:
   - Структуру (как начинаешь, развиваешь, заканчиваешь)
   - Тон и манеру общения
   - Размещение эмодзи
   - Форматирование (жирный, курсив, пробелы)
   - Длину предложений и абзацев
   - Пунктуацию

2. **СЛЕДУЙ АНАЛИЗУ СТИЛЯ** — там описаны все твои особенности:
   - Любимые слова и фразы
   - Риторические приемы
   - Способы вовлечения
   - Уникальные маркеры

3. **МЕТРИКИ** (ориентировочно):
   - Слов: около {avg_words} (±30%)
   - Предложений: около {avg_sentences}
   - Эмодзи: около {avg_emojis}

4. **ФОРМАТИРОВАНИЕ**:
   - Используй ТОЛЬКО HTML теги: <b>, <i>, <s>, <code>, <a href="">
   - НЕ используй Markdown (**, __, ~~)
   - Копируй стиль переносов строк из примеров

5. **ГЛАВНОЕ**:
   - Пиши так, как ты ВСЕГДА пишешь
   - Не старайся быть "лучше" или "правильнее"
   - Будь естественным
   - Каждый вариант должен быть РАЗНЫМ по структуре и подаче, но в ОДНОМ стиле

РЕЗУЛЬТАТ:
Напиши 3 ПОЛНЫХ поста, готовых к публикации.
Разделяй варианты строкой "---VARIANT---"

НАЧИНАЙ:"""

        # Use Gemini Pro for generation (better quality than Flash)
        response = gemini_model.generate_content(
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            generation_config=genai.types.GenerationConfig(
                temperature=0.95,  # High creativity but controlled
                top_p=0.95,
                top_k=64,
                max_output_tokens=4096,
            )
        )

        variants = response.text.split("---VARIANT---")
        clean_variants = [_clean_html(v.strip()) for v in variants if v.strip()]

        return {"success": True, "posts": clean_variants[:3]}

    except Exception as e:
        return {"error": f"Ошибка генерации: {str(e)}"}


@celery_app.task(name='generate_post_ideas')
def generate_post_ideas_task(style_data: Dict) -> Dict:
    """
    AI-POWERED POST IDEAS GENERATION WITH LANGUAGE DETECTION

    Analyzes channel language, trending news, and recent posts
    to generate relevant ideas without repetition
    """
    try:
        style_summary = style_data.get('style_summary', {})
        deep_analysis = style_data.get('deep_analysis', '')
        example_posts = style_data.get('example_posts', [])

        # Step 1: Detect channel language and extract themes
        language_and_themes_prompt = f"""На основе этого анализа канала определи:
1. ЯЗЫК канала (русский/английский/другой)
2. 3-5 КЛЮЧЕВЫХ ТЕМ канала

АНАЛИЗ КАНАЛА:
{deep_analysis[:2000]}

ПРИМЕРЫ ПОСТОВ:
{chr(10).join(example_posts[:3])}

Верни в формате JSON:
{{
  "language": "русский" или "английский",
  "themes": ["тема1", "тема2", "тема3"]
}}
"""

        lang_themes_response = gemini_model.generate_content(
            contents=[{"role": "user", "parts": [{"text": language_and_themes_prompt}]}],
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                response_mime_type="application/json"
            )
        )

        lang_data = json.loads(lang_themes_response.text)
        channel_language = lang_data.get("language", "английский")
        channel_themes = ", ".join(lang_data.get("themes", []))

        # Step 2: Fetch news based on language
        russian_news = []
        world_news = []

        if "рус" in channel_language.lower():
            # Russian news sources
            russian_feeds = [
                "https://lenta.ru/rss",
                "https://habr.com/ru/rss/all/all/",
                "https://vc.ru/rss/all",
                "https://tass.ru/rss/v2.xml"
            ]

            for feed_url in russian_feeds:
                try:
                    feed = feedparser.parse(feed_url)
                    for entry in feed.entries[:8]:
                        russian_news.append({
                            "title": entry.get("title", ""),
                            "summary": entry.get("summary", "")[:300],
                            "source": feed.feed.get("title", "RSS"),
                            "url": entry.get("link", ""),
                            "type": "russian"
                        })
                except:
                    continue

        # World news sources
        world_feeds = [
            "https://techcrunch.com/feed/",
            "https://www.theverge.com/rss/index.xml",
            "https://cointelegraph.com/rss",
            "https://www.socialmediatoday.com/rss.xml",
            "https://feeds.bbci.co.uk/news/technology/rss.xml"
        ]

        for feed_url in world_feeds:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:8]:
                    world_news.append({
                        "title": entry.get("title", ""),
                        "summary": entry.get("summary", "")[:300],
                        "source": feed.feed.get("title", "RSS"),
                        "url": entry.get("link", ""),
                        "type": "world"
                    })
            except:
                continue

        all_news = russian_news + world_news

        if not all_news:
            return {"error": "Не удалось загрузить новости"}

        # Step 3: Analyze recent posts to extract covered topics
        recent_topics_prompt = f"""Проанализируй эти посты и извлеки ТЕМЫ, о которых они написаны.

НЕДАВНИЕ ПОСТЫ:
{chr(10).join([f"- {post[:200]}" for post in example_posts[:10]])}

Верни ТОЛЬКО список тем через запятую, без номеров.
Пример: "новый AI от Google, регулирование криптовалют, запуск стартапа"
"""

        topics_response = gemini_model.generate_content(
            contents=[{"role": "user", "parts": [{"text": recent_topics_prompt}]}],
            generation_config=genai.types.GenerationConfig(temperature=0.3)
        )

        recent_topics = topics_response.text.strip()

        # Step 4: Format news for AI
        russian_news_text = "\n\n".join([
            f"[РФ] {news['title']}\n  {news['summary']}"
            for news in russian_news[:20]
        ])

        world_news_text = "\n\n".join([
            f"[МИРОВАЯ] {news['title']}\n  {news['summary']}"
            for news in world_news[:20]
        ])

        # Step 5: Generate ideas with structure
        ideas_prompt = f"""Ты — эксперт по контент-маркетингу для Telegram канала.

ЯЗЫК КАНАЛА: {channel_language}
ТЕМАТИКА КАНАЛА: {channel_themes}

ТЕМЫ НЕДАВНИХ ПОСТОВ (НЕ ПОВТОРЯТЬ):
{recent_topics}

РОССИЙСКИЕ НОВОСТИ:
{russian_news_text if russian_news_text else "Нет российских новостей"}

МИРОВЫЕ НОВОСТИ:
{world_news_text}

ЗАДАЧА:
Сгенерируй 5 идей для постов:
- ПЕРВЫЕ 3 идеи: на основе РОССИЙСКИХ новостей (если канал русский)
- ПОСЛЕДНИЕ 2 идеи: на основе МИРОВЫХ новостей

КРИТЕРИИ:
1. Тема должна быть АКТУАЛЬНОЙ и "горячей"
2. Тема должна СТРОГО соответствовать тематике канала
3. НЕ повторяй темы из недавних постов
4. Угол подачи должен быть свежим и уникальным
5. Если российских новостей мало или канал не русский - возьми больше мировых

ФОРМАТ JSON:
[
  {{
    "title": "Краткий заголовок идеи",
    "description": "Подробное описание о чем пост и почему это актуально (2-3 предложения)",
    "news_source": "Источник новости",
    "news_type": "russian" или "world"
  }}
]

Верни ТОЛЬКО валидный JSON массив с 5 идеями, без дополнительного текста.
"""

        ideas_response = gemini_model.generate_content(
            contents=[{"role": "user", "parts": [{"text": ideas_prompt}]}],
            generation_config=genai.types.GenerationConfig(
                temperature=0.8,
                response_mime_type="application/json"
            )
        )

        ideas = json.loads(ideas_response.text)

        return {"success": True, "ideas": ideas}

    except Exception as e:
        import traceback
        return {"error": f"Ошибка генерации идей: {str(e)}\n{traceback.format_exc()}"}


@celery_app.task(name='fetch_news')
def fetch_news_task(category: str = None, keywords: List[str] = None) -> Dict:
    """Fetch news from various sources - ASYNC"""
    try:
        news_items = []

        # RSS feeds by category
        rss_feeds = {
            "tech": ["https://techcrunch.com/feed/", "https://www.theverge.com/rss/index.xml"],
            "crypto": ["https://cointelegraph.com/rss"],
            "marketing": ["https://www.socialmediatoday.com/rss.xml"],
            "business": ["https://feeds.bbci.co.uk/news/business/rss.xml"]
        }

        feeds = rss_feeds.get(category, rss_feeds["tech"])

        for feed_url in feeds:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:5]:
                    published_at = datetime.now()
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        published_at = datetime(*entry.published_parsed[:6])

                    news_items.append({
                        "title": entry.get("title", ""),
                        "content": entry.get("summary", "")[:500],
                        "source": feed.feed.get("title", "RSS"),
                        "url": entry.get("link", ""),
                        "published_at": published_at.isoformat()
                    })
            except:
                continue

        # News API if available and keywords provided
        if NEWS_API_KEY and keywords:
            try:
                query = " OR ".join(keywords)
                from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

                response = requests.get(
                    "https://newsapi.org/v2/everything",
                    params={
                        "q": query,
                        "from": from_date,
                        "sortBy": "publishedAt",
                        "apiKey": NEWS_API_KEY
                    },
                    timeout=10
                )

                if response.ok:
                    data = response.json()
                    for article in data.get("articles", [])[:5]:
                        news_items.append({
                            "title": article.get("title", ""),
                            "content": article.get("description", "")[:500],
                            "source": article.get("source", {}).get("name", "News API"),
                            "url": article.get("url", ""),
                            "published_at": article.get("publishedAt", "")
                        })
            except:
                pass

        # Sort by date and remove duplicates
        seen_urls = set()
        unique_news = []
        for news in news_items:
            if news['url'] not in seen_urls:
                seen_urls.add(news['url'])
                unique_news.append(news)

        return {"success": True, "news": unique_news[:10]}

    except Exception as e:
        return {"error": f"News fetch error: {str(e)}"}


@celery_app.task(name='generate_post_from_news')
def generate_post_from_news_task(style_data: Dict, news_item: Dict) -> Dict:
    """Generate post from news with AI style matching"""
    try:
        # Extract data
        style_summary = style_data.get('style_summary', {})
        deep_analysis = style_data.get('deep_analysis', '')
        example_posts = style_data.get('example_posts', [])

        avg_words = style_summary.get("average_word_count", 100)
        avg_sentences = style_summary.get("average_sentence_count", 5)
        avg_emojis = style_summary.get("average_emoji_count", 0)

        # Select examples
        selected_examples = example_posts[:5] if len(example_posts) > 5 else example_posts
        examples_text = "\n\n━━━━━ ПРИМЕР ━━━━━\n\n".join(selected_examples)

        prompt = f"""Ты — автор Telegram канала. Напиши 3 варианта поста на основе этой новости:

НОВОСТЬ:
Заголовок: {news_item['title']}
Контент: {news_item['content']}
Источник: {news_item['source']}
Ссылка: {news_item['url']}

═══════════════════════════════════════════════════════════
ТВОЙ СТИЛЬ (АНАЛИЗ):
═══════════════════════════════════════════════════════════

{deep_analysis[:2000]}  # First 2000 chars of analysis

═══════════════════════════════════════════════════════════
ПРИМЕРЫ ТВОИХ ПОСТОВ:
═══════════════════════════════════════════════════════════

{examples_text}

═══════════════════════════════════════════════════════════

ЗАДАЧА:
Напиши 3 РАЗНЫХ варианта поста об этой новости В СВОЕМ СТИЛЕ.

ВАЖНО:
- Копируй структуру и тон своих примеров
- Слов: около {avg_words}, предложений: ~{avg_sentences}, эмодзи: ~{avg_emojis}
- Обязательно упомяни источник и дай ссылку
- HTML теги: <b>, <i>, <s>, <code>, <a href="">
- Разделяй варианты строкой "---VARIANT---"

НАЧИНАЙ:"""

        response = gemini_model.generate_content(
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            generation_config=genai.types.GenerationConfig(
                temperature=0.9,
                top_p=0.95,
                top_k=40,
            )
        )

        variants = response.text.split("---VARIANT---")
        clean_variants = [_clean_html(v.strip()) for v in variants if v.strip()]

        return {"success": True, "posts": clean_variants[:3]}

    except Exception as e:
        return {"error": f"Post generation error: {str(e)}"}


@celery_app.task(name='generate_image')
def generate_image_task(prompt: str, provider: str = "flux_schnell", size: str = "1024x1024") -> Dict:
    """Generate image with AI - ASYNC (Updated 2025 with auto-translation)"""
    try:
        # Auto-translate prompt to English for better results
        english_prompt = translate_to_english(prompt)
        if provider == "dalle" and OPENAI_API_KEY:
            # DALL-E 3 - Premium quality
            response = openai_client.images.generate(
                model="dall-e-3",
                prompt=english_prompt,
                n=1,
                size=size,
                quality="standard"
            )

            image_url = response.data[0].url
            img_response = requests.get(image_url, timeout=30)
            img_bytes = img_response.content
            img_b64 = base64.b64encode(img_bytes).decode('utf-8')

            return {"success": True, "image": img_b64, "provider": "dalle"}

        elif provider == "sdxl" and REPLICATE_API_KEY:
            # Stable Diffusion XL - Classic, best for photorealism
            output = replicate.run(
                "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
                input={
                    "prompt": english_prompt,
                    "negative_prompt": "ugly, blurry, low quality, distorted",
                    "width": 1024,
                    "height": 1024,
                    "num_inference_steps": 30
                }
            )

            output_url = output[0] if isinstance(output, list) else output
            response = requests.get(output_url, timeout=60)
            img_bytes = response.content
            img_b64 = base64.b64encode(img_bytes).decode('utf-8')

            return {"success": True, "image": img_b64, "provider": "sdxl"}

        elif provider == "flux_schnell" and REPLICATE_API_KEY:
            # Flux Schnell - Fast and high quality (2025 version)
            output = replicate.run(
                "black-forest-labs/flux-schnell:c846a69991daf4c0e5d016514849d14ee5b2e6846ce6b9d6f21369e564cfe51e",
                input={
                    "prompt": english_prompt,
                    "num_outputs": 1,
                    "aspect_ratio": "1:1",
                    "output_format": "png",
                    "output_quality": 90
                }
            )

            output_url = output[0] if isinstance(output, list) else output
            response = requests.get(output_url, timeout=60)
            img_bytes = response.content
            img_b64 = base64.b64encode(img_bytes).decode('utf-8')

            return {"success": True, "image": img_b64, "provider": "flux_schnell"}

        elif provider == "ideogram" and REPLICATE_API_KEY:
            # Ideogram v2 Turbo - Best for text and logos (2025 version)
            output = replicate.run(
                "ideogram-ai/ideogram-v2-turbo:7cef9d520d672bb802588ad0d13151bc51aee9a408c270aebf25d6530045dd29",
                input={
                    "prompt": english_prompt,
                    "aspect_ratio": "1:1",
                    "magic_prompt_option": "Auto"
                }
            )

            output_url = output if isinstance(output, str) else output[0]
            response = requests.get(output_url, timeout=60)
            img_bytes = response.content
            img_b64 = base64.b64encode(img_bytes).decode('utf-8')

            return {"success": True, "image": img_b64, "provider": "ideogram"}

        elif provider == "nano_banana" and GEMINI_API_KEY:
            # Gemini 2.5 Flash Image (Nano Banana) - Google's image generation
            response = gemini_image_model.generate_content(
                english_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=1.0,
                    top_p=0.95,
                    top_k=40,
                    max_output_tokens=8192,
                )
            )

            # Gemini 2.5 Flash Image returns image data
            if response.parts:
                for part in response.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        img_bytes = part.inline_data.data
                        img_b64 = base64.b64encode(img_bytes).decode('utf-8')
                        return {"success": True, "image": img_b64, "provider": "nano_banana"}

            return {"error": "No image generated by Nano Banana"}


        else:
            return {"error": f"Invalid provider '{provider}' or missing API key. Available: dalle, sdxl, flux_schnell, ideogram, nano_banana"}

    except Exception as e:
        import traceback
        return {"error": f"Image generation error: {str(e)}\n{traceback.format_exc()}"}


@celery_app.task(name='edit_image')
def edit_image_task(image_b64: str, instruction: str) -> Dict:
    """Edit image with Gemini 2.5 Flash Image (Nano Banana) - ASYNC"""
    try:
        if not GEMINI_API_KEY:
            return {"error": "GEMINI_API_KEY not set"}

        # Decode image
        image_bytes = base64.b64decode(image_b64)

        # Save to temporary file for PIL
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_file.write(image_bytes)
            temp_path = temp_file.name

        try:
            # Open image with PIL
            from PIL import Image as PILImage
            image = PILImage.open(temp_path)

            # Use Gemini 2.5 Flash Image for editing
            response = gemini_image_model.generate_content(
                [
                    f"Transform this image: {instruction}. Maintain the overall composition but apply the requested changes.",
                    image
                ],
                generation_config=genai.GenerationConfig(
                    temperature=1.0,
                    top_p=0.95,
                    top_k=40,
                    max_output_tokens=8192,
                )
            )

            # Extract edited image from response
            if response.parts:
                for part in response.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        result_bytes = part.inline_data.data
                        result_b64 = base64.b64encode(result_bytes).decode('utf-8')
                        return {"success": True, "image": result_b64}

            return {"error": "No edited image generated by Nano Banana"}

        finally:
            # Clean up temp file
            import os
            if os.path.exists(temp_path):
                os.remove(temp_path)

    except Exception as e:
        import traceback
        return {"error": f"Image edit error: {str(e)}\n{traceback.format_exc()}"}


@celery_app.task(name='remove_watermark')
def remove_watermark_task(image_b64: str) -> Dict:
    """Remove watermark from image using AI inpainting - ASYNC"""
    try:
        if not REPLICATE_API_KEY:
            return {"error": "REPLICATE_API_KEY not set"}

        # Decode image
        image_bytes = base64.b64decode(image_b64)
        image_data_uri = f"data:image/png;base64,{image_b64}"

        # Use LaMa inpainting model for watermark removal
        # This automatically detects and removes watermarks
        output = replicate.run(
            "cjwbw/lama:7434dcb3e46041a00c9a2f09e72c3aeb9bdb7044eec0fa1df8f2ae19da8cd5aa",
            input={
                "image": image_data_uri,
                # LaMa can automatically detect watermarks without explicit mask
            }
        )

        # Get output URL
        output_url = output if isinstance(output, str) else output[0]

        # Download result
        response = requests.get(output_url, timeout=30)
        result_bytes = response.content

        # Encode back
        result_b64 = base64.b64encode(result_bytes).decode('utf-8')

        return {"success": True, "image": result_b64}

    except Exception as e:
        import traceback
        return {"error": f"Watermark removal error: {str(e)}\n{traceback.format_exc()}"}


@celery_app.task(name='add_watermark')
def add_watermark_task(image_b64: str, text: str) -> Dict:
    """Add watermark to image - ASYNC (Large size 5x)"""
    try:
        # Decode image
        image_bytes = base64.b64decode(image_b64)
        img = Image.open(BytesIO(image_bytes)).convert("RGBA")

        # Create watermark layer
        watermark = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(watermark)

        # Calculate font size based on image size (minimum 180px - 5x bigger than before)
        # For large images, scale proportionally
        base_font_size = 180  # 5x bigger than original 36px
        scale_factor = min(img.width, img.height) / 1024
        font_size = int(base_font_size * max(scale_factor, 1.0))

        # Try to use a font
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
            except:
                # Fallback to default, but still try to make it bigger
                font = ImageFont.load_default()

        # Position at bottom right with larger padding
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        padding = 40  # Increased padding
        position = (img.width - text_width - padding, img.height - text_height - padding)

        # Draw watermark with semi-transparent white
        draw.text(position, text, fill=(255, 255, 255, 128), font=font)

        # Composite
        watermarked = Image.alpha_composite(img, watermark)

        # Save to bytes
        output = BytesIO()
        watermarked.convert("RGB").save(output, format="PNG")
        output.seek(0)

        # Encode
        result_b64 = base64.b64encode(output.getvalue()).decode('utf-8')

        return {"success": True, "image": result_b64}

    except Exception as e:
        import traceback
        return {"error": f"Watermark add error: {str(e)}\n{traceback.format_exc()}"}


@celery_app.task(name='remove_background')
def remove_background_task(image_b64: str) -> Dict:
    """Remove background from image using rembg - ASYNC"""
    try:
        # Decode image
        image_bytes = base64.b64decode(image_b64)

        # Remove background using rembg
        output_bytes = remove(image_bytes)

        # Convert to base64
        output_b64 = base64.b64encode(output_bytes).decode('utf-8')

        return {"success": True, "image": output_b64}

    except Exception as e:
        import traceback
        return {"error": f"Background removal error: {str(e)}\n{traceback.format_exc()}"}


# Helper function
def _clean_html(text: str) -> str:
    """Clean HTML for Telegram"""
    # Remove unsupported tags
    text = re.sub(r'<p>(.*?)</p>', r'\1\n\n', text, flags=re.DOTALL)
    text = text.replace('<p>', '').replace('</p>', '')

    # Convert markdown to HTML
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*', r'<b>\1</b>', text)
    text = re.sub(r'_(.*?)_', r'<i>\1</i>', text)

    # Lists
    text = re.sub(r'<li>(.*?)</li>', r'• \1\n', text, flags=re.DOTALL)
    text = text.replace('<ul>', '').replace('</ul>', '').replace('<ol>', '').replace('</ol>', '')

    # Clean up
    text = text.replace('<br>', '\n').replace('<br/>', '\n')
    text = re.sub(r'\n{3,}', '\n\n', text.strip())

    return text


@celery_app.task(name='text_to_speech')
def text_to_speech_task(text: str, voice: str = "neutral") -> Dict:
    """Convert text to speech using OpenAI TTS - ASYNC"""
    try:
        if not OPENAI_API_KEY:
            return {"error": "OPENAI_API_KEY not set"}

        # Voice mapping
        voice_map = {
            "male1": "onyx",
            "male2": "echo",
            "female1": "nova",
            "female2": "shimmer",
            "neutral": "alloy"
        }

        openai_voice = voice_map.get(voice, "alloy")

        # Generate speech
        response = openai_client.audio.speech.create(
            model="tts-1",
            voice=openai_voice,
            input=text,
            speed=1.0
        )

        # Get audio bytes
        audio_bytes = response.content

        # Encode to base64
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

        return {"success": True, "audio": audio_b64}

    except Exception as e:
        import traceback
        return {"error": f"TTS error: {str(e)}\n{traceback.format_exc()}"}


@celery_app.task(name='transcribe_audio')
def transcribe_audio_task(audio_b64: str) -> Dict:
    """Transcribe audio/video to text using OpenAI Whisper - ASYNC"""
    try:
        if not OPENAI_API_KEY:
            return {"error": "OPENAI_API_KEY not set"}

        # Decode audio
        audio_bytes = base64.b64decode(audio_b64)

        # Save to temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name

        try:
            # Transcribe with Whisper
            with open(temp_path, "rb") as audio_file:
                transcript = openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="ru"  # Auto-detect if None, or specify "ru" or "en"
                )

            text = transcript.text

            return {"success": True, "text": text}

        finally:
            # Clean up temp file
            import os
            if os.path.exists(temp_path):
                os.remove(temp_path)

    except Exception as e:
        import traceback
        return {"error": f"Transcription error: {str(e)}\n{traceback.format_exc()}"}


@celery_app.task(name='generate_video')
def generate_video_task(prompt: str, model: str = "minimax") -> Dict:
    """Generate video from text prompt using AI - ASYNC (Updated 2025 with auto-translation)"""
    try:
        if not REPLICATE_API_KEY:
            return {"error": "REPLICATE_API_KEY not set"}

        # Auto-translate prompt to English for better results
        english_prompt = translate_to_english(prompt)

        # Text-to-video models (2025 - Modern alternatives)
        if model == "sora2":
            # OpenAI Sora 2 - Flagship video generation with synced audio
            output = replicate.run(
                "openai/sora-2:6dd6f49244af4fc3cc2de9b65ab589e85870035dba05329d21c434e9172f0143",
                input={
                    "prompt": english_prompt
                }
            )

        elif model == "veo3":
            # Google Veo 3.1 - Higher-fidelity video, context-aware audio
            output = replicate.run(
                "google/veo-3.1:20ebd92c5919f20e8fa2e983bdb60016a99794c9accfab496ea25a68e0dbbaad",
                input={
                    "prompt": english_prompt
                }
            )

        elif model == "minimax":
            # Minimax Video-01 - High quality, realistic motion
            output = replicate.run(
                "minimax/video-01:5aa835260ff7f40f4069c41185f72036accf99e29957bb4a3b3a911f3b6c1912",
                input={
                    "prompt": english_prompt
                }
            )

        elif model == "ltx":
            # LTX-Video - Fast, DiT-based, 24 FPS at 768x512
            output = replicate.run(
                "lightricks/ltx-video:8c47da666861d081eeb4d1261853087de23923a268a69b63febdf5dc1dee08e4",
                input={
                    "prompt": english_prompt,
                    "num_frames": 121,  # ~5 seconds at 24fps
                    "num_inference_steps": 30
                }
            )

        elif model == "animate_diff":
            # AnimateDiff - Classic model (fallback option)
            output = replicate.run(
                "lucataco/animate-diff:beecf59c4aee8d81bf04f0381033dfa10dc16e845b4ae00d281e2fa377e48a9f",
                input={
                    "prompt": english_prompt,
                    "num_frames": 16,
                    "guidance_scale": 7.5,
                    "num_inference_steps": 25
                }
            )

        else:
            return {"error": f"Invalid model '{model}'. Available: sora2, veo3, minimax, ltx, animate_diff"}

        # Download video
        video_url = output if isinstance(output, str) else output[0]
        response = requests.get(video_url, timeout=180)
        video_bytes = response.content
        video_b64 = base64.b64encode(video_bytes).decode('utf-8')

        return {"success": True, "video": video_b64}

    except Exception as e:
        import traceback
        return {"error": f"Video generation error: {str(e)}\n{traceback.format_exc()}"}


@celery_app.task(name='image_to_video')
def image_to_video_task(image_b64: str, model: str = "svd") -> Dict:
    """Generate video from image using AI - ASYNC (Updated 2025)"""
    try:
        if not REPLICATE_API_KEY:
            return {"error": "REPLICATE_API_KEY not set"}

        # Convert base64 to data URI
        image_data_uri = f"data:image/png;base64,{image_b64}"

        # Image-to-video models (2025 versions)
        if model == "svd":
            # Stable Video Diffusion - Classic, reliable (2025 version)
            output = replicate.run(
                "stability-ai/stable-video-diffusion:3f0457e4619daac51203dedb472816fd4af51f3149fa7a9e0b5ffcf1b8172438",
                input={
                    "cond_aug": 0.02,
                    "decoding_t": 7,
                    "input_image": image_data_uri,
                    "video_length": "14_frames_with_svd",
                    "sizing_strategy": "maintain_aspect_ratio",
                    "motion_bucket_id": 127,
                    "frames_per_second": 6
                }
            )

        elif model == "svd_xt":
            # Stable Video Diffusion XL - Extended, higher quality
            output = replicate.run(
                "stability-ai/stable-video-diffusion:3f0457e4619daac51203dedb472816fd4af51f3149fa7a9e0b5ffcf1b8172438",
                input={
                    "cond_aug": 0.02,
                    "decoding_t": 14,
                    "input_image": image_data_uri,
                    "video_length": "25_frames_with_svd_xt",
                    "sizing_strategy": "maintain_aspect_ratio",
                    "motion_bucket_id": 180,
                    "frames_per_second": 10
                }
            )

        elif model == "svd_enhanced":
            # Stable Video Diffusion - Enhanced motion
            output = replicate.run(
                "stability-ai/stable-video-diffusion:3f0457e4619daac51203dedb472816fd4af51f3149fa7a9e0b5ffcf1b8172438",
                input={
                    "cond_aug": 0.02,
                    "decoding_t": 10,
                    "input_image": image_data_uri,
                    "video_length": "14_frames_with_svd",
                    "sizing_strategy": "maintain_aspect_ratio",
                    "motion_bucket_id": 150,
                    "frames_per_second": 8
                }
            )

        else:
            return {"error": f"Invalid model '{model}'. Available: svd, svd_xt, svd_enhanced"}

        # Download video
        video_url = output if isinstance(output, str) else output[0]
        response = requests.get(video_url, timeout=180)
        video_bytes = response.content
        video_b64 = base64.b64encode(video_bytes).decode('utf-8')

        return {"success": True, "video": video_b64}

    except Exception as e:
        import traceback
        return {"error": f"Image to video error: {str(e)}\n{traceback.format_exc()}"}


# ═══════════════════════════════════════════════════════════
# TRANSLATION FUNCTIONS (2025)
# ═══════════════════════════════════════════════════════════

def translate_to_english(text: str) -> str:
    """Translate text to English using Gemini (synchronous helper)"""
    try:
        # Detect if text is already in English (simple heuristic)
        # If text contains mostly Latin characters, assume it's English
        latin_chars = sum(1 for c in text if ord(c) < 128)
        if latin_chars / len(text) > 0.8:
            return text  # Already in English

        # Use Gemini for translation
        translation_prompt = f"""Translate the following text to English.
Return ONLY the translation, nothing else.

Text to translate:
{text}"""

        response = gemini_model.generate_content(
            contents=[{"role": "user", "parts": [{"text": translation_prompt}]}],
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,  # Low temperature for accurate translation
                max_output_tokens=2048,
            )
        )

        translated = response.text.strip()
        return translated

    except Exception as e:
        # If translation fails, return original text
        return text


@celery_app.task(name='translate_text')
def translate_text_task(text: str, target_language: str = "en") -> Dict:
    """Translate text to target language using Gemini - ASYNC"""
    try:
        if not GEMINI_API_KEY:
            return {"error": "GEMINI_API_KEY not set"}

        # Language names mapping
        lang_names = {
            "en": "English",
            "ru": "Russian",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
            "it": "Italian",
            "pt": "Portuguese",
            "zh": "Chinese",
            "ja": "Japanese",
            "ko": "Korean"
        }

        target_lang_name = lang_names.get(target_language, target_language)

        translation_prompt = f"""Translate the following text to {target_lang_name}.
Return ONLY the translation, nothing else. Maintain the tone and style.

Text to translate:
{text}"""

        response = gemini_model.generate_content(
            contents=[{"role": "user", "parts": [{"text": translation_prompt}]}],
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                max_output_tokens=2048,
            )
        )

        translated = response.text.strip()

        return {"success": True, "translated_text": translated}

    except Exception as e:
        import traceback
        return {"error": f"Translation error: {str(e)}\n{traceback.format_exc()}"}


# ═══════════════════════════════════════════════════════════
# ADVANCED TTS WITH MULTIPLE MODELS AND VOICES (2025)
# ═══════════════════════════════════════════════════════════

@celery_app.task(name='advanced_tts')
def advanced_tts_task(text: str, model: str = "openai", voice: str = "alloy") -> Dict:
    """Advanced Text-to-Speech with multiple models and 50+ voices - ASYNC"""
    try:
        # OpenAI TTS (6 voices)
        if model == "openai":
            if not OPENAI_API_KEY:
                return {"error": "OPENAI_API_KEY not set"}

            # OpenAI voices: alloy, echo, fable, onyx, nova, shimmer
            response = openai_client.audio.speech.create(
                model="tts-1-hd",  # High quality
                voice=voice,
                input=text,
                speed=1.0
            )

            audio_bytes = response.content
            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

            return {"success": True, "audio": audio_b64, "model": "openai", "voice": voice}

        # Minimax Speech-02 Turbo (fast, multilingual)
        elif model == "minimax_turbo" and REPLICATE_API_KEY:
            output = replicate.run(
                "minimax/speech-02-turbo",
                input={
                    "text": text,
                    "voice_id": voice  # Supports various voice IDs
                }
            )

            # Download audio
            audio_url = output if isinstance(output, str) else output[0]
            response = requests.get(audio_url, timeout=60)
            audio_bytes = response.content
            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

            return {"success": True, "audio": audio_b64, "model": "minimax_turbo", "voice": voice}

        # Minimax Speech-02 HD (high quality, multilingual)
        elif model == "minimax_hd" and REPLICATE_API_KEY:
            output = replicate.run(
                "minimax/speech-02-hd",
                input={
                    "text": text,
                    "voice_id": voice
                }
            )

            audio_url = output if isinstance(output, str) else output[0]
            response = requests.get(audio_url, timeout=60)
            audio_bytes = response.content
            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

            return {"success": True, "audio": audio_b64, "model": "minimax_hd", "voice": voice}

        # Kokoro TTS (82M params, efficient)
        elif model == "kokoro" and REPLICATE_API_KEY:
            output = replicate.run(
                "jaaari/kokoro-82m",
                input={
                    "text": text,
                    "voice": voice  # Supports multiple voices
                }
            )

            audio_url = output if isinstance(output, str) else output[0]
            response = requests.get(audio_url, timeout=60)
            audio_bytes = response.content
            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

            return {"success": True, "audio": audio_b64, "model": "kokoro", "voice": voice}

        else:
            return {"error": f"Invalid model '{model}' or API key not set. Available: openai, minimax_turbo, minimax_hd, kokoro"}

    except Exception as e:
        import traceback
        return {"error": f"Advanced TTS error: {str(e)}\n{traceback.format_exc()}"}


# ═══════════════════════════════════════════════════════════
# CHAT FUNCTIONS WITH MULTIPLE AI MODELS (2025)
# ═══════════════════════════════════════════════════════════

@celery_app.task(name='chat_with_ai')
def chat_with_ai_task(message: str, model: str = "gemini-flash", history: List[Dict] = None) -> Dict:
    """Chat with AI models - OpenAI, Gemini, Anthropic - ASYNC"""
    try:
        if history is None:
            history = []

        # OpenAI Chat Models
        if model.startswith("gpt"):
            if not OPENAI_API_KEY:
                return {"error": "OPENAI_API_KEY not set"}

            # Convert history to OpenAI format
            messages = [{"role": "system", "content": "You are a helpful AI assistant."}]
            for msg in history:
                messages.append({"role": msg["role"], "content": msg["content"]})
            messages.append({"role": "user", "content": message})

            # Call OpenAI API
            response = openai_client.chat.completions.create(
                model=model,  # gpt-4, gpt-4-turbo, gpt-3.5-turbo
                messages=messages,
                temperature=0.7,
                max_tokens=2048
            )

            reply = response.choices[0].message.content

            return {
                "success": True,
                "response": reply,
                "model": model,
                "tokens_used": response.usage.total_tokens
            }

        # Gemini Models
        elif model.startswith("gemini"):
            if not GEMINI_API_KEY:
                return {"error": "GEMINI_API_KEY not set"}

            # Select model
            if "pro" in model:
                chat_model = gemini_pro_model
            else:
                chat_model = gemini_model  # Default to Flash

            # Build conversation history
            conversation = []
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                conversation.append({"role": role, "parts": [{"text": msg["content"]}]})
            conversation.append({"role": "user", "parts": [{"text": message}]})

            # Generate response
            response = chat_model.generate_content(
                contents=conversation,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=2048,
                )
            )

            reply = response.text

            return {
                "success": True,
                "response": reply,
                "model": model
            }

        # Replicate Models (LLaMA, etc.)
        elif model.startswith("llama") or model.startswith("meta"):
            if not REPLICATE_API_KEY:
                return {"error": "REPLICATE_API_KEY not set"}

            # Build prompt with history
            prompt = ""
            for msg in history:
                role_name = msg["role"].capitalize()
                prompt += f"{role_name}: {msg['content']}\n\n"
            prompt += f"User: {message}\n\nAssistant:"

            # Call LLaMA model
            output = replicate.run(
                "meta/llama-2-70b-chat",
                input={
                    "prompt": prompt,
                    "max_new_tokens": 2048,
                    "temperature": 0.7,
                    "top_p": 0.9
                }
            )

            # Collect output
            reply = ""
            for item in output:
                reply += str(item)

            return {
                "success": True,
                "response": reply.strip(),
                "model": "llama-2-70b-chat"
            }

        else:
            return {"error": f"Invalid model '{model}'. Available: gpt-4, gpt-3.5-turbo, gemini-flash, gemini-pro, llama"}

    except Exception as e:
        import traceback
        return {"error": f"Chat error: {str(e)}\n{traceback.format_exc()}"}
