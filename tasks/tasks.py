"""Celery tasks for async operations"""
from tasks.celery_app import celery_app
from telethon.sync import TelegramClient
from telethon.errors import ChannelInvalidError, ChannelPrivateError
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
    MAX_POSTS_TO_ANALYZE
)


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
    """Analyze Telegram channel style - ASYNC"""
    try:
        # Parse channel with Telethon
        client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
        client.connect()

        if not client.is_user_authorized():
            return {"error": "Telethon not authorized"}

        entity = client.get_entity(channel_url)
        messages = client.get_messages(entity, limit=MAX_POSTS_TO_ANALYZE)

        posts_data = []
        for msg in messages:
            if msg.text:
                emoji_count = len(re.findall(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001FAFF\U00002702-\U000027B0]', msg.text))
                posts_data.append({
                    "text": msg.text,
                    "emoji_count": emoji_count
                })

        client.disconnect()

        if not posts_data:
            return {"error": "No text posts found"}

        # Calculate metrics
        total_words = sum(len(p['text'].split()) for p in posts_data)
        total_sentences = sum(len(re.split(r'[.!?]+', p['text'])) for p in posts_data)
        total_emojis = sum(p['emoji_count'] for p in posts_data)
        num_posts = len(posts_data)

        metrics = {
            "average_word_count": round(total_words / num_posts),
            "average_sentence_count": round(total_sentences / num_posts),
            "average_emoji_count": round(total_emojis / num_posts),
        }

        # Analyze style with Gemini
        posts_text = "\n\n---POST---\n\n".join([p['text'] for p in posts_data[:20]])  # Limit for API

        prompt = f"""Analyze these Telegram posts and describe the style in JSON format.

Posts:
{posts_text}

Return JSON with these fields:
- tone: overall tone (e.g., "expert", "casual", "humorous")
- themes: array of 3-5 main themes
- post_structure: typical structure description
- formatting_usage: how formatting is used
- call_to_action_frequency: how often CTAs appear
- target_audience: who is the target audience
- professionalism_level: level of professionalism"""

        response = gemini_model.generate_content(
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
            )
        )

        style_json = json.loads(response.text)
        style_json.update(metrics)

        return {"success": True, "style": style_json}

    except (ChannelInvalidError, ValueError):
        return {"error": "Invalid channel URL"}
    except ChannelPrivateError:
        return {"error": "Channel is private"}
    except Exception as e:
        return {"error": f"Analysis error: {str(e)}"}


@celery_app.task(name='generate_posts')
def generate_posts_task(style_summary: Dict, topic: str) -> Dict:
    """Generate post variations - ASYNC"""
    try:
        avg_words = style_summary.get("average_word_count", 100)
        avg_sentences = style_summary.get("average_sentence_count", 5)
        avg_emojis = style_summary.get("average_emoji_count", 0)

        style_clean = {k: v for k, v in style_summary.items()
                       if k not in ['average_word_count', 'average_sentence_count', 'average_emoji_count']}

        prompt = f"""You are a Telegram channel author. Create 3 different post variations on the topic: "{topic}"

Style guide:
{json.dumps(style_clean, indent=2, ensure_ascii=False)}

Constraints:
- Words: ~{avg_words}
- Sentences: ~{avg_sentences}
- Emojis: ~{avg_emojis}

Write 3 complete, ready-to-publish posts.
Use only Telegram HTML tags: <b>, <i>, <s>, <code>, <a href="">.
Separate variants with "---VARIANT---"."""

        response = gemini_model.generate_content(
            contents=[{"role": "user", "parts": [{"text": prompt}]}]
        )

        variants = response.text.split("---VARIANT---")
        clean_variants = [_clean_html(v.strip()) for v in variants if v.strip()]

        return {"success": True, "posts": clean_variants[:3]}

    except Exception as e:
        return {"error": f"Generation error: {str(e)}"}


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
                        "language": "ru",
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
