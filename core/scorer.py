from dataclasses import dataclass, field

from core.keywords import KeywordSpec
from core.matcher import keyword_in_text
from core.normalizer import normalize_text


@dataclass
class MatchResult:
    score: float
    matched: list[str] = field(default_factory=list)
    must_have_matched: int = 0
    must_have_total: int = 0
    nice_have_matched: int = 0
    nice_have_total: int = 0
    warning: str | None = None


def match_cv_with_keywords(cv_text: str, keywords: list[KeywordSpec]) -> MatchResult:
    """Chấm CV theo trọng số keyword."""
    normalized_cv = normalize_text(cv_text)

    if not keywords:
        return MatchResult(score=0.0)

    if len(normalized_cv) < 50:
        return MatchResult(
            score=0.0,
            warning="CV quá ngắn hoặc PDF scan — cần kiểm tra thủ công",
        )

    matched: list[str] = []
    total_weight = 0
    matched_weight = 0
    must_have_matched = 0
    must_have_total = 0
    nice_have_matched = 0
    nice_have_total = 0

    for spec in keywords:
        total_weight += spec.weight
        is_must_have = spec.weight >= 3
        if is_must_have:
            must_have_total += 1
        else:
            nice_have_total += 1

        if keyword_in_text(spec.term, normalized_cv, spec.synonyms):
            matched.append(spec.term)
            matched_weight += spec.weight
            if is_must_have:
                must_have_matched += 1
            else:
                nice_have_matched += 1

    score = (matched_weight / total_weight * 100) if total_weight else 0.0
    return MatchResult(
        score=round(score, 2),
        matched=matched,
        must_have_matched=must_have_matched,
        must_have_total=must_have_total,
        nice_have_matched=nice_have_matched,
        nice_have_total=nice_have_total,
    )
