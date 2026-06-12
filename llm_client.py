"""GreenNode LLM (OpenAI-compatible) — moi cuoc goi LLM deu di qua ask_llm_json."""
import json

from openai import OpenAI

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

llm = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)


def ask_llm_json(prompt: str, max_tokens: int = 1500) -> dict:
    resp = llm.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.2,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1].removeprefix("json").strip()
    return json.loads(raw)
