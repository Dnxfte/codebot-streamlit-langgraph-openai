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

Нижче наведено 6 сценаріїв, які демонструють звичайний чат, LangGraph-агента з інструментами, специфічні функції CodeBot та основні UI-компоненти Streamlit.

### 1. Звичайний режим чату: пояснення Python-коду

**Налаштування UI:** у sidebar вибрано `python`, модель `gpt-4o-mini`, режим `Звичайний чат`. Користувач вводить повідомлення через `st.chat_input`, історія показується через `st.chat_message`.

**Користувач:**

```text
Поясни цей Python-код:

numbers = [1, 2, 3, 4]
print([x * x for x in numbers])
```

**CodeBot:**

```text
Що робить код:
Код створює список чисел і виводить новий список з квадратами кожного числа.

Покрокове пояснення:
1. numbers містить значення [1, 2, 3, 4].
2. List comprehension проходить по кожному x у numbers.
3. Для кожного x обчислюється x * x.
4. print() виводить результат: [1, 4, 9, 16].

Потенційні проблеми:
Для такого простого прикладу критичних проблем немає.

Рекомендації:
Якщо логіка повторюється, її можна винести у функцію.
```

### 2. LangGraph-агент з інструментом статичного аналізу

**Налаштування UI:** у sidebar вибрано режим `LangGraph агент з інструментами`. Агент може викликати `analyze_code_static`, а результат інструменту видно в expander `Журнал інструментів агента`.

**Користувач:**

```text
Знайди баги та ризики безпеки:

password = "admin123"
value = eval(input("Enter expression: "))
try:
    print(value)
except Exception:
    pass
```

**CodeBot:**

```text
Що робить код:
Код зберігає пароль у змінній, приймає введення користувача, виконує його через eval()
і намагається вивести результат.

Потенційні проблеми:
- Hardcoded password у коді.
- eval(input(...)) дозволяє виконати довільний Python-код.
- except Exception приховує реальну причину помилки.

Рекомендації:
- Зберігати секрети в environment variables або secrets.
- Не використовувати eval для введення користувача.
- Обробляти конкретні типи помилок.

Кращий варіант:
Для математичних виразів краще використати безпечний parser або numexpr з обмеженнями.
```

**Інструмент агента:** `analyze_code_static(language="python", code="...")`.

### 3. Збереження, список і перегляд snippets через агента

**Налаштування UI:** режим `LangGraph агент з інструментами`. Агент використовує `save_snippet`, `list_snippets`, `show_snippet`. Збережені елементи відображаються у sidebar та вкладці `📁 Снипети` через `st.expander` і `st.code`.

**Користувач:**

```text
Збережи цей код як "приклад сортування":

items = [3, 1, 2]
items.sort()
print(items)
```

**CodeBot:**

```text
Снипет збережено як "приклад сортування".
Мова: python.

Код сортує список items на місці методом sort() і виводить [1, 2, 3].
```

**Користувач:**

```text
Покажи мої збережені коди.
```

**CodeBot:**

```text
Збережені snippets:
#1 | python | приклад сортування | items = [3, 1, 2] items.sort() print(items)
```

**Користувач:**

```text
Покажи снипет 1 повністю.
```

**CodeBot:**

```python
items = [3, 1, 2]
items.sort()
print(items)
```

### 4. Вкладка "Код": швидкі дії CodeBot

**Налаштування UI:** користувач відкриває вкладку `📝 Код`, вставляє код у `st.text_area`, бачить підсвітку через `st.code` і натискає кнопку `🔧 Оптимізувати`.

**Код у редакторі:**

```python
result = []
for item in items:
    if item > 10:
        result.append(item * 2)
```

**Користувач натискає:** `🔧 Оптимізувати`

**CodeBot у правій колонці:**

```text
Що робить код:
Формує список result з подвоєних значень item, якщо item більше 10.

Рекомендації щодо покращення:
Код можна зробити коротшим через list comprehension.

Кращий варіант:
result = [item * 2 for item in items if item > 10]
```

**Демонстрація UI-компонентів:** `st.tabs`, `st.columns`, `st.text_area`, `st.code`, `st.button`, `st.markdown`.

### 5. Wikipedia та calculator у LangGraph-режимі

**Налаштування UI:** режим `LangGraph агент з інструментами`. Агент може викликати `wikipedia_search` для довідки та `calculator` для безпечних обчислень.

**Користувач:**

```text
Знайди у Wikipedia коротку інформацію про list comprehension і порахуй 2 * (8 + 4).
```

**CodeBot:**

```text
Wikipedia:
List comprehension є компактним способом створення списків на основі iterable-об'єктів.
У Python такий запис часто замінює простий цикл for з append().

Обчислення:
2 * (8 + 4) = 24

Практичний приклад:
squares = [x * x for x in range(5)]
```

**Інструменти агента:** `wikipedia_search(query="list comprehension")`, `calculator(expression="2 * (8 + 4)")`.

### 6. Snippets, статистика та експорт JSON

**Налаштування UI:** користувач відкриває вкладки `📁 Снипети` та `📊 Статистика`. Снипети показуються в `st.expander`, статистика в `st.metric`, а історія та snippets експортуються через `st.download_button`.

**Користувач у вкладці "Снипети":**

```text
Відкриває snippet "приклад сортування", натискає "Використати в редакторі".
```

**Результат UI:**

```text
Код переноситься у вкладку "Код", де його можна повторно проаналізувати або оптимізувати.
```

**Користувач у вкладці "Статистика":**

```text
Переглядає кількість повідомлень, snippets, викликів агента та приблизну кількість символів у чаті.
```

**Результат UI:**

```text
st.metric показує статистику сесії.
st.progress показує активність сесії.
st.bar_chart показує розподіл snippets за мовами програмування.
st.download_button дозволяє експортувати messages або snippets у JSON.
```

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
