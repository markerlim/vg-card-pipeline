import csv
import re
import time
import requests
from bs4 import BeautifulSoup

BASE = "https://yuyu-tei.jp"
OUTPUT_CSV = "data/cards_yyt_price.csv"

FIELDS = ["set_code", "cardno", "name", "rarity", "price_yen", "original_price_yen", "in_stock"]

# Set codes to scrape — derived from JP expansion names
# Pattern: "DZ-BT01" → "dzbt01", "DZ-SS04" → "dzss04"
SET_CODES = [
    "dzbt01", "dzbt02", "dzbt03", "dzbt04", "dzbt05", "dzbt06",
    "dzbt07", "dzbt08", "dzbt09", "dzbt10", "dzbt11", "dzbt12",
    "dzbt13", "dzbt14",
    "dzss01", "dzss02", "dzss03", "dzss04", "dzss05", "dzss06",
    "dzss07", "dzss08", "dzss09", "dzss10", "dzss11", "dzss12",
]

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://yuyu-tei.jp/",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Connection": "keep-alive",
    "Cache-Control": "max-age=0",
})

# Prime session with homepage to get cookies
try:
    session.get("https://yuyu-tei.jp/", timeout=15)
except requests.RequestException:
    pass


def parse_price(text: str) -> str:
    text = text.replace("円", "").replace(",", "").strip()
    return text if text.isdigit() else ""


def scrape_set(set_code: str) -> list[dict]:
    url = f"{BASE}/sell/vg/s/search?vers[]={set_code}"

    for attempt in range(3):
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            break
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)

    soup = BeautifulSoup(resp.text, "html.parser")

    cards = []
    current_rarity = ""

    for section in soup.select("div.py-4.cards-list"):
        h3 = section.find("h3")
        if h3:
            rarity_span = h3.find("span")
            current_rarity = rarity_span.get_text(strip=True) if rarity_span else h3.get_text(strip=True)

        for card_div in section.select(".card-product"):
            sold_out = "sold-out" in card_div.get("class", [])

            cardno_span = card_div.find("span", class_=re.compile(r"border-dark"))
            cardno = cardno_span.get_text(strip=True) if cardno_span else ""

            name_el = card_div.find("h4")
            name = name_el.get_text(strip=True) if name_el else ""

            # Sale: <del> = original, <strong class="text-danger"> = sale price
            del_el = card_div.find("del")
            if del_el:
                original_price = parse_price(del_el.get_text())
                strong_el = card_div.find("strong", class_=re.compile(r"text-danger"))
                price = parse_price(strong_el.get_text()) if strong_el else ""
            else:
                original_price = ""
                strong_el = card_div.find("strong", class_=re.compile(r"text-end"))
                price = parse_price(strong_el.get_text()) if strong_el else ""

            # Stock status from 在庫 label
            stock_text = ""
            for text_node in card_div.stripped_strings:
                if "在庫" in text_node:
                    stock_text = text_node.strip()
                    break
            in_stock = "false" if sold_out else "true"

            cards.append({
                "set_code": set_code,
                "cardno": cardno,
                "name": name,
                "rarity": current_rarity,
                "price_yen": price,
                "original_price_yen": original_price,
                "in_stock": in_stock,
            })

    return cards


def main():
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()

        for code in SET_CODES:
            print(f"Scraping {code}...")
            try:
                cards = scrape_set(code)
                print(f"  -> {len(cards)} cards")
                for card in cards:
                    writer.writerow(card)
                f.flush()
            except Exception as e:
                print(f"  ERROR: {e}")

            time.sleep(0.5)

    print(f"\nDone! Saved to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
