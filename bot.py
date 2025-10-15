"""
SMM Bot - Main bot file
Intuitive multi-tool for SMM specialists
"""
import telebot
from telebot import types
import time
import base64
from io import BytesIO

from core.config import BOT_TOKEN, validate_config
from core.state_manager import state_manager
from core.localization import get_text
from db.database import db
from tasks.celery_app import celery_app
from tasks.tasks import (
    analyze_channel_task,
    generate_posts_task,
    fetch_news_task,
    generate_post_from_news_task,
    generate_image_task,
    edit_image_task,
    remove_watermark_task,
    add_watermark_task
)

# Validate config
validate_config()

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Constants
STATES = {
    "WAITING_CHANNEL": "waiting_channel",
    "WAITING_TOPIC": "waiting_topic",
    "WAITING_NEWS_KEYWORDS": "waiting_news_keywords",
    "WAITING_IMAGE_PROMPT": "waiting_image_prompt",
    "WAITING_EDIT_INSTRUCTION": "waiting_edit_instruction",
    "WAITING_WATERMARK_TEXT": "waiting_watermark_text",
    "WAITING_IMAGE_FOR_EDIT": "waiting_image_for_edit",
    "WAITING_IMAGE_FOR_WM": "waiting_image_for_wm",
}


# ===== KEYBOARDS =====

def main_menu_keyboard(lang='en'):
    """Main menu keyboard"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        types.KeyboardButton(get_text(lang, 'analyze_channel')),
        types.KeyboardButton(get_text(lang, 'generate_post')),
        types.KeyboardButton(get_text(lang, 'news_to_post')),
        types.KeyboardButton(get_text(lang, 'create_image')),
        types.KeyboardButton(get_text(lang, 'edit_image')),
        types.KeyboardButton(get_text(lang, 'watermark')),
        types.KeyboardButton(get_text(lang, 'my_stats')),
        types.KeyboardButton("❓ Help")
    )
    return keyboard


def cancel_keyboard(lang='en'):
    """Cancel keyboard"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton(get_text(lang, 'cancel')))
    return keyboard


def news_category_keyboard():
    """News categories inline keyboard"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("🖥 Tech", callback_data="news_tech"),
        types.InlineKeyboardButton("💰 Crypto", callback_data="news_crypto"),
        types.InlineKeyboardButton("📱 Marketing", callback_data="news_marketing"),
        types.InlineKeyboardButton("💼 Business", callback_data="news_business"),
        types.InlineKeyboardButton("🔍 Custom Search", callback_data="news_custom")
    )
    return keyboard


def image_provider_keyboard():
    """Image generation provider keyboard"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("🎨 DALL-E 3", callback_data="img_dalle"),
        types.InlineKeyboardButton("⚡ Stable Diffusion", callback_data="img_sd")
    )
    return keyboard


# ===== START & HELP =====

@bot.message_handler(commands=['start'])
def start_handler(message):
    """Start command handler"""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    # Clear any existing state
    state_manager.clear_state(user_id)
    state_manager.clear_user_data(user_id)

    # Check if user already has language set
    user_lang = db.get_user_language(user_id)

    if not user_lang or user_lang == 'en':
        # Show language selection
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
            types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")
        )
        bot.send_message(
            message.chat.id,
            "👋 <b>Welcome to SMM Bot!</b>\n\nPlease select your language:\nПожалуйста, выберите язык:",
            reply_markup=markup
        )
    else:
        # User already has language, show main menu
        db.add_user(user_id, username, first_name, user_lang)
        show_main_menu(message, user_lang)


