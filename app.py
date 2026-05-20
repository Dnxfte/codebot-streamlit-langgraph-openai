from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import streamlit as st
from dotenv import load_dotenv

from agent import invoke_codebot_agent, stream_openai_chat

APP_DIR = Path(__file__).resolve().parent
load_dotenv(APP_DIR / ".env")

LANGUAGES = ["python", "javascript", "typescript", "java", "c++", "c#", "rust", "go", "php"]
MODELS = ["gpt-4o-mini", "gpt-4.1-mini", "gpt-4.1"]
CHAT_MODE = "Звичайний чат"
AGENT_MODE = "LangGraph агент з інструментами"

CODE_LANGUAGE_MAP = {
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "java": "java",
    "c++": "cpp",
    "c#": "csharp",
    "rust": "rust",
    "go": "go",
    "php": "php",
}

DEFAULT_SYSTEM_PROMPT = """
Ти CodeBot, українськомовний AI Code Reviewer.
Пояснюй код структуровано, шукай ризики, пропонуй оптимізації та показуй
кращий варіант коду тільки тоді, коли це справді корисно.
""".strip()

ACTION_PROMPTS = {
    "explain": "Поясни цей код мовою {language}. Опиши призначення, логіку та важливі деталі.",
    "optimize": "Оптимізуй цей код мовою {language}. Поясни, що саме покращено і чому.",
    "bugs": "Знайди баги, edge cases і ризики безпеки в цьому коді мовою {language}.",
    "comments": "Додай корисні коментарі до цього коду мовою {language}. Поверни оновлений код.",
}


