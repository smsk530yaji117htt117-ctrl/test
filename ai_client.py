# -*- coding: utf-8 -*-
"""
AI クライアント共通モジュール
Claude / OpenAI / Gemini を同一インターフェースで呼び出す
"""

import os
import sys

from config import CLAUDE_MODEL, CLAUDE_MODEL_S, OPENAI_MODEL, GEMINI_MODEL, API_TIMEOUT


def ask_claude(prompt: str, system: str = "", smart: bool = False) -> str:
    """Claude に問い合わせる（smart=True で Sonnet、False で Haiku）"""
    import anthropic
    client = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
    )
    model = CLAUDE_MODEL_S if smart else CLAUDE_MODEL
    messages = [{"role": "user", "content": prompt}]
    kwargs: dict = {"model": model, "max_tokens": 4096, "messages": messages}
    if system:
        kwargs["system"] = system
    resp = client.messages.create(**kwargs)
    return resp.content[0].text


def ask_openai(prompt: str, system: str = "") -> str:
    """OpenAI GPT に問い合わせる"""
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        timeout=API_TIMEOUT,
    )
    return resp.choices[0].message.content or ""


def ask_gemini(prompt: str) -> str:
    """Gemini に問い合わせる（情報収集・裏取り用）"""
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(max_output_tokens=2048),
    )
    return resp.text


def ask_ai(prompt: str, provider: str = "claude", system: str = "") -> str:
    """
    provider: "claude" | "claude_smart" | "openai" | "gemini"
    """
    if provider == "claude_smart":
        return ask_claude(prompt, system, smart=True)
    if provider == "openai":
        return ask_openai(prompt, system)
    if provider == "gemini":
        return ask_gemini(prompt)
    return ask_claude(prompt, system, smart=False)
