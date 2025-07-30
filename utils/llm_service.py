import google.generativeai as genai
from utils.config import GEMINI_API_KEY
import json
import re
import collections # Для подсчета частоты слов/эмодзи, если понадобится более сложный анализ

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')

def _clean_html_for_telegram(html_text):
    """
    Очищает HTML-текст, удаляя неподдерживаемые Telegram теги
    и заменяя их на корректные переносы строк и форматирование.
    Также пытается конвертировать Markdown-подобные выделения в HTML.
    """
    cleaned_text = html_text

    # 1. Заменяем <p> на двойной перенос строки для абзацев
    cleaned_text = re.sub(r'<p>(.*?)</p>', r'\1\n\n', cleaned_text, flags=re.DOTALL)
    cleaned_text = cleaned_text.replace('<p>', '').replace('</p>', '') # Удаляем любые оставшиеся открывающие/закрывающие теги <p>

    # 2. Конвертируем Markdown-подобные выделения в HTML-теги
    # Жирный текст: *текст* -> <b>текст</b>
    cleaned_text = re.sub(r'\*(.*?)\*', r'<b>\1</b>', cleaned_text)
    # Курсив: _текст_ -> <i>текст</i>
    cleaned_text = re.sub(r'_(.*?)_', r'<i>\1</i>', cleaned_text)
    # Зачеркнутый: ~текст~ -> <s>текст</s>
    cleaned_text = re.sub(r'~(.*?)~', r'<s>\1</s>', cleaned_text)
    # Моноширинный: `текст` -> <code>текст</code>
    cleaned_text = re.sub(r'`(.*?)`', r'<code>\1</code>', cleaned_text)

    # 3. Обработка списков (<ul>, <ol>, <li>)
    # Заменяем <li> на маркер и перенос строки
    cleaned_text = re.sub(r'<li>(.*?)</li>', r'• \1\n', cleaned_text, flags=re.DOTALL)
    # Удаляем теги <ul>, <ol> (они сами по себе не форматируют текст, только содержат <li>)
    cleaned_text = cleaned_text.replace('<ul>', '').replace('</ul>', '')
    cleaned_text = cleaned_text.replace('<ol>', '').replace('</ol>', '')
    
    # 4. Обработка тега <br>
    # Заменяем <br> на обычный перенос строки
    cleaned_text = cleaned_text.replace('<br>', '\n')
    cleaned_text = cleaned_text.replace('<br/>', '\n') # На случай, если генерируется самозакрывающийся тег

    # 5. Убедимся, что нет лишних двойных переносов строк в начале/конце
    cleaned_text = cleaned_text.strip()
    # И что нет более двух последовательных переносов строк (если это не нужно для форматирования <pre>)
    cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
    
    return cleaned_text

def _analyze_text_metrics(posts_raw_text):
    """
    Анализирует текстовые метрики (количество слов, предложений)
    из сырого текста постов.
    """
    individual_posts = posts_raw_text.split("---РАЗДЕЛИТЕЛЬ ПОСТОВ---")
    
    total_words = 0
    total_sentences = 0
    num_posts = 0

    for post in individual_posts:
        post = post.strip()
        if not post:
            continue
        num_posts += 1
        
        # Простой подсчет слов
        words = post.split()
        total_words += len(words)
        
        # Простой подсчет предложений (можно улучшить с NLTK, но для начала сойдет)
        sentences = re.split(r'[.!?]+\s*', post)
        sentences = [s.strip() for s in sentences if s.strip()]
        total_sentences += len(sentences)

    avg_word_count = round(total_words / num_posts) if num_posts > 0 else 0
    avg_sentence_count = round(total_sentences / num_posts) if num_posts > 0 else 0
    
    return {
        "average_word_count_per_post": avg_word_count,
        "average_sentence_count_per_post": avg_sentence_count
    }

