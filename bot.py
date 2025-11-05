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
    "WAITING_IMAGE_PROMPT": "waiting_image_prompt",
    "WAITING_EDIT_INSTRUCTION": "waiting_edit_instruction",
    "WAITING_WATERMARK_TEXT": "waiting_watermark_text",
    "WAITING_IMAGE_FOR_EDIT": "waiting_image_for_edit",
    "WAITING_IMAGE_FOR_WM": "waiting_image_for_wm",
    "WAITING_IMAGE_FOR_WM_REMOVE": "waiting_image_for_wm_remove",
    "WAITING_TTS_TEXT": "waiting_tts_text",
    "WAITING_STT_FILE": "waiting_stt_file",
}


# ===== KEYBOARDS =====

def main_menu_keyboard():
    """Main menu keyboard"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        types.KeyboardButton("📊 Анализ канала"),
        types.KeyboardButton("✍️ Создать пост"),
        types.KeyboardButton("🎨 Создать картинку"),
        types.KeyboardButton("✏️ Редактировать фото"),
        types.KeyboardButton("🎤 Озвучить текст"),
        types.KeyboardButton("🎙 Транскрибировать"),
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


def image_provider_keyboard():
    """Image generation provider keyboard with descriptions"""
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton(
            "🌟 Flux Schnell - Быстро и качественно ($0.003)",
            callback_data="img_flux_schnell"
        ),
        types.InlineKeyboardButton(
            "💎 SDXL - Классика, фотореализм ($0.0023)",
            callback_data="img_sdxl"
        ),
        types.InlineKeyboardButton(
            "🚀 Ideogram v3 Turbo - Лучший для текста ($0.08)",
            callback_data="img_ideogram"
        ),
        types.InlineKeyboardButton(
            "🎨 DALL-E 3 - Премиум качество ($0.04)",
            callback_data="img_dalle"
        )
    )
    return keyboard


def tts_voice_keyboard():
    """TTS voice selection keyboard"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("👨 Мужской голос 1", callback_data="tts_male1"),
        types.InlineKeyboardButton("👨 Мужской голос 2", callback_data="tts_male2"),
        types.InlineKeyboardButton("👩 Женский голос 1", callback_data="tts_female1"),
        types.InlineKeyboardButton("👩 Женский голос 2", callback_data="tts_female2"),
        types.InlineKeyboardButton("🤖 Нейтральный", callback_data="tts_neutral")
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
✍️ Генерировать посты в любом стиле (с предложением актуальных новостей)
🎨 Генерировать AI изображения (DALL-E 3, Stable Diffusion, Flux)
✏️ Редактировать изображения с AI (Google Imagen 3)
🎤 Озвучивать текст с выбором голосов (TTS)
🎙 Транскрибировать аудио/видео в текст (STT)
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
При генерации бот предложит актуальные темы из новостей или вы можете ввести свою тему.

🎨 <b>Создать картинку</b>
Генерация изображений с помощью AI:
• DALL-E 3 (OpenAI) - высокое качество
• Stable Diffusion XL - быстрая генерация
• Flux - новейшая модель
• Midjourney (через API)

✏️ <b>Редактировать фото</b>
Редактирование изображений с Google Imagen 3:
- Добавление/изменение объектов
- Изменение стиля и цветов
- Применение эффектов
- Инпейнтинг и аутпейнтинг

🎤 <b>Озвучить текст</b>
Преобразование текста в речь (TTS):
• Выбор из нескольких голосов
• Поддержка русского и английского
• Высокое качество озвучки

🎙 <b>Транскрибировать</b>
Преобразование аудио/видео в текст (STT):
• Поддержка различных форматов
• Автоматическое определение языка
• Точная транскрибация

💧 <b>Водяной знак</b>
• Добавление: текстовый водяной знак
• Удаление: AI-удаление водяных знаков с изображений

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




