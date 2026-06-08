#!/usr/bin/env python3
"""Re-scrape Yuyutei prices for already-scraped sets and re-merge final CSV."""

import csv
import json
import os
import re
import sys
import time

from functions.scrape_yyt_price import scrape_set as yyt_scrape_set
from functions.scrape_yyt_price import FIELDS as YYT_FIELDS

WIKI_SETS_JSON = "data/wiki_sets.json"
MAPPED_CSV     = "data/cards_mapped.csv"
YYT_CSV        = "data/cards_yyt_price.csv"
FINAL_CSV      = "data/cards_final.csv"


def wiki_code_to_yyt(set_code: str) -> str:
    parts = re.split(r'dz-', set_code.lower())
    if len(parts) >= 2:
        return "dz" + re.sub(r'[^a-z0-9]', '', parts[-1])
    return ""


def get_scraped_sets(filter_code: str | None = None) -> list[dict]:
    with open(WIKI_SETS_JSON, encoding="utf-8") as f:
        wiki_sets = json.load(f)

    result = []
    for code, info in wiki_sets.items():
        if not info.get("scraped"):
            continue
        if filter_code and code.upper() != filter_code.upper():
            continue
        yyt_code = wiki_code_to_yyt(code)
        if not yyt_code:
            print(f"  SKIP {code} (no YYT code derived)")
            continue
        result.append({"set_code": code, "yyt_code": yyt_code, **info})
    return result


def scrape_prices(sets: list[dict]):
    mode = "w"
    with open(YYT_CSV, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=YYT_FIELDS, extrasaction="ignore")
        writer.writeheader()

        for s in sets:
            print(f"  {s['set_code']} → {s['yyt_code']}")
            try:
                cards = yyt_scrape_set(s["yyt_code"])
                print(f"    {len(cards)} cards")
                for card in cards:
                    writer.writerow(card)
                f.flush()
            except Exception as e:
                print(f"    ERROR: {e}")
            time.sleep(0.5)


def merge_final():
    with open(MAPPED_CSV, newline="", encoding="utf-8") as f:
        mapped_rows = list(csv.DictReader(f))

    yyt_by_cardno: dict[str, dict] = {}
    if os.path.exists(YYT_CSV):
        with open(YYT_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                base = re.sub(r'_\w+$', '', row["cardno"])
                yyt_by_cardno.setdefault(base, row)

    price_fields = ["price_yen", "original_price_yen", "in_stock"]
    out_fields = (list(mapped_rows[0].keys()) + price_fields) if mapped_rows else []

    with open(FINAL_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        for row in mapped_rows:
            base_cardno = re.sub(r'_\w+$', '', row.get("cardno", ""))
            price_data = yyt_by_cardno.get(base_cardno, {})
            for field in price_fields:
                row[field] = price_data.get(field, "")
            writer.writerow(row)

    print(f"Saved {len(mapped_rows)} rows to {FINAL_CSV}")


def main():
    filter_code = sys.argv[1] if len(sys.argv) > 1 else None
    if filter_code:
        print(f"=== Repricing: {filter_code} ===")
    else:
        print("=== Repricing: all scraped sets ===")

    sets = get_scraped_sets(filter_code)
    if not sets:
        print("No scraped sets found to reprice.")
        return

    print(f"Found {len(sets)} set(s)")
    scrape_prices(sets)
    merge_final()
    print("=== Reprice complete ===")


if __name__ == "__main__":
    main()
