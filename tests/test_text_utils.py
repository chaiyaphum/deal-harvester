from card_retrieval.utils.text import extract_discount, extract_minimum_spend, normalize_thai_text


def test_normalize_thai_text():
    assert normalize_thai_text("  hello   world  ") == "hello world"
    assert normalize_thai_text("test\u200btext") == "testtext"
    assert normalize_thai_text("ส่วนลด   50%") == "ส่วนลด 50%"


def test_extract_discount_percentage():
    dtype, dval = extract_discount("รับส่วนลด 50% ที่ร้านอาหาร")
    assert dtype == "percentage"
    assert dval == "50%"


def test_extract_discount_cashback():
    dtype, dval = extract_discount("รับเงินคืน 500 บาท")
    assert dtype == "cashback"
    assert dval == "500 baht"


def test_extract_discount_points():
    dtype, dval = extract_discount("รับ 5000 คะแนนพิเศษ")
    assert dtype == "points"
    assert dval == "5000 points"


def test_extract_discount_none():
    dtype, dval = extract_discount("สิทธิพิเศษสำหรับสมาชิก")
    assert dtype is None
    assert dval is None


def test_extract_minimum_spend():
    assert extract_minimum_spend("ช้อปครบ 3,000 บาท") == 3000.0
    assert extract_minimum_spend("ขั้นต่ำ 500 baht") == 500.0
    assert extract_minimum_spend("no minimum") is None


def test_extract_minimum_spend_thai():
    assert extract_minimum_spend("ใช้จ่ายตั้งแต่ 10,000 บาท") == 10000.0
