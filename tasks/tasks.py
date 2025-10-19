"""Celery tasks for async operations"""
from tasks.celery_app import celery_app
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

from core.config import (
    API_ID, API_HASH, SESSION_NAME, GEMINI_API_KEY,
    OPENAI_API_KEY, REPLICATE_API_KEY, NEWS_API_KEY,
    MAX_POSTS_TO_ANALYZE, BASE_DIR
)

# Ensure sessions directory exists
import os
os.makedirs(BASE_DIR / "sessions", exist_ok=True)


# Initialize AI clients
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')

if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)

if REPLICATE_API_KEY:
    import os
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_KEY


@celery_app.task(name='analyze_channel')
def analyze_channel_task(channel_url: str) -> Dict:
    """Analyze Telegram channel style with DEEP analysis - ASYNC"""
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
                if msg.text:
                    emoji_count = len(re.findall(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001FAFF\U00002702-\U000027B0]', msg.text))

                    # Deep metrics per post
                    words = msg.text.split()
                    sentences = [s.strip() for s in re.split(r'[.!?]+', msg.text) if s.strip()]
                    lines = [l.strip() for l in msg.text.split('\n') if l.strip()]

                    # Formatting analysis
                    bold_count = msg.text.count('<b>') + msg.text.count('**')
                    italic_count = msg.text.count('<i>') + msg.text.count('_')
                    code_count = msg.text.count('<code>') + msg.text.count('`')
                    link_count = msg.text.count('http')

                    # Punctuation analysis
                    question_marks = msg.text.count('?')
                    exclamation_marks = msg.text.count('!')
                    hashtags = len(re.findall(r'#\w+', msg.text))

                    posts_data.append({
                        "text": msg.text,
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
                        "has_cta": any(word in msg.text.lower() for word in ['подпишись', 'жми', 'переходи', 'смотри', 'читай', 'узнай'])
                    })

        if not posts_data:
            return {"error": "Текстовые посты не найдены"}

        num_posts = len(posts_data)

        # Calculate detailed metrics
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

        # Deep AI analysis with Gemini - take all posts for analysis
        posts_text = "\n\n═══ ПОСТ ═══\n\n".join([p['text'] for p in posts_data[:30]])

        prompt = f"""Ты эксперт по анализу стиля письма в Telegram каналах. Проанализируй эти посты МАКСИМАЛЬНО ГЛУБОКО и верни детальное описание стиля в JSON.

ПОСТЫ ДЛЯ АНАЛИЗА:
{posts_text}

ВЕРНИ JSON СО СЛЕДУЮЩИМИ ПОЛЯМИ:

1. "tone" - общий тон (например: "экспертный", "дружеский", "юмористический", "мотивационный", "информативный", "провокационный")

2. "writing_style" - стиль написания:
   - "vocabulary_level": уровень лексики (простая/средняя/сложная)
   - "sentence_structure": структура предложений (короткие/длинные/смешанные)
   - "paragraph_style": стиль абзацев (одно предложение/несколько/длинные блоки)

3. "content_patterns" - паттерны контента:
   - "opening_style": как автор начинает посты (вопрос/утверждение/история/факт)
   - "closing_style": как автор заканчивает посты (вывод/CTA/вопрос/многоточие)
   - "uses_stories": использует ли истории/примеры (да/нет)
   - "uses_lists": использует ли списки/перечисления (да/нет)
   - "uses_quotes": использует ли цитаты (да/нет)

4. "linguistic_features" - лингвистические особенности:
   - "uses_slang": использует ли сленг (да/нет)
   - "uses_professional_terms": использует ли профессиональные термины (да/нет)
   - "rhetorical_questions": частота риторических вопросов (часто/редко/никогда)
   - "personal_pronouns": какие местоимения ("я"/"мы"/"ты"/"вы"/смешанные)

5. "formatting_style" - стиль форматирования:
   - "emoji_placement": где размещает эмодзи (начало/конец/везде/редко)
   - "capitalization_pattern": паттерн заглавных букв (стандартно/все заглавные в заголовках/особый стиль)
   - "spacing_style": стиль пробелов между блоками (плотно/разреженно)

6. "engagement_tactics" - тактики вовлечения:
   - "asks_questions": задает ли вопросы читателям (часто/редко/никогда)
   - "direct_address": обращается ли напрямую к читателю (часто/редко/никогда)
   - "creates_intrigue": создает ли интригу/саспенс (да/нет)

7. "unique_markers" - уникальные маркеры стиля (массив из 3-5 отличительных особенностей, которые делают стиль узнаваемым)

8. "themes" - основные темы (массив из 3-5 главных тем)

9. "target_audience" - целевая аудитория (детальное описание)

10. "author_personality" - личность автора (описание характера и подхода автора к написанию)

ВАЖНО: Будь максимально детальным, это нужно для того чтобы сгенерировать посты НЕОТЛИЧИМЫЕ от оригинального автора!"""

        response = gemini_model.generate_content(
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.3,  # Lower temperature for more consistent analysis
            )
        )

        style_json = json.loads(response.text)[0]
        style_json.update(metrics)

        return {"success": True, "style": style_json, "channel_title": channel_title}

    except (UsernameNotOccupied, UsernameInvalid, ValueError):
        return {"error": "Неверный URL канала"}
    except ChannelPrivate:
        return {"error": "Канал приватный"}
    except Exception as e:
        return {"error": f"Ошибка анализа: {str(e)}"}


