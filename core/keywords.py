import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache

from core.matcher import keyword_in_text
from core.normalizer import load_stopwords, normalize_text, strip_header_noise
from core.sections import extract_skill_sections


@dataclass
class KeywordSpec:
    term: str
    weight: int = 1
    synonyms: list[str] = field(default_factory=list)
    source: str = "dictionary"
    category: str = ""


@lru_cache(maxsize=1)
def _load_skills() -> dict:
    from core.normalizer import _load_json
    return _load_json("skills_it.json")


@lru_cache(maxsize=1)
def _load_phrases() -> dict[str, int]:
    from core.normalizer import _load_json
    return _load_json("phrases.json")


def _sorted_terms() -> list[tuple[str, dict]]:
    """Sắp xếp skill dài trước để match phrase trước single word."""
    skills = _load_skills()
    phrases = _load_phrases()
    all_terms: dict[str, dict] = {}

    for phrase, weight in phrases.items():
        all_terms[phrase] = {"weight": weight, "synonyms": [], "category": "phrase"}

    for term, meta in skills.items():
        all_terms[term] = meta

    return sorted(all_terms.items(), key=lambda x: len(x[0]), reverse=True)


def _find_dictionary_keywords(text: str) -> list[KeywordSpec]:
    found: list[KeywordSpec] = []
    seen: set[str] = set()

    for term, meta in _sorted_terms():
        normalized_term = normalize_text(term)
        if not normalized_term or normalized_term in seen:
            continue

        synonyms = meta.get("synonyms", [])
        if keyword_in_text(term, text, synonyms):
            found.append(
                KeywordSpec(
                    term=term,
                    weight=meta.get("weight", 1),
                    synonyms=synonyms,
                    source="dictionary",
                    category=meta.get("category", ""),
                )
            )
            seen.add(normalized_term)
            for syn in synonyms:
                seen.add(normalize_text(syn))

    return found


def _find_frequency_keywords(text: str, stopwords: set[str], limit: int = 5) -> list[KeywordSpec]:
    """Bổ sung keyword từ tần suất (chỉ trong section đã lọc), tránh trùng dictionary."""
    words = re.findall(r"\b[a-z0-9+#.]+\b", text)
    filtered = []
    for w in words:
        w_clean = w.strip(".")
        if w_clean and w_clean not in stopwords and len(w_clean) > 2 and not w_clean.isdigit():
            filtered.append(w_clean)

    results = []
    dict_terms = existing
    for word, _ in Counter(filtered).most_common(limit * 3):
        if word in stopwords:
            continue
        if any(word in t or t in word for t in dict_terms if len(t) > 2):
            continue
        results.append(
            KeywordSpec(term=word, weight=1, source="frequency", category="other")
        )
        if len(results) >= limit:
            break
    return results


def extract_keywords_from_jd(jd_text: str, top_n: int = 20) -> list[KeywordSpec]:
    """
    Hybrid extraction:
    1. Strip header noise
    2. Focus skill sections
    3. Dictionary + phrase match (ưu tiên)
    4. Frequency bổ sung (giới hạn)
    """
    normalized = normalize_text(strip_header_noise(jd_text))
    if not normalized:
        return []

    skill_section = normalize_text(extract_skill_sections(normalized))
    search_text = skill_section if skill_section else normalized
    stopwords = load_stopwords()

    keywords = _find_dictionary_keywords(search_text)

    existing = {normalize_text(k.term) for k in keywords}
    for syn_spec in list(keywords):
        for syn in syn_spec.synonyms:
            existing.add(normalize_text(syn))

    freq_limit = max(0, min(3, top_n - len(keywords)))
    if freq_limit > 0 and len(keywords) < 8:
        for kw in _find_frequency_keywords(search_text, stopwords, limit=freq_limit):
            if normalize_text(kw.term) not in existing:
                keywords.append(kw)
                existing.add(normalize_text(kw.term))

    keywords.sort(key=lambda k: (-k.weight, k.term))
    return keywords[:top_n]