def show_main_menu(message, lang='en'):
    """Show main menu with selected language"""
    if lang == 'ru':
        welcome_text = """👋 <b>Добро пожаловать в SMM Bot!</b>

Я ваш AI-ассистент для создания контента в социальных сетях.

<b>Что я умею:</b>
📊 Анализировать стиль Telegram каналов
✍️ Генерировать посты в любом стиле
📰 Создавать посты из последних новостей
🎨 Генерировать AI изображения (DALL-E 3)
✏️ Редактировать изображения с AI
💧 Добавлять/удалять водяные знаки

Выберите опцию из меню ниже или введите /help для подробной информации."""
    else:
        welcome_text = """👋 <b>Welcome to SMM Bot!</b>

I'm your AI-powered assistant for social media content creation.

<b>What I can do:</b>
📊 Analyze Telegram channels' style
✍️ Generate posts in any style
📰 Create posts from latest news
🎨 Generate AI images (DALL-E 3)
✏️ Edit images with AI
💧 Add/remove watermarks

Choose an option from the menu below or type /help for more info."""

    bot.send_message(
        message.chat.id,
        welcome_text,
        reply_markup=main_menu_keyboard(lang)
    )


@bot.message_handler(commands=['help'])
def help_handler(message):
    """Help command handler"""
    help_text = """<b>📚 SMM Bot Help</b>

<b>Main Features:</b>

📊 <b>Analyze Channel</b>
Analyze any Telegram channel's writing style, tone, and structure.
Just provide the channel username (@channel).

✍️ <b>Generate Post</b>
Create posts in your channel's style.
First analyze a channel, then generate posts on any topic.

📰 <b>News to Post</b>
Find latest news and automatically generate posts about them.
Categories: Tech, Crypto, Marketing, Business

🎨 <b>Create Image</b>
Generate unique images with AI (DALL-E 3).
Just describe what you want to see.

✏️ <b>Edit Image</b>
Edit images using AI instructions:
- Add text or logos
- Change colors/background
- Apply effects
- Remove watermarks

💧 <b>Watermark</b>
Add watermark text to your images.

📈 <b>My Stats</b>
View your usage statistics.

<b>Quick Tips:</b>
• All tasks run asynchronously - no waiting!
• You can cancel any operation with ❌ Cancel
• Images are optimized for Telegram

Need help? Just ask!"""

    bot.send_message(message.chat.id, help_text)


# ===== MENU BUTTON HANDLERS =====

@bot.message_handler(func=lambda m: m.text in ["📊 Analyze Channel", "📊 Анализ канала"])
def analyze_channel_button(message):
    """Analyze channel button handler"""
    user_id = message.from_user.id

    state_manager.set_state(user_id, STATES["WAITING_CHANNEL"])

    bot.send_message(
        message.chat.id,
        "📊 <b>Channel Analysis</b>\n\n"
        "Send me the channel username in format: <code>@channel_name</code>\n\n"
        "Example: @durov",
        reply_markup=cancel_keyboard()
    )


@bot.message_handler(func=lambda m: m.text in ["✍️ Generate Post", "✍️ Создать пост"])
def generate_post_button(message):
    """Generate post button handler"""
    user_id = message.from_user.id

    # Check if channel is analyzed
    style = db.get_channel_style(user_id)

    if not style:
        bot.send_message(
            message.chat.id,
            "❌ Please analyze a channel first!\n\n"
            "Use 📊 Analyze Channel to get started."
        )
        return

    state_manager.set_state(user_id, STATES["WAITING_TOPIC"])

    bot.send_message(
        message.chat.id,
        "✍️ <b>Generate Post</b>\n\n"
        "What topic should I write about?\n\n"
        "Example: <i>\"New AI trends in 2025\"</i>",
        reply_markup=cancel_keyboard()
    )


@bot.message_handler(func=lambda m: m.text in ["📰 News to Post", "📰 Новости в пост"])
def news_to_post_button(message):
    """News to post button handler"""
    bot.send_message(
        message.chat.id,
        "📰 <b>News to Post</b>\n\n"
        "Choose a news category or search by keywords:",
        reply_markup=news_category_keyboard()
    )


