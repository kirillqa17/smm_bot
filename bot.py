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

def main_menu_keyboard():
    """Main menu keyboard"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        types.KeyboardButton("📊 Анализ канала"),
        types.KeyboardButton("✍️ Создать пост"),
        types.KeyboardButton("📰 Новости в пост"),
        types.KeyboardButton("🎨 Создать картинку"),
        types.KeyboardButton("✏️ Редактировать фото"),
        types.KeyboardButton("💧 Водяной знак"),
        types.KeyboardButton("📈 Моя статистика"),
        types.KeyboardButton("❓ Помощь")
    )
    return keyboard


def cancel_keyboard():
    """Cancel keyboard"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("❌ Отмена"))
    return keyboard


def news_category_keyboard():
    """News categories inline keyboard"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("🖥 Технологии", callback_data="news_tech"),
        types.InlineKeyboardButton("💰 Криптовалюты", callback_data="news_crypto"),
        types.InlineKeyboardButton("📱 Маркетинг", callback_data="news_marketing"),
        types.InlineKeyboardButton("💼 Бизнес", callback_data="news_business"),
        types.InlineKeyboardButton("🔍 Свой запрос", callback_data="news_custom")
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

    # Add user to database
    db.add_user(user_id, username, first_name)

    # Show main menu
    show_main_menu(message)


def show_main_menu(message):
    """Show main menu"""
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

    bot.send_message(
        message.chat.id,
        welcome_text,
        reply_markup=main_menu_keyboard()
    )


@bot.message_handler(commands=['help'])
def help_handler(message):
    """Help command handler"""
    help_text = """<b>📚 Справка по SMM Bot</b>

<b>Основные функции:</b>

📊 <b>Анализ канала</b>
Анализ стиля, тона и структуры любого Telegram канала.
Просто укажите username канала (@канал).

✍️ <b>Создать пост</b>
Создание постов в стиле вашего канала.
Сначала проанализируйте канал, затем генерируйте посты на любую тему.

📰 <b>Новости в пост</b>
Поиск последних новостей и автоматическая генерация постов.
Категории: Tech, Crypto, Marketing, Business

🎨 <b>Создать картинку</b>
Генерация уникальных изображений с помощью AI (DALL-E 3).
Просто опишите, что хотите увидеть.

✏️ <b>Редактировать фото</b>
Редактирование изображений с помощью AI:
- Добавление текста или логотипов
- Изменение цветов/фона
- Применение эффектов
- Удаление водяных знаков

💧 <b>Водяной знак</b>
Добавление текста-водяного знака на изображения.

📈 <b>Моя статистика</b>
Просмотр статистики использования.

<b>Полезные советы:</b>
• Все задачи выполняются асинхронно - не нужно ждать!
• Вы можете отменить любую операцию через ❌ Отмена
• Изображения оптимизированы для Telegram

