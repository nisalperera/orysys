"""Helpers for parsing small-model output: strip <think> blocks and fences, find the first JSON object."""
import json
import re

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE = re.compile(r"```(?:json|python)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def strip_think(text: str) -> str:
    return _THINK.sub("", text).strip()


def extract_code(text: str) -> str:
    text = strip_think(text)
    m = _FENCE.search(text)
    return (m.group(1) if m else text).strip()


def extract_json(text: str) -> dict:
    text = extract_code(text)
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object found")
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(obj, dict):
        raise ValueError("JSON root is not an object")
    return obj
