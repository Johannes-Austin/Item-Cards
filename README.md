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

### Open5e magic items and spells (third-party books)
**`RunOpen5eGather.BAT`** runs `Open5eGather.py`.

- Downloads the magic items and spells from the Open5e API (https://api.open5e.com), which serves openly licensed books: Kobold Press's *Vault of Magic*, *Deep Magic*, *Tome of Heroes* and *Warlock Archives* (Open Gaming License), *Level Up Advanced 5e* (Creative Commons) and a few others.
- Writes **`open5eItems.csv`** with only the items `items.csv` doesn't already have. A name that matches an item on the wiki, or a wiki item's variants (Level Up's single "Ioun Stone" entry), is skipped.
- Writes **`open5eSpells.csv`** with only the spells `spells.csv` doesn't already have (a finished version of a wiki "(UA)" spell counts as had). It has the spell columns too, written like the wiki's spells: "Concentration, up to 1 minute", "V, S, M (a magnifying lens)", and "At Higher Levels" at the end of the text. Kobold Press's own classes (Herald, Anti-Paladin) show up in the class filter; about 90 spells list no class.
- The whole SRD is skipped, since the wiki already has all of it.
- Uses the `items.csv` / `spells.csv` columns. Source is the book's title, URL is the Open5e page and Notes says which license the book uses.
- Saves the downloads in `raw_pages\open5e_*.json`. Run `RunOpen5eGather.BAT --cached` to rebuild the CSVs from them without downloading.
- Step 3 embeds both files too (if they exist) as the page's **secondary entries**. Run step 3 afterwards.

### The Griffon's Saddlebag items (personal, locked with a passphrase)
`GriffonsGather.py` turns The Griffon's Saddlebag's item list into **`griffonsSaddlebag.csv`**. These items are the creator's paid content (their Ledger+ subscription), so they're for your own printing only:

- `.gitignore` keeps the CSV out of the repository.
- Step 3 embeds them in `index.html` **encrypted** (AES-256, with a key made from a passphrase). Anyone can see the site, but without the passphrase the items are unreadable data.
- In the page, **🔒 Unlock personal items** (under the item counts) asks for the passphrase. The items then appear as secondary entries with the source "The Griffon's Saddlebag". That browser remembers the unlock, so on each PC you type it once; **Lock** makes it forget.
- The passphrase is never saved anywhere. Step 3 asks for it (twice) when it runs. Press Enter instead to keep the encrypted items already in `index.html` (handy when only other things changed). To use a new passphrase, just type a new one; every browser then needs to unlock again.
- A long passphrase of several unrelated words is much harder to guess, since anyone can download the encrypted copy and try passwords against it.

To refresh it:
1. Sign in to https://ledger.thegriffonssaddlebag.com and open its `/text` page, which lists every item.
2. Save that page's items as `raw_pages\griffons_ledger.json`: a list of `{name, meta, date, html, links}` from each item's `<section>` (`meta` is the "Wondrous item, rare (requires attunement)" line, `html` is the item's text).
3. Run `python GriffonsGather.py`.

- The rules text is converted like the wiki items (bold, italics, lists and tables). Source is "The Griffon's Saddlebag" and URL is the item's art post on Patreon.
- About 40 items list several rarities ("common or uncommon", "varies"); they show under Other / Varies. The script lists them.
- An item with the same name and rarity as a built-in item gets " (Griffon's Saddlebag)" added to its name, so loading the file doesn't replace the other one.

### 3. Build the single HTML file
**`BuildSingleHtml.BAT`** runs `build_single_html.py`.

- Embeds `items.csv` (magic items), `mundaneItems.csv` (regular items), `spells.csv` (spells), and `open5eItems.csv` and `open5eSpells.csv` (secondary items and spells), plus `griffonsSaddlebag.csv` encrypted (see above), into `template.html` and creates **`..\index.html`** in the main CardHTML folder.
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
| `open5eItems.csv` | Magic items from Open5e's third-party books that `items.csv` doesn't have, from `Open5eGather.py` |
| `open5eSpells.csv` | Spells from Open5e's third-party books that `spells.csv` doesn't have, from `Open5eGather.py` |
| `raw_pages\` | Saved HTML of every downloaded wiki page |
| `template.html` | Card maker page source (step 3 embeds the items into it) |
| `InstallPython.BAT`, `python-3.12.1-amd64.exe`, `my_env\`, `offline_packages\`, `automatic_packages\` | Python setup. Run `InstallPython.BAT` if a `.BAT` says the environment is missing |

## Things to know

- **Always run step 3 after step 2.** `index.html` only contains the data from the last build.
- **Other / Varies items:** a few items have no standard rarity on the wiki (for example "unique" or "unknown"). They appear under "Other / Varies" in the page and use the common card background.
- **Standard, secondary and user entries:** the line under the CSV box counts the page's items. Standard entries come from the wiki (`items.csv`, `mundaneItems.csv`, `spells.csv`), secondary entries from third-party books (`open5eItems.csv`, `open5eSpells.csv`), and user entries are your own custom, edited and CSV-loaded items. Untick **Include secondary entries** to hide the secondary ones everywhere: the lists, the source filter and Generate Queue. The browser remembers the choice.
- **Tabs:** under the search box, **Magic Items**, **Regular Items** and **Spells** switch the item list. The card preview and print queue are shared, so one print can mix them, and clicking a queued item switches to its tab. Magic items filter by rarity and regular items by category (gear, weapons, armor, ammunition, tools, poisons, explosives); the category comes from the item's Type.
- **Regular items in your own CSVs or the editor:** an item whose Rarity is `mundane` is a regular item. It goes in the Regular Items tab, prints on the common card, and its Attunement column is its cost. In the editor, the **Regular Item** tab has a Cost field. Create Item on the Regular Items list tab starts there.
- **Spell filters:** drag either end of the **Level** slider to pick a range of levels (cantrips to 9th). Class pills, and the School, Casting Time and Range pills under **More filters**, show everything until you pick some, then show spells matching any of the ones picked. Components (V, S, M), Concentration and Ritual can each be Any, Has/Yes or Without/No. **Reset filters** clears them all. The C and R tags in the list mark concentration and ritual spells.
- **Spells in your own CSVs or the editor:** a row whose Rarity is `spell` is a spell; include the spell columns (`Level`, `School`, `CastingTime`, `Range`, `Components`, `Duration`, `Classes`) so it filters properly. In the editor, the **Spell** tab has those fields (plus a Ritual checkbox). You only type the school; the card's "5th-level Evocation" line is made from the level and school.
- **Generate Queue** (in the print queue) opens a window with three tabs, each making a random list you can trim before adding it to the queue:
  - **Shop:** how many items, the kind of shop (general store, blacksmith, bowyer, alchemist, jeweler, tailor, baubles, arcane supplies, magic shop or anything) and how wealthy it is. Wealth sets how much of the stock is magic, which rarities show up, and the most a regular item can cost.
    - Each shop stocks items by Type (a blacksmith sells magic weapons, armor and shields) plus a list of **favored name words** (gauntlets, bracers, helm, horseshoe... for the blacksmith). Favored items are added to the stock and are **twice as likely** to come up, so Gauntlets of Ogre Power (a "Wondrous Item") can turn up at a blacksmith without the shop running short. A favored word never brings in a potion or scroll the shop doesn't otherwise sell.
    - The **tailor** sells light armor, clothes, bedding and bags, and magic light armor and clothing (cloaks, robes, boots, hats, gloves...), favoring cloaks and robes. **Baubles** sells wondrous items and rings, musical instruments, games and trinkets, favoring figurines, beads, stones, decks and similar curios.
    - The shops and their word lists are `SHOPS` in `template.html`.
  - **Loot:** how many items, the party's level (which rarities show up, roughly following the DMG's treasure tables), the kind of loot, and whether regular gear is mixed in.
  - **Spellbook:** how many spells, the class, a level range and a school. Spells are spread evenly over the levels. Unearthed Arcana spells are left out unless ticked.
  - **✖** on an entry removes it and puts a new random one in its place (never one you removed). **Start Over** rerolls the whole list, and **Add to Queue** adds them all. Click an entry to see its card on the right (on phones, the card replaces the list until **Back to list**); click the card for full details.
- **Source filter:** the page builds its source list (with item counts) from the `Source` column, so new books and homebrew CSVs appear automatically. An item with several sources, separated by commas, counts under each one. Slightly different spellings of the same book show up as separate entries. The scrapers correct the ones the wiki has (`SOURCE_FIXES` in `DataGather.py`, which `SpellGather.py` uses too): add a line there if a new one turns up, then re-run the scraper with `--cached`. A source written "Book A/Book B" is split into both books.
- **Custom items:** **Create Item** (next to the CSV box) and **Customize Card** (under the card preview) open an editor with a live card preview. Its **Magic Item / Regular Item / Spell** tabs pick the kind of card, each with its own fields. New items are marked "custom" in the list. A changed built-in item that keeps its name and rarity is marked "edited" and replaces the original until you choose **Restore Original**. When editing your own card, **Save Changes** updates it and **Save as New Item** keeps it and saves a copy (give the copy a different name or rarity).
- **Loading CSV files:** each row is added as if you had made it with **Create Item**, so it's marked "custom", or "edited" when it matches a built-in item's name and rarity. Every file you load adds to what's already there. A row with the same name and rarity as an item you already added replaces it. **Remove all added items** clears every custom and edited item.
- **Saved in the browser:** custom items and items loaded from CSV files are remembered by the browser that added them (its local storage), so they're still there next visit. They don't carry over to other browsers or computers and aren't added to `items.csv`. **Download added items** saves them all as `my-items.csv` in the same format, which you can load into another browser with "Choose Files" or add to `items.csv`.
- **Copies:** each item in the print queue has a copies box (starting at 1, up to 99). Adding an item that's already in the queue adds a copy instead of a new entry. An item split into several cards is one queue entry, and each copy prints all of its cards. The queue count is the total number of cards that will print.
- **Saving a print queue:** **Download Queue** saves the queue as `print-queue.csv` (one row per queue entry, with a `Copies` column plus the `items.csv` columns). **Load Queue** adds a file's rows to the end of the queue; a missing or blank `Copies` means 1. Rows that match an item in the list use that item. Other rows print from the file's own details, so the file works anywhere. A hand-made file only needs a Name column; add Rarity to pick between items with the same name.
- **Check the results after a big re-run.** Search the page for a few items you know have variants, such as Ioun Stone, Potion of Giant Strength and Ammunition, and make sure they came out as separate items.
- **The images are not embedded.** `index.html` needs `common.png`, `uncommon.png`, `rare.png`, `very-rare.png`, `legendary.png` and `artifact.png` in the same folder, plus the spell cards `spell-cantrip.png` and `spell-1.png` to `spell-9.png`.
- **Spell card backgrounds** are made from `common.png` by `make_spell_cards.ps1`: each level gets its own border color, a light tint of it on the parchment, and a faint magic circle behind the text. To change a level's color, edit the list at the top of the script and run `powershell -ExecutionPolicy Bypass -File make_spell_cards.ps1` from this folder.