Нужна помощь? Просто спросите!"""

    bot.send_message(message.chat.id, help_text)


# ===== MENU BUTTON HANDLERS =====

@bot.message_handler(func=lambda m: m.text in ["📊 Analyze Channel", "📊 Анализ канала"])
def analyze_channel_button(message):
    """Analyze channel button handler"""
    user_id = message.from_user.id

    state_manager.set_state(user_id, STATES["WAITING_CHANNEL"])

    bot.send_message(
        message.chat.id,
        "📊 <b>Анализ канала</b>\n\n"
        "Отправьте мне username канала в формате: <code>@имя_канала</code>\n\n"
        "Пример: @durov",
        reply_markup=cancel_keyboard()
    )


@bot.message_handler(func=lambda m: m.text in ["✍️ Generate Post", "✍️ Создать пост"])
def generate_post_button(message):
    """Generate post button handler"""
    user_id = message.from_user.id

    # Get all user's channels
    channels = db.get_user_channels(user_id)

    if not channels:
        bot.send_message(
            message.chat.id,
            "❌ У вас нет проанализированных каналов!\n\n"
            "Используйте 📊 Анализ канала для начала."
        )
        return

    # If only one channel - use it directly
    if len(channels) == 1:
        channel_id = channels[0]['id']
        channel_title = channels[0]['channel_title'] or channels[0]['channel_url']

        state_manager.set_data(user_id, "selected_channel_id", channel_id)
        state_manager.set_state(user_id, STATES["WAITING_TOPIC"])

        bot.send_message(
            message.chat.id,
            f"✍️ <b>Создать пост</b>\n\n"
            f"📺 Канал: <b>{channel_title}</b>\n\n"
            f"На какую тему написать?\n\n"
            f"Пример: <i>\"Новые AI тренды в 2025\"</i>",
            reply_markup=cancel_keyboard()
        )
        return

    # Multiple channels - show selection
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for channel in channels:
        channel_title = channel['channel_title'] or channel['channel_url']
        analyzed_date = channel['analyzed_at'].strftime('%d.%m.%Y')

        keyboard.add(
            types.InlineKeyboardButton(
                f"📺 {channel_title} ({analyzed_date})",
                callback_data=f"select_channel_{channel['id']}"
            )
        )

    bot.send_message(
        message.chat.id,
        "✍️ <b>Создать пост</b>\n\n"
        "Выберите канал для генерации поста:",
        reply_markup=keyboard
    )


@bot.message_handler(func=lambda m: m.text in ["📰 News to Post", "📰 Новости в пост"])
def news_to_post_button(message):
    """News to post button handler"""
    bot.send_message(
        message.chat.id,
        "📰 <b>Новости в пост</b>\n\n"
        "Выберите категорию новостей или поиск по ключевым словам:",
        reply_markup=news_category_keyboard()
    )


@bot.message_handler(func=lambda m: m.text in ["🎨 Create Image", "🎨 Создать картинку"])
def create_image_button(message):
    """Create image button handler"""
    user_id = message.from_user.id

    state_manager.set_state(user_id, STATES["WAITING_IMAGE_PROMPT"])

    bot.send_message(
        message.chat.id,
        "🎨 <b>Создать картинку</b>\n\n"
        "Опишите изображение, которое хотите создать:\n\n"
        "Примеры:\n"
        "• <i>\"Современное рабочее место с AI темой\"</i>\n"
        "• <i>\"Концепт-арт для социальных сетей\"</i>\n"
        "• <i>\"Футуристический город на закате\"</i>",
        reply_markup=cancel_keyboard()
    )


@bot.message_handler(func=lambda m: m.text in ["✏️ Edit Image", "✏️ Редактировать фото"])
def edit_image_button(message):
    """Edit image button handler"""
    user_id = message.from_user.id

    state_manager.set_state(user_id, STATES["WAITING_IMAGE_FOR_EDIT"])

    bot.send_message(
        message.chat.id,
        "✏️ <b>Редактировать фото</b>\n\n"
        "Отправьте мне изображение, которое хотите отредактировать.\n\n"
        "После этого я спрошу, какие изменения вы хотите внести.",
        reply_markup=cancel_keyboard()
    )


@bot.message_handler(func=lambda m: m.text in ["💧 Watermark", "💧 Водяной знак"])
def watermark_button(message):
    """Watermark button handler"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("➕ Добавить водяной знак", callback_data="wm_add"),
        types.InlineKeyboardButton("➖ Убрать водяной знак", callback_data="wm_remove")
    )

    bot.send_message(
        message.chat.id,
        "💧 <b>Инструменты водяных знаков</b>\n\n"
        "Выберите опцию:",
        reply_markup=keyboard
    )


@bot.message_handler(func=lambda m: m.text in ["📈 My Stats", "📈 Моя статистика"])
def stats_button(message):
    """Stats button handler"""
    user_id = message.from_user.id

    stats = db.get_user_stats(user_id)

    stats_text = f"""📈 <b>Ваша статистика</b>

📊 Каналов проанализировано: <b>{stats['channels_analyzed']}</b>
✍️ Постов создано: <b>{stats['posts_generated']}</b>
🎨 Изображений создано: <b>{stats['images_created']}</b>

Продолжайте создавать отличный контент! 🚀"""

    bot.send_message(message.chat.id, stats_text)


