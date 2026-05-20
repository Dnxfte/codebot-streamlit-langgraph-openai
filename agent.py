from __future__ import annotations

import json
import math
import os
import re
import uuid
from datetime import datetime
from functools import lru_cache
from typing import Annotated, Any, TypedDict

import numexpr as ne
import wikipedia
from dotenv import load_dotenv
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph, add_messages
from langgraph.prebuilt import InjectedState, ToolNode, tools_condition

load_dotenv()


class AgentState(TypedDict):
    # Єдиний стан LangGraph: історія, snippets і службовий журнал tool-call.
    messages: Annotated[list, add_messages]
    snippets: list[dict]
    next_snippet_id: int
    tool_call_log: list[str]


CODEBOT_SYSTEM_PROMPT = """
Ти CodeBot, технічний Code Reviewer і асистент для роботи з кодом.
Відповідай українською мовою, точно і практично.

Коли аналізуєш код, дотримуйся структури:
- Що робить код
- Покрокове пояснення
- Потенційні проблеми
- Рекомендації щодо покращення
- Кращий варіант коду, якщо доречно

Якщо користувач просить зберегти код, виклич інструмент save_snippet.
Якщо користувач просить показати або перелічити збережені коди, використовуй
list_snippets або show_snippet. Для базових перевірок коду можеш викликати
analyze_code_static перед фінальною відповіддю.
""".strip()

SAVE_SNIPPET_MARKER = "CODEBOT_SAVE_SNIPPET_REQUEST::"


def _get_openai_api_key() -> str:
    # У Streamlit ключ прокидається в os.environ з app.py; локально його читає dotenv.
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY не знайдено. Додайте ключ у .streamlit/secrets.toml або .env."
        )
    return api_key


def create_llm(
    model_name: str = "gpt-4o-mini",
    temperature: float = 0.2,
    max_tokens: int = 1000,
) -> ChatOpenAI:
    # Одна фабрика моделі для звичайного чату і LangGraph-агента.
    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=_get_openai_api_key(),
    )


def _normalize_language(language: str) -> str:
    return (language or "text").strip().lower()


def _new_snippet_id(snippets: list[dict]) -> int:
    ids = [int(snippet.get("id", 0)) for snippet in snippets if str(snippet.get("id", "")).isdigit()]
    return max(ids, default=0) + 1


def _compact_code(code: str, limit: int = 90) -> str:
    one_line = " ".join((code or "").strip().split())
    return one_line[:limit] + ("..." if len(one_line) > limit else "")


