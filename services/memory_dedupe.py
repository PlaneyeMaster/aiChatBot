import re
from difflib import SequenceMatcher

def normalize_text(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[\"'`]", "", s)
    return s

def is_text_duplicate(candidate: str, existing: list[str], ratio_threshold: float = 0.92) -> bool:
    c = normalize_text(candidate)
    for e in existing:
        en = normalize_text(e)
        if c == en:
            return True
        if c in en or en in c:
            # 거의 포함 관계면 중복 취급
            if min(len(c), len(en)) >= 12:
                return True
        if SequenceMatcher(None, c, en).ratio() >= ratio_threshold:
            return True
    return False

def is_vector_duplicate(pinecone_matches, score_threshold: float = 0.90) -> bool:
    matches = getattr(pinecone_matches, "matches", None) or pinecone_matches.get("matches", [])
    if not matches:
        return False
    top = matches[0]
    score = getattr(top, "score", None) or top.get("score", 0.0)
    return score >= score_threshold
