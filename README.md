# D&D Magic Item Card Maker: Data Guide

This folder builds the item data and the one-file card maker page.

```
CardHTML\
  index.html              <- the finished single-file card maker (created by step 3)
  common.png, rare.png... <- card background images (must stay next to index.html)
  WebExtraction\          <- you are here
    template.html         <- the card maker page source (edit this one)
```

## The normal routine

Run these in order, by double-clicking the `.BAT` files in this folder.

### 1. Find new items (optional, occasionally)
**`RunUpdateItemNames.BAT`** runs `update_item_names.py`.

- Checks the wiki's Wondrous Items index for pages that aren't in `itemNames.csv` yet.
- Adds any new ones to `itemNames.csv` (the master list of items to scrape) and records them in `newItemNames.csv`.
- Only needed when the wiki gets new items, such as after a new book. Skip it otherwise.

### 2. Download and parse the items
**`RunDataGather.BAT`** runs `DataGather.py`.

- Reads `itemNames.csv`, downloads every item page, and rebuilds **`items.csv`** from scratch.
- Saves a copy of every downloaded page in `raw_pages\` so you can look at the original HTML.
- Slow, because it downloads everything. Run it when you want fresh data from the wiki.

**`RunDataGatherCached.BAT`** does the same parsing but uses the pages already saved in `raw_pages\` instead of downloading them.

- Fast. Use it after changing the parsing code in `DataGather.py`.
- Any page not saved yet is downloaded, then saved.

### 3. Build the single HTML file
**`BuildSingleHtml.BAT`** runs `build_single_html.py`.

- Embeds `items.csv` into `template.html` and creates **`..\index.html`** in the main CardHTML folder.
- Open `index.html` in a browser, or put it and the PNG images on GitHub Pages.
- The page's "choose file" box still lets people add more items from their own CSV. The built-in items are kept.

Use a different CSV with `BuildSingleHtml.BAT --csv MyOtherItems.csv`.

## Which file to edit

| To change... | Edit this file | Then run |
|---|---|---|
| How items are parsed (names, rarities, splitting) | `DataGather.py` | step 2 (cached is fine), then step 3 |
| How the card page looks or works | `template.html` (this folder) | step 3 |
| The list of items to scrape | `itemNames.csv` | step 2, then step 3 |

`template.html` is the source that step 3 uses. Never edit `..\index.html` directly: it is overwritten every time you build.

## Files in this folder

| File | What it is |
|---|---|
| `itemNames.csv` | Master list of item page URLs and names to scrape |
| `newItemNames.csv` | Log of new items found by step 1. Only grows; clear it whenever you like |
| `items.csv` | The scraped item data (output of step 2, input to step 3) |
| `raw_pages\` | Saved HTML of every downloaded wiki page |
| `template.html` | Card maker page source (step 3 embeds the items into it) |
| `InstallPython.BAT`, `python-3.12.1-amd64.exe`, `my_env\`, `offline_packages\`, `automatic_packages\` | Python setup. Run `InstallPython.BAT` if a `.BAT` says the environment is missing |

## Things to know

- **Always run step 3 after step 2.** `index.html` only contains the data from the last build.
- **Other / Varies items:** a few items have no standard rarity on the wiki (for example "unique" or "unknown"). They appear under "Other / Varies" in the page and use the common card background.
- **Check the results after a big re-run.** Search the page for a few items you know have variants, such as Ioun Stone, Potion of Giant Strength and Ammunition, and make sure they came out as separate items.
- **The images are not embedded.** `index.html` needs `common.png`, `uncommon.png`, `rare.png`, `very-rare.png`, `legendary.png` and `artifact.png` in the same folder.
