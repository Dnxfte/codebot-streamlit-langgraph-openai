# CodeBot — AI Code Reviewer

Повноцінний Python-проєкт для практичного завдання №3 з теми 12.

**Варіант:** 11. Код-ревʼюер «CodeBot»

## Короткий опис

CodeBot — це веб-застосунок на Streamlit для пояснення, ревʼю, оптимізації та збереження фрагментів коду. Користувач вставляє код, вибирає мову програмування, ставить питання в чаті або запускає швидку дію, а AI-асистент аналізує код українською мовою.

У проєкті використано OpenAI LLM через LangChain, а також LangGraph-агента з інструментами для роботи зі снипетами, статичного аналізу, пошуку у Wikipedia та простих обчислень.

## Предметна область

Предметна область — автоматизоване code review і навчальна підтримка програміста. Застосунок допомагає швидко зрозуміти призначення коду, знайти потенційні помилки, побачити варіанти оптимізації, додати коментарі та зберегти корисні приклади у локальну колекцію під час сесії.

## Структура файлів

```text
codebot-streamlit-langgraph-openai/
├── .streamlit/
│   └── secrets.toml.example
├── app.py
├── agent.py
├── requirements.txt
├── README.md
└── .gitignore
```

## Налаштування API-ключа

Не комітьте реальний OpenAI API key у репозиторій.

Створіть файл:

```text
.streamlit/secrets.toml
```

Додайте в нього:

```toml
OPENAI_API_KEY = "your_openai_api_key_here"
```

Альтернатива — створити `.env` у корені проєкту:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

## Запуск

```bash
python -m venv .venv
```

Linux або macOS:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\activate
```

Встановлення залежностей:

```bash
pip install -r requirements.txt
```

Запуск застосунку:

```bash
streamlit run app.py
```

## UI-компоненти

У застосунку використано такі компоненти Streamlit:

- `st.chat_message` — відображення історії діалогу.
- `st.chat_input` — введення нового повідомлення в чаті.
- `st.text_area` — редактор для вставлення коду.
- `st.code` — підсвітка коду.
- `st.selectbox` — вибір мови програмування та моделі OpenAI.
- `st.expander` — перегляд збережених снипетів.
- `st.tabs` — вкладки «Чат», «Код», «Снипети», «Статистика».
- `st.metric` — статистика сесії.
- `st.download_button` — експорт історії та snippets у JSON.

## Інструменти LangGraph-агента

- `save_snippet(language, code, note)` — готує збереження фрагмента коду у колекцію.
- `list_snippets()` — повертає короткий список збережених snippets.
- `show_snippet(snippet_id)` — показує повний код конкретного snippet.
- `calculator(expression)` — безпечно обчислює прості математичні вирази через `numexpr`.
- `wikipedia_search(query)` — шукає коротку довідку у Wikipedia.
- `analyze_code_static(language, code)` — виконує простий статичний аналіз без LLM.

## Приклади діалогів

1. Поясни цей Python-код:

```python
numbers = [1, 2, 3, 4]
print([x * x for x in numbers])
```

2. Знайди баги в коді з `eval()`:

```python
value = eval(input("Enter value: "))
print(value)
```

3. Оптимізуй цикл:

```python
result = []
for item in items:
    if item > 10:
        result.append(item * 2)
```

4. Збережи снипет як "приклад сортування":

```python
items = [3, 1, 2]
items.sort()
```

5. Покажи мої збережені коди.

6. Знайди інформацію про list comprehension у Wikipedia.

## Місце для скріншотів інтерфейсу

Додайте сюди скріншоти після запуску застосунку:

```text
docs/screenshots/chat.png
docs/screenshots/code-review.png
docs/screenshots/snippets.png
docs/screenshots/stats.png
```

## Примітки

- Застосунок читає ключ з `st.secrets["OPENAI_API_KEY"]` або `os.getenv("OPENAI_API_KEY")`.
- У звичайному режимі використовується streaming через `ChatOpenAI.stream()`.
- У режимі LangGraph відповідь агента показується псевдострімінгом через `st.write_stream()`.
- Колекція snippets зберігається у `st.session_state` і може бути експортована в JSON.