def _calculate_metrics(parsed_posts):
    """
    Вычисляет количественные метрики на основе спарсенных постов.
    `parsed_posts` - это список словарей вида [{'text': '...', 'emoji_count': N}, ...].
    """
    if not parsed_posts or not isinstance(parsed_posts, list):
        return {
            "average_word_count": 0,
            "average_sentence_count": 0,
            "average_emoji_count": 0,
            "post_with_emoji_ratio": 0.0
        }

    total_words = 0
    total_sentences = 0
    total_emojis = 0
    posts_with_emojis = 0
    num_posts = len(parsed_posts)

    for post_data in parsed_posts:
        text = post_data.get("text", "")
        if not text:
            num_posts -= 1 # Игнорируем посты без текста при подсчете среднего
            continue
            
        total_words += len(text.split())
        sentences = re.split(r'[.!?]+\s*', text)
        total_sentences += len([s for s in sentences if s.strip()])
        
        emoji_count = post_data.get("emoji_count", 0)
        total_emojis += emoji_count
        if emoji_count > 0:
            posts_with_emojis += 1

    if num_posts == 0:
        return { "average_word_count": 0, "average_sentence_count": 0, "average_emoji_count": 0, "post_with_emoji_ratio": 0.0 }


    return {
        "average_word_count": round(total_words / num_posts),
        "average_sentence_count": round(total_sentences / num_posts),
        "average_emoji_count": round(total_emojis / num_posts),
        "post_with_emoji_ratio": round(posts_with_emojis / num_posts, 2) # Доля постов с эмодзи
    }

def analyze_style(parsed_posts):
    """
    Анализирует стиль постов. Сначала вычисляет метрики, затем просит LLM описать остальное.
    """
    # Шаг 1: Вычисляем точные метрики
    metrics = _calculate_metrics(parsed_posts)
    
    # Шаг 2: Объединяем тексты постов для качественного анализа LLM
    posts_text_for_llm = "\n\n---РАЗДЕЛИТЕЛЬ ПОСТОВ---\n\n".join([p['text'] for p in parsed_posts])

    # Шаг 3: Изменяем промпт. Убираем из него вопросы про то, что мы уже посчитали.
    prompt = f"""
    Проанализируй эти посты из Telegram-канала.
    Твоя задача — детально описать КАЧЕСТВЕННЫЕ характеристики стиля.
    Количественные метрики уже посчитаны. Сосредоточься на следующем:
    1.  <b>tone</b>: Тон общения (например, 'юмористический', 'экспертный', 'формальный', 'дружелюбный').
    2.  <b>themes</b>: Основные темы или рубрики канала (список из 3-5 ключевых тем).
    3.  <b>post_structure</b>: Типичная структура поста (например, 'заголовок, 2-3 абзаца, список, призыв к действию').
    4.  <b>formatting_usage</b>: Как используется форматирование (жирный, курсив) и для чего (например, 'жирный для заголовков, курсив для цитат').
    5.  <b>call_to_action_frequency</b>: Как часто встречаются призывы к действию ('в каждом посте', 'редко').
    6.  <b>call_to_action_style</b>: Стиль призывов к действию ('прямой и императивный', 'вопросительный').
    7.  <b>target_audience</b>: Целевая аудитория канала ('новички в IT', 'опытные инвесторы').
    8.  <b>topic_depth</b>: Глубина раскрытия темы ('поверхностно', 'глубокий анализ').
    9.  <b>professionalism_level</b>: Уровень профессионализма ('деловой', 'неформальный').
    
    Верни результат строго в формате JSON. Не придумывай ничего про количество эмодзи или длину постов.
    Вот тексты постов для анализа:
    ---
    {posts_text_for_llm}
    ---
    """
    try:
        response = model.generate_content(
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                # Схема теперь короче, т.к. часть полей мы вычисляем сами
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "tone": {"type": "STRING"},
                        "themes": {"type": "ARRAY", "items": {"type": "STRING"}},
                        "post_structure": {"type": "STRING"},
                        "formatting_usage": {"type": "STRING"},
                        "call_to_action_frequency": {"type": "STRING"},
                        "call_to_action_style": {"type": "STRING"},
                        "target_audience": {"type": "STRING"},
                        "topic_depth": {"type": "STRING"},
                        "professionalism_level": {"type": "STRING"}
                    },
                    "required": [
                        "tone", "themes", "post_structure", "formatting_usage",
                        "call_to_action_frequency", "call_to_action_style",
                        "target_audience", "topic_depth", "professionalism_level"
                    ]
                }
            )
        )
        style_json = json.loads(response.text)
        
        # Шаг 4: Объединяем вычисленные метрики и качественный анализ от LLM
        style_json.update(metrics)
        
        return style_json
    except Exception as e:
        print(f"Ошибка при анализе стиля Gemini: {e}")
        return None

