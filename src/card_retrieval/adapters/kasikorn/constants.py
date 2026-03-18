BASE_URL = "https://www.kasikornbank.com"
HOME_URL = f"{BASE_URL}/th/personal"
PROMOTION_URL = f"{BASE_URL}/th/promotion/creditcard/Pages/index.aspx"
BANK_NAME = "kasikorn"
RATE_LIMIT_SECONDS = 10.0

# CSS selectors for KBank promotion page elements (updated 2026-03)
# Note: Kasikorn blocks headless browsers (403). Use headed mode or Xvfb.
SELECTORS = {
    "promotion_card": ".box-thumb",
    "title": ".thumb-title",
    "image": ".img-thumb img",
    "link": "a.img-thumb",
    "date": ".thumb-date",
    "category": ".promo-item dt",
    "description": ".thumb-des",
    "load_more": "button[class*='more'], a[class*='more'], .load-more",
}
