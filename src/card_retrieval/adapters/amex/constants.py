BASE_URL = "https://www.americanexpress.com"
# Amex Thailand's public "Cardmember Offers" program is split across four
# category hubs under /th-th/benefits/promotions/. Dining is the largest (45+
# offers) and the simplest to scrape — the others (travel, lifestyle,
# explore-asia) use the same DOM shape so extending later is mechanical.
# The historical `/th/benefits/offers/` path 404s as of 2026-04-22. The
# `/th/` root redirects EN visitors to `th-th` for actual content pages.
PROMOTION_URL = f"{BASE_URL}/th-th/benefits/promotions/dining.html"
# Amex blocks direct access to the promotion hub without a warm session — we
# pre-visit the TH root first so Akamai Bot Manager sets the _abck / bm_sz
# cookies before we request the offer-bearing page.
PRE_VISIT_URL = f"{BASE_URL}/th/"
BANK_NAME = "amex"
RATE_LIMIT_SECONDS = 6.0

# CSS selectors verified 2026-04-22 against a live-captured fixture (dining
# category, 45 offers). Every offer tile is a `div.offer.parbase` rendered by
# Amex's AEM template.
SELECTORS = {
    "promotion_card": ".offer.parbase",
    "image": "img.card-detail-image, img",
    "title": ".offer-header p, .offer-header",
    "description": ".offer-desc",
    "date": ".offer-dates",
    "link": "a.link-underlined[href], a[role='button'][href], a[href]",
}