def init_session_state() -> None:
    defaults = {
        "messages": [],
        "snippets": [],
        "thread_id": str(uuid.uuid4()),
        "code_analysis": "",
        "tool_call_log": [],
        "system_prompt": DEFAULT_SYSTEM_PROMPT,
        "editor_code": "",
        "selected_language": "python",
        "usage_stats": {
            "messages": 0,
            "snippets": 0,
            "agent_calls": 0,
        },
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def apply_technical_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --codebot-bg: #0e1117;
            --codebot-panel: #151a23;
            --codebot-border: #2d3748;
            --codebot-accent: #35c2ff;
            --codebot-green: #7ee787;
        }
        .stApp {
            background:
                radial-gradient(circle at 12% 12%, rgba(53, 194, 255, 0.08), transparent 28%),
                linear-gradient(180deg, #0e1117 0%, #111827 45%, #0b0f16 100%);
            color: #e5e7eb;
        }
        [data-testid="stSidebar"] {
            background: #0b1220;
            border-right: 1px solid var(--codebot-border);
        }
        .codebot-header {
            border: 1px solid var(--codebot-border);
            background: rgba(21, 26, 35, 0.82);
            padding: 1.15rem 1.25rem;
            border-radius: 8px;
            margin-bottom: 1rem;
        }
        .codebot-header h1 {
            font-size: 2rem;
            line-height: 1.2;
            margin: 0 0 .3rem 0;
            letter-spacing: 0;
        }
        .codebot-header p {
            color: #b6c2d1;
            margin: 0;
        }
        .stButton > button,
        .stDownloadButton > button,
        div[data-testid="stFormSubmitButton"] button {
            border-radius: 8px;
            border: 1px solid #334155;
            background: #172033;
            color: #f8fafc;
        }
        .stButton > button:hover,
        .stDownloadButton > button:hover,
        div[data-testid="stFormSubmitButton"] button:hover {
            border-color: var(--codebot-accent);
            color: #ffffff;
        }
        div[data-testid="stMetric"] {
            background: rgba(21, 26, 35, 0.72);
            border: 1px solid var(--codebot-border);
            border-radius: 8px;
            padding: .8rem;
        }
        code {
            color: var(--codebot-green);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_openai_key() -> str:
    secret_key = ""
    try:
        secret_key = str(st.secrets["OPENAI_API_KEY"]).strip()
    except Exception:
        secret_key = ""

    api_key = secret_key or os.getenv("OPENAI_API_KEY", "").strip()
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key
    return api_key


def json_dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def snippet_title(snippet: dict) -> str:
    note = snippet.get("note") or "Без назви"
    language = snippet.get("language") or "text"
    return f"#{snippet.get('id')} · {note} · {language}"


def code_language(language: str) -> str:
    return CODE_LANGUAGE_MAP.get(language, language or "text")


def refresh_usage_stats() -> None:
    st.session_state.usage_stats["messages"] = len(st.session_state.messages)
    st.session_state.usage_stats["snippets"] = len(st.session_state.snippets)


def next_snippet_id() -> int:
    ids = [int(item.get("id", 0)) for item in st.session_state.snippets if str(item.get("id", "")).isdigit()]
    return max(ids, default=0) + 1


def save_snippet_from_editor(language: str, code: str, note: str) -> None:
    snippet = {
        "id": next_snippet_id(),
        "language": language,
        "code": code,
        "note": note.strip() or "Без назви",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    st.session_state.snippets.append(snippet)
    refresh_usage_stats()


def use_snippet_in_editor(snippet_id: int) -> None:
    for snippet in st.session_state.snippets:
        if int(snippet.get("id", -1)) == int(snippet_id):
            st.session_state.editor_code = snippet.get("code", "")
            language = snippet.get("language", "python")
            if language in LANGUAGES:
                st.session_state.selected_language = language
            return


def delete_snippet(snippet_id: int) -> None:
    st.session_state.snippets = [
        snippet for snippet in st.session_state.snippets if int(snippet.get("id", -1)) != int(snippet_id)
    ]
    refresh_usage_stats()


def pseudo_stream(text: str) -> Iterable[str]:
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.012)


def langgraph_stream(
    user_text: str,
    thread_id: str,
    snippets: list[dict],
    model_name: str,
    temperature: float,
    max_tokens: int,
) -> Iterable[str]:
    result = invoke_codebot_agent(
        user_text=user_text,
        thread_id=thread_id,
        snippets=snippets,
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    st.session_state.snippets = result["snippets"]
    st.session_state.tool_call_log = result["tool_call_log"]
    refresh_usage_stats()
    yield from pseudo_stream(result["answer"])


def run_streamed_response(
    prompt: str,
    mode: str,
    model_name: str,
    temperature: float,
    max_tokens: int,
    api_key: str,
    messages_for_chat: list[dict] | None = None,
) -> str:
    if not api_key:
        st.error(
            "OPENAI_API_KEY не знайдено. Створіть .streamlit/secrets.toml або .env "
            "і додайте OPENAI_API_KEY."
        )
        return ""

    st.session_state.usage_stats["agent_calls"] += 1
    if mode == CHAT_MODE:
        chat_messages = messages_for_chat or [{"role": "user", "content": prompt}]
        return st.write_stream(
            stream_openai_chat(
                messages=chat_messages,
                model_name=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                system_prompt=st.session_state.system_prompt,
            )
        )

    return st.write_stream(
        langgraph_stream(
            user_text=prompt,
            thread_id=st.session_state.thread_id,
            snippets=st.session_state.snippets,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    )


def build_code_prompt(action: str, language: str, code: str) -> str:
    instruction = ACTION_PROMPTS[action].format(language=language)
    return f"{instruction}\n\n```{code_language(language)}\n{code}\n```"


def render_sidebar() -> tuple[str, str, float, int, str]:
    with st.sidebar:
        st.subheader("Параметри")
        language = st.selectbox("Мова програмування", LANGUAGES, key="selected_language")
        model_name = st.selectbox("Модель OpenAI", MODELS, index=0)
        temperature = st.slider("temperature", 0.0, 1.0, 0.2, 0.05)
        max_tokens = st.slider("max_tokens", 300, 2000, 1000, 100)
        mode = st.radio("Режим", [CHAT_MODE, AGENT_MODE])

        if st.button("Очистити історію", use_container_width=True):
            st.session_state.messages = []
            st.session_state.code_analysis = ""
            st.session_state.tool_call_log = []
            st.session_state.thread_id = str(uuid.uuid4())
            refresh_usage_stats()
            st.rerun()

        st.info(
            "CodeBot пояснює код, шукає помилки, пропонує оптимізацію, "
            "працює з LangGraph-інструментами та зберігає корисні снипети."
        )

        with st.expander("Системний промпт", expanded=False):
            st.text_area("Промпт", key="system_prompt", height=180)

        st.subheader("Мої снипети")
        if not st.session_state.snippets:
            st.caption("Колекція поки порожня.")
        for snippet in st.session_state.snippets:
            with st.expander(snippet_title(snippet)):
                st.caption(snippet.get("created_at", ""))
                st.code(snippet.get("code", ""), language=code_language(snippet.get("language", "text")))

    return language, model_name, float(temperature), int(max_tokens), mode


def render_chat_tab(mode: str, model_name: str, temperature: float, max_tokens: int, api_key: str) -> None:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Напишіть питання про код або попросіть агента виконати дію")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        refresh_usage_stats()
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            try:
                with st.spinner("CodeBot генерує відповідь..."):
                    answer = run_streamed_response(
                        prompt=prompt,
                        mode=mode,
                        model_name=model_name,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        api_key=api_key,
                        messages_for_chat=st.session_state.messages,
                    )
            except Exception as exc:
                st.error(f"Помилка під час відповіді OpenAI або агента: {exc}")
                answer = ""

        if answer:
            st.session_state.messages.append({"role": "assistant", "content": answer})
            refresh_usage_stats()

    st.download_button(
        "Експортувати історію чату JSON",
        data=json_dump(st.session_state.messages),
        file_name="codebot_messages.json",
        mime="application/json",
        use_container_width=True,
    )

    if st.session_state.tool_call_log:
        with st.expander("Журнал інструментів агента"):
            for item in st.session_state.tool_call_log[-12:]:
                if "\n" in item:
                    title, body = item.split("\n", 1)
                    st.markdown(f"**{title}**")
                    st.code(body, language="text")
                else:
                    st.caption(item)


def render_code_tab(
    language: str,
    mode: str,
    model_name: str,
    temperature: float,
    max_tokens: int,
    api_key: str,
) -> None:
    left, right = st.columns([1, 1], gap="large")

    with left:
        code_input = st.text_area("Ваш код", height=300, key="editor_code")
        if code_input.strip():
            st.code(code_input, language=code_language(language))

        st.caption("Швидкі дії")
        action_cols = st.columns(4)
        action = None
        if action_cols[0].button("💡 Пояснити", use_container_width=True):
            action = "explain"
        if action_cols[1].button("🔧 Оптимізувати", use_container_width=True):
            action = "optimize"
        if action_cols[2].button("🐛 Знайти баги", use_container_width=True):
            action = "bugs"
        if action_cols[3].button("📝 Додати коментарі", use_container_width=True):
            action = "comments"

        with st.form("save_snippet_form", clear_on_submit=True):
            note = st.text_input("Назва або нотатка для snippet")
            submitted = st.form_submit_button("💾 Зберегти снипет", use_container_width=True)
            if submitted:
                if code_input.strip():
                    save_snippet_from_editor(language, code_input, note)
                    st.success("Снипет збережено.")
                else:
                    st.warning("Додайте код перед збереженням.")

    with right:
        st.subheader("Результат аналізу")
        if action:
            if not code_input.strip():
                st.warning("Вставте код, щоб виконати швидку дію.")
            else:
                prompt = build_code_prompt(action, language, code_input)
                try:
                    with st.spinner("CodeBot аналізує код..."):
                        answer = run_streamed_response(
                            prompt=prompt,
                            mode=mode,
                            model_name=model_name,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            api_key=api_key,
                        )
                    st.session_state.code_analysis = answer
                except Exception as exc:
                    st.error(f"Помилка під час аналізу коду: {exc}")

        elif st.session_state.code_analysis:
            st.markdown(st.session_state.code_analysis)
        else:
            st.caption("Тут зʼявиться пояснення, ревʼю або оптимізована версія коду.")


def render_snippets_tab() -> None:
    if not st.session_state.snippets:
        st.info("Снипетів ще немає. Збережіть код у вкладці «Код» або попросіть агента зробити це.")
    else:
        for snippet in st.session_state.snippets:
            with st.expander(snippet_title(snippet), expanded=False):
                st.caption(f"Створено: {snippet.get('created_at', '')}")
                st.code(snippet.get("code", ""), language=code_language(snippet.get("language", "text")))
                col_use, col_delete = st.columns(2)
                col_use.button(
                    "Використати в редакторі",
                    key=f"use_snippet_{snippet.get('id')}",
                    on_click=use_snippet_in_editor,
                    args=(int(snippet.get("id")),),
                    use_container_width=True,
                )
                col_delete.button(
                    "Видалити",
                    key=f"delete_snippet_{snippet.get('id')}",
                    on_click=delete_snippet,
                    args=(int(snippet.get("id")),),
                    use_container_width=True,
                )

    st.download_button(
        "Експортувати snippets JSON",
        data=json_dump(st.session_state.snippets),
        file_name="codebot_snippets.json",
        mime="application/json",
        use_container_width=True,
    )


def render_stats_tab() -> None:
    refresh_usage_stats()
    chat_chars = sum(len(message.get("content", "")) for message in st.session_state.messages)
    stats = st.session_state.usage_stats

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Повідомлення", stats["messages"])
    col2.metric("Snippets", stats["snippets"])
    col3.metric("Виклики агента", stats["agent_calls"])
    col4.metric("Символи в чаті", chat_chars)

    activity = min(100, stats["messages"] * 8 + stats["snippets"] * 12 + stats["agent_calls"] * 10)
    st.progress(activity, text=f"Активність сесії: {activity}%")

    language_counts: dict[str, int] = {}
    for snippet in st.session_state.snippets:
        language = snippet.get("language", "text")
        language_counts[language] = language_counts.get(language, 0) + 1

    if language_counts:
        chart_data = [
            {"Мова": language, "Кількість": count}
            for language, count in sorted(language_counts.items())
        ]
        st.bar_chart(chart_data, x="Мова", y="Кількість")
        st.dataframe(chart_data, hide_index=True, use_container_width=True)
    else:
        st.caption("Статистика за мовами зʼявиться після збереження snippets.")

    st.download_button(
        "Експортувати повну сесію JSON",
        data=json_dump(
            {
                "messages": st.session_state.messages,
                "snippets": st.session_state.snippets,
                "usage_stats": st.session_state.usage_stats,
                "thread_id": st.session_state.thread_id,
            }
        ),
        file_name="codebot_session.json",
        mime="application/json",
        use_container_width=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="CodeBot — AI Code Reviewer",
        page_icon="💻",
        layout="wide",
    )
    init_session_state()
    apply_technical_theme()

    api_key = get_openai_key()
    if not api_key:
        st.error(
            "OPENAI_API_KEY відсутній. Створіть файл .streamlit/secrets.toml "
            "з рядком OPENAI_API_KEY = \"your_openai_api_key_here\" або додайте ключ у .env."
        )

    language, model_name, temperature, max_tokens, mode = render_sidebar()

    st.markdown(
        """
        <div class="codebot-header">
            <h1>💻 CodeBot — AI Code Reviewer</h1>
            <p>Асистент для пояснення, ревʼю, оптимізації та збереження коду</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_chat, tab_code, tab_snippets, tab_stats = st.tabs(
        ["💬 Чат", "📝 Код", "📁 Снипети", "📊 Статистика"]
    )

    with tab_chat:
        render_chat_tab(mode, model_name, temperature, max_tokens, api_key)

    with tab_code:
        render_code_tab(language, mode, model_name, temperature, max_tokens, api_key)

    with tab_snippets:
        render_snippets_tab()

    with tab_stats:
        render_stats_tab()


if __name__ == "__main__":
    main()