def generate_post_ideas(style_summary):
    """
    Генерирует идеи для постов на основе анализа стиля, используя Gemini API.
    Идеи будут в формате HTML (минимально).
    """
    prompt = f"""
    Основываясь на этом детальном анализе стиля Telegram-канала:
    {json.dumps(style_summary, indent=2, ensure_ascii=False)}

    Предложи 3 *короткие, емкие идеи* для следующих постов.
    Каждая идея должна быть *строго одним предложением*.
    Учитывай последние мировые события и тренды, если это релевантно тематике канала.
    Представь идеи в виде *нумерованного списка*.
    Используй только HTML-теги <b> для названий идей.
    Для списка используй маркеры (например, "1. ", "2. ") и переносы строк, *не используй теги <ul>, <ol>, <li>, <p>, <br>*.
    Пример формата ответа:
    1. <b>Идея 1</b>: Описание идеи в одном предложении.
    2. <b>Идея 2</b>: Описание идеи в одном предложении.
    3. <b>Идея 3</b>: Описание идеи в одном предложении.
    """
    try:
        response = model.generate_content(
            contents=[{"role": "user", "parts": [{"text": prompt}]}]
        )
        # Очищаем HTML от неподдерживаемых тегов и конвертируем Markdown
        return _clean_html_for_telegram(response.text)
    except Exception as e:
        print(f"Ошибка при генерации идей Gemini: {e}")
        return "Не удалось сгенерировать идеи."

def create_post_variations(style_summary, topic):
    """
    Создает 3 варианта поста на заданную тему в нужном стиле, используя точные метрики.
    """
    # Извлекаем точные метрики
    avg_word_count = style_summary.get("average_word_count", 100)
    avg_sentence_count = style_summary.get("average_sentence_count", 5)
    avg_emoji_count = style_summary.get("average_emoji_count", 0) # Самое важное изменение

    prompt = f"""
    Ты — автор Telegram-канала.
    Твоя задача — написать 3 разных варианта поста на заданную тему, строго придерживаясь следующего стиля и метрик.

    # Гайд по стилю (качественные характеристики):
    {json.dumps({k: v for k, v in style_summary.items() if k not in ['average_word_count', 'average_sentence_count', 'average_emoji_count', 'post_with_emoji_ratio']}, indent=2, ensure_ascii=False)}

    # КЛЮЧЕВЫЕ КОЛИЧЕСТВЕННЫЕ ОГРАНИЧЕНИЯ:
    - Среднее количество слов в посте: **строго около {avg_word_count} слов**.
    - Среднее количество предложений в посте: **строго около {avg_sentence_count} предложений**.
    - Среднее количество эмодзи в посте: **строго около {avg_emoji_count} штук**. Если это значение 0 или 1, это означает, что эмодзи либо нет совсем, либо они используются крайне редко. НЕ ИСПОЛЬЗУЙ ЭМОДЗИ, если среднее значение близко к нулю.

    # Тема поста:
    {topic}

    Напиши три полноценных, готовых к публикации варианта поста.
    Используй HTML для форматирования.
    Раздели варианты между собой строкой "---ВАРИАНТ---".
    Используй только следующие HTML-теги, поддерживаемые Telegram: <b>, <i>, <s>, <code>, <a href="...">.
    Для разделения абзацев используй двойной перенос строки. Не используй теги <p>, <ul>, <li>.
    """
    try:
        response = model.generate_content(
            contents=[{"role": "user", "parts": [{"text": prompt}]}]
        )
        variations = response.text.split("---ВАРИАНТ---")
        return [_clean_html_for_telegram(v.strip()) for v in variations if v.strip()]
    except Exception as e:
        print(f"Ошибка при создании постов Gemini: {e}")
        return []