@celery_app.task(name='generate_posts')
def generate_posts_task(style_summary: Dict, topic: str) -> Dict:
    """Generate post variations with DEEP style matching - ASYNC"""
    try:
        # Extract metrics
        avg_words = style_summary.get("average_word_count")
        avg_sentences = style_summary.get("average_sentence_count")
        avg_lines = style_summary.get("average_line_count")
        avg_emojis = style_summary.get("average_emoji_count")
        avg_bolds = style_summary.get("average_bold_usage")
        avg_italics = style_summary.get("average_italic_usage")
        avg_questions = style_summary.get("average_question_marks")
        avg_exclamations = style_summary.get("average_exclamation_marks")
        avg_hashtags = style_summary.get("average_hashtags")

        prompt = f"""Ты - автор Telegram канала. Тебе нужно написать 3 РАЗНЫХ варианта поста на тему: "{topic}"

КРИТИЧЕСКИ ВАЖНО: Посты должны быть АБСОЛЮТНО НЕОТЛИЧИМЫ от оригинального стиля автора! Читатель НЕ ДОЛЖЕН понять, что пост написан AI!

═══ ДЕТАЛЬНЫЙ АНАЛИЗ СТИЛЯ АВТОРА ═══

{json.dumps(style_summary, indent=2, ensure_ascii=False)}

═══ СТРОГИЕ ТРЕБОВАНИЯ ═══

МЕТРИКИ (соблюдай точно!):
• Слов: {avg_words} ±20%
• Предложений: {avg_sentences} ±3%
• Строк/абзацев: {avg_lines} ±3%
• Эмодзи: {avg_emojis} ±3%
• Выделений жирным: ~{avg_bolds}
• Выделений курсивом: ~{avg_italics}
• Вопросительных знаков: ~{avg_questions}
• Восклицательных знаков: ~{avg_exclamations}
• Хештегов: ~{avg_hashtags}

СТИЛЬ НАПИСАНИЯ:
1. Используй ТОЧНО такой же тон и манеру письма как в примерах
2. Копируй структуру постов (как автор начинает, развивает мысль, заканчивает)
3. Используй те же лингвистические особенности (слова, обороты, местоимения)
4. Применяй те же тактики вовлечения
5. Размещай эмодзи так же, как автор
6. Соблюдай форматирование (жирный, курсив, пробелы между абзацами)

УНИКАЛЬНЫЕ МАРКЕРЫ:
Обязательно используй отличительные особенности стиля автора, чтобы пост был узнаваемым!

ФОРМАТИРОВАНИЕ:
• Используй ТОЛЬКО Telegram HTML теги: <b>, <i>, <s>, <code>, <a href="">
• НЕ используй Markdown (**, __, ~~ и т.д.)
• Размещай переносы строк как в оригинале

РЕЗУЛЬТАТ:
Напиши 3 ПОЛНЫХ, ГОТОВЫХ К ПУБЛИКАЦИИ поста.
Каждый вариант должен быть УНИКАЛЬНЫМ, но в ОДНОМ СТИЛЕ.
Разделяй варианты строкой "---VARIANT---"

НАЧИНАЙ ПИСАТЬ ПОСТЫ:"""

        response = gemini_model.generate_content(
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            generation_config=genai.types.GenerationConfig(
                temperature=0.9,  # Higher temperature for more creative variations
                top_p=0.95,
                top_k=40,
            )
        )

        variants = response.text.split("---VARIANT---")
        clean_variants = [_clean_html(v.strip()) for v in variants if v.strip()]

        return {"success": True, "posts": clean_variants[:3]}

    except Exception as e:
        return {"error": f"Ошибка генерации: {str(e)}"}


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
def generate_post_from_news_task(style_summary: Dict, news_item: Dict) -> Dict:
    """Generate post from news - ASYNC"""
    try:
        avg_words = style_summary.get("average_word_count", 100)
        avg_sentences = style_summary.get("average_sentence_count", 5)
        avg_emojis = style_summary.get("average_emoji_count", 0)

        style_clean = {k: v for k, v in style_summary.items()
                       if k not in ['average_word_count', 'average_sentence_count', 'average_emoji_count']}

        prompt = f"""Create 3 post variations based on this news:

Title: {news_item['title']}
Content: {news_item['content']}
Source: {news_item['source']}
URL: {news_item['url']}

Style guide:
{json.dumps(style_clean, indent=2, ensure_ascii=False)}

Constraints:
- Words: ~{avg_words}
- Sentences: ~{avg_sentences}
- Emojis: ~{avg_emojis}
- Include source link at the end

Write 3 complete posts. HTML tags: <b>, <i>, <s>, <code>, <a href="">.
Separate with "---VARIANT---"."""

        response = gemini_model.generate_content(
            contents=[{"role": "user", "parts": [{"text": prompt}]}]
        )

        variants = response.text.split("---VARIANT---")
        clean_variants = [_clean_html(v.strip()) for v in variants if v.strip()]

        return {"success": True, "posts": clean_variants[:3]}

    except Exception as e:
        return {"error": f"Post generation error: {str(e)}"}


