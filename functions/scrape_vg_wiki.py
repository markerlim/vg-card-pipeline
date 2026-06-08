import csv
import re
import sys
import time
import requests
from bs4 import BeautifulSoup

BASE = "https://cardfight.fandom.com"
OUTPUT_CSV = "data/cards_vg_wiki.csv"

FIELDS = [
    "set_code", "set_name", "set_url",
    "card_no", "name", "jp_name", "card_url",
    "grade", "nation", "type", "rarity",
]

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

session = requests.Session()
session.headers.update(API_HEADERS)


def api_fetch(wiki_url: str) -> BeautifulSoup:
    page = wiki_url.split("/wiki/")[-1]
    api_url = f"{BASE}/api.php?action=parse&page={page}&prop=text&format=json"
    resp = session.get(api_url, timeout=15)
    resp.raise_for_status()
    html = resp.json()["parse"]["text"]["*"]
    return BeautifulSoup(html, "html.parser")


def scrape_set_list(wiki_url: str, code_pattern: str) -> list[dict]:
    """Return list of {set_code, set_name, set_url} matching code_pattern."""
    soup = api_fetch(wiki_url)
    sets = []
    seen = set()

    for a in soup.find_all("a", href=re.compile(r"^/wiki/")):
        text = a.get_text(strip=True)
        if not re.match(code_pattern, text):
            continue
        href = a["href"]
        full_url = BASE + href
        if full_url in seen:
            continue
        seen.add(full_url)

        # Text is like "VGE-DZ-BT06: Generation Dragenesis"
        # Split on first colon/space to get code vs name
        code_match = re.match(r"(VG[E]?-DZ-(?:BT|SS)\d+)[:\s]*(.*)", text)
        if code_match:
            code = code_match.group(1)
            name = code_match.group(2).strip()
        else:
            code = text
            name = text

        sets.append({"set_code": code, "set_name": name, "set_url": full_url})

    return sets


def fetch_jp_name(card_url: str) -> str:
    try:
        soup = api_fetch(card_url)
        header = soup.select_one(".header")
        if header:
            br = header.find("br")
            if br:
                for rt in header.find_all("rt"):
                    rt.decompose()
                texts = []
                for sib in br.next_siblings:
                    t = sib.get_text(strip=True) if hasattr(sib, "get_text") else str(sib).strip()
                    if t:
                        texts.append(t)
                return "".join(texts).strip()
    except Exception:
        pass
    return ""


def _parse_card_table(table) -> list[dict]:
    cards = []
    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        card_no = cells[0].get_text(strip=True)
        link = cells[1].find("a")
        if link and link.get("href"):
            name = link.get_text(strip=True)
            card_url = BASE + link["href"] if link["href"].startswith("/") else link["href"]
        else:
            name = cells[1].get_text(strip=True)
            card_url = ""

        grade = cells[2].get_text(strip=True) if len(cells) > 2 else ""
        nation = cells[3].get_text(strip=True) if len(cells) > 3 else ""
        card_type = cells[4].get_text(strip=True) if len(cells) > 4 else ""
        rarity = cells[5].get_text(strip=True) if len(cells) > 5 else ""

        cards.append({
            "card_no": card_no,
            "name": name,
            "jp_name": "",
            "card_url": card_url,
            "grade": grade,
            "nation": nation,
            "type": card_type,
            "rarity": rarity,
        })

    return cards


def scrape_card_list(set_url: str) -> list[dict]:
    soup = api_fetch(set_url)
    cards = []

    # Main card list
    card_list_span = soup.find("span", id="Card_List")
    if card_list_span:
        table = card_list_span.find_parent("h2").find_next("table")
        if table:
            cards.extend(_parse_card_table(table))

    # Edition Exclusives (collab / alternate art cards listed separately)
    ee_span = soup.find("span", id="Edition_Exclusives")
    if ee_span:
        table = ee_span.find_parent("h2").find_next("table")
        if table:
            cards.extend(_parse_card_table(table))

    # PR Card List (promo cards)
    pr_span = soup.find("span", id="PR_Card_List")
    if pr_span:
        table = pr_span.find_parent("h2").find_next("table")
        if table:
            cards.extend(_parse_card_table(table))

    return cards


def main():
    all_sets = []

    print("Fetching DZ Booster Sets (VG-DZ-BT / VGE-DZ-BT)...")
    booster_url = f"{BASE}/wiki/List_of_Cardfight!!_Vanguard_Booster_Sets"
    boosters = scrape_set_list(booster_url, r"VG[E]?-DZ-BT\d+")
    print(f"  Found {len(boosters)} booster sets")
    all_sets.extend(boosters)

    print("Fetching DZ Special Series (VG-DZ-SS)...")
    special_url = f"{BASE}/wiki/List_of_Cardfight!!_Vanguard_Special_Series"
    specials = scrape_set_list(special_url, r"VG[E]?-DZ-SS\d+")
    print(f"  Found {len(specials)} special series")
    all_sets.extend(specials)

    print(f"\nTotal sets to scrape: {len(all_sets)}\n")

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()

        for s in all_sets:
            print(f"Scraping: {s['set_code']} - {s['set_name']}")
            try:
                cards = scrape_card_list(s["set_url"])
                print(f"  -> {len(cards)} cards")
                for card in cards:
                    writer.writerow({**s, **card})
                f.flush()
            except Exception as e:
                print(f"  ERROR: {e}")

            time.sleep(0.3)

    print(f"\nDone! Saved to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
