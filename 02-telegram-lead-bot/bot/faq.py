import json
import re
from typing import Optional


def load_faq(path: str) -> list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def find_answer(faq: list, text: str) -> Optional[dict]:
    """Ищет пункт FAQ по ключевым словам (по началу слова, чтобы работали окончания)."""
    words = re.findall(r"\w+", (text or "").lower())
    best, best_score = None, 0
    for item in faq:
        score = sum(1 for kw in item.get("keywords", []) if any(w.startswith(kw[:5]) for w in words))
        if score > best_score:
            best, best_score = item, score
    return best
