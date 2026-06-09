import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=1)
def _load_json(filename: str):
    with open(DATA_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def load_stopwords() -> set[str]:
    return set(_load_json("stopwords.json"))


def normalize_text(text: str) -> str:
    """Lowercase, bỏ dấu tiếng Việt, chuẩn hóa khoảng trắng."""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^\w\s+#\.\-/]", " ", text)
    return " ".join(text.split())


def strip_header_noise(text: str) -> str:
    """Loại bỏ email, URL, số điện thoại phổ biến trong header JD."""
    text = re.sub(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b", " ", text)
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"\b\+?\d[\d\s\-().]{7,}\d\b", " ", text)
    return " ".join(text.split())
