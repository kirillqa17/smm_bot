import openai
from utils.config import OPENAI_API_KEY
import json

client = openai.OpenAI(api_key=OPENAI_API_KEY)

def analyze_style(posts_text):
    """Анализирует стиль постов и возвращает JSON."""
    prompt = f"""
    Проанализируй эти посты из Telegram-канала.
    Твоя задача — детально описать стиль ведения канала.
    Опиши следующие характеристики:
    1.  **tone**: Тон общения (например, 'юмористический', 'экспертный', 'формальный', 'дружелюбный').
    2.  **themes**: Основные темы или рубрики канала.
    3.  **length**: Средняя длина поста (например, 'короткие, до 50 слов', 'средние, 100-200 слов', 'длинные лонгриды').
    4.  **emoji**: Как часто и какие эмодзи используются (например, 'часто, в конце каждого абзаца', 'редко, только по теме', 'не используются').
    5.  **formatting**: Используется ли форматирование текста (жирный, курсив, моноширинный), как часто и для чего.

    Верни результат строго в формате JSON. Пример:
    {{
      "tone": "экспертный и немного ироничный",
      "themes": ["новости IT", "обзоры гаджетов", "советы по программированию"],
      "length": "средние, 150-300 слов",
      "emoji": "умеренно, для выделения ключевых моментов",
      "formatting": "жирный шрифт для заголовков, моноширинный для кода"
    }}

    Вот тексты постов для анализа:
    ---
    {posts_text}
    ---
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o", # или gpt-3.5-turbo
            messages=[
                {"role": "system", "content": "Ты — ИИ-аналитик, специализирующийся на стилях Telegram-каналов. Твоя задача - вернуть ответ в формате JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        style_json = json.loads(response.choices[0].message.content)
        return style_json
    except Exception as e:
        print(f"Ошибка при анализе стиля OpenAI: {e}")
        return None

def generate_post_ideas(style_summary):
    """Генерирует идеи для постов на основе анализа стиля."""
    prompt = f"""
    Основываясь на этом анализе стиля Telegram-канала:
    {json.dumps(style_summary, indent=2, ensure_ascii=False)}

    Предложи 3 актуальные и интересные идеи для следующих постов. 
    Учитывай последние мировые события и тренды, если это релевантно тематике канала.
    Идеи должны быть краткими, по одному предложению каждая.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Ты — креативный ИИ-генератор идей для постов в Telegram."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Ошибка при генерации идей OpenAI: {e}")
        return "Не удалось сгенерировать идеи."

def create_post_variations(style_summary, topic):
    """Создает 3 варианта поста на заданную тему в нужном стиле."""
    prompt = f"""
    Ты — автор Telegram-канала.
    Твоя задача — написать 3 разных варианта поста на заданную тему, строго придерживаясь следующего стиля.

    # Гайд по стилю:
    {json.dumps(style_summary, indent=2, ensure_ascii=False)}

    # Тема поста:
    {topic}

    Напиши три полноценных, готовых к публикации варианта поста. Используй Markdown для форматирования, если это соответствует стилю.
    Раздели варианты между собой строкой "---ВАРИАНТ---".
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Ты — талантливый автор постов для Telegram-каналов."},
                {"role": "user", "content": prompt}
            ]
        )
        # Разделяем полученный текст на 3 варианта
        variations = response.choices[0].message.content.split("---ВАРИАНТ---")
        return [v.strip() for v in variations if v.strip()]
    except Exception as e:
        print(f"Ошибка при создании постов OpenAI: {e}")
        return []