@bot.message_handler(func=lambda m: m.text in ["🎨 Create Image", "🎨 Создать картинку"])
def create_image_button(message):
    """Create image button handler"""
    user_id = message.from_user.id

    state_manager.set_state(user_id, STATES["WAITING_IMAGE_PROMPT"])

    bot.send_message(
        message.chat.id,
        "🎨 <b>Create Image</b>\n\n"
        "Describe the image you want to create:\n\n"
        "Examples:\n"
        "• <i>\"Modern tech workspace with AI theme\"</i>\n"
        "• <i>\"Social media marketing concept art\"</i>\n"
        "• <i>\"Futuristic cityscape at sunset\"</i>",
        reply_markup=cancel_keyboard()
    )


@bot.message_handler(func=lambda m: m.text in ["✏️ Edit Image", "✏️ Редактировать фото"])
def edit_image_button(message):
    """Edit image button handler"""
    user_id = message.from_user.id

    state_manager.set_state(user_id, STATES["WAITING_IMAGE_FOR_EDIT"])

    bot.send_message(
        message.chat.id,
        "✏️ <b>Edit Image</b>\n\n"
        "Send me the image you want to edit.\n\n"
        "After that, I'll ask what changes you want to make.",
        reply_markup=cancel_keyboard()
    )


@bot.message_handler(func=lambda m: m.text in ["💧 Watermark", "💧 Водяной знак"])
def watermark_button(message):
    """Watermark button handler"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("➕ Add Watermark", callback_data="wm_add"),
        types.InlineKeyboardButton("➖ Remove Watermark", callback_data="wm_remove")
    )

    bot.send_message(
        message.chat.id,
        "💧 <b>Watermark Tools</b>\n\n"
        "Choose an option:",
        reply_markup=keyboard
    )


@bot.message_handler(func=lambda m: m.text in ["📈 My Stats", "📈 Моя статистика"])
def stats_button(message):
    """Stats button handler"""
    user_id = message.from_user.id

    stats = db.get_user_stats(user_id)

    stats_text = f"""📈 <b>Your Statistics</b>

📊 Channels analyzed: <b>{stats['channels_analyzed']}</b>
✍️ Posts generated: <b>{stats['posts_generated']}</b>
🎨 Images created: <b>{stats['images_created']}</b>