@bot.message_handler(func=lambda m: m.text in ["🎨 Create Image", "🎨 Создать картинку"])
def create_image_button(message):
    """Create image button handler"""
    user_id = message.from_user.id

    state_manager.set_state(user_id, STATES["WAITING_IMAGE_PROMPT"])

    bot.send_message(
        message.chat.id,
        "🎨 <b>Создать картинку с AI</b>\n\n"
        "Опишите изображение, которое хотите создать.\n"
        "Чем подробнее описание, тем лучше результат!\n\n"
        "<b>Примеры промптов:</b>\n"
        "• <i>\"Современное рабочее место с AI темой, минималистичный стиль\"</i>\n"
        "• <i>\"Футуристический город на закате, неоновые огни, киберпанк\"</i>\n"
        "• <i>\"Логотип для IT компании с текстом 'TechAI', профессиональный\"</i>\n\n"
        "💡 <b>Совет:</b> Укажите стиль, цвета, настроение для лучшего результата",
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


@bot.message_handler(func=lambda m: m.text in ["🎤 Text to Speech", "🎤 Озвучить текст"])
def tts_button(message):
    """TTS button handler"""
    user_id = message.from_user.id

    state_manager.set_state(user_id, STATES["WAITING_TTS_TEXT"])

    bot.send_message(
        message.chat.id,
        "🎤 <b>Озвучить текст</b>\n\n"
        "Отправьте текст, который хотите озвучить:\n\n"
        "Примеры:\n"
        "• <i>\"Добро пожаловать в наш канал!\"</i>\n"
        "• <i>\"Сегодня мы расскажем о новых технологиях\"</i>\n\n"
        "Поддерживаются русский и английский языки.",
        reply_markup=cancel_keyboard()
    )


@bot.message_handler(func=lambda m: m.text in ["🎙 Transcribe", "🎙 Транскрибировать"])
def stt_button(message):
    """STT button handler"""
    user_id = message.from_user.id

    state_manager.set_state(user_id, STATES["WAITING_STT_FILE"])

    bot.send_message(
        message.chat.id,
        "🎙 <b>Транскрибировать аудио/видео</b>\n\n"
        "Отправьте аудио или видео файл для транскрибации.\n\n"
        "Поддерживаемые форматы:\n"
        "• Аудио: MP3, WAV, OGG, M4A\n"
        "• Видео: MP4, MOV, AVI\n\n"
        "Максимальный размер: 50 МБ",
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
        "Это может занять до 5 минут.\n"
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

    # Prepare full style data with deep analysis and examples
    style_data = {
        'style_summary': channel['style_summary'],
        'deep_analysis': channel.get('deep_analysis', ''),
        'example_posts': channel.get('example_posts', [])
    }

    processing_msg = bot.send_message(
        message.chat.id,
        "⏳ Генерирую посты с глубоким AI-анализом...\n\n"
        "Создаю 3 варианта, НЕОТЛИЧИМЫХ от оригинального стиля.",
        reply_markup=main_menu_keyboard()
    )

    # Start async task with full data
    task = generate_posts_task.delay(style_data, topic)
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


@bot.message_handler(content_types=['photo'], func=lambda m: state_manager.get_state(m.from_user.id) == STATES["WAITING_IMAGE_FOR_WM_REMOVE"])
def handle_image_for_watermark_remove(message):
    """Handle image for watermark removal"""
    user_id = message.from_user.id

    state_manager.clear_state(user_id)

    photo = message.photo[-1]
    file_info = bot.get_file(photo.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    img_b64 = base64.b64encode(downloaded_file).decode('utf-8')

    processing_msg = bot.send_message(
        message.chat.id,
        "⏳ Удаляю водяной знак с помощью AI...\n\n"
        "Это может занять 1-2 минуты.",
        reply_markup=main_menu_keyboard()
    )

    task = remove_watermark_task.delay(img_b64)
    state_manager.set_task_id(user_id, task.id)

    check_task_result(user_id, task.id, processing_msg.message_id, "remove_watermark")


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


@bot.message_handler(func=lambda m: state_manager.get_state(m.from_user.id) == STATES["WAITING_TTS_TEXT"])
def handle_tts_text(message):
    """Handle TTS text input"""
    user_id = message.from_user.id
    text = message.text.strip()

    if len(text) > 5000:
        bot.send_message(
            message.chat.id,
            "❌ Текст слишком длинный. Максимум 5000 символов.\n\n"
            f"Ваш текст: {len(text)} символов."
        )
        return

    state_manager.set_data(user_id, "tts_text", text)

    bot.send_message(
        message.chat.id,
        "🎤 Выберите голос для озвучки:",
        reply_markup=tts_voice_keyboard()
    )


@bot.message_handler(content_types=['audio', 'voice', 'video', 'video_note'],
                    func=lambda m: state_manager.get_state(m.from_user.id) == STATES["WAITING_STT_FILE"])
def handle_stt_file(message):
    """Handle STT file upload"""
    user_id = message.from_user.id

    state_manager.clear_state(user_id)

    # Get file
    if message.audio:
        file_id = message.audio.file_id
        file_size = message.audio.file_size
    elif message.voice:
        file_id = message.voice.file_id
        file_size = message.voice.file_size
    elif message.video:
        file_id = message.video.file_id
        file_size = message.video.file_size
    elif message.video_note:
        file_id = message.video_note.file_id
        file_size = message.video_note.file_size
    else:
        bot.send_message(message.chat.id, "❌ Неподдерживаемый формат файла")
        return

    # Check file size (50 MB limit)
    if file_size and file_size > 50 * 1024 * 1024:
        bot.send_message(
            message.chat.id,
            f"❌ Файл слишком большой: {file_size / 1024 / 1024:.1f} МБ\n\n"
            "Максимальный размер: 50 МБ"
        )
        return

    # Download file
    file_info = bot.get_file(file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    # Convert to base64
    file_b64 = base64.b64encode(downloaded_file).decode('utf-8')

    processing_msg = bot.send_message(
        message.chat.id,
        "⏳ Транскрибирую аудио/видео...\n\n"
        "Это может занять несколько минут в зависимости от длительности.",
        reply_markup=main_menu_keyboard()
    )

    # Import task
    from tasks.tasks import transcribe_audio_task

    task = transcribe_audio_task.delay(file_b64)
    state_manager.set_task_id(user_id, task.id)

    check_task_result(user_id, task.id, processing_msg.message_id, "transcribe")


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

    # Ask if user has an idea
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton("💡 У меня есть идея для поста", callback_data=f"have_idea_{channel_id}"),
        types.InlineKeyboardButton("🔥 Сгенерировать идеи из новостей", callback_data=f"need_ideas_{channel_id}")
    )

    bot.send_message(
        call.message.chat.id,
        f"✍️ <b>Создать пост</b>\n\n"
        f"📺 Канал: <b>{channel_title}</b>\n\n"
        f"У вас есть идея для поста, или мне предложить актуальные темы?",
        reply_markup=keyboard
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith('have_idea_'))
def have_idea_callback(call):
    """User has an idea for the post"""
    user_id = call.from_user.id
    channel_id = int(call.data.split('_')[-1])

    bot.answer_callback_query(call.id)

    # Get channel info
    channel = db.get_channel_by_id(channel_id)
    channel_title = channel['channel_title'] or channel['channel_url']

    state_manager.set_state(user_id, STATES["WAITING_TOPIC"])

    bot.send_message(
        call.message.chat.id,
        f"✍️ <b>Создать пост</b>\n\n"
        f"📺 Канал: <b>{channel_title}</b>\n\n"
        f"💡 Отлично! На какую тему написать?\n\n"
        f"Пример: <i>\"Новые AI тренды в 2025\"</i>",
        reply_markup=cancel_keyboard()
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith('need_ideas_'))
def need_ideas_callback(call):
    """User needs ideas from news"""
    user_id = call.from_user.id
    channel_id = int(call.data.split('_')[-1])

    bot.answer_callback_query(call.id)

    # Get channel info
    channel = db.get_channel_by_id(channel_id)
    if not channel or channel['user_id'] != user_id:
        bot.send_message(call.message.chat.id, "❌ Канал не найден")
        return

    channel_title = channel['channel_title'] or channel['channel_url']
    style_data = {
        'style_summary': channel['style_summary'],
        'deep_analysis': channel.get('deep_analysis', ''),
        'example_posts': channel.get('example_posts', [])
    }

    processing_msg = bot.send_message(
        call.message.chat.id,
        f"🔥 <b>Генерирую идеи для постов</b>\n\n"
        f"📺 Канал: <b>{channel_title}</b>\n\n"
        f"⏳ Анализирую актуальные новости и темы канала...\n"
        f"Это займет до 5 минут.",
        reply_markup=main_menu_keyboard()
    )

    # Import task here to avoid circular import
    from tasks.tasks import generate_post_ideas_task

    task = generate_post_ideas_task.delay(style_data)
    state_manager.set_task_id(user_id, task.id)

    check_task_result(user_id, task.id, processing_msg.message_id, "generate_ideas")




@bot.callback_query_handler(func=lambda c: c.data.startswith('img_'))
def image_provider_callback(call):
    """Image provider selection with detailed info"""
    user_id = call.from_user.id
    bot.answer_callback_query(call.id)

    # Map callback data to provider names
    provider_map = {
        "img_dalle": "dalle",
        "img_sdxl": "sdxl",
        "img_flux_schnell": "flux_schnell",
        "img_ideogram": "ideogram"
    }

    provider = provider_map.get(call.data)
    if not provider:
        bot.send_message(call.message.chat.id, "❌ Неверная модель")
        return

    prompt = state_manager.get_data(user_id, "image_prompt")
    if not prompt:
        bot.send_message(call.message.chat.id, "❌ Промпт не найден. Пожалуйста, попробуйте снова.")
        return

    # Model descriptions
    model_info = {
        "dalle": {
            "name": "DALL-E 3",
            "description": "Премиум модель от OpenAI",
            "features": "• Отличное понимание сложных промптов\n• Высокое качество деталей\n• Лучше для художественных изображений",
            "time": "1-2 минуты"
        },
        "sdxl": {
            "name": "Stable Diffusion XL",
            "description": "Классическая модель, проверенная временем",
            "features": "• Фотореалистичные портреты\n• Отличный баланс цены/качества\n• Быстрая генерация",
            "time": "30-60 секунд"
        },
        "flux_schnell": {
            "name": "Flux Schnell",
            "description": "Новейшая модель 2025 года",
            "features": "• Очень быстрая генерация\n• Отличное качество\n• Гибкость стилей",
            "time": "15-30 секунд"
        },
        "ideogram": {
            "name": "Ideogram v3 Turbo",
            "description": "Лучший для текста и логотипов",
            "features": "• Идеален для текста на изображении\n• Профессиональные логотипы\n• Высокая детализация",
            "time": "30-45 секунд"
        }
    }

    info = model_info.get(provider, model_info["sdxl"])

    processing_msg = bot.send_message(
        call.message.chat.id,
        f"🎨 <b>Генерирую с {info['name']}</b>\n\n"
        f"📝 {info['description']}\n\n"
        f"<b>Особенности:</b>\n{info['features']}\n\n"
        f"⏱ Время: {info['time']}\n\n"
        f"🔄 Генерация началась...",
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
        state_manager.set_state(user_id, STATES["WAITING_IMAGE_FOR_WM_REMOVE"])
        bot.send_message(
            call.message.chat.id,
            "💧 <b>Удалить водяной знак</b>\n\n"
            "Отправьте мне изображение с водяным знаком:\n\n"
            "⚡ <b>Используется AI-инпейнтинг для удаления водяных знаков</b>",
            reply_markup=cancel_keyboard()
        )


@bot.callback_query_handler(func=lambda c: c.data.startswith('tts_'))
def tts_voice_callback(call):
    """TTS voice selection callback"""
    user_id = call.from_user.id
    bot.answer_callback_query(call.id)

    # Voice mapping
    voice_map = {
        "tts_male1": "male1",
        "tts_male2": "male2",
        "tts_female1": "female1",
        "tts_female2": "female2",
        "tts_neutral": "neutral"
    }

    voice = voice_map.get(call.data, "neutral")
    text = state_manager.get_data(user_id, "tts_text")

    if not text:
        bot.send_message(call.message.chat.id, "❌ Текст не найден. Пожалуйста, начните сначала.")
        return

    voice_names = {
        "male1": "Мужской голос 1",
        "male2": "Мужской голос 2",
        "female1": "Женский голос 1",
        "female2": "Женский голос 2",
        "neutral": "Нейтральный голос"
    }

    processing_msg = bot.send_message(
        call.message.chat.id,
        f"🎤 Озвучиваю текст ({voice_names.get(voice)})...\n\n"
        "Это может занять около минуты.",
        reply_markup=main_menu_keyboard()
    )

    # Import task
    from tasks.tasks import text_to_speech_task

    task = text_to_speech_task.delay(text, voice)
    state_manager.set_task_id(user_id, task.id)

    check_task_result(user_id, task.id, processing_msg.message_id, "tts")


@bot.callback_query_handler(func=lambda c: c.data.startswith('select_idea_'))
def select_idea_callback(call):
    """Select idea and generate post"""
    user_id = call.from_user.id
    idea_index = int(call.data.split('_')[-1])

    bot.answer_callback_query(call.id, "✅ Идея выбрана!")

    ideas = state_manager.get_data(user_id, "generated_ideas")
    channel_id = state_manager.get_data(user_id, "selected_channel_id")

    if not ideas or idea_index >= len(ideas):
        bot.send_message(call.message.chat.id, "❌ Идея не найдена")
        return

    selected_idea = ideas[idea_index]

    # Get channel data
    channel = db.get_channel_by_id(channel_id)
    if not channel:
        bot.send_message(call.message.chat.id, "❌ Канал не найден")
        return

    style_data = {
        'style_summary': channel['style_summary'],
        'deep_analysis': channel.get('deep_analysis', ''),
        'example_posts': channel.get('example_posts', [])
    }

    # Generate post with selected idea
    topic = f"{selected_idea['title']}: {selected_idea['description']}"

    processing_msg = bot.send_message(
        call.message.chat.id,
        f"⏳ Генерирую посты с глубоким AI-анализом...\n\n"
        f"💡 <b>Тема:</b> {selected_idea['title']}\n\n"
        f"Создаю 3 варианта, НЕОТЛИЧИМЫХ от оригинального стиля.",
        reply_markup=main_menu_keyboard()
    )

    from tasks.tasks import generate_posts_task

    task = generate_posts_task.delay(style_data, topic)
    state_manager.set_task_id(user_id, task.id)

    check_task_result(user_id, task.id, processing_msg.message_id, "generate_posts")


@bot.callback_query_handler(func=lambda c: c.data.startswith('select_post_'))
def select_post_callback(call):
    """Select post variant"""
    user_id = call.from_user.id
    post_index = int(call.data.split('_')[-1])

    bot.answer_callback_query(call.id, "✅ Пост выбран!")

    posts = state_manager.get_data(user_id, "generated_posts")
    channel_id = state_manager.get_data(user_id, "selected_channel_id")

    if posts and post_index < len(posts):
        selected = posts[post_index]

        # Save to DB with channel_id
        db.save_post(user_id, selected, channel_id=channel_id)

        bot.send_message(
            call.message.chat.id,
            selected
        )


# ===== TASK RESULT CHECKER =====

def check_task_result(user_id: int, task_id: str, msg_id: int, task_type: str):
    """Check Celery task result and handle response"""
    import html

    def check_and_update():
        task_result = celery_app.AsyncResult(task_id)

        max_attempts = 300 
        attempt = 0

        while attempt < max_attempts:
            if task_result.ready():
                result = task_result.get()

                if result.get("error"):
                    # Escape HTML to prevent parsing errors
                    error_text = html.escape(str(result['error']))
                    bot.send_message(
                        user_id,
                        f"❌ Ошибка:\n<code>{error_text[:1000]}</code>",
                        parse_mode="HTML"
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

                elif task_type == "generate_ideas":
                    handle_ideas_result(user_id, result)

                elif task_type == "tts":
                    handle_tts_result(user_id, result)

                elif task_type == "transcribe":
                    handle_transcribe_result(user_id, result)

                elif task_type == "remove_watermark":
                    handle_watermark_removed_result(user_id, result)

                return

            time.sleep(1)
            attempt += 1

        bot.send_message(user_id, "❌ Превышено время ожидания. Пожалуйста, попробуйте снова.")

    # Run in thread to not block bot
    import threading
    threading.Thread(target=check_and_update).start()


def handle_analyze_result(user_id: int, result: dict):
    """Handle channel analysis result with DEEP AI analysis"""
    import html

    style = result.get("style")
    deep_analysis = result.get("deep_analysis", "")
    example_posts = result.get("example_posts", [])
    channel_title = result.get("channel_title", "Неизвестный канал")

    if not style:
        bot.send_message(user_id, "❌ Анализ не удался")
        return

    # Get channel URL from state
    channel_url = state_manager.get_data(user_id, "analyzing_channel_url") or "unknown"

    # Save to DB with ALL analysis data
    db.save_channel_style(
        user_id,
        channel_url,
        channel_title,
        style,
        deep_analysis,
        example_posts
    )

    # Clean up temp data
    state_manager.delete_data(user_id, "analyzing_channel_url")

    # Format response with AI analysis preview (escape HTML!)
    analysis_preview = deep_analysis[:400] if len(deep_analysis) > 400 else deep_analysis
    # Escape HTML entities to avoid parsing errors
    analysis_preview = html.escape(analysis_preview)

    response = f"""✅ <b>РЕВОЛЮЦИОННЫЙ AI-АНАЛИЗ ЗАВЕРШЕН!</b>

📺 <b>Канал:</b> {html.escape(channel_title)}

📊 <b>Проанализировано постов:</b> {style.get('analyzed_posts_count', 0)}

📈 <b>Основные метрики:</b>
• Среднее слов: {style.get('average_word_count', 0)}
• Среднее предложений: {style.get('average_sentence_count', 0)}
• Среднее эмодзи: {style.get('average_emoji_count', 0)}

💎 <b>Сохранено примеров постов:</b> {len(example_posts)}

🧠 <b>Превью глубокого анализа:</b>
<code>{analysis_preview[:300]}...</code>

✨ Теперь я буду генерировать посты, НЕОТЛИЧИМЫЕ от оригинала!
Используйте ✍️ Создать пост для генерации."""

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


def handle_ideas_result(user_id: int, result: dict):
    """Handle generated ideas result"""
    import html

    ideas = result.get("ideas", [])

    if not ideas:
        bot.send_message(user_id, "❌ Не удалось сгенерировать идеи. Попробуйте еще раз.")
        return

    # Save ideas
    state_manager.set_data(user_id, "generated_ideas", ideas)

    # Show ideas as inline buttons
    keyboard = types.InlineKeyboardMarkup(row_width=1)

    response = "🔥 <b>Актуальные идеи для постов:</b>\n\n"

    for i, idea in enumerate(ideas):
        # Determine emoji based on news type
        news_type = idea.get('news_type', 'world')
        emoji = "🇷🇺" if news_type == "russian" else "🌍"

        title = html.escape(idea.get('title', 'Идея'))
        description = html.escape(idea.get('description', '')[:100])
        source = html.escape(idea.get('news_source', 'Новости'))

        response += f"{emoji} <b>{i+1}. {title}</b>\n"
        response += f"   <i>{description}...</i>\n"
        response += f"   📰 {source}\n\n"

        keyboard.add(
            types.InlineKeyboardButton(
                f"✍️ Написать пост #{i+1}",
                callback_data=f"select_idea_{i}"
            )
        )

    bot.send_message(user_id, response, reply_markup=keyboard)


def handle_tts_result(user_id: int, result: dict):
    """Handle TTS result"""
    audio_b64 = result.get("audio")

    if not audio_b64:
        bot.send_message(user_id, "❌ Не удалось озвучить текст")
        return

    # Decode audio
    audio_bytes = base64.b64decode(audio_b64)

    # Send audio
    bot.send_voice(user_id, voice=audio_bytes, caption="✅ Ваш озвученный текст!")


def handle_transcribe_result(user_id: int, result: dict):
    """Handle transcription result"""
    text = result.get("text")

    if not text:
        bot.send_message(user_id, "❌ Не удалось транскрибировать аудио")
        return

    # Send transcription
    response = f"📝 <b>Транскрибация:</b>\n\n{text}"

    # Split if too long
    if len(response) > 4000:
        # Send in parts
        parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
        for part in parts:
            bot.send_message(user_id, part)
    else:
        bot.send_message(user_id, response)


def handle_watermark_removed_result(user_id: int, result: dict):
    """Handle watermark removal result"""
    img_b64 = result.get("image")

    if not img_b64:
        bot.send_message(user_id, "❌ Не удалось удалить водяной знак")
        return

    img_bytes = base64.b64decode(img_b64)

    bot.send_photo(user_id, photo=img_bytes, caption="✅ Водяной знак удален!")


# ===== MAIN =====

if __name__ == '__main__':
    print("🤖 SMM Bot started!")
    print("Press Ctrl+C to stop")

    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=30)
    except KeyboardInterrupt:
        print("\n👋 Bot stopped")

