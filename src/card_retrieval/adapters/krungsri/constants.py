BASE_URL = "https://www.krungsri.com"
# Krungsri's credit-card promotion hub (Thai locale). A single landing page lists
# all promotions as cards with thumbnail + title + (sometimes) merchant + date range.
PROMOTION_URL = f"{BASE_URL}/th/personal/credit-card/promotion-all"
BANK_NAME = "krungsri"
RATE_LIMIT_SECONDS = 3.0

# CSS selectors for Krungsri promotion list page (verified 2026-04-22 against a saved
# fixture). The site is server-rendered HTML; selectors are intentionally broad so that
# minor Krungsri template tweaks do not break parsing outright.
SELECTORS = {
    # Each card is an <a> or <article> element under a grid container.
    "promotion_card": "a.promotion-card, article.promotion-card, div.promotion-item",
    "title": ".promotion-card__title, .promo-title, h3, h4",
    "image": "img",
    "link_attr": "href",
    "date": ".promotion-card__date, .promo-date, time",
    "category": ".promotion-card__category, .promo-category",
    "description": ".promotion-card__desc, .promo-desc, p",
}
