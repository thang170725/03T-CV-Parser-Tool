import re

SECTION_START_PATTERNS = [
    r"skills?\s*(?:and|&)\s*experience",
    r"technical\s+skills?",
    r"required\s+skills?",
    r"key\s+skills?",
    r"qualifications?",
    r"requirements?",
    r"job\s+requirements?",
    r"what\s+you(?:'ll|\s+will)\s+(?:need|bring|have)",
    r"what\s+we(?:'re|\s+are)\s+looking\s+for",
    r"mo\s+ta\s+cong\s+viec",
    r"yeu\s+cau",
    r"ky\s+nang",
    r"trach\s+nhiem",
    r"pham\s+vi\s+cong\s+viec",
]

SECTION_END_PATTERNS = [
    r"why\s+you(?:'ll|\s+ll|\s+will)\s+love",
    r"benefits?",
    r"what\s+we\s+offer",
    r"compensation",
    r"how\s+to\s+apply",
    r"contact\s+(?:us|hr)",
    r"about\s+(?:us|the\s+company)",
    r"quyen\s+loi",
    r"che\s+do",
    r"lien\s+he",
    r"ung\s+tuyen",
    r"phuc\s+loi",
    r"happy\s+hour",
    r"team\s+building",
]


def _find_first(patterns: list[str], text: str) -> int | None:
    best = None
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match and (best is None or match.start() < best):
            best = match.start()
    return best


def extract_skill_sections(jd_text: str) -> str:
    """
    Cắt các section skills/requirements từ JD (text đã normalize, không dấu).
    Nếu không tìm thấy section, trả về toàn bộ text.
    """
    if not jd_text.strip():
        return ""

    starts = []
    for pattern in SECTION_START_PATTERNS:
        for match in re.finditer(pattern, jd_text, re.IGNORECASE):
            starts.append(match.start())

    if not starts:
        return jd_text

    sections = []
    for start in sorted(set(starts)):
        end = len(jd_text)
        for pattern in SECTION_END_PATTERNS:
            match = re.search(pattern, jd_text[start + 20 :], re.IGNORECASE)
            if match:
                candidate = start + 20 + match.start()
                if candidate > start:
                    end = min(end, candidate)
        chunk = jd_text[start:end].strip()
        if chunk:
            sections.append(chunk)

    return "\n".join(dict.fromkeys(sections)) if sections else jd_text
