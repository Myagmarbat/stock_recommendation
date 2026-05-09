from __future__ import annotations


POSITIVE = {"beat", "growth", "raise", "raised", "strong", "upgrade", "profit", "record", "approval", "buyback"}
NEGATIVE = {"miss", "weak", "cut", "cuts", "downgrade", "lawsuit", "probe", "decline", "warning", "bankruptcy"}


def get_news_summary(news_items: list[dict], limit: int = 8) -> dict:
    headlines = []
    for item in news_items[:limit]:
        title = str(item.get("title") or "").strip()
        if title:
            headlines.append(title)
    if not headlines:
        return {"score": 0.0, "headlines": [], "summary": "No recent headlines found."}

    raw = 0
    for title in headlines:
        low = title.lower()
        raw += sum(1 for word in POSITIVE if word in low)
        raw -= sum(1 for word in NEGATIVE if word in low)
    score = max(-1.0, min(1.0, raw / max(3, len(headlines))))
    return {
        "score": round(score, 4),
        "headlines": headlines,
        "summary": "; ".join(headlines[:3]),
    }