Keep creating amazing content! 🚀"""

    bot.send_message(message.chat.id, stats_text)


@bot.message_handler(func=lambda m: m.text == "❓ Help")
def help_button(message):
    """Help button handler"""
    help_handler(message)


@bot.message_handler(func=lambda m: m.text in ["❌ Cancel", "❌ Отмена"])
def cancel_button(message):
    """Cancel button handler"""
    user_id = message.from_user.id

    state_manager.clear_state(user_id)
    state_manager.clear_user_data(user_id)

    bot.send_message(
        message.chat.id,
        "✅ Operation cancelled.\n\nChoose what to do next:",
        reply_markup=main_menu_keyboard()
    )


# ===== STATE HANDLERS =====

@bot.message_handler(func=lambda m: state_manager.get_state(m.from_user.id) == STATES["WAITING_CHANNEL"])
def handle_channel_input(message):
    """Handle channel URL input"""
    user_id = message.from_user.id
    channel_url = message.text.strip()

    if not channel_url.startswith('@'):
        bot.send_message(
            message.chat.id,
            "❌ Invalid format. Please use: <code>@channel_name</code>"
        )
        return

    state_manager.clear_state(user_id)

    # Send processing message
    processing_msg = bot.send_message(
        message.chat.id,
        "⏳ Analyzing channel...\n\n"
        "This may take up to 1 minute.\n"
        "I'm fetching posts and analyzing the style with AI.",
        reply_markup=main_menu_keyboard()
    )

    # Start async task
    task = analyze_channel_task.delay(channel_url)
    state_manager.set_task_id(user_id, task.id)

    # Wait for result
    check_task_result(user_id, task.id, processing_msg.message_id, "analyze")


@bot.message_handler(func=lambda m: state_manager.get_state(m.from_user.id) == STATES["WAITING_TOPIC"])
def handle_topic_input(message):
    """Handle topic input for post generation"""
    user_id = message.from_user.id
    topic = message.text.strip()

    state_manager.clear_state(user_id)

    style = db.get_channel_style(user_id)

    processing_msg = bot.send_message(
        message.chat.id,
        "⏳ Generating posts...\n\n"
        "Creating 3 variations in your channel's style.",
        reply_markup=main_menu_keyboard()
    )

    # Start async task
    task = generate_posts_task.delay(style, topic)
    state_manager.set_task_id(user_id, task.id)

    check_task_result(user_id, task.id, processing_msg.message_id, "generate_posts")


@bot.message_handler(func=lambda m: state_manager.get_state(m.from_user.id) == STATES["WAITING_IMAGE_PROMPT"])
def handle_image_prompt(message):
    """Handle image generation prompt"""
    user_id = message.from_user.id
    prompt = message.text.strip()

    state_manager.set_data(user_id, "image_prompt", prompt)

    bot.send_message(
        message.chat.id,
        "🎨 Choose AI model:",
        reply_markup=image_provider_keyboard()
    )


@bot.message_handler(content_types=['photo'], func=lambda m: state_manager.get_state(m.from_user.id) == STATES["WAITING_IMAGE_FOR_EDIT"])
def handle_image_for_edit(message):
    """Handle image upload for editing"""
    user_id = message.from_user.id

    # Get largest photo
    photo = message.photo[-1]
    file_info = bot.get_file(photo.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    # Convert to base64
    img_b64 = base64.b64encode(downloaded_file).decode('utf-8')

    # Save image
    state_manager.set_data(user_id, "current_image", img_b64)
    state_manager.set_state(user_id, STATES["WAITING_EDIT_INSTRUCTION"])

    bot.send_message(
        message.chat.id,
        "✅ Image received!\n\n"
        "Now tell me what to change:\n\n"
        "Examples:\n"
        "• <i>\"Add red text 'SALE' at the top\"</i>\n"
        "• <i>\"Make background blue\"</i>\n"
        "• <i>\"Add company logo in corner\"</i>\n"
        "• <i>\"Make it brighter\"</i>",
        reply_markup=cancel_keyboard()
    )


@bot.message_handler(func=lambda m: state_manager.get_state(m.from_user.id) == STATES["WAITING_EDIT_INSTRUCTION"])
def handle_edit_instruction(message):
    """Handle edit instruction"""
    user_id = message.from_user.id
    instruction = message.text.strip()

    state_manager.clear_state(user_id)

    img_b64 = state_manager.get_data(user_id, "current_image")

    if not img_b64:
        bot.send_message(message.chat.id, "❌ Image not found. Please start over.")
        return

    processing_msg = bot.send_message(
        message.chat.id,
        "⏳ Editing image with AI...\n\n"
        "This may take 1-2 minutes.",
        reply_markup=main_menu_keyboard()
    )

    task = edit_image_task.delay(img_b64, instruction)
    state_manager.set_task_id(user_id, task.id)

    check_task_result(user_id, task.id, processing_msg.message_id, "edit_image")


@bot.message_handler(content_types=['photo'], func=lambda m: state_manager.get_state(m.from_user.id) == STATES["WAITING_IMAGE_FOR_WM"])
def handle_image_for_watermark(message):
    """Handle image for watermark"""
    user_id = message.from_user.id

    photo = message.photo[-1]
    file_info = bot.get_file(photo.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    img_b64 = base64.b64encode(downloaded_file).decode('utf-8')

    state_manager.set_data(user_id, "current_image", img_b64)
    state_manager.set_state(user_id, STATES["WAITING_WATERMARK_TEXT"])

    bot.send_message(
        message.chat.id,
        "✅ Image received!\n\n"
        "Enter watermark text:",
        reply_markup=cancel_keyboard()
    )


@bot.message_handler(func=lambda m: state_manager.get_state(m.from_user.id) == STATES["WAITING_WATERMARK_TEXT"])
def handle_watermark_text(message):
    """Handle watermark text"""
    user_id = message.from_user.id
    text = message.text.strip()

    state_manager.clear_state(user_id)

    img_b64 = state_manager.get_data(user_id, "current_image")

    processing_msg = bot.send_message(
        message.chat.id,
        "⏳ Adding watermark...",
        reply_markup=main_menu_keyboard()
    )

    task = add_watermark_task.delay(img_b64, text)
    state_manager.set_task_id(user_id, task.id)

    check_task_result(user_id, task.id, processing_msg.message_id, "add_watermark")


@bot.message_handler(func=lambda m: state_manager.get_state(m.from_user.id) == STATES["WAITING_NEWS_KEYWORDS"])
def handle_news_keywords(message):
    """Handle custom news search keywords"""
    user_id = message.from_user.id
    keywords_text = message.text.strip()

    state_manager.clear_state(user_id)

    keywords = [kw.strip() for kw in keywords_text.split(',')]

    processing_msg = bot.send_message(
        message.chat.id,
        f"🔍 Searching news: {', '.join(keywords)}...",
        reply_markup=main_menu_keyboard()
    )

    task = fetch_news_task.delay(keywords=keywords)
    state_manager.set_task_id(user_id, task.id)

    check_task_result(user_id, task.id, processing_msg.message_id, "fetch_news")


# ===== CALLBACK HANDLERS =====

@bot.callback_query_handler(func=lambda c: c.data.startswith('lang_'))
def language_callback(call):
    """Language selection callback"""
    user_id = call.from_user.id
    username = call.from_user.username
    first_name = call.from_user.first_name

    bot.answer_callback_query(call.id)

    # Get selected language
    lang = call.data.split('_')[1]  # 'en' or 'ru'

    # Save user with language
    db.add_user(user_id, username, first_name, lang)
    db.set_user_language(user_id, lang)

    # Delete language selection message
    bot.delete_message(call.message.chat.id, call.message.message_id)

    # Show main menu
    show_main_menu(call.message, lang)


@bot.callback_query_handler(func=lambda c: c.data.startswith('news_'))
def news_callback(call):
    """News category callbacks"""
    user_id = call.from_user.id
    bot.answer_callback_query(call.id)

    if call.data == "news_custom":
        state_manager.set_state(user_id, STATES["WAITING_NEWS_KEYWORDS"])

        bot.send_message(
            call.message.chat.id,
            "🔍 Enter keywords (comma-separated):\n\n"
            "Example: <code>Python, AI, Machine Learning</code>",
            reply_markup=cancel_keyboard()
        )
        return

    category = call.data.replace('news_', '')

    processing_msg = bot.send_message(
        call.message.chat.id,
        f"📰 Fetching {category.upper()} news...",
        reply_markup=main_menu_keyboard()
    )

    task = fetch_news_task.delay(category=category)
    state_manager.set_task_id(user_id, task.id)

    check_task_result(user_id, task.id, processing_msg.message_id, "fetch_news")


@bot.callback_query_handler(func=lambda c: c.data.startswith('select_news_'))
def select_news_callback(call):
    """Select news for post generation"""
    user_id = call.from_user.id
    news_index = int(call.data.split('_')[-1])

    bot.answer_callback_query(call.id)

    news_list = state_manager.get_data(user_id, "news_list")
    style = db.get_channel_style(user_id)

    if not news_list or not style:
        bot.send_message(call.message.chat.id, "❌ Data not found. Please try again.")
        return

    if news_index >= len(news_list):
        bot.send_message(call.message.chat.id, "❌ Invalid news selection.")
        return

    news_item = news_list[news_index]

    processing_msg = bot.send_message(
        call.message.chat.id,
        f"⏳ Generating posts from:\n<b>{news_item['title']}</b>",
        reply_markup=main_menu_keyboard()
    )

    task = generate_post_from_news_task.delay(style, news_item)
    state_manager.set_task_id(user_id, task.id)

    check_task_result(user_id, task.id, processing_msg.message_id, "generate_posts")


@bot.callback_query_handler(func=lambda c: c.data.startswith('img_'))
def image_provider_callback(call):
    """Image provider selection"""
    user_id = call.from_user.id
    bot.answer_callback_query(call.id)

    provider = "dalle" if call.data == "img_dalle" else "stability"
    prompt = state_manager.get_data(user_id, "image_prompt")

    if not prompt:
        bot.send_message(call.message.chat.id, "❌ Prompt not found. Please try again.")
        return

    processing_msg = bot.send_message(
        call.message.chat.id,
        f"🎨 Generating image with {provider.upper()}...\n\n"
        "This may take 1-2 minutes.",
        reply_markup=main_menu_keyboard()
    )

    task = generate_image_task.delay(prompt, provider)
    state_manager.set_task_id(user_id, task.id)

    check_task_result(user_id, task.id, processing_msg.message_id, "generate_image")


@bot.callback_query_handler(func=lambda c: c.data.startswith('wm_'))
def watermark_callback(call):
    """Watermark action callbacks"""
    user_id = call.from_user.id
    bot.answer_callback_query(call.id)

    if call.data == "wm_add":
        state_manager.set_state(user_id, STATES["WAITING_IMAGE_FOR_WM"])
        bot.send_message(
            call.message.chat.id,
            "💧 <b>Add Watermark</b>\n\n"
            "Send me the image:",
            reply_markup=cancel_keyboard()
        )

    elif call.data == "wm_remove":
        state_manager.set_state(user_id, STATES["WAITING_IMAGE_FOR_EDIT"])
        bot.send_message(
            call.message.chat.id,
            "💧 <b>Remove Watermark</b>\n\n"
            "Send me the image with watermark:",
            reply_markup=cancel_keyboard()
        )


@bot.callback_query_handler(func=lambda c: c.data.startswith('select_post_'))
def select_post_callback(call):
    """Select post variant"""
    user_id = call.from_user.id
    post_index = int(call.data.split('_')[-1])

    bot.answer_callback_query(call.id, "✅ Post selected!")

    posts = state_manager.get_data(user_id, "generated_posts")

    if posts and post_index < len(posts):
        selected = posts[post_index]

        # Save to DB
        db.save_post(user_id, selected)

        bot.send_message(
            call.message.chat.id,
            "✅ <b>Final Post:</b>\n\n" + selected + "\n\n<i>Saved to your history!</i>"
        )


# ===== TASK RESULT CHECKER =====

def check_task_result(user_id: int, task_id: str, msg_id: int, task_type: str):
    """Check Celery task result and handle response"""

    def check_and_update():
        task_result = celery_app.AsyncResult(task_id)

        max_attempts = 60  # 60 seconds
        attempt = 0

        while attempt < max_attempts:
            if task_result.ready():
                result = task_result.get()

                if result.get("error"):
                    bot.send_message(
                        user_id,
                        f"❌ Error: {result['error']}"
                    )
                    return

                # Handle different task types
                if task_type == "analyze":
                    handle_analyze_result(user_id, result)

                elif task_type == "generate_posts":
                    handle_posts_result(user_id, result)

                elif task_type == "fetch_news":
                    handle_news_result(user_id, result)

                elif task_type == "generate_image":
                    handle_image_result(user_id, result)

                elif task_type == "edit_image":
                    handle_edited_image_result(user_id, result)

                elif task_type == "add_watermark":
                    handle_watermarked_image_result(user_id, result)

                return

            time.sleep(1)
            attempt += 1

        bot.send_message(user_id, "❌ Task timeout. Please try again.")

    # Run in thread to not block bot
    import threading
    threading.Thread(target=check_and_update).start()


def handle_analyze_result(user_id: int, result: dict):
    """Handle channel analysis result"""
    style = result.get("style")

    if not style:
        bot.send_message(user_id, "❌ Analysis failed")
        return

    # Save to DB
    db.save_channel_style(user_id, "analyzed", style)

    # Format response
    response = f"""✅ <b>Channel Analysis Complete!</b>

