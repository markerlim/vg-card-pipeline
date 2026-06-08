import csv
import re

INPUT_CSV  = "data/cards_final.csv"
OUTPUT_CSV = "data/shopify_products.csv"

VENDOR   = "Cardboard Collectible"
JPY_RATE      = 110
PRODUCT_TYPE  = "Vanguard Singles"
BASE_TAGS     = ["Vanguard", "Vanguard Singles", "Singles"]

SHOPIFY_FIELDS = [
    "Handle", "Title", "Body (HTML)", "Vendor", "Type", "Tags",
    "Published",
    "Option1 Name", "Option1 Value",
    "Option2 Name", "Option2 Value",
    "Option3 Name", "Option3 Value",
    "Variant SKU", "Variant Grams",
    "Variant Inventory Tracker", "Variant Inventory Qty",
    "Variant Inventory Policy", "Variant Fulfillment Service",
    "Variant Price", "Variant Requires Shipping", "Variant Taxable",
    "Image Src", "Image Position",
    "Gift Card", "Variant Weight Unit",
    "Included / Singapore",
    "Included / Australia",
    "Included / Eurozone",
    "Included / India",
    "Included / International",
    "Included / Japan",
    "Included / United Kingdom",
    "Included / United States",
    "Status",
]


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
    # VGE-DZ-BT14 → DZ-BT14, DZ-BT
    short = re.sub(r'^VGE-', '', set_code)          # DZ-BT14
    series = re.sub(r'\d+$', '', short)              # DZ-BT
    extras = [t for t in [series, short] if t]
    return ", ".join(BASE_TAGS + extras)


def main():
    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    written = skipped = 0
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SHOPIFY_FIELDS, extrasaction="ignore")
        writer.writeheader()

        for row in rows:
            name_en   = row.get("name_en", "").strip() or row.get("name", "").strip()
            cardno    = row.get("cardno", "").strip()
            price_yen = row.get("price_yen", "").strip()
            image_url = row.get("image_url", "").strip()
            rarity    = row.get("rarity", "").strip()
            grade     = row.get("grade", "").strip()
            nation    = row.get("nation", "").strip()
            set_code  = row.get("set_code_wiki", "").strip()
            if not set_code:
                m = re.match(r'((?:VG[E]?-)?DZ-(?:BT|SS)\d+)', cardno)
                if m:
                    set_code = m.group(1)
            in_stock  = row.get("in_stock", "true").strip().lower()

            if not cardno:
                skipped += 1
                continue

            try:
                price = f"{int(price_yen) / JPY_RATE:.1f}" if price_yen else ""
            except ValueError:
                price = ""

            qty = "1" if in_stock == "true" else "0"

            writer.writerow({
                "Handle":                    make_handle(cardno),
                "Title":                     f"{cardno} {name_en} [{rarity}]" if rarity else f"{cardno} {name_en}",
                "Body (HTML)":               make_body(name_en, cardno, rarity, grade, nation),
                "Vendor":                    VENDOR,
                "Type":                      PRODUCT_TYPE,
                "Tags":                      make_tags(set_code),
                "Published":                 "true",
                "Option1 Name":              "Title",
                "Option1 Value":             "Default Title",
                "Variant SKU":               cardno,
                "Variant Grams":             "0.002",
                "Variant Inventory Tracker": "shopify",
                "Variant Inventory Qty":     qty,
                "Variant Inventory Policy":  "deny",
                "Variant Fulfillment Service": "manual",
                "Variant Price":             price,
                "Variant Requires Shipping": "true",
                "Variant Taxable":           "true",
                "Image Src":                 image_url,
                "Image Position":            "1",
                "Gift Card":                 "false",
                "Variant Weight Unit":       "kg",
                "Included / Singapore":      "true",
                "Included / Australia":      "true",
                "Included / Eurozone":       "true",
                "Included / India":          "true",
                "Included / International":  "true",
                "Included / Japan":          "true",
                "Included / United Kingdom": "true",
                "Included / United States":  "true",
                "Status":                    "active",
            })
            written += 1

    print(f"Exported {written} products → {OUTPUT_CSV}  (skipped {skipped} unmatched)")


if __name__ == "__main__":
    main()
