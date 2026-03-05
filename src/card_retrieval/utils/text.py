import re


def normalize_thai_text(text: str) -> str:
    """Normalize Thai text: collapse whitespace, strip zero-width chars."""
    # Remove zero-width characters
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_discount(text: str) -> tuple[str | None, str | None]:
    """Try to extract discount type and value from Thai promotion text."""
    text_lower = text.lower()

    # Percentage patterns
    pct = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if pct:
        return "percentage", f"{pct.group(1)}%"

    # Points (check before baht since "บาท" can be a spend threshold)
    points = re.search(r"(\d[\d,]*)\s*(?:คะแนน|points?|พอยท์|เท่า)", text_lower)
    if points:
        val = points.group(1).replace(",", "")
        return "points", f"{val} points"

    # Cashback patterns (Thai baht)
    baht = re.search(r"(\d[\d,]*)\s*(?:บาท|baht|฿)", text_lower)
    if baht:
        val = baht.group(1).replace(",", "")
        if "คืน" in text_lower or "cashback" in text_lower or "cash back" in text_lower:
            return "cashback", f"{val} baht"
        return "discount", f"{val} baht"

    return None, None


def extract_minimum_spend(text: str) -> float | None:
    """Try to extract minimum spend amount from text."""
    match = re.search(
        r"(?:ครบ|ตั้งแต่|ขั้นต่ำ|min(?:imum)?)\s*(\d[\d,]*)\s*(?:บาท|baht|฿)?",
        text.lower(),
    )
    if match:
        return float(match.group(1).replace(",", ""))
    return None