📊 <b>Style Summary:</b>
• Tone: {style.get('tone', 'N/A')}
• Avg Words: {style.get('average_word_count', 0)}
• Avg Emojis: {style.get('average_emoji_count', 0)}

Now you can:
✍️ Generate posts in this style
📰 Create posts from news"""

    bot.send_message(user_id, response)


def handle_posts_result(user_id: int, result: dict):
    """Handle generated posts result"""
    posts = result.get("posts", [])

    if not posts:
        bot.send_message(user_id, "❌ No posts generated")
        return

    # Save posts
    state_manager.set_data(user_id, "generated_posts", posts)

    # Send variants
    keyboard = types.InlineKeyboardMarkup(row_width=1)

    for i, post in enumerate(posts):
        bot.send_message(user_id, f"<b>Variant {i+1}:</b>\n\n{post}")

        keyboard.add(
            types.InlineKeyboardButton(
                f"✅ Select Variant {i+1}",
                callback_data=f"select_post_{i}"
            )
        )

    bot.send_message(
        user_id,
        "Choose your favorite variant:",
        reply_markup=keyboard
    )


def handle_news_result(user_id: int, result: dict):
    """Handle news fetch result"""
    news_list = result.get("news", [])

    if not news_list:
        bot.send_message(user_id, "❌ No news found")
        return

    # Save news
    state_manager.set_data(user_id, "news_list", news_list)

    # Send news
    response = "📰 <b>Latest News:</b>\n\n"

    keyboard = types.InlineKeyboardMarkup(row_width=1)

    for i, news in enumerate(news_list[:5]):
        response += f"{i+1}. <b>{news['title']}</b>\n"
        response += f"   {news['source']} • <a href='{news['url']}'>Link</a>\n\n"

        keyboard.add(
            types.InlineKeyboardButton(
                f"📝 Create post from #{i+1}",
                callback_data=f"select_news_{i}"
            )
        )

    bot.send_message(user_id, response, reply_markup=keyboard, disable_web_page_preview=True)


def handle_image_result(user_id: int, result: dict):
    """Handle generated image result"""
    img_b64 = result.get("image")

    if not img_b64:
        bot.send_message(user_id, "❌ Image generation failed")
        return

    # Decode image
    img_bytes = base64.b64decode(img_b64)

    # Send image
    bot.send_photo(user_id, photo=img_bytes, caption="✅ Your generated image!")

    # Save image data
    state_manager.set_data(user_id, "current_image", img_b64)


def handle_edited_image_result(user_id: int, result: dict):
    """Handle edited image result"""
    img_b64 = result.get("image")

    if not img_b64:
        bot.send_message(user_id, "❌ Image editing failed")
        return

    img_bytes = base64.b64decode(img_b64)

    bot.send_photo(user_id, photo=img_bytes, caption="✅ Your edited image!")

    state_manager.set_data(user_id, "current_image", img_b64)


def handle_watermarked_image_result(user_id: int, result: dict):
    """Handle watermarked image result"""
    img_b64 = result.get("image")

    if not img_b64:
        bot.send_message(user_id, "❌ Watermark operation failed")
        return

    img_bytes = base64.b64decode(img_b64)

    bot.send_photo(user_id, photo=img_bytes, caption="✅ Watermark applied!")


# ===== MAIN =====

if __name__ == '__main__':
    print("🤖 SMM Bot started!")
    print("Press Ctrl+C to stop")

    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=30)
    except KeyboardInterrupt:
        print("\n👋 Bot stopped")

