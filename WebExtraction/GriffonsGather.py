"""Turns a saved copy of The Griffon's Saddlebag's Ledger+ item list into griffonsSaddlebag.csv.

The Ledger+ (https://ledger.thegriffonssaddlebag.com) is the creator's paid item database. Its /text page lists every
item you have access to. With that page open (and signed in), its items are saved as raw_pages/griffons_ledger.json:
a list of {name, meta, date, html, links}, where meta is the "Wondrous item, rare (requires attunement)" line and html
is the item's text.

griffonsSaddlebag.csv uses the items.csv columns. It is for your own use: load it in the card maker with
"Choose Files". It is NOT embedded in index.html, and .gitignore keeps it out of the repository, since the items are
the creator's paid content.

    python GriffonsGather.py
"""
import csv
import json
import os
import re
import sys

from bs4 import BeautifulSoup as bs

from DataGather import tags_to_markdown, table_to_markdown, headers

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
in_file = os.path.join(BASE_DIR, "raw_pages", "griffons_ledger.json")
out_file = os.path.join(BASE_DIR, "griffonsSaddlebag.csv")
SOURCE = "The Griffon's Saddlebag"

STANDARD_RARITIES = {"common", "uncommon", "rare", "very rare", "legendary", "artifact"}
# The type ends at the first ", " that is followed by a rarity ("Ammunition (arrow, bolt, or firearm bullet), rare")
META = re.compile(r'^(?P<type>.*?),\s*(?P<rest>(?:very rare|uncommon|common|rare|legendary|artifact|unique|rarity\b|varies\b).*)$', re.I)


def parse_meta(meta):
    """'Weapon (longsword), legendary (requires attunement)' -> ('Weapon (longsword)', 'legendary', 'requires attunement')"""
    match = META.match(meta.strip())
    if not match:
        return meta.strip(), "", ""
    rest = match.group("rest")
    attune = re.search(r'\((requires attunement[^)]*)\)', rest, re.I)
    rarity = (rest[:attune.start()] + rest[attune.end():]) if attune else rest
    rarity = re.sub(r'\s+', ' ', rarity).strip().strip(',').strip().lower()
    if rarity == "rarity varies":
        rarity = "varies"
    return match.group("type").strip(), rarity, attune.group(1).strip() if attune else ""


def description(html):
    """The item's text in the items.csv style: one line per paragraph, **bold**, *italic*, "- " list items, tables"""
    soup = bs(html, "html.parser")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    root = soup.find("div") or soup
    lines = []
    for el in root.find_all(["p", "ul", "ol", "table", "blockquote"], recursive=False) or [root]:
        if el.name == "table":
            lines.append(table_to_markdown(el))
        elif el.name in ("ul", "ol"):
            lines.extend("- " + tags_to_markdown(li) for li in el.find_all("li", recursive=False))
        else:
            text = tags_to_markdown(el)
            if text:
                lines.append(text)
    return "\n".join(lines)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    with open(in_file, encoding="utf-8") as f:
        items = json.load(f)
    # The page's built-in items (wiki and Open5e). An item with the same name and rarity would replace one of them when
    # loaded, so it gets " (Griffon's Saddlebag)" added to its name instead.
    builtin = set()
    for name in ("items.csv", "open5eItems.csv"):
        path = os.path.join(BASE_DIR, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8-sig") as f:
                builtin |= {(r["Name"].strip().lower(), r["Rarity"].strip().lower()) for r in csv.DictReader(f)}

    rows, odd_rarity, clashes, seen = [], [], [], set()
    for item in items:
        item_type, rarity, attunement = parse_meta(item["meta"])
        name = item["name"].strip()
        key = (name.lower(), rarity)
        if key in seen:
            continue
        seen.add(key)
        if key in builtin:
            clashes.append(name)
            name += " (Griffon's Saddlebag)"
        if rarity not in STANDARD_RARITIES:
            odd_rarity.append(f"{item['name']} ({rarity or item['meta']})")
        url = next((link["href"] for link in item.get("links", []) if link.get("text") == "Art"), "")
        rows.append([name, rarity, attunement, item_type, SOURCE, description(item["html"]), url,
                     "From The Griffon's Saddlebag's Ledger+ (personal use)"])

    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    print(f"Wrote {len(rows)} of {len(items)} items to {out_file}")
    if clashes:
        print(f"\nRenamed {len(clashes)} that share a name and rarity with a built-in item: {', '.join(clashes)}")
    if odd_rarity:
        print(f"\n{len(odd_rarity)} have no single standard rarity (they show under Other / Varies):")
        print("  " + "\n  ".join(odd_rarity))
