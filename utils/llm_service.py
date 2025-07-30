import google.generativeai as genai
from utils.config import GEMINI_API_KEY
import json
import re

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
    
    # 4. НОВОЕ: Обработка тега <br>
    # Заменяем <br> на обычный перенос строки
    cleaned_text = cleaned_text.replace('<br>', '\n')
    cleaned_text = cleaned_text.replace('<br/>', '\n') # На случай, если генерируется самозакрывающийся тег

    # 5. Убедимся, что нет лишних двойных переносов строк в начале/конце
    cleaned_text = cleaned_text.strip()
    # И что нет более двух последовательных переносов строк (если это не нужно для форматирования <pre>)
    cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
    
    return cleaned_text

def analyze_style(posts_text):
    """
    Анализирует стиль постов и возвращает JSON, используя Gemini API.
    Для получения структурированного JSON-ответа используется response_schema.
    """
    prompt = f"""
    Проанализируй эти посты из Telegram-канала.
    Твоя задача — детально описать стиль ведения канала.
    Опиши следующие характеристики:
    1.  <b>tone</b>: Тон общения (например, 'юмористический', 'экспертный', 'формальный', 'дружелюбный').
    2.  <b>themes</b>: Основные темы или рубрики канала.
    3.  <b>length</b>: Средняя длина поста (например, 'короткие, до 50 слов', 'средние, 100-200 слов', 'длинные лонгриды').
    4.  <b>emoji</b>: Как часто и какие эмодзи используются (например, 'часто, в конце каждого абзаца', 'редко, только по теме', 'не используются').
    5.  <b>formatting</b>: Используется ли форматирование текста (жирный, курсив, моноширинный), как часто и для чего.

    Верни результат строго в формате JSON.
    Вот тексты постов для анализа:
    ---
    {posts_text}
    ---
    """
    try:
        # Для структурированного ответа используем generation_config с response_schema
        response = model.generate_content(
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "tone": {"type": "STRING"},
                        "themes": {"type": "ARRAY", "items": {"type": "STRING"}},
                        "length": {"type": "STRING"},
                        "emoji": {"type": "STRING"},
                        "formatting": {"type": "STRING"}
                    },
                    "required": ["tone", "themes", "length", "emoji", "formatting"]
                }
            )
        )
        # Ответ приходит в виде строки JSON, нужно ее распарсить
        style_json = json.loads(response.text)
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
    Основываясь на этом анализе стиля Telegram-канала:
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
    Создает 3 варианта поста на заданную тему в нужном стиле, используя Gemini API.
    Варианты будут в формате HTML.
    """
    prompt = f"""
    Ты — автор Telegram-канала.
    Твоя задача — написать 3 разных варианта поста на заданную тему, строго придерживаясь следующего стиля.

    # Гайд по стилю:
    {json.dumps(style_summary, indent=2, ensure_ascii=False)}

    # Тема поста:
    {topic}

    Напиши три полноценных, готовых к публикации варианта поста.
    Используй HTML для форматирования.
    Раздели варианты между собой строкой "---ВАРИАНТ---".
    Используй только следующие HTML-теги, поддерживаемые Telegram: <b>, <i>, <u>, <s>, <code>, <pre>, <a href="...">.
    Для разделения абзацев используй двойной перенос строки (например, "Первый абзац.\n\nВторой абзац.").
    Ни в коем случае не используй теги <p>, <ul>, <ol>, <li>, <br> или любую Markdown-разметку (например, звездочки * для жирного).
    Если нужны списки, используй маркеры (например, "• " или "- ") и переносы строк.

    В конце каждого поста, где уместно, добавь призыв к действию, используя *примерную* ссылку.
    Например: <b><a href="https://example.com/your_link">Подключиться</a></b>.
    Четко укажи, что это *примерная* ссылка и пользователь должен будет ее заменить.
    """
    try:
        response = model.generate_content(
            contents=[{"role": "user", "parts": [{"text": prompt}]}]
        )
        # Разделяем полученный текст на 3 варианта
        variations = response.text.split("---ВАРИАНТ---")
        # Очищаем каждый вариант от неподдерживаемых тегов и конвертируем Markdown
        return [_clean_html_for_telegram(v.strip()) for v in variations if v.strip()]
    except Exception as e:
        print(f"Ошибка при создании постов Gemini: {e}")
        return []

