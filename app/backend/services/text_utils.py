import re


def strip_think(text: str) -> str:
    text = re.sub(r"<think>[\s\S]*?</think>", "", text)
    think_start = text.lower().find("<think>")
    if think_start != -1:
        text = text[:think_start]
    return text.strip()
