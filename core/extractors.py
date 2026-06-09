import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

MIN_TEXT_LENGTH = 50


@dataclass
class ExtractResult:
    text: str
    error: str | None = None
    likely_scanned: bool = False


def _read_pdf_bytes(pdf_path: str) -> bytes:
    raw = Path(pdf_path).read_bytes()
    # Một số PDF export có newline trước header %PDF
    start = raw.find(b"%PDF")
    if start > 0:
        raw = raw[start:]
    return raw


def extract_text_from_pdf(pdf_path: str) -> ExtractResult:
    """Đọc PDF và trả về text thô (chưa normalize)."""
    try:
        raw = _read_pdf_bytes(pdf_path)
        reader = PdfReader(BytesIO(raw))
        parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                parts.append(page_text)
        text = " ".join(parts)
        if len(text.strip()) < MIN_TEXT_LENGTH:
            return ExtractResult(
                text=text.strip(),
                error=None,
                likely_scanned=True,
            )
        return ExtractResult(text=text)
    except Exception as exc:
        return ExtractResult(text="", error=str(exc))


def collect_cv_files(folder: str, recursive: bool = True) -> list[str]:
    """Thu thập file PDF trong thư mục (có thể quét subfolder)."""
    root = Path(folder)
    pattern = "**/*.pdf" if recursive else "*.pdf"
    return sorted(str(p) for p in root.glob(pattern) if p.is_file())
