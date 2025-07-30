from telebot import types

# Словарь для хранения состояний и данных пользователей
user_data = {}

def generate_post_variants_keyboard(variants):
    """Создает клавиатуру с вариантами постов."""
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    buttons = []
    for i, _ in enumerate(variants):
        # Сохраняем текст варианта для последующего использования
        # В реальном приложении это лучше хранить в кэше (Redis) или базе
        user_data[f'variant_{i+1}'] = variants[i]
        buttons.append(types.InlineKeyboardButton(text=f"Выбрать вариант {i+1}", callback_data=f"select_variant_{i+1}"))
    
    keyboard.add(*buttons)
    return keyboard

def offer_subscription_keyboard():
    """Клавиатура с предложением подписки."""
    keyboard = types.InlineKeyboardMarkup()
    buy_button = types.InlineKeyboardButton("🚀 Купить подписку", callback_data="buy_subscription")
    keyboard.add(buy_button)
    return keyboard