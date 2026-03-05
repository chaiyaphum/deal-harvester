BASE_URL = "https://www.kasikornbank.com"
HOME_URL = f"{BASE_URL}/th/personal"
PROMOTION_URL = f"{BASE_URL}/th/personal/card/credit-card/pages/promotions.aspx"
BANK_NAME = "kasikorn"
RATE_LIMIT_SECONDS = 10.0

# CSS selectors for KBank promotion page elements
SELECTORS = {
    "promotion_card": ".kb-card-promotion, .promotion-item, .card-item",
    "title": "h2, h3, h4, .title, .card-title, [class*='title']",
    "image": "img",
    "link": "a[href]",
    "date": ".date, .period, [class*='date'], [class*='period']",
    "category": ".category, .tag, [class*='category']",
    "description": ".description, .detail, p, [class*='desc']",
    "load_more": "button[class*='more'], a[class*='more'], .load-more, .view-more",
}
