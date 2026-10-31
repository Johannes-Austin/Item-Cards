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

### Regular (non-magic) items
**`RunMundaneGather.BAT`** runs `MundaneGather.py`.

- Reads the wiki's equipment pages (adventuring gear, armor, weapons, firearms, explosives, poisons and tools) and writes **`mundaneItems.csv`**. Each poison's own page is downloaded too, for its rules text.
- Uses the same columns as `items.csv`. Rarity is `mundane`, and the **Attunement** column holds the **cost**, since these items never need attunement. Weight, damage, armor class and similar stats are bold lines at the start of the description.
- Saves the pages in `raw_pages\` like step 2. Run `RunMundaneGather.BAT --cached` to re-parse them without downloading.
- Step 3 embeds this file too (if it exists). Run step 3 afterwards.

### Spells
**`RunSpellGather.BAT`** runs `SpellGather.py`.

- Reads the wiki's spell list, then every spell's own page, and writes **`spells.csv`**. That's about 570 pages, so it takes a few minutes.
- Uses the `items.csv` columns plus `Level` (0 for cantrips), `School`, `CastingTime`, `Range`, `Components`, `Duration` and `Classes`. Rarity is `spell`.
- The card prints the casting time, range, components and duration above the spell's text, and the classes where attunement would go. Each level has its own card background (see "Spell card backgrounds" below).
- A few spell pages have no class list; their classes are filled in from the wiki's class spell list pages.
- Unearthed Arcana spells are included, with "(UA)" in their names and their UA source. Untick those sources in the page's source filter to hide them.
- Saves the pages in `raw_pages\`. Run `RunSpellGather.BAT --cached` to re-parse them without downloading.
- Step 3 embeds this file too (if it exists). Run step 3 afterwards.

### 3. Build the single HTML file
**`BuildSingleHtml.BAT`** runs `build_single_html.py`.

- Embeds `items.csv` (magic items), `mundaneItems.csv` (regular items) and `spells.csv` (spells) into `template.html` and creates **`..\index.html`** in the main CardHTML folder.
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
| `mundaneItems.csv` | The scraped regular (non-magic) items, from `MundaneGather.py` |
| `spells.csv` | The scraped spells, from `SpellGather.py` |
| `raw_pages\` | Saved HTML of every downloaded wiki page |
| `template.html` | Card maker page source (step 3 embeds the items into it) |
| `InstallPython.BAT`, `python-3.12.1-amd64.exe`, `my_env\`, `offline_packages\`, `automatic_packages\` | Python setup. Run `InstallPython.BAT` if a `.BAT` says the environment is missing |

## Things to know

- **Always run step 3 after step 2.** `index.html` only contains the data from the last build.
- **Other / Varies items:** a few items have no standard rarity on the wiki (for example "unique" or "unknown"). They appear under "Other / Varies" in the page and use the common card background.
- **Tabs:** under the search box, **Magic Items**, **Regular Items** and **Spells** switch the item list. The card preview and print queue are shared, so one print can mix them, and clicking a queued item switches to its tab. Magic items filter by rarity and regular items by category (gear, weapons, armor, ammunition, tools, poisons, explosives); the category comes from the item's Type.
- **Regular items in your own CSVs or the editor:** an item whose Rarity is `mundane` is a regular item. It goes in the Regular Items tab, prints on the common card, and its Attunement column is its cost. In the editor, the **Regular Item** tab has a Cost field. Create Item on the Regular Items list tab starts there.
- **Spell filters:** drag either end of the **Level** slider to pick a range of levels (cantrips to 9th). Class pills, and the School, Casting Time and Range pills under **More filters**, show everything until you pick some, then show spells matching any of the ones picked. Components (V, S, M), Concentration and Ritual can each be Any, Has/Yes or Without/No. **Reset filters** clears them all. The C and R tags in the list mark concentration and ritual spells.
- **Spells in your own CSVs or the editor:** a row whose Rarity is `spell` is a spell; include the spell columns (`Level`, `School`, `CastingTime`, `Range`, `Components`, `Duration`, `Classes`) so it filters properly. In the editor, the **Spell** tab has those fields (plus a Ritual checkbox). You only type the school; the card's "5th-level Evocation" line is made from the level and school.
- **Generate Queue** (in the print queue) opens a window with three tabs, each making a random list you can trim before adding it to the queue:
  - **Shop:** how many items, the kind of shop (general store, blacksmith, bowyer, alchemist, jeweler, arcane supplies, magic shop or anything) and how wealthy it is. Wealth sets how much of the stock is magic, which rarities show up, and the most a regular item can cost.
  - **Loot:** how many items, the party's level (which rarities show up, roughly following the DMG's treasure tables), the kind of loot, and whether regular gear is mixed in.
  - **Spellbook:** how many spells, the class, a level range and a school. Spells are spread evenly over the levels. Unearthed Arcana spells are left out unless ticked.
  - **✖** on an entry removes it and puts a new random one in its place (never one you removed). **Start Over** rerolls the whole list, and **Add to Queue** adds them all. Click a name to see its details.
- **Source filter:** the page builds its source list (with item counts) from the `Source` column, so new books and homebrew CSVs appear automatically. An item with several sources, separated by commas, counts under each one. Slightly different spellings of the same book show up as separate entries, so fix those in the data.
- **Custom items:** **Create Item** (next to the CSV box) and **Customize Card** (under the card preview) open an editor with a live card preview. Its **Magic Item / Regular Item / Spell** tabs pick the kind of card, each with its own fields. New items are marked "custom" in the list. A changed built-in item that keeps its name and rarity is marked "edited" and replaces the original until you choose **Restore Original**. When editing your own card, **Save Changes** updates it and **Save as New Item** keeps it and saves a copy (give the copy a different name or rarity).
- **Loading CSV files:** each row is added as if you had made it with **Create Item**, so it's marked "custom", or "edited" when it matches a built-in item's name and rarity. Every file you load adds to what's already there. A row with the same name and rarity as an item you already added replaces it. **Remove all added items** clears every custom and edited item.
- **Saved in the browser:** custom items and items loaded from CSV files are remembered by the browser that added them (its local storage), so they're still there next visit. They don't carry over to other browsers or computers and aren't added to `items.csv`. **Download added items** saves them all as `my-items.csv` in the same format, which you can load into another browser with "Choose Files" or add to `items.csv`.
- **Copies:** each item in the print queue has a copies box (starting at 1, up to 99). Adding an item that's already in the queue adds a copy instead of a new entry. An item split into several cards is one queue entry, and each copy prints all of its cards. The queue count is the total number of cards that will print.
- **Saving a print queue:** **Download Queue** saves the queue as `print-queue.csv` (one row per queue entry, with a `Copies` column plus the `items.csv` columns). **Load Queue** adds a file's rows to the end of the queue; a missing or blank `Copies` means 1. Rows that match an item in the list use that item. Other rows print from the file's own details, so the file works anywhere. A hand-made file only needs a Name column; add Rarity to pick between items with the same name.
- **Check the results after a big re-run.** Search the page for a few items you know have variants, such as Ioun Stone, Potion of Giant Strength and Ammunition, and make sure they came out as separate items.
- **The images are not embedded.** `index.html` needs `common.png`, `uncommon.png`, `rare.png`, `very-rare.png`, `legendary.png` and `artifact.png` in the same folder, plus the spell cards `spell-cantrip.png` and `spell-1.png` to `spell-9.png`.
- **Spell card backgrounds** are made from `common.png` by `make_spell_cards.ps1`: each level gets its own border color, a light tint of it on the parchment, and a faint magic circle behind the text. To change a level's color, edit the list at the top of the script and run `powershell -ExecutionPolicy Bypass -File make_spell_cards.ps1` from this folder.