@celery_app.task(name='generate_image')
def generate_image_task(prompt: str, provider: str = "dalle", size: str = "1024x1024") -> Dict:
    """Generate image with AI - ASYNC"""
    try:
        if provider == "dalle" and OPENAI_API_KEY:
            response = openai_client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                n=1,
                size=size,
                quality="standard"
            )

            image_url = response.data[0].url
            img_response = requests.get(image_url, timeout=30)
            img_bytes = img_response.content

            # Encode to base64 for JSON serialization
            img_b64 = base64.b64encode(img_bytes).decode('utf-8')

            return {"success": True, "image": img_b64, "provider": "dalle"}

        elif provider == "stability":
            # Placeholder for Stability AI
            return {"error": "Stability AI not yet implemented"}

        else:
            return {"error": "Invalid provider or missing API key"}

    except Exception as e:
        return {"error": f"Image generation error: {str(e)}"}


@celery_app.task(name='edit_image')
def edit_image_task(image_b64: str, instruction: str) -> Dict:
    """Edit image with Nano Banana - ASYNC"""
    try:
        if not REPLICATE_API_KEY:
            return {"error": "REPLICATE_API_KEY not set"}

        # Decode image
        image_bytes = base64.b64decode(image_b64)

        # Convert to data URI
        image_data_uri = f"data:image/png;base64,{image_b64}"

        # Run Nano Banana
        output = replicate.run(
            "fofr/nano-banana",
            input={
                "image": image_data_uri,
                "prompt": instruction,
                "guidance_scale": 7.5,
                "num_inference_steps": 50
            }
        )

        # Get output URL
        output_url = output[0] if isinstance(output, list) else output

        # Download result
        response = requests.get(output_url, timeout=30)
        result_bytes = response.content

        # Encode back
        result_b64 = base64.b64encode(result_bytes).decode('utf-8')

        return {"success": True, "image": result_b64}

    except Exception as e:
        return {"error": f"Image edit error: {str(e)}"}


@celery_app.task(name='remove_watermark')
def remove_watermark_task(image_b64: str) -> Dict:
    """Remove background/watermark from image - ASYNC"""
    try:
        # Decode image
        image_bytes = base64.b64decode(image_b64)

        # Use rembg to remove background
        # This can also help remove watermarks in some cases
        result_bytes = remove(image_bytes)

        # Encode back
        result_b64 = base64.b64encode(result_bytes).decode('utf-8')

        return {"success": True, "image": result_b64}

    except Exception as e:
        return {"error": f"Watermark removal error: {str(e)}"}


@celery_app.task(name='add_watermark')
def add_watermark_task(image_b64: str, text: str) -> Dict:
    """Add watermark to image - ASYNC"""
    try:
        # Decode image
        image_bytes = base64.b64decode(image_b64)
        img = Image.open(BytesIO(image_bytes)).convert("RGBA")

        # Create watermark layer
        watermark = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(watermark)

        # Try to use a font
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
        except:
            font = ImageFont.load_default()

        # Position at bottom right
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        position = (img.width - text_width - 20, img.height - text_height - 20)

        # Draw watermark
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
        return {"error": f"Watermark add error: {str(e)}"}


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
