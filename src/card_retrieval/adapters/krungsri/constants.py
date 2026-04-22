BASE_URL = "https://www.krungsri.com"
# Krungsri's credit-card promotion hub (Thai locale). The historical
# `/th/personal/credit-card/promotion-all` path is a 404 behind Imperva/Incapsula
# — the live listing lives at `/th/promotions/cards`, which links out to
# category sub-pages (hot-promotion, dining, shopping-online, travel, etc.).
# Verified 2026-04-22 via StealthFetcher with a `/th/` warm-up.
PROMOTION_URL = f"{BASE_URL}/th/promotions/cards/hot-promotion"
# Krungsri is protected by Incapsula/Imperva — plain httpx returns a 958-byte
# challenge page. A StealthFetcher pre-visit to the TH root seeds the bot
# cookies, then the subsequent navigation to the promotion hub succeeds.
PRE_VISIT_URL = f"{BASE_URL}/th/"
BANK_NAME = "krungsri"
RATE_LIMIT_SECONDS = 3.0

# Category sub-pages off `/th/promotions/cards/`. Each renders ~1-6 `.card-info`
# tiles using the same DOM. Hot-promotion is the primary hub; the others are
# listed here for future iteration if we decide to walk them like the Amex
# category hubs (each adds only a handful of offers today).
CATEGORY_SLUGS = [
    "hot-promotion",
    "dining",
    "shopping-online",
    "travel",
]

# CSS selectors for the live Krungsri promotion list (verified 2026-04-22 on
# `/th/promotions/cards/hot-promotion`). The listing page only exposes title +
# description + image + detail link — no inline dates or categories; those
# live on the detail pages.
SELECTORS = {
    # Each tile is `<div class="card-info item">` wrapping a single <a>.
    "promotion_card": "div.card-info",
    "title": ".content .header h3, .content h3, h3",
    "image": "img",
    "link_attr": "href",
    # Listing pages do NOT ship date or category slots; kept for compatibility
    # with the parser's graceful-degradation path.
    "date": ".promotion-card__date, .promo-date, time",
    "category": ".promotion-card__category, .promo-category",
    "description": ".content > p, p",
}
