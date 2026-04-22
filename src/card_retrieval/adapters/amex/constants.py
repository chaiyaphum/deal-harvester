BASE_URL = "https://www.americanexpress.com"
# Amex Thailand's public "Cardmember Offers" program is split across four
# category hubs under /th-th/benefits/promotions/. All four use the same AEM
# template (`div.offer.parbase`) so the adapter iterates them and stamps the
# `category` field based on which hub a tile was sourced from.
# Verified 2026-04-22:
#   dining       → 45 tiles
#   lifestyle    → 20 tiles
#   travel       → 13 tiles
#   explore-asia →  8 tiles
# Historical `/th/benefits/offers/` path 404s.
PROMOTION_HUBS: list[tuple[str, str]] = [
    # (hub_slug, URL). `hub_slug` is what gets stamped on Promotion.category
    # via HUB_CATEGORY_MAP below (not a 1:1 — explore-asia maps to "travel").
    ("dining", f"{BASE_URL}/th-th/benefits/promotions/dining.html"),
    ("travel", f"{BASE_URL}/th-th/benefits/promotions/travel.html"),
    ("lifestyle", f"{BASE_URL}/th-th/benefits/promotions/lifestyle.html"),
    ("explore-asia", f"{BASE_URL}/th-th/benefits/promotions/explore-asia.html"),
]
# Hub slug → Promotion.category. We fold explore-asia into "travel" (it's
# regional travel benefits). Lifestyle maps to "shopping" since the hub is
# dominated by retail/beauty/entertainment merchants.
HUB_CATEGORY_MAP: dict[str, str] = {
    "dining": "dining",
    "travel": "travel",
    "lifestyle": "shopping",
    "explore-asia": "travel",
}
# The first hub (dining) is the canonical source_url reported via
# `AmexAdapter.get_source_url()`. Kept as a constant for back-compat with the
# old `PROMOTION_URL` attribute some call sites may reference.
PROMOTION_URL = PROMOTION_HUBS[0][1]
# Amex blocks direct access to the promotion hub without a warm session — we
# pre-visit the TH root first so Akamai Bot Manager sets the _abck / bm_sz
# cookies before we request the offer-bearing page.
PRE_VISIT_URL = f"{BASE_URL}/th/"
BANK_NAME = "amex"
RATE_LIMIT_SECONDS = 6.0

# CSS selectors verified 2026-04-22 against live captures from all four hubs.
# Every offer tile is a `div.offer.parbase` rendered by Amex's AEM template.
SELECTORS = {
    "promotion_card": ".offer.parbase",
    "image": "img.card-detail-image, img",
    "title": ".offer-header p, .offer-header",
    "description": ".offer-desc",
    "date": ".offer-dates",
    "link": "a.link-underlined[href], a[role='button'][href], a[href]",
}