@tool
def save_snippet(
    language: str,
    code: str,
    note: str,
    state: Annotated[dict, InjectedState],
) -> str:
    """Підготувати збереження фрагмента коду у колекцію користувача."""
    # ToolNode не має прямого доступу до st.session_state, тому повертаємо JSON-маркер.
    # invoke_codebot_agent потім знаходить цей маркер і синхронізує snippets зі Streamlit.
    snippets = list(state.get("snippets", []) or [])
    snippet_id = int(state.get("next_snippet_id") or _new_snippet_id(snippets))
    snippet = {
        "id": snippet_id,
        "language": _normalize_language(language),
        "code": code.strip(),
        "note": (note or "Без назви").strip(),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    payload = json.dumps(snippet, ensure_ascii=False)
    return (
        f"{SAVE_SNIPPET_MARKER}{payload}\n"
        f"Снипет #{snippet_id} підготовлено до збереження: {snippet['note']}."
    )


@tool
def list_snippets(state: Annotated[dict, InjectedState]) -> str:
    """Показати короткий список збережених снипетів."""
    snippets = list(state.get("snippets", []) or [])
    if not snippets:
        return "Колекція снипетів порожня."

    rows = []
    for snippet in snippets:
        rows.append(
            f"#{snippet.get('id')} | {snippet.get('language', 'text')} | "
            f"{snippet.get('note', 'Без назви')} | {_compact_code(snippet.get('code', ''))}"
        )
    return "\n".join(rows)


@tool
def show_snippet(snippet_id: int, state: Annotated[dict, InjectedState]) -> str:
    """Показати повний код снипета за його id."""
    snippets = list(state.get("snippets", []) or [])
    for snippet in snippets:
        if int(snippet.get("id", -1)) == int(snippet_id):
            language = snippet.get("language", "text")
            note = snippet.get("note", "Без назви")
            code = snippet.get("code", "")
            return f"Снипет #{snippet_id}: {note}\nМова: {language}\n\n```{language}\n{code}\n```"
    return f"Снипет #{snippet_id} не знайдено."


@tool
def calculator(expression: str) -> str:
    """Безпечно обчислити простий математичний вираз."""
    expression = (expression or "").strip()
    if not expression:
        return "Вираз порожній."

    # Не використовуємо eval: пропускаємо тільки прості символи математичного виразу.
    if not re.fullmatch(r"[0-9+\-*/%().,\sEeipPI]+", expression):
        return "Дозволені лише числа, дужки, оператори + - * / %, pi та e."

    safe_expression = expression.replace(",", ".")
    try:
        result = ne.evaluate(
            safe_expression,
            local_dict={"pi": math.pi, "PI": math.pi, "e": math.e, "E": math.e},
        )
        value = result.item() if hasattr(result, "item") else result
        return f"{expression} = {value}"
    except Exception as exc:
        return f"Не вдалося обчислити вираз: {exc}"


@tool
def wikipedia_search(query: str) -> str:
    """Знайти коротку технічну довідку у Wikipedia."""
    query = (query or "").strip()
    if not query:
        return "Порожній пошуковий запит."

    wrapper_error = ""
    for language in ("uk", "en"):
        # Спочатку пробуємо LangChain Community wrapper, щоб агент мав типовий LangChain-tool flow.
        try:
            wrapper = WikipediaAPIWrapper(
                top_k_results=1,
                lang=language,
                doc_content_chars_max=900,
            )
            result = wrapper.run(query)
            if result and "No good Wikipedia Search Result was found" not in result:
                return f"Wikipedia ({language}):\n{result}"
        except Exception as exc:
            wrapper_error = str(exc)

        # Fallback через пакет wikipedia корисний, якщо wrapper не знайшов сторінку.
        try:
            wikipedia.set_lang(language)
            titles = wikipedia.search(query, results=3)
            if not titles:
                continue
            summary = wikipedia.summary(titles[0], sentences=3, auto_suggest=False)
            return f"Wikipedia ({language}) — {titles[0]}:\n{summary}"
        except wikipedia.DisambiguationError as exc:
            options = ", ".join(exc.options[:5])
            return f"Запит неоднозначний. Уточніть один з варіантів: {options}"
        except wikipedia.PageError:
            continue
        except Exception as exc:
            return f"Не вдалося отримати довідку з Wikipedia: {exc}"

    if wrapper_error:
        return f"Нічого не знайдено у Wikipedia. Остання помилка: {wrapper_error}"
    return "Нічого не знайдено у Wikipedia."


def _check_hardcoded_secret(line: str) -> bool:
    pattern = r"(password|passwd|token|secret|api[_-]?key)\s*[:=]\s*['\"][^'\"]{4,}['\"]"
    return re.search(pattern, line, flags=re.IGNORECASE) is not None


@tool
def analyze_code_static(language: str, code: str) -> str:
    """Виконати простий статичний аналіз коду без LLM."""
    language = _normalize_language(language)
    code = code or ""
    issues: list[str] = []
    lines = code.splitlines()

    # Набір правил навмисно простий: це швидка підказка перед LLM-аналізом.
    if language == "python":
        for index, line in enumerate(lines, start=1):
            stripped = line.strip()
            if _check_hardcoded_secret(line):
                issues.append(f"Рядок {index}: схоже на hardcoded password/token/secret.")
            if re.search(r"\beval\s*\(", line):
                issues.append(f"Рядок {index}: eval() може виконати небезпечний код.")
            if re.search(r"\bexec\s*\(", line):
                issues.append(f"Рядок {index}: exec() може виконати небезпечний код.")
            if re.search(r"\beval\s*\(\s*input\s*\(", line):
                issues.append(f"Рядок {index}: eval(input(...)) є критично небезпечним.")
            if stripped in {"except:", "except Exception:", "except BaseException:"}:
                issues.append(f"Рядок {index}: занадто широкий except приховує помилки.")

    elif language in {"javascript", "typescript", "js", "ts"}:
        for index, line in enumerate(lines, start=1):
            stripped = line.strip()
            if _check_hardcoded_secret(line):
                issues.append(f"Рядок {index}: схоже на hardcoded token/password/secret.")
            if re.search(r"\beval\s*\(", line):
                issues.append(f"Рядок {index}: eval() створює ризик виконання довільного коду.")
            if re.search(r"\bvar\s+\w+", line):
                issues.append(f"Рядок {index}: var краще замінити на const або let.")
            if "console.log" in line:
                issues.append(f"Рядок {index}: console.log варто прибрати з production-коду.")
            if ".innerHTML" in line:
                issues.append(f"Рядок {index}: innerHTML може спричинити XSS без санітизації.")
            if stripped.startswith("catch") and "{}" in stripped:
                issues.append(f"Рядок {index}: порожній catch приховує помилки.")

    else:
        for index, line in enumerate(lines, start=1):
            if _check_hardcoded_secret(line):
                issues.append(f"Рядок {index}: схоже на hardcoded credential.")
            if re.search(r"\beval\s*\(", line):
                issues.append(f"Рядок {index}: eval-подібний виклик потребує перевірки безпеки.")

    if not issues:
        return "Статичний аналіз не знайшов очевидних проблем за базовими правилами."

    return "Потенційні проблеми:\n" + "\n".join(f"- {issue}" for issue in issues)


TOOLS = [
    save_snippet,
    list_snippets,
    show_snippet,
    calculator,
    wikipedia_search,
    analyze_code_static,
]


def _message_text(content: Any) -> str:
    # LangChain може повертати content як рядок або список частин, залежно від моделі.
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content or "")


