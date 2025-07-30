import telebot
from telebot import types
import threading

from utils.config import BOT_TOKEN
import utils.database as db
import utils.keyboards as kb
from utils.parser import run_parser
import utils.llm_service

# Поскольку вы изучаете DevOps, важно понимать этот момент:
# `telebot` — блокирующая библиотека. Это значит, что пока выполняется одна долгая операция
# (например, парсинг), бот не может отвечать другим.
# Чтобы обойти это, мы запускаем долгие задачи в отдельных потоках (threads).
# В "боевом" продакшене для этого используют системы очередей, как вы и писали в плане (Celery + Redis),
# но для старта потоки — отличное и простое решение.
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="MARKDOWN")

# Хранилище временных данных. В проде лучше использовать Redis.
user_states = {}

# --- Поток для анализа канала ---
def analysis_thread_target(chat_id, channel_url):
    """Функция, которая будет выполняться в отдельном потоке."""
    try:
        # 1. Отправляем сообщение о начале анализа
        bot.send_message(chat_id, "⏳ Начинаю анализ канала... Это может занять до минуты.")
        
        # 2. Парсим посты
        posts_text = run_parser(channel_url)
        if posts_text.startswith("Ошибка"):
            bot.send_message(chat_id, posts_text)
            return

        # 3. Анализируем стиль через ИИ
        bot.send_message(chat_id, "🧐 Почти готово! Отправил посты на анализ искусственному интеллекту...")
        style_summary = llm_service.analyze_style(posts_text)
        if not style_summary:
            bot.send_message(chat_id, "❌ Произошла ошибка при анализе стиля. Попробуйте позже.")
            return

        # 4. Сохраняем результат в БД
        db.save_channel_style(chat_id, channel_url, style_summary)
        
        # 5. Спрашиваем пользователя о теме поста
        msg = bot.send_message(chat_id, 
            "✅ Стиль канала успешно проанализирован!\n\n"
            "📝 Теперь напишите тему для нового поста. Например: 'Обзор новой функции в Python'.\n\n"
            "Или, если идей нет, просто напишите 'нет идей', и я предложу вам варианты."
        )
        
        # 6. Устанавливаем следующий шаг для этого пользователя
        bot.register_next_step_handler(msg, handle_topic_input)

    except Exception as e:
        print(f"Ошибка в потоке анализа: {e}")
        bot.send_message(chat_id, "❌ Произошла непредвиденная ошибка во время анализа. Пожалуйста, попробуйте снова.")

# --- Обработчики команд и сообщений ---

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Обработчик команды /start."""
    db.add_user_if_not_exists(message.chat.id, message.from_user.username)
    welcome_text = (
        "👋 Привет!\n\n"
        "Я ваш личный контент-менеджер на базе ИИ.\n"
        "Я могу проанализировать любой публичный Telegram-канал, "
        "понять его стиль и генерировать посты в такой же манере.\n\n"
        "➡️ **Просто отправьте мне ссылку на канал в формате `@channel_name`**"
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(func=lambda message: message.text and message.text.startswith('@'))
def handle_channel_link(message):
    """Обрабатывает получение ссылки на канал."""
    channel_url = message.text.strip()
    
    # Запускаем анализ в отдельном потоке, чтобы не блокировать бота
    thread = threading.Thread(target=analysis_thread_target, args=(message.chat.id, channel_url))
    thread.start()

def handle_topic_input(message):
    """Обрабатывает ввод темы от пользователя."""
    chat_id = message.chat.id
    topic = message.text.strip()

    style_summary = db.get_channel_style_by_user(chat_id)
    if not style_summary:
        bot.send_message(chat_id, "Не нашел ваш анализ стиля. Пожалуйста, отправьте ссылку на канал снова.")
        return

    bot.send_message(chat_id, f"🤖 Принял! Генерирую варианты по теме: '{topic}'. Это займет немного времени...")
    
    if topic.lower() in ['нет идей', 'нет', 'не знаю']:
        # Генерируем идеи
        ideas_text = llm_service.generate_post_ideas(style_summary)
        bot.send_message(chat_id, f"Вот несколько идей, основанных на стиле канала:\n\n{ideas_text}\n\nВыберите одну и отправьте ее мне.")
        bot.register_next_step_handler(message, handle_topic_input) # Ждем выбора идеи
        return

    # Генерируем варианты постов
    variations = llm_service.create_post_variations(style_summary, topic)
    if not variations:
        bot.send_message(chat_id, "❌ Не удалось сгенерировать посты. Возможно, тема слишком сложная. Попробуйте другую.")
        return
        
    # Сохраняем варианты для этого пользователя
    user_states[chat_id] = {'variants': variations}

    response_text = "Вот несколько вариантов поста. Выберите лучший:"
    
    # Создаем клавиатуру с вариантами
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    buttons = [types.InlineKeyboardButton(text=f"Вариант {i+1}", callback_data=f"select_variant_{i}") for i in range(len(variations))]
    keyboard.add(*buttons)

    # Отправляем превью каждого варианта
    for i, variant in enumerate(variations):
        bot.send_message(chat_id, f"*--- Вариант {i+1} ---*\n{variant}")

    bot.send_message(chat_id, "👇 Нажмите на кнопку, чтобы выбрать пост для публикации.", reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data.startswith('select_variant_'))
def handle_variant_selection(call):
    """Обрабатывает выбор варианта поста."""
    chat_id = call.message.chat.id
    variant_index = int(call.data.split('_')[-1])

    if chat_id not in user_states or 'variants' not in user_states[chat_id]:
        bot.answer_callback_query(call.id, "Ошибка: варианты не найдены. Попробуйте сначала.")
        return
    
    selected_post = user_states[chat_id]['variants'][variant_index]
    
    # Удаляем временные данные
    del user_states[chat_id]

    bot.edit_message_text("Отлично! Вот ваш готовый пост. Просто скопируйте его.", chat_id, call.message.message_id)
    
    # Отправляем финальный пост
    bot.send_message(chat_id, selected_post)
    
    # Предлагаем подписку
    subscription_offer = (
        "Понравилось? ✨\n\n"
        "С платной подпиской я могу делать это автоматически!\n"
        "- **Ежедневный постинг**: Я буду сам предлагать посты каждый день.\n"
        "- **Контент-план**: Планируйте посты на недели вперед!\n"
    )
    bot.send_message(chat_id, subscription_offer, reply_markup=kb.offer_subscription_keyboard())
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'buy_subscription')
def handle_buy_subscription(call):
    """Обрабатывает нажатие на кнопку покупки."""
    # Здесь должна быть интеграция с платежной системой (Stripe, ЮKassa и т.д.)
    # 1. Генерация уникальной ссылки на оплату.
    # 2. Отправка ее пользователю.
    # 3. После успешной оплаты платежная система отправляет webhook на ваш сервер,
    #    который обновляет статус подписки в базе данных.
    
    # Заглушка для демонстрации
    bot.answer_callback_query(call.id, "Переход к оплате...")
    bot.send_message(call.message.chat.id, "В реальной версии здесь была бы ссылка на страницу оплаты. "
                                          "Сейчас я просто активирую вам подписку для теста.")
    # db.activate_subscription(call.message.chat.id, 'daily') # Пример функции, которую нужно создать

if __name__ == '__main__':
    print("Бот запущен...")
    # Запуск бота в режиме бесконечного опроса
    bot.infinity_polling()