BASE_URL = "https://www.americanexpress.com"
# Amex Thailand "Amex Offers" hub. The TH locale keeps the URL segment /th/,
# and most promotions live under /th/benefits/offers or /th/credit-cards/offers.
# Verify on first fetch — Amex redirects based on geolocation cookies.
PROMOTION_URL = f"{BASE_URL}/th/benefits/offers/"
BANK_NAME = "amex"
RATE_LIMIT_SECONDS = 6.0
