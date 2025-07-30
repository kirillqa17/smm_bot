import telebot
from telebot import types
import threading

from utils.config import BOT_TOKEN
import utils.database as db
import utils.keyboards as kb
from utils.parser import run_parser
import utils.llm_service as llm_service

# Поскольку вы изучаете DevOps, важно понимать этот момент:
# `telebot` — блокирующая библиотека. Это значит, что пока выполняется одна долгая операция
# (например, парсинг), бот не может отвечать другим.
# Чтобы обойти это, мы запускаем долгие задачи в отдельных потоках (threads).
# В "боевом" продакшене для этого используют системы очередей, как вы и писали в плане (Celery + Redis),
# но для старта потоки — отличное и простое решение.
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML") # parse_mode="HTML"

# Хранилище временных данных. В проде лучше использовать Redis.
user_states = {} # Это хранилище теперь будет использоваться для сохранения вариантов постов

# --- Поток для анализа канала ---
def analysis_thread_target(chat_id, channel_url):
    """Функция, которая будет выполняться в отдельном потоке."""
    try:
        bot.send_message(chat_id, "⏳ Начинаю анализ канала... Это может занять до минуты.")
        
        # 1. Парсим посты, теперь получаем список словарей
        parsed_posts = run_parser(channel_url)
        # Проверяем, вернул ли парсер ошибку (строку)
        if isinstance(parsed_posts, str) and parsed_posts.startswith("Ошибка"):
            bot.send_message(chat_id, parsed_posts)
            return

        bot.send_message(chat_id, "🧐 Почти готово! Анализирую стиль и считаю метрики...")
        
        # 2. Анализируем стиль, передавая структурированные данные
        style_summary = llm_service.analyze_style(parsed_posts)
        if not style_summary:
            bot.send_message(chat_id, "❌ Произошла ошибка при анализе стиля. Попробуйте позже.")
            return

        # ... (остальная часть функции остается без изменений) ...
        # 3. Сохраняем результат в БД
        db.save_channel_style(chat_id, channel_url, style_summary)
        
        # 4. Спрашиваем пользователя о теме поста
        msg = bot.send_message(chat_id, 
            "✅ Стиль канала успешно проанализирован!\n\n"
            "📝 Теперь напишите тему для нового поста. Например: 'Обзор новой функции в Python'.\n\n"
            "Или, если идей нет, просто напишите 'нет идей', и я предложу вам варианты."
        )
        
        # 5. Устанавливаем следующий шаг
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
        "➡️ <b>Просто отправьте мне ссылку на канал в формате @channel_name</b>"
    )
    # Используем register_next_step_handler для обработки следующего сообщения
    msg = bot.reply_to(message, welcome_text)
    bot.register_next_step_handler(msg, handle_channel_link)

# handle_channel_link теперь вызывается через register_next_step_handler
def handle_channel_link(message):
    """Обрабатывает получение ссылки на канал."""
    chat_id = message.chat.id
    channel_url = message.text.strip()

    # Простая валидация ссылки на канал
    if not channel_url.startswith('@'):
        msg = bot.send_message(chat_id, "Пожалуйста, отправьте ссылку в формате @channel_name (например, @durov).")
        bot.register_next_step_handler(msg, handle_channel_link) # Повторно регистрируем обработчик
        return

    # Запускаем анализ в отдельном потоке, чтобы не блокировать бота
    analysis_thread = threading.Thread(target=analysis_thread_target, args=(chat_id, channel_url))
    analysis_thread.start()
    # Состояние теперь управляется через register_next_step_handler

def handle_topic_input(message):
    """Обрабатывает ввод темы от пользователя."""
    chat_id = message.chat.id
    topic = message.text.strip()

    style_summary = db.get_channel_style_by_user(chat_id)
    if not style_summary:
        msg = bot.send_message(chat_id, "Не нашел ваш анализ стиля. Пожалуйста, отправьте ссылку на канал снова.")
        bot.register_next_step_handler(msg, handle_channel_link) # Возвращаем к началу
        return

    if topic.lower() == 'нет идей' or topic.lower() == 'нет':
        bot.send_message(chat_id, "🤖 Принял! Генерирую варианты идеи постов. Это займет немного времени...")
        
        ideas = llm_service.generate_post_ideas(style_summary)
        # Отправляем ideas напрямую, ожидая, что LLM генерирует корректный HTML
        
        msg = bot.send_message(chat_id, f"Вот несколько идей, основанных на стиле канала:\n\n{ideas}\n\nВыберите одну и отправьте ее мне.")
        bot.register_next_step_handler(msg, handle_topic_input) # Снова регистрируем обработчик
        return
    
    bot.send_message(chat_id, f"🤖 Принял! Генерирую варианты по теме: '{topic}'. Это займет немного времени...")


    # Генерируем варианты постов
    # ИЗМЕНЕНИЕ: УДАЛЕН VPN_BOT_LINK из вызова функции
    variations = llm_service.create_post_variations(style_summary, topic)
    if not variations:
        msg = bot.send_message(chat_id, "❌ Не удалось сгенерировать посты. Возможно, тема слишком сложная. Попробуйте другую.")
        bot.register_next_step_handler(msg, handle_topic_input) # Если не удалось, просим новую тему
        return
        
    # Сохраняем варианты для этого пользователя
    user_states[chat_id] = {'variants': variations}

    
    # Создаем клавиатуру с вариантами
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    # Используем индекс 0, 1, 2 для callback_data, чтобы соответствовать массиву
    buttons = [types.InlineKeyboardButton(text=f"Вариант {i+1}", callback_data=f"select_variant_{i}") for i in range(len(variations))]
    keyboard.add(*buttons)

    # Отправляем превью каждого варианта
    for i, variant in enumerate(variations):
        bot.send_message(chat_id, f"<b>--- Вариант {i+1} ---</b>\n{variant}") # Отправляем variant напрямую
        
    bot.send_message(chat_id, "Нажмите на кнопку, чтобы выбрать пост для публикации.", reply_markup=keyboard)


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

    # Вместо edit_message_text, лучше отправить новое сообщение, чтобы не было проблем с Markdown
    bot.send_message(chat_id, "Отлично! Вот ваш готовый пост. Просто скопируйте его.")
    
    # Отправляем финальный пост
    bot.send_message(chat_id, selected_post) # Отправляем selected_post напрямую
    
    # НОВОЕ: Предупреждение о замене ссылок
    warning_message = (
        "⚠️ <b>ВНИМАНИЕ:</b> В сгенерированном посте могут быть примеры ссылок (например, на example.com).\n"
        "<b>ОБЯЗАТЕЛЬНО ЗАМЕНИТЕ ИХ НА ВАШИ АКТУАЛЬНЫЕ ССЫЛКИ</b> (на бота, сайт и т.д.) перед публикацией!"
    )
    bot.send_message(chat_id, warning_message, parse_mode="HTML")

    # Предлагаем подписку
    subscription_offer = (
        "Понравилось? ✨\n\n"
        "С платной подпиской я могу делать это автоматически!\n"
        "- <b>Ежедневный постинг</b>: Я буду сам предлагать посты каждый день.\n"
        "- <b>Контент-план</b>: Планируйте посты на недели вперед!\n"
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

