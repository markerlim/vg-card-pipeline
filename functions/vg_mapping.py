import csv
import json
import os
import time
import requests
from bs4 import BeautifulSoup

JP_CSV = "data/cards_vg_jp.csv"
WIKI_CSV = "data/cards_vg_wiki.csv"
OUTPUT_CSV = "data/cards_mapped.csv"
CACHE_FILE = "data/wiki_kanji_cache.json"

BASE_WIKI = "https://cardfight.fandom.com"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
})


def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def fetch_kanji(card_url: str, cache: dict) -> str:
    if card_url in cache:
        return cache[card_url]

    page = card_url.split("/wiki/")[-1]
    api_url = f"{BASE_WIKI}/api.php?action=parse&page={page}&prop=text&format=json"

    try:
        resp = session.get(api_url, timeout=15)
        resp.raise_for_status()
        html = resp.json()["parse"]["text"]["*"]
        soup = BeautifulSoup(html, "html.parser")

        jp_name = ""
        header = soup.select_one(".header")
        if header:
            br = header.find("br")
            if br:
                # Drop furigana readings (<rt>) so we keep only the base text (<rb>)
                for rt in header.find_all("rt"):
                    rt.decompose()
                texts = []
                for sib in br.next_siblings:
                    t = sib.get_text(strip=True) if hasattr(sib, "get_text") else str(sib).strip()
                    if t:
                        texts.append(t)
                jp_name = "".join(texts).strip()

        cache[card_url] = jp_name
        time.sleep(0.3)
        return jp_name

    except Exception as e:
        print(f"    ERROR fetching {card_url.split('/wiki/')[-1][:50]}: {e}")
        cache[card_url] = ""
        return ""


def main():
    # --- Load wiki CSV ---
    with open(WIKI_CSV, newline="", encoding="utf-8") as f:
        wiki_rows = list(csv.DictReader(f))
    print(f"Loaded {len(wiki_rows)} wiki card entries")

    # --- Fetch Kanji names (with cache) ---
    cache = load_cache()

    unique_wiki_urls = {row["card_url"] for row in wiki_rows if row.get("card_url")}
    missing = [u for u in unique_wiki_urls if u not in cache]
    print(f"Cache: {len(cache)} entries | Need to fetch: {len(missing)}\n")

    for i, url in enumerate(missing, 1):
        print(f"  [{i}/{len(missing)}] {url.split('/wiki/')[-1][:60]}")
        fetch_kanji(url, cache)
        if i % 100 == 0:
            save_cache(cache)

    save_cache(cache)
    print(f"\nCache saved ({len(cache)} entries)")

    # --- Build kanji → wiki data lookup ---
    # Same card can appear in multiple sets; keep all so we can pick closest set match
    kanji_to_wiki: dict[str, dict] = {}
    for row in wiki_rows:
        url = row.get("card_url", "")
        kanji = cache.get(url, "").strip()
        if not kanji:
            continue
        # Store first occurrence per kanji name (cards are listed in release order)
        if kanji not in kanji_to_wiki:
            kanji_to_wiki[kanji] = {
                "name_en":      row["name"],
                "card_url_wiki": url,
                "set_code_wiki": row["set_code"],
                "card_no_wiki":  row["card_no"],
            }

    print(f"Built {len(kanji_to_wiki)} unique kanji → English mappings")

    # --- Load JP CSV ---
    with open(JP_CSV, newline="", encoding="utf-8") as f:
        jp_rows = list(csv.DictReader(f))
    print(f"Loaded {len(jp_rows)} JP cards\n")

    jp_fields = list(jp_rows[0].keys()) if jp_rows else []
    extra_fields = ["name_en", "card_url_wiki", "set_code_wiki", "card_no_wiki"]
    output_fields = jp_fields + extra_fields

    matched = unmatched = 0

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=output_fields, extrasaction="ignore")
        writer.writeheader()

        for row in jp_rows:
            jp_name = row.get("name", "").strip()
            wiki = kanji_to_wiki.get(jp_name)

            if wiki:
                row.update(wiki)
                matched += 1
            else:
                for field in extra_fields:
                    row[field] = ""
                unmatched += 1

            writer.writerow(row)

    total = matched + unmatched
    print(f"Matched:   {matched}/{total} ({matched/total*100:.1f}%)")
    print(f"Unmatched: {unmatched}/{total}")
    print(f"\nSaved to {OUTPUT_CSV}")

    # Print sample unmatched names to help debug gaps
    if unmatched:
        print("\nSample unmatched JP names:")
        count = 0
        for row in jp_rows:
            if not kanji_to_wiki.get(row.get("name", "").strip()):
                print(f"  {row.get('cardno','?')} | {row.get('name','?')}")
                count += 1
                if count >= 10:
                    break


if __name__ == "__main__":
    main()
