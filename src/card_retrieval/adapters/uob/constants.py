BASE_URL = "https://www.uob.co.th"
# UOB Thailand's canonical credit-card promotion hub. The historical
# "/personal/cards/promotions/all-promotions.page" path 404s and redirects to
# "/personal/credit-cards/promotions.page"; the sitemap-declared entry point
# below is what UOB publishes for the Thai locale and returns HTTP 301 → the
# canonical hub, which httpx follows transparently.
PROMOTION_URL = f"{BASE_URL}/personal/promotions/creditcard/all-promotion.page"
BANK_NAME = "uob"
RATE_LIMIT_SECONDS = 4.0

# CSS selectors verified 2026-04-22 against a live-captured fixture. UOB runs an
# AEM (Adobe Experience Manager) template; each promo is a `.category-item`
# containing a card with image, title, description, and a CTA link to the promo
# detail page. Selectors are intentionally broad enough to tolerate small class
# reshuffles without breaking parsing.
SELECTORS = {
    "promotion_card": ".category-item",
    "image": "img.card-img-top, img",
    "title": "h4.card-title, h4",
    "description": "p.paragraph, p",
    "link": "a.dtm-button[href], a[href]",
}