def _collect_tool_log(messages: list[Any]) -> list[str]:
    # Перетворюємо LangChain messages у компактний журнал для Streamlit expander.
    log: list[str] = []
    for message in messages:
        tool_calls = getattr(message, "tool_calls", None) or []
        for call in tool_calls:
            name = call.get("name", "unknown_tool") if isinstance(call, dict) else str(call)
            log.append(f"Виклик інструмента: {name}")
        if getattr(message, "type", "") == "tool":
            content = _message_text(getattr(message, "content", ""))
            preview = _preview_tool_result(content)
            log.append(f"Результат інструмента:\n{preview}")
    return log


def _preview_tool_result(content: str, limit: int = 900) -> str:
    lines = [line.rstrip() for line in (content or "").strip().splitlines()]
    preview = "\n".join(line for line in lines if line.strip())
    if not preview:
        return "Інструмент не повернув текстового результату."
    if len(preview) > limit:
        return preview[:limit].rstrip() + "\n..."
    return preview


def _extract_latest_answer(messages: list[Any]) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage) and _message_text(message.content).strip():
            return _message_text(message.content).strip()
    return "Не вдалося отримати відповідь агента."


def _sync_snippet_requests(messages: list[Any], snippets: list[dict]) -> list[dict]:
    # save_snippet повертає JSON у tool-message; тут переносимо його в UI-колекцію.
    updated = [dict(snippet) for snippet in snippets]
    known = {
        (
            snippet.get("language", ""),
            snippet.get("code", ""),
            snippet.get("note", ""),
        )
        for snippet in updated
    }

    for message in messages:
        if getattr(message, "type", "") != "tool":
            continue
        content = _message_text(getattr(message, "content", ""))
        if SAVE_SNIPPET_MARKER not in content:
            continue
        payload = content.split(SAVE_SNIPPET_MARKER, 1)[1].splitlines()[0].strip()
        try:
            snippet = json.loads(payload)
        except json.JSONDecodeError:
            continue

        key = (snippet.get("language", ""), snippet.get("code", ""), snippet.get("note", ""))
        if key in known:
            continue

        snippet["id"] = _new_snippet_id(updated)
        snippet.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
        updated.append(snippet)
        known.add(key)

    return updated


@lru_cache(maxsize=12)
def create_codebot_graph(
    model_name: str = "gpt-4o-mini",
    temperature: float = 0.2,
    max_tokens: int = 1000,
):
    llm_with_tools = create_llm(model_name, temperature, max_tokens).bind_tools(TOOLS)

    def agent_node(state: AgentState) -> dict:
        # Кожен крок агента отримує системний промпт і накопичену історію діалогу.
        messages = [SystemMessage(content=CODEBOT_SYSTEM_PROMPT), *state.get("messages", [])]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    # Класичний цикл ReAct: agent вирішує, чи потрібен tool, ToolNode виконує його,
    # після чого відповідь tool знову повертається агенту для фінального висновку.
    builder = StateGraph(AgentState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(TOOLS))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")

    return builder.compile(checkpointer=InMemorySaver())


def invoke_codebot_agent(
    user_text: str,
    thread_id: str,
    snippets: list[dict],
    model_name: str,
    temperature: float,
    max_tokens: int,
) -> dict:
    # thread_id дозволяє LangGraph checkpointer тримати окрему історію для сесії Streamlit.
    current_snippets = [dict(snippet) for snippet in snippets or []]
    graph = create_codebot_graph(model_name, float(temperature), int(max_tokens))
    config = {"configurable": {"thread_id": thread_id or str(uuid.uuid4())}}
    initial_state: AgentState = {
        "messages": [HumanMessage(content=user_text)],
        "snippets": current_snippets,
        "next_snippet_id": _new_snippet_id(current_snippets),
        "tool_call_log": [],
    }

    state = graph.invoke(initial_state, config=config)
    messages = list(state.get("messages", []))
    updated_snippets = _sync_snippet_requests(messages, current_snippets)
    tool_call_log = _collect_tool_log(messages)

    state["snippets"] = updated_snippets
    state["next_snippet_id"] = _new_snippet_id(updated_snippets)
    state["tool_call_log"] = tool_call_log

    return {
        "answer": _extract_latest_answer(messages),
        "snippets": updated_snippets,
        "tool_call_log": tool_call_log,
        "state": state,
    }


def _dict_to_langchain_messages(messages: list[dict]) -> list[Any]:
    converted: list[Any] = []
    for message in messages:
        role = message.get("role")
        content = str(message.get("content", ""))
        if role == "user":
            converted.append(HumanMessage(content=content))
        elif role == "assistant":
            converted.append(AIMessage(content=content))
    return converted


def stream_openai_chat(
    messages: list[dict],
    model_name: str,
    temperature: float,
    max_tokens: int,
    system_prompt: str,
):
    # Звичайний режим не використовує tools: лише streaming-відповідь ChatOpenAI.
    llm = create_llm(model_name, temperature, max_tokens)
    langchain_messages = [
        SystemMessage(content=system_prompt or CODEBOT_SYSTEM_PROMPT),
        *_dict_to_langchain_messages(messages),
    ]

    for chunk in llm.stream(langchain_messages):
        text = _message_text(getattr(chunk, "content", ""))
        if text:
            yield text
