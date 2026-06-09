import re

from core.normalizer import normalize_text


def _needs_substring_match(term: str) -> bool:
    """Cụm đa từ hoặc ký tự đặc biệt (C++, node.js) dùng substring."""
    if " " in term:
        return True
    return any(ch in term for ch in "+#./")


def keyword_in_text(keyword: str, text: str, synonyms: list[str] | None = None) -> bool:
    """Match keyword với word-boundary (tránh java ⊂ javascript)."""
    variants = [keyword] + (synonyms or [])
    for variant in variants:
        normalized = normalize_text(variant)
        if not normalized:
            continue
        if _needs_substring_match(normalized):
            if normalized in text:
                return True
        else:
            pattern = rf"(?<![a-z0-9+#.]){re.escape(normalized)}(?![a-z0-9+#.])"
            if re.search(pattern, text):
                return True
    return False
