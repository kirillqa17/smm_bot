"""Localization module for multi-language support"""

TRANSLATIONS = {
    'en': {
        # Start command
        'welcome': '👋 <b>Welcome to SMM Bot!</b>\n\nPlease select your language:',
        'language_selected': '✅ Language set to English',

        # Menu
        'main_menu': '📱 <b>Main Menu</b>\n\nChoose an action:',
        'analyze_channel': '📊 Analyze Channel',
        'generate_post': '✍️ Generate Post',
        'news_to_post': '📰 News to Post',
        'create_image': '🎨 Create Image',
        'edit_image': '✏️ Edit Image',
        'watermark': '💧 Watermark',
        'my_stats': '📈 My Stats',
        'cancel': '❌ Cancel',

        # Help
        'help_text': '''📖 <b>SMM Bot Help</b>

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

Need help? Just ask!''',

        # Channel analysis
        'channel_analysis_prompt': '📊 <b>Channel Analysis</b>\n\nSend me the channel username in format: <code>@channel_name</code>\n\nExample: @durov',
        'channel_analyzing': '🔍 Analyzing channel... This may take a minute.',
        'channel_analyzed': '✅ Channel analyzed successfully!',

        # Errors
        'error': '❌ Error: {}',
        'cancelled': '✅ Operation cancelled',
    },

    'ru': {
        # Start command
        'welcome': '👋 <b>Добро пожаловать в SMM Bot!</b>\n\nВыберите язык:',
        'language_selected': '✅ Язык установлен: Русский',

        # Menu
        'main_menu': '📱 <b>Главное меню</b>\n\nВыберите действие:',
        'analyze_channel': '📊 Анализ канала',
        'generate_post': '✍️ Создать пост',
        'news_to_post': '📰 Новости в пост',
        'create_image': '🎨 Создать картинку',
        'edit_image': '✏️ Редактировать фото',
        'watermark': '💧 Водяной знак',
        'my_stats': '📈 Моя статистика',
        'cancel': '❌ Отмена',

        # Help
        'help_text': '''📖 <b>Справка по SMM Bot</b>

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

Нужна помощь? Просто спросите!''',

        # Channel analysis
        'channel_analysis_prompt': '📊 <b>Анализ канала</b>\n\nОтправьте мне username канала в формате: <code>@имя_канала</code>\n\nПример: @durov',
        'channel_analyzing': '🔍 Анализирую канал... Это может занять минуту.',
        'channel_analyzed': '✅ Канал успешно проанализирован!',

        # Errors
        'error': '❌ Ошибка: {}',
        'cancelled': '✅ Операция отменена',
    }
}

def get_text(lang: str, key: str, *args) -> str:
    """Get localized text"""
    text = TRANSLATIONS.get(lang, TRANSLATIONS['en']).get(key, TRANSLATIONS['en'].get(key, key))
    if args:
        return text.format(*args)
    return text