@bot.message_handler(func=lambda m: m.text == "❓ Помощь")
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
        "✅ Операция отменена.\n\nВыберите, что делать дальше:",
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
            "❌ Неверный формат. Используйте: <code>@имя_канала</code>"
        )
        return

    state_manager.clear_state(user_id)

    # Save channel URL for later use
    state_manager.set_data(user_id, "analyzing_channel_url", channel_url)

    # Send processing message
    processing_msg = bot.send_message(
        message.chat.id,
        "⏳ Анализирую канал...\n\n"
        "Это может занять до 1 минуты.\n"
        "Я загружаю посты и анализирую стиль с помощью AI.",
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

    # Get the selected channel's style instead of latest
    channel_id = state_manager.get_data(user_id, "selected_channel_id")
    if not channel_id:
        bot.send_message(message.chat.id, "❌ Канал не выбран. Пожалуйста, начните сначала.")
        return

    channel = db.get_channel_by_id(channel_id)
    if not channel or channel['user_id'] != user_id:
        bot.send_message(message.chat.id, "❌ Канал не найден.")
        return

    style = channel['style_summary']

    processing_msg = bot.send_message(
        message.chat.id,
        "⏳ Генерирую посты...\n\n"
        "Создаю 3 варианта в стиле вашего канала.",
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
        "✅ Изображение получено!\n\n"
        "Теперь скажите, что изменить:\n\n"
        "Примеры:\n"
        "• <i>\"Добавь красный текст 'СКИДКА' вверху\"</i>\n"
        "• <i>\"Сделай фон синим\"</i>\n"
        "• <i>\"Добавь логотип компании в углу\"</i>\n"
        "• <i>\"Сделай ярче\"</i>",
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
        bot.send_message(message.chat.id, "❌ Изображение не найдено. Пожалуйста, начните сначала.")
        return

    processing_msg = bot.send_message(
        message.chat.id,
        "⏳ Редактирую изображение с AI...\n\n"
        "Это может занять 1-2 минуты.",
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
        "✅ Изображение получено!\n\n"
        "Введите текст водяного знака:",
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
        "⏳ Добавляю водяной знак...",
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

@bot.callback_query_handler(func=lambda c: c.data.startswith('select_channel_'))
def select_channel_callback(call):
    """Select channel for post generation"""
    user_id = call.from_user.id
    channel_id = int(call.data.split('_')[-1])

    bot.answer_callback_query(call.id)

    # Get channel info
    channel = db.get_channel_by_id(channel_id)

    if not channel or channel['user_id'] != user_id:
        bot.send_message(call.message.chat.id, "❌ Канал не найден")
        return

    channel_title = channel['channel_title'] or channel['channel_url']

    # Save selected channel
    state_manager.set_data(user_id, "selected_channel_id", channel_id)
    state_manager.set_state(user_id, STATES["WAITING_TOPIC"])

    bot.send_message(
        call.message.chat.id,
        f"✍️ <b>Создать пост</b>\n\n"
        f"📺 Канал: <b>{channel_title}</b>\n\n"
        f"На какую тему написать?\n\n"
        f"Пример: <i>\"Новые AI тренды в 2025\"</i>",
        reply_markup=cancel_keyboard()
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith('news_'))
def news_callback(call):
    """News category callbacks"""
    user_id = call.from_user.id
    bot.answer_callback_query(call.id)

    if call.data == "news_custom":
        state_manager.set_state(user_id, STATES["WAITING_NEWS_KEYWORDS"])

        bot.send_message(
            call.message.chat.id,
            "🔍 Введите ключевые слова (через запятую):\n\n"
            "Пример: <code>Python, AI, Machine Learning</code>",
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

    if not news_list:
        bot.send_message(call.message.chat.id, "❌ Данные не найдены. Пожалуйста, попробуйте снова.")
        return

    if news_index >= len(news_list):
        bot.send_message(call.message.chat.id, "❌ Неверный выбор новости.")
        return

    news_item = news_list[news_index]

    # Save selected news
    state_manager.set_data(user_id, "selected_news", news_item)

    # Get user's channels
    channels = db.get_user_channels(user_id)

    if not channels:
        bot.send_message(
            call.message.chat.id,
            "❌ У вас нет проанализированных каналов!\n\n"
            "Используйте 📊 Анализ канала для начала."
        )
        return

    # If only one channel - use it directly
    if len(channels) == 1:
        channel_id = channels[0]['id']
        channel = db.get_channel_by_id(channel_id)
        style = channel['style_summary']

        processing_msg = bot.send_message(
            call.message.chat.id,
            f"⏳ Генерирую посты из:\n<b>{news_item['title']}</b>",
            reply_markup=main_menu_keyboard()
        )

        task = generate_post_from_news_task.delay(style, news_item)
        state_manager.set_task_id(user_id, task.id)

        check_task_result(user_id, task.id, processing_msg.message_id, "generate_posts")
        return

    # Multiple channels - show selection
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for channel in channels:
        channel_title = channel['channel_title'] or channel['channel_url']
        analyzed_date = channel['analyzed_at'].strftime('%d.%m.%Y')

        keyboard.add(
            types.InlineKeyboardButton(
                f"📺 {channel_title} ({analyzed_date})",
                callback_data=f"select_news_channel_{channel['id']}"
            )
        )

    bot.send_message(
        call.message.chat.id,
        f"📰 <b>Выбранная новость:</b>\n{news_item['title']}\n\n"
        "Выберите канал для генерации поста:",
        reply_markup=keyboard
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith('select_news_channel_'))
def select_news_channel_callback(call):
    """Select channel for news post generation"""
    user_id = call.from_user.id
    channel_id = int(call.data.split('_')[-1])

    bot.answer_callback_query(call.id)

    # Get channel info
    channel = db.get_channel_by_id(channel_id)

    if not channel or channel['user_id'] != user_id:
        bot.send_message(call.message.chat.id, "❌ Канал не найден")
        return

    # Get selected news
    news_item = state_manager.get_data(user_id, "selected_news")

    if not news_item:
        bot.send_message(call.message.chat.id, "❌ Новость не найдена. Пожалуйста, начните сначала.")
        return

    style = channel['style_summary']

    processing_msg = bot.send_message(
        call.message.chat.id,
        f"⏳ Генерирую посты из:\n<b>{news_item['title']}</b>",
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
        bot.send_message(call.message.chat.id, "❌ Промпт не найден. Пожалуйста, попробуйте снова.")
        return

    processing_msg = bot.send_message(
        call.message.chat.id,
        f"🎨 Генерирую изображение с {provider.upper()}...\n\n"
        "Это может занять 1-2 минуты.",
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
            "💧 <b>Добавить водяной знак</b>\n\n"
            "Отправьте мне изображение:",
            reply_markup=cancel_keyboard()
        )

    elif call.data == "wm_remove":
        state_manager.set_state(user_id, STATES["WAITING_IMAGE_FOR_EDIT"])
        bot.send_message(
            call.message.chat.id,
            "💧 <b>Удалить водяной знак</b>\n\n"
            "Отправьте мне изображение с водяным знаком:",
            reply_markup=cancel_keyboard()
        )


@bot.callback_query_handler(func=lambda c: c.data.startswith('select_post_'))
def select_post_callback(call):
    """Select post variant"""
    user_id = call.from_user.id
    post_index = int(call.data.split('_')[-1])

    bot.answer_callback_query(call.id, "✅ Пост выбран!")

    posts = state_manager.get_data(user_id, "generated_posts")

    if posts and post_index < len(posts):
        selected = posts[post_index]

        # Save to DB
        db.save_post(user_id, selected)

        bot.send_message(
            call.message.chat.id,
            "✅ <b>Финальный пост:</b>\n\n" + selected + "\n\n<i>Сохранено в вашу историю!</i>"
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
                        f"❌ Ошибка: {result['error']}"
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

        bot.send_message(user_id, "❌ Превышено время ожидания. Пожалуйста, попробуйте снова.")

    # Run in thread to not block bot
    import threading
    threading.Thread(target=check_and_update).start()


def handle_analyze_result(user_id: int, result: dict):
    """Handle channel analysis result"""
    style = result.get("style")
    channel_title = result.get("channel_title", "Неизвестный канал")

    if not style:
        bot.send_message(user_id, "❌ Анализ не удался")
        return

    # Get channel URL from state
    channel_url = state_manager.get_data(user_id, "analyzing_channel_url") or "unknown"

    # Save to DB with channel title
    db.save_channel_style(user_id, channel_url, channel_title, style)

    # Clean up temp data
    state_manager.delete_data(user_id, "analyzing_channel_url")

    # Format response with deep analysis info
    response = f"""✅ <b>Глубокий анализ завершен!</b>

📺 <b>Канал:</b> {channel_title}

📊 <b>Проанализировано постов:</b> {style.get('analyzed_posts_count', 0)}

📈 <b>Основные метрики:</b>
• Тон: {style.get('tone', 'N/A')}
• Среднее слов: {style.get('average_word_count', 0)}
• Среднее предложений: {style.get('average_sentence_count', 0)}
• Среднее эмодзи: {style.get('average_emoji_count', 0)}

🎯 <b>Целевая аудитория:</b> {style.get('target_audience', 'Определяется...')[:100]}...

Канал сохранен в вашем списке!
Теперь вы можете генерировать посты в этом стиле ✍️"""

    bot.send_message(user_id, response)


def handle_posts_result(user_id: int, result: dict):
    """Handle generated posts result"""
    posts = result.get("posts", [])

    if not posts:
        bot.send_message(user_id, "❌ Посты не созданы")
        return

    # Save posts
    state_manager.set_data(user_id, "generated_posts", posts)

    # Send variants
    keyboard = types.InlineKeyboardMarkup(row_width=1)

    for i, post in enumerate(posts):
        bot.send_message(user_id, f"<b>Вариант {i+1}:</b>\n\n{post}")

        keyboard.add(
            types.InlineKeyboardButton(
                f"✅ Выбрать вариант {i+1}",
                callback_data=f"select_post_{i}"
            )
        )

    bot.send_message(
        user_id,
        "Выберите понравившийся вариант:",
        reply_markup=keyboard
    )


def handle_news_result(user_id: int, result: dict):
    """Handle news fetch result"""
    news_list = result.get("news", [])

    if not news_list:
        bot.send_message(user_id, "❌ Новости не найдены")
        return

    # Save news
    state_manager.set_data(user_id, "news_list", news_list)

    # Send news
    response = "📰 <b>Последние новости:</b>\n\n"

    keyboard = types.InlineKeyboardMarkup(row_width=1)

    for i, news in enumerate(news_list[:5]):
        response += f"{i+1}. <b>{news['title']}</b>\n"
        response += f"   {news['source']} • <a href='{news['url']}'>Ссылка</a>\n\n"

        keyboard.add(
            types.InlineKeyboardButton(
                f"📝 Создать пост из #{i+1}",
                callback_data=f"select_news_{i}"
            )
        )

    bot.send_message(user_id, response, reply_markup=keyboard, disable_web_page_preview=True)


def handle_image_result(user_id: int, result: dict):
    """Handle generated image result"""
    img_b64 = result.get("image")

    if not img_b64:
        bot.send_message(user_id, "❌ Не удалось создать изображение")
        return

    # Decode image
    img_bytes = base64.b64decode(img_b64)

    # Send image
    bot.send_photo(user_id, photo=img_bytes, caption="✅ Ваше сгенерированное изображение!")

    # Save image data
    state_manager.set_data(user_id, "current_image", img_b64)


def handle_edited_image_result(user_id: int, result: dict):
    """Handle edited image result"""
    img_b64 = result.get("image")

    if not img_b64:
        bot.send_message(user_id, "❌ Не удалось отредактировать изображение")
        return

    img_bytes = base64.b64decode(img_b64)

    bot.send_photo(user_id, photo=img_bytes, caption="✅ Ваше отредактированное изображение!")

    state_manager.set_data(user_id, "current_image", img_b64)


def handle_watermarked_image_result(user_id: int, result: dict):
    """Handle watermarked image result"""
    img_b64 = result.get("image")

    if not img_b64:
        bot.send_message(user_id, "❌ Не удалось применить водяной знак")
        return

    img_bytes = base64.b64decode(img_b64)

    bot.send_photo(user_id, photo=img_bytes, caption="✅ Водяной знак применен!")


# ===== MAIN =====

if __name__ == '__main__':
    print("🤖 SMM Bot started!")
    print("Press Ctrl+C to stop")

    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=30)
    except KeyboardInterrupt:
        print("\n👋 Bot stopped")

