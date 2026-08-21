"""
Тонкая обёртка над Anthropic API.

Ranker просит строго JSON, Editor — свободный текст.
`call_json` устойчиво вытаскивает JSON, даже если модель добавила пояснения.
"""
import json
import re

from config import settings

_client = None


def client():
    """Ленивая инициализация Anthropic-клиента (SDK нужен только тут)."""
    global _client
    if _client is None:
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY не задан (см. .env).")
        from anthropic import Anthropic  # ленивый импорт
        _client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def call_text(system: str, user: str, model: str, max_tokens: int = 1500,
              temperature: float = 0.7) -> str:
    _ = temperature
    resp = client().messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(block.text for block in resp.content if block.type == "text").strip()


def _escape_control_chars_in_strings(raw: str) -> str:
    """Escape raw newlines/tabs that models sometimes put inside JSON strings."""
    out = []
    in_string = False
    escaped = False
    replacements = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}

    for char in raw:
        if escaped:
            out.append(char)
            escaped = False
            continue
        if char == "\\" and in_string:
            out.append(char)
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            out.append(char)
            continue
        if in_string and char in replacements:
            out.append(replacements[char])
            continue
        out.append(char)
    return "".join(out)


def _loads_json_lenient(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return json.loads(_escape_control_chars_in_strings(raw))


def _first_json_object(raw: str) -> str | None:
    start = raw.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(raw[start:], start=start):
        if escaped:
            escaped = False
            continue
        if char == "\\" and in_string:
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return raw[start:index + 1]
    return None


def call_json(system: str, user: str, model: str, max_tokens: int = 1200) -> dict:
    """Возвращает распарсенный JSON. Терпит ```json-обёртки и мусор вокруг."""
    raw = call_text(
        system + "\n\nМаңызды: тек жарамды JSON қайтар, түсініктемесіз.",
        user, model, max_tokens=max_tokens, temperature=0.2,
    )
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        return _loads_json_lenient(raw)
    except json.JSONDecodeError:
        # Последняя попытка — вытащить первый {...} блок.
        first_object = _first_json_object(raw)
        if first_object:
            return _loads_json_lenient(first_object)
        raise
