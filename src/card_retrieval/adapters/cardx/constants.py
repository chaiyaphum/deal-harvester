BASE_URL = "https://www.cardx.co.th"
PROMOTION_URL = f"{BASE_URL}/credit-card/promotion"
BANK_NAME = "cardx"
RATE_LIMIT_SECONDS = 5.0

# API patterns to intercept (Flutter web apps often call REST APIs)
API_INTERCEPT_PATTERNS = [
    "api.cardx.co.th",
    "/api/",
    "promotion",
    "graphql",
]
