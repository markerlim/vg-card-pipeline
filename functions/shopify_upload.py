import csv
import os
import re
import time
import requests

STORE    = "j0rzcq-0a.myshopify.com"
API_VER  = "2024-10"
BASE_URL = f"https://{STORE}/admin/api/{API_VER}"

INPUT_CSV    = "data/cards_final.csv"
VENDOR       = "Cardboard Collectible"
PRODUCT_TYPE = "Vanguard Singles"
BASE_TAGS    = ["Vanguard", "Vanguard Singles", "Singles"]
JPY_RATE     = 110


def load_env():
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


def make_session(token: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json",
    })
    return s


def make_handle(cardno: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", cardno.lower()).strip("-")


def make_body(name_en: str, cardno: str, rarity: str, grade: str, nation: str) -> str:
    lines = [f"<p><strong>{name_en}</strong></p>"]
    if cardno:
        lines.append(f"<p>Card Number: {cardno}</p>")
    if rarity:
        lines.append(f"<p>Rarity: {rarity}</p>")
    if grade:
        lines.append(f"<p>Grade: {grade}</p>")
    if nation:
        lines.append(f"<p>Nation: {nation}</p>")
    return "\n".join(lines)


def make_tags(set_code: str) -> str:
    short = re.sub(r"^VGE-", "", set_code)
    series = re.sub(r"\d+$", "", short)
    extras = [t for t in [series, short] if t]
    return ", ".join(BASE_TAGS + extras)


def fetch_existing_skus(session: requests.Session) -> dict[str, str]:
    """Return {sku: product_id} for all products on the store."""
    print("Fetching existing products from Shopify...")
    skus = {}
    url = f"{BASE_URL}/products.json?fields=id,variants&limit=250"
    while url:
        resp = session.get(url)
        resp.raise_for_status()
        for product in resp.json().get("products", []):
            for variant in product.get("variants", []):
                if variant.get("sku"):
                    skus[variant["sku"]] = str(product["id"])
        url = None
        for part in resp.headers.get("Link", "").split(","):
            if 'rel="next"' in part:
                url = part.split(";")[0].strip().strip("<>")
        if url:
            time.sleep(0.5)
    print(f"  {len(skus)} existing SKUs found")
    return skus


def build_payload(name_en: str, cardno: str, price: str, image_url: str,
                  rarity: str, grade: str, nation: str, set_code: str, qty: int) -> dict:
    title = f"{cardno} {name_en} [{rarity}]" if rarity else f"{cardno} {name_en}"
    payload = {
        "title":        title,
        "body_html":    make_body(name_en, cardno, rarity, grade, nation),
        "vendor":       VENDOR,
        "product_type": PRODUCT_TYPE,
        "tags":         make_tags(set_code),
        "status":       "active",
        "handle":       make_handle(cardno),
        "variants": [{
            "price":                str(price) if price else "",
            "sku":                  cardno,
            "inventory_management": "shopify",
            "inventory_quantity":   qty,
            "fulfillment_service":  "manual",
            "requires_shipping":    True,
            "taxable":              True,
            "weight":               0.002,
            "weight_unit":          "kg",
        }],
    }
    if image_url:
        payload["images"] = [{"src": image_url}]
    return payload


def throttle(resp: requests.Response):
    """Slow down if approaching Shopify's rate limit bucket."""
    header = resp.headers.get("X-Shopify-Shop-Api-Call-Limit", "")
    if header:
        used, total = (int(x) for x in header.split("/"))
        if used >= total - 5:
            time.sleep(1.0)
        else:
            time.sleep(0.3)
    else:
        time.sleep(0.3)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--update", action="store_true", help="Update existing products (default: skip)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without uploading")
    parser.add_argument("--set", type=str, default=None, dest="filter_set", help="Only upload cards from this set, e.g. VGE-DZ-SS16")
    args = parser.parse_args()

    load_env()
    token = os.environ.get("SHOPIFY_TOKEN", "")
    if not token:
        print("ERROR: SHOPIFY_TOKEN not set. Add it to .env or export it.")
        return

    session = make_session(token)

    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if args.filter_set:
        target = args.filter_set.upper()
        short = re.sub(r"^VGE-", "", target)   # DZ-SS16
        rows = [r for r in rows if r.get("set_code_wiki", "").upper() == target
                or r.get("cardno", "").upper().startswith(short + "/")]
        print(f"Filtered to {len(rows)} cards for {target}")

    existing = {} if args.dry_run else fetch_existing_skus(session)

    created = updated = skipped = errors = 0

    for row in rows:
        name_en   = row.get("name_en", "").strip() or row.get("name", "").strip()
        cardno    = row.get("cardno", "").strip()
        price_yen = row.get("price_yen", "").strip()
        image_url = row.get("image_url", "").strip()
        rarity    = row.get("rarity", "").strip()
        grade     = row.get("grade", "").strip()
        nation    = row.get("nation", "").strip()
        set_code  = row.get("set_code_wiki", "").strip()
        in_stock  = row.get("in_stock", "").strip().lower()

        if not cardno:
            skipped += 1
            continue

        if not set_code:
            m = re.match(r"((?:VG[E]?-)?DZ-(?:BT|SS)\d+)", cardno)
            if m:
                set_code = m.group(1)

        try:
            price = f"{int(price_yen) / JPY_RATE:.1f}" if price_yen else ""
        except ValueError:
            price = ""

        qty = 1 if in_stock == "true" else 0
        payload = build_payload(name_en, cardno, price, image_url, rarity, grade, nation, set_code, qty)

        if args.dry_run:
            print(f"  [DRY RUN] {cardno} — {payload['title'][:60]}")
            created += 1
            continue

        if cardno in existing:
            if args.update:
                try:
                    resp = session.put(f"{BASE_URL}/products/{existing[cardno]}.json",
                                       json={"product": payload})
                    resp.raise_for_status()
                    throttle(resp)
                    updated += 1
                    print(f"  UPDATE {cardno}")
                except Exception as e:
                    print(f"  ERROR  {cardno}: {e}")
                    errors += 1
            else:
                skipped += 1
        else:
            try:
                resp = session.post(f"{BASE_URL}/products.json", json={"product": payload})
                resp.raise_for_status()
                throttle(resp)
                created += 1
                print(f"  CREATE {cardno}")
            except Exception as e:
                print(f"  ERROR  {cardno}: {e}")
                errors += 1

    print(f"\nDone — created: {created}, updated: {updated}, skipped: {skipped}, errors: {errors}")


if __name__ == "__main__":
    main()
