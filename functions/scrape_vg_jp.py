import csv
import re
import sys
import time
import requests
from bs4 import BeautifulSoup

BASE = "https://cf-vanguard.com"
CARDLIST_URL = f"{BASE}/cardlist/"
OUTPUT_CSV = "data/cards_vg_jp.csv"
YEAR_FROM = 2024

FIELDS = [
    "expansion", "expansion_id",
    "cardno", "name", "ruby",
    "card_url", "image_url",
    "type", "nation", "race", "grade", "power", "critical", "shield", "skill", "gift",
    "regulation", "rarity", "illustrator",
    "effect", "flavor",
]

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en;q=0.5",
})


def get(url: str) -> BeautifulSoup:
    resp = session.get(url, timeout=15)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def scrape_products() -> list[dict]:
    soup = get(CARDLIST_URL)
    products = []

    for year_div in soup.select("div.expansion-year"):
        h4 = year_div.find("h4")
        if not h4:
            continue
        match = re.search(r"(\d{4})年", h4.get_text())
        if not match or int(match.group(1)) < YEAR_FROM:
            continue
        year = int(match.group(1))

        products_div = year_div.find("div", class_="products-list")
        if not products_div:
            continue

        for a in products_div.find_all("a", href=re.compile(r"expansion=\d+")):
            exp_match = re.search(r"expansion=(\d+)", a["href"])
            if not exp_match:
                continue
            products.append({
                "year": year,
                "expansion_id": exp_match.group(1),
                "name": a.get_text(separator=" ", strip=True),
            })

    return products


def scrape_product_cards(expansion_id: str) -> list[dict]:
    cards = []
    page = 1

    while True:
        url = f"{CARDLIST_URL}cardsearch/?expansion={expansion_id}&view=image&page={page}"
        soup = get(url)

        links = soup.select("a[href*='cardno=']")
        if not links:
            break

        for a in links:
            href = a["href"]
            img = a.find("img")
            card_url = BASE + href if href.startswith("/") else href
            image_url = ""
            if img:
                src = img.get("src", "")
                image_url = BASE + src if src.startswith("/") else src

            cardno_match = re.search(r"cardno=([^&]+)", href)
            cardno = cardno_match.group(1) if cardno_match else ""

            cards.append({"cardno": cardno, "card_url": card_url, "image_url": image_url})

        page += 1
        time.sleep(0.2)

    return cards


def scrape_card_detail(card_url: str) -> dict:
    soup = get(card_url)
    detail = {}

    box = soup.select_one(".cardlist_detail")
    if not box:
        return detail

    # Card image from detail page (higher quality path)
    img = box.select_one(".image .main img")
    if img:
        src = img.get("src", "")
        detail["image_url"] = BASE + src if src.startswith("/") else src

    name_el = box.select_one(".name .face")
    detail["name"] = name_el.get_text(strip=True) if name_el else ""

    ruby_el = box.select_one(".name .ruby")
    detail["ruby"] = ruby_el.get_text(strip=True) if ruby_el else ""

    for field in ["type", "nation", "race", "grade", "power", "critical", "shield", "skill", "gift"]:
        el = box.select_one(f".text-list .{field}")
        detail[field] = el.get_text(strip=True) if el else ""

    effect_el = box.select_one(".effect")
    detail["effect"] = effect_el.get_text(strip=True) if effect_el else ""

    flavor_el = box.select_one(".flavor")
    detail["flavor"] = flavor_el.get_text(strip=True) if flavor_el else ""

    for field, css_class in [
        ("regulation", "regulation"),
        ("rarity", "rarity"),
        ("illustrator", "illstrator"),
    ]:
        el = box.select_one(f".{css_class}")
        detail[field] = el.get_text(strip=True) if el else ""

    return detail


def main():
    print("Fetching product list...")
    products = scrape_products()
    print(f"Found {len(products)} products from {YEAR_FROM}+\n")

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()

        for product in products:
            print(f"Scraping: {product['name']} (expansion={product['expansion_id']})")
            try:
                cards = scrape_product_cards(product["expansion_id"])
                print(f"  Found {len(cards)} cards")
            except Exception as e:
                print(f"  ERROR fetching card list: {e}")
                continue

            for i, card in enumerate(cards, 1):
                print(f"  [{i}/{len(cards)}] {card['cardno']}")
                row = {
                    "expansion": product["name"],
                    "expansion_id": product["expansion_id"],
                    **card,
                }

                if card["card_url"]:
                    try:
                        details = scrape_card_detail(card["card_url"])
                        row.update(details)
                    except Exception as e:
                        print(f"    ERROR: {e}")

                writer.writerow(row)
                f.flush()
                time.sleep(0.3)

    print(f"\nDone! Saved to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
