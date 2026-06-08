# VG Card Data Pipeline

Automated pipeline that tracks new Cardfight!! Vanguard DZ-era releases, maps Japanese card data to English names, and attaches Yuyutei market prices.

## Flow

```
JP Official Site (cf-vanguard.com)
        │ scrape_vg_jp.py
        ▼
  cards_vg_jp.csv
        │
        │ vg_mapping.py  ◄──  Cardfight Wiki (cardfight.fandom.com)
        │                              │ scrape_vg_wiki.py
        │                              ▼
        │                       cards_vg_wiki.csv
        ▼
  cards_mapped.csv  (JP data + EN name)
        │
        │  + Yuyutei (yuyu-tei.jp)
        │         │ scrape_yyt_price.py
        │         ▼
        │  cards_yyt_price.csv
        ▼
  cards_final.csv  (all data merged)
```

## How It Works

### 1. New Booster Detection
`boosters.json` tracks processed expansion IDs. On each run, `main.py` fetches the current JP product list and finds expansions not yet in that file.

### 2. Wiki Matching
New JP boosters are matched to wiki sets by booster number (e.g., JP 第14弾 → `VGE-DZ-BT14`). If no wiki entry exists yet the pipeline stops — the set likely hasn't been added to the English wiki.

### 3. Card Scraping
Both sources are scraped for metadata. The JP site provides Japanese names, stats, and images. The wiki provides English names, grades, nations, and rarities. New data is appended to existing CSVs.

### 4. Name Mapping
JP cards are linked to English names via the Kanji field on each wiki card page. Results are cached in `wiki_kanji_cache.json` to avoid redundant fetches.

### 5. Price Scraping
Yuyutei prices are fetched per set using codes derived from the wiki set code (`VGE-DZ-BT14` → `dzbt14`). Sale and sold-out cards are flagged separately.

### 6. Final Merge
All data is joined on card number into `cards_final.csv`.

## Usage

### Full pipeline
```bash
python main.py
```

### Individual scripts
```bash
python scrape_vg_jp.py       # JP official site → cards_vg_jp.csv
python scrape_vg_wiki.py     # EN wiki          → cards_vg_wiki.csv
python vg_mapping.py         # Kanji match      → cards_mapped.csv
python scrape_yyt_price.py   # Yuyutei prices   → cards_yyt_price.csv
```

## Output Files

| File | Description |
|------|-------------|
| `cards_vg_jp.csv` | JP card data: kanji name, stats, image URLs |
| `cards_vg_wiki.csv` | Wiki data: English name, grade, nation, rarity |
| `cards_mapped.csv` | JP data joined with English names |
| `cards_yyt_price.csv` | Yuyutei prices by card number and rarity |
| `cards_final.csv` | Complete dataset: JP + EN name + price |
| `boosters.json` | Pipeline state: processed expansion IDs |
| `wiki_kanji_cache.json` | Cached kanji lookups from wiki card pages |

## Scope

Covers DZ-era sets (2024+):
- Booster sets: `VG-DZ-BT` / `VGE-DZ-BT`
- Special series: `VG-DZ-SS`

## Setup

```bash
pip install -r requirements.txt
```
