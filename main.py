#!/usr/bin/env python3
"""VG Card Data Pipeline — orchestrates the full scraping and mapping flow."""

import csv
import json
import os
import re
import time

from functions.scrape_vg_jp import scrape_products, scrape_product_cards, scrape_card_detail
from functions.scrape_vg_jp import FIELDS as JP_FIELDS
from functions.scrape_vg_wiki import scrape_card_list, fetch_jp_name
from functions.scrape_vg_wiki import FIELDS as WIKI_FIELDS
from functions.scrape_yyt_price import scrape_set as yyt_scrape_set
from functions.scrape_yyt_price import FIELDS as YYT_FIELDS

BOOSTERS_JSON   = "data/boosters.json"
WIKI_SETS_JSON  = "data/wiki_sets.json"
JP_CSV          = "data/cards_vg_jp.csv"
WIKI_CSV        = "data/cards_vg_wiki.csv"
MAPPED_CSV      = "data/cards_mapped.csv"
YYT_CSV         = "data/cards_yyt_price.csv"
FINAL_CSV       = "data/cards_final.csv"
UNMATCHED_CSV   = "data/cards_unmatched.csv"



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_boosters() -> dict:
    if os.path.exists(BOOSTERS_JSON):
        with open(BOOSTERS_JSON, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_boosters(boosters: dict):
    with open(BOOSTERS_JSON, "w", encoding="utf-8") as f:
        json.dump(boosters, f, ensure_ascii=False, indent=2)


def load_wiki_sets() -> dict:
    with open(WIKI_SETS_JSON, encoding="utf-8") as f:
        return json.load(f)


def save_wiki_sets(wiki_sets: dict):
    with open(WIKI_SETS_JSON, "w", encoding="utf-8") as f:
        json.dump(wiki_sets, f, ensure_ascii=False, indent=2)


def wiki_code_to_yyt(set_code: str) -> str:
    """VGE-DZ-BT14 → dzbt14, VG-DZ-SS04 → dzss04"""
    parts = re.split(r'dz-', set_code.lower())
    if len(parts) >= 2:
        return "dz" + re.sub(r'[^a-z0-9]', '', parts[-1])
    return ""


def extract_set_info(jp_name: str) -> tuple[str, str] | None:
    """Extract (type, number) from JP product name. e.g. 'DZ-BT14' → ('BT', '14')"""
    m = re.search(r'DZ-(BT|SS)(\d+)', jp_name)
    if m:
        return m.group(1), m.group(2)
    return None


def find_wiki_set(set_type: str, number: str, wiki_sets: list[dict]) -> dict | None:
    for ws in wiki_sets:
        m = re.search(rf'{set_type}(\d+)', ws["set_code"])
        if m and m.group(1).lstrip("0") == number.lstrip("0"):
            return ws
    return None


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def step1_find_new_boosters(boosters: dict) -> list[dict]:
    print("=== Step 1: Checking JP site for new boosters ===")
    products = scrape_products()
    print(f"JP site: {len(products)} products")

    new = [p for p in products if p["expansion_id"] not in boosters]
    print(f"New (unprocessed): {len(new)}")
    return new


def step2_match_wiki_sets(new_products: list[dict], wiki_sets: dict) -> list[dict]:
    """Match JP products against wiki_sets.json, skipping already-scraped sets."""
    print("\n=== Step 2: Matching against wiki_sets.json ===")
    print(f"Registry: {len(wiki_sets)} sets")

    matched = []
    for prod in new_products:
        info = extract_set_info(prod["name"])
        if not info:
            print(f"  SKIP   {prod['name'][:80]} (no set code found)")
            continue

        ws_code = None
        for code in wiki_sets:
            m = re.search(rf'{info[0]}(\d+)', code)
            if m and m.group(1).lstrip("0") == info[1].lstrip("0"):
                ws_code = code
                break

        if not ws_code:
            print(f"  SKIP   {prod['name'][:80]} (not in wiki_sets.json)")
        elif wiki_sets[ws_code].get("scraped"):
            print(f"  SKIP   {prod['name'][:80]} (already scraped as {ws_code})")
        else:
            print(f"  MATCH  {prod['name'][:80]} → {ws_code}")
            matched.append({"jp": prod, "wiki": {"set_code": ws_code, **wiki_sets[ws_code]}})

    return matched


def step3_scrape_jp_cards(matched: list[dict]):
    print("\n=== Step 3: Scraping JP card data ===")

    write_header = not os.path.exists(JP_CSV)
    with open(JP_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=JP_FIELDS, extrasaction="ignore")
        if write_header:
            writer.writeheader()

        for m in matched:
            prod = m["jp"]
            print(f"  {prod['name']} (id={prod['expansion_id']})")
            try:
                cards = scrape_product_cards(prod["expansion_id"])
            except Exception as e:
                print(f"    ERROR: {e}")
                continue

            print(f"    {len(cards)} cards")
            for i, card in enumerate(cards, 1):
                print(f"    [{i}/{len(cards)}] {card['cardno']}")
                row = {"expansion": prod["name"], "expansion_id": prod["expansion_id"], **card}
                if card["card_url"]:
                    try:
                        row.update(scrape_card_detail(card["card_url"]))
                    except Exception as e:
                        print(f"      ERROR: {e}")
                writer.writerow(row)
                f.flush()
                time.sleep(0.3)


def step4_scrape_wiki_cards(matched: list[dict]):
    print("\n=== Step 4: Scraping wiki card data ===")

    write_header = not os.path.exists(WIKI_CSV)
    with open(WIKI_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=WIKI_FIELDS, extrasaction="ignore")
        if write_header:
            writer.writeheader()

        for m in matched:
            ws = m["wiki"]
            print(f"  {ws['set_code']}")
            try:
                cards = scrape_card_list(ws["set_url"])
                print(f"    {len(cards)} cards — fetching JP names...")
                for i, card in enumerate(cards, 1):
                    if card["card_url"]:
                        card["jp_name"] = fetch_jp_name(card["card_url"])
                        print(f"    [{i}/{len(cards)}] {card['card_no']} → {card['jp_name'][:30]}")
                        time.sleep(0.3)
                    writer.writerow({**ws, **card})
                f.flush()
            except Exception as e:
                print(f"    ERROR: {e}")
            time.sleep(0.3)


def step5_run_mapping():
    print("\n=== Step 5: Mapping JP → wiki (jp_name match) ===")

    with open(WIKI_CSV, newline="", encoding="utf-8") as f:
        wiki_rows = list(csv.DictReader(f))
    with open(JP_CSV, newline="", encoding="utf-8") as f:
        jp_rows = list(csv.DictReader(f))

    def norm(s: str) -> str:
        return re.sub(r"\s+", "", s).strip()

    # JP site name → wiki jp_name (for known typos / naming differences)
    JP_NAME_CORRECTIONS: dict[str, str] = {
        "Bel-Fioreピネッセ":        "Bel-Fioreピネッゼ",
        "促進魔法ヴォクストール":      "保進魔法ヴォクストール",
        "100億の少女澤村遥":          "アサガオの長女澤村遥",
    }

    kanji_to_wiki: dict[str, dict] = {}
    for row in wiki_rows:
        jp_name = row.get("jp_name", "").strip()
        if jp_name:
            key = norm(jp_name)
            if key and key not in kanji_to_wiki:
                kanji_to_wiki[key] = {
                    "name_en":       row["name"],
                    "card_url_wiki": row.get("card_url", ""),
                    "set_code_wiki": row["set_code"],
                    "card_no_wiki":  row["card_no"],
                }

    extra_fields = ["name_en", "card_url_wiki", "set_code_wiki", "card_no_wiki"]
    out_fields = (list(jp_rows[0].keys()) + extra_fields) if jp_rows else []

    matched = unmatched = 0
    with open(MAPPED_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        for row in jp_rows:
            key = norm(row.get("name", ""))
            key = JP_NAME_CORRECTIONS.get(key, key)
            wiki = kanji_to_wiki.get(key)
            if wiki:
                row.update(wiki)
                matched += 1
            else:
                for field in extra_fields:
                    row[field] = ""
                unmatched += 1
            writer.writerow(row)

    total = matched + unmatched
    if total:
        print(f"Mapped {matched}/{total} ({matched / total * 100:.1f}%)")

    unmatched_rows = [r for r in jp_rows if not r.get("name_en")]
    with open(UNMATCHED_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["cardno", "name", "expansion"], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(unmatched_rows)
    print(f"Unmatched cards saved to {UNMATCHED_CSV} ({len(unmatched_rows)} cards)")


def step6_scrape_yyt(matched: list[dict]):
    print("\n=== Step 6: Scraping Yuyutei prices ===")

    write_header = not os.path.exists(YYT_CSV)
    with open(YYT_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=YYT_FIELDS, extrasaction="ignore")
        if write_header:
            writer.writeheader()

        for m in matched:
            yyt_code = wiki_code_to_yyt(m["wiki"]["set_code"])
            if not yyt_code:
                continue
            print(f"  {m['wiki']['set_code']} → {yyt_code}")
            try:
                cards = yyt_scrape_set(yyt_code)
                print(f"    {len(cards)} cards")
                for card in cards:
                    writer.writerow(card)
                f.flush()
            except Exception as e:
                print(f"    ERROR: {e}")
            time.sleep(0.5)


def step7_merge_final():
    print("\n=== Step 7: Merging final output ===")

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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Process at most N new sets (for testing)")
    parser.add_argument("--from-step", type=int, default=1, dest="from_step", help="Resume from this step (1-7), skipping earlier steps")
    parser.add_argument("--set", type=str, default=None, dest="force_set", help="Set code from wiki_sets.json to process, e.g. VGE-DZ-BT13")
    args = parser.parse_args()

    boosters    = load_boosters()
    wiki_sets   = load_wiki_sets()

    if args.force_set:
        target = args.force_set.upper()
        if target not in wiki_sets:
            print(f"'{target}' not found in {WIKI_SETS_JSON}. Available sets:")
            for code, info in wiki_sets.items():
                status = "[scraped]" if info.get("scraped") else "[ ]"
                print(f"  {status} {code}: {info['set_name']}")
            return
        ws = {"set_code": target, **wiki_sets[target]}
        print(f"=== --set {target}: {ws['set_name']} ===")
        # Find matching JP product
        all_products = scrape_products()
        info = re.search(r'DZ-(BT|SS)(\d+)', target)
        jp_product = None
        if info:
            for p in all_products:
                pi = extract_set_info(p["name"])
                if pi and pi[0] == info.group(1) and pi[1].lstrip("0") == info.group(2).lstrip("0"):
                    jp_product = p
                    break
        if not jp_product:
            print(f"  No JP product found for {target} — will scrape wiki only (no JP cards/images)")
            matched = [{"jp": {"name": target, "expansion_id": target}, "wiki": ws}]
        else:
            print(f"  JP product: {jp_product['name'][:60]}")
            matched = [{"jp": jp_product, "wiki": ws}]
    else:
        new_products = step1_find_new_boosters(boosters)
        if not new_products:
            print("\nNo new boosters. Pipeline complete.")
            return
        matched = step2_match_wiki_sets(new_products, wiki_sets)
        if not matched:
            print("\nNo new unscraped sets found. Pipeline complete.")
            return

    if args.limit:
        matched = matched[:args.limit]
        print(f"\n[--limit {args.limit}] Processing {len(matched)} set(s) only.")

    if args.from_step > 1:
        print(f"\n[--from-step {args.from_step}] Skipping to step {args.from_step}.\n")

    if args.from_step <= 3:
        step3_scrape_jp_cards(matched)
    if args.from_step <= 4:
        step4_scrape_wiki_cards(matched)
    if args.from_step <= 5:
        step5_run_mapping()
    if args.from_step <= 6:
        step6_scrape_yyt(matched)
    step7_merge_final()

    for m in matched:
        if m["jp"].get("expansion_id") and m["jp"]["expansion_id"] != m["wiki"]["set_code"]:
            boosters[m["jp"]["expansion_id"]] = {
                "jp_name":       m["jp"]["name"],
                "wiki_set_code": m["wiki"]["set_code"],
                "yyt_code":      wiki_code_to_yyt(m["wiki"]["set_code"]),
            }
        wiki_sets[m["wiki"]["set_code"]]["scraped"] = True
    save_boosters(boosters)
    save_wiki_sets(wiki_sets)
    print(f"\nUpdated {BOOSTERS_JSON} and {WIKI_SETS_JSON}")
    print("=== Pipeline complete ===")


if __name__ == "__main__":
    main()
