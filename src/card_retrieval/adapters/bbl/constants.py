BASE_URL = "https://www.bangkokbank.com"
# Bangkok Bank's published Thai-locale promotions path at
# /th/personal/other-services/promotions/credit-card-promotions is a 404 and
# the /th landing page itself returns a 500 as of 2026-04-22 (BBL's Thai
# Sitecore instance is intermittently broken). The EN hub at
# /en/Personal/Cards/Credit-Cards/Promotions is stable and renders the same
# promotion tile component. We use the EN hub and note the limitation in
# PLAN.md — the TH hub will be swapped in automatically once BBL repairs it.
PROMOTION_URL = f"{BASE_URL}/en/Personal/Cards/Credit-Cards/Promotions"
BANK_NAME = "bbl"
RATE_LIMIT_SECONDS = 5.0

# CSS selectors for the Sitecore-rendered promotion cards. Each promotion is a
# `.thumb-default` block inside `.divCardPromotionsListing`, with a thumbnail
# style attribute (not a plain `src`), a `.desc` headline, a `.promotion-tip`
# category label, and a `.promotion-valid` date string.
SELECTORS = {
    "promotion_card": ".thumb-default",
    "image_bg": ".thumb[style*=background-image]",
    "image_fallback": "img.img-print, img",
    "title": ".desc, .caption .desc",
    "description": ".caption .desc",
    "category": ".promotion-tip",
    "date": ".promotion-valid",
    "link": "a.btn-primary[href], a[href]",
}
