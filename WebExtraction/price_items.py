"""Magic item prices: a power rating (1-10) for each item within its rarity, turned into a price by a fixed formula.

The ratings are in magicPrices.csv (items.csv and open5eItems.csv) and griffonsPrices.csv (the Griffon's Saddlebag
items; .gitignore keeps it out of the repository like griffonsSaddlebag.csv). Each row: Name, Rarity, Rating, Note
(the reason), and an optional Price that overrides the formula. The build reads the prices from here, so re-running
a scraper never loses them.

    python price_items.py list items.csv 0 80      # items to rate, short form (from row 0, 80 of them)
    python price_items.py check                     # which items have no rating yet
    python price_items.py prices                    # the rating -> price table

Rating 1-2: a novelty or very situational; 3-4: niche but real; 5-6: typical for its rarity; 7-8: strong, sought
after; 9-10: exceptional for its rarity. Below 1 or above 10: worth less or more than its rarity says (the price
carries on into the band below or above). One-use items (potions, scrolls, ammunition) are rated as what one use is
worth. Artifacts are priceless.
"""
import csv
import math
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRICE_FILES = {"items.csv": "magicPrices.csv", "open5eItems.csv": "magicPrices.csv", "griffonsSaddlebag.csv": "griffonsPrices.csv"}
COLUMNS = ["Name", "Rarity", "Rating", "Price", "Note"]

# The DMG's price range for each rarity (legendary capped, since the DMG gives no top)
BANDS = {"common": (50, 100), "uncommon": (100, 500), "rare": (500, 5000), "very rare": (5000, 50000), "legendary": (50000, 200000)}
RARITY_WORDS = ["very rare", "uncommon", "common", "rare", "legendary", "artifact"]


def item_key(name, rarity):
    return f"{name.strip().lower()}|{rarity.strip().lower()}"


def base_rarity(rarity):
    """'uncommon (+1), rare (+2)' -> 'uncommon' (the lowest it can be); '' if it names no rarity"""
    found = [(rarity.lower().find(w), w) for w in RARITY_WORDS if w in rarity.lower()]
    # "very rare" contains "rare": prefer the longer match at the same place
    found = sorted(found, key=lambda f: (f[0], -len(f[1])))
    return found[0][1] if found else ""


def nice(amount):
    """Rounds to a price a shopkeeper would say: 2 significant figures, to 5s under 100"""
    if amount < 100:
        return int(round(amount / 5) * 5)
    digits = int(math.floor(math.log10(amount))) - 1
    step = 10 ** digits
    return int(round(amount / step) * step)


def rating_price(rarity, rating):
    """The price for a rating within the rarity's band: 1-10 spread evenly (on a log scale) from the bottom of the band
    to the top. A rating below 1 or above 10 carries on past the band, for an item worth less or more than its rarity
    says (the Talarith, legendary but useless to anyone but its maker, is rated -2). None if priceless."""
    rarity = base_rarity(rarity)
    if rarity == "artifact" or rarity not in BANDS:
        return None
    # Past either end of the scale, carry on into the next rarity's band (rating 1 of a rarity is rating 10 of the one
    # below), so a one-use legendary potion and a very rare one sit on the same curve
    order = list(BANDS)
    i, r = order.index(rarity), min(max(float(rating), -20), 25)
    while r < 1 and i > 0:
        i, r = i - 1, r + 9
    while r > 10 and i < len(order) - 1:
        i, r = i + 1, r - 9
    low, high = BANDS[order[i]]
    return nice(max(low * (high / low) ** ((r - 1) / 9), 5))


def price_text(rarity, rating, override=""):
    if override.strip():
        return override.strip()
    if base_rarity(rarity) == "artifact":
        return "Priceless"
    price = rating_price(rarity, rating)
    return f"{price:,} gp" if price else ""


def read(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def short(text, length=320):
    text = re.sub(r'\*+|\|', ' ', text or '')
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:length] + ("…" if len(text) > length else "")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")  # item names like Járngreipr, piped in for add and rerate
    command = sys.argv[1] if len(sys.argv) > 1 else "check"
    if command == "list":
        source, start, count = sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
        rated = {item_key(r["Name"], r["Rarity"]) for r in read(os.path.join(BASE_DIR, PRICE_FILES[source]))}
        rows = read(os.path.join(BASE_DIR, source))
        for i, r in enumerate(rows[start:start + count], start):
            mark = "✓" if item_key(r["Name"], r["Rarity"]) in rated else " "
            print(f"{i}{mark} {r['Name']} | {r['Rarity']} | {r['Type']} | {r['Attunement'] or '-'} | {short(r['Description'])}")
    elif command == "todo":
        # The next unrated items of a source, short form: python price_items.py todo items.csv 60
        source, count = sys.argv[2], int(sys.argv[3])
        length = int(sys.argv[4]) if len(sys.argv) > 4 else 210
        rated = {item_key(r["Name"], r["Rarity"]) for r in read(os.path.join(BASE_DIR, PRICE_FILES[source]))}
        todo = [r for r in read(os.path.join(BASE_DIR, source)) if item_key(r["Name"], r["Rarity"]) not in rated]
        for r in todo[:count]:
            print(f"{r['Name']} | {r['Rarity']} | {r['Type']} | {r['Attunement'] or '-'} | {short(r['Description'], length)}")
        print(f"({len(todo) - min(count, len(todo))} more after these)")
    elif command == "check":
        for source, price_file in PRICE_FILES.items():
            rows = read(os.path.join(BASE_DIR, source))
            rated = {item_key(r["Name"], r["Rarity"]) for r in read(os.path.join(BASE_DIR, price_file))}
            missing = [r["Name"] for r in rows if item_key(r["Name"], r["Rarity"]) not in rated]
            print(f"{source}: {len(rows) - len(missing)} of {len(rows)} rated" + (f"; next unrated: {', '.join(missing[:5])}" if missing else ""))
    elif command == "add":
        # Ratings from standard input, one per line: Name | Rarity | Rating | Note [| Price]. A row for an item that
        # already has one replaces it.
        price_file = os.path.join(BASE_DIR, sys.argv[2])
        existing = {item_key(r["Name"], r["Rarity"]): r for r in read(price_file)}
        added = 0
        for line in sys.stdin.read().splitlines():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 4 or not parts[0]:
                continue
            name, rarity, rating, note = parts[:4]
            existing[item_key(name, rarity)] = {"Name": name, "Rarity": rarity, "Rating": rating,
                                                "Price": parts[4] if len(parts) > 4 else "", "Note": note}
            added += 1
        with open(price_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(existing.values())
        print(f"Added {added}; {len(existing)} rated in {os.path.basename(price_file)}")
    elif command == "compare":
        # Random groups of items priced alike (across every source), for checking that the prices are fair against
        # each other: python price_items.py compare 15 5 [seed]. Items with a fixed price are left out.
        import random
        groups, size = int(sys.argv[2]), int(sys.argv[3])
        rng = random.Random(int(sys.argv[4]) if len(sys.argv) > 4 else None)
        pool = []
        for source, price_file in PRICE_FILES.items():
            ratings = {item_key(r["Name"], r["Rarity"]): r for r in read(os.path.join(BASE_DIR, price_file))}
            for r in read(os.path.join(BASE_DIR, source)):
                rated = ratings.get(item_key(r["Name"], r["Rarity"]))
                if rated and not rated["Price"].strip():
                    price = rating_price(r["Rarity"], rated["Rating"])
                    if price:
                        pool.append((price, r, rated))
        pool.sort(key=lambda p: p[0])
        for g in range(groups):
            anchor = rng.choice(pool)[0]
            near = [p for p in pool if anchor / 1.2 <= p[0] <= anchor * 1.2]
            print(f"== Group {g + 1}: about {anchor:,} gp")
            for price, r, rated in rng.sample(near, min(size, len(near))):
                print(f"{r['Name']} | {r['Rarity']} | {rated['Rating']} = {price:,} gp | {r['Type']} | "
                      f"{r['Attunement'] or '-'} | {short(r['Description'], 170)}")
    elif command == "rerate":
        # New ratings from standard input, one per line: Name | Rarity | Rating. Finds the item in whichever price file
        # has it and keeps its note.
        files = {pf: read(os.path.join(BASE_DIR, pf)) for pf in set(PRICE_FILES.values())}
        changed = 0
        for line in sys.stdin.read().splitlines():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 3 or not parts[0]:
                continue
            key = item_key(parts[0], parts[1])
            hits = [r for rows in files.values() for r in rows if item_key(r["Name"], r["Rarity"]) == key]
            if not hits:
                print(f"Not found: {parts[0]} | {parts[1]}")
            for r in hits:
                r["Rating"] = parts[2]
                changed += 1
        for pf, rows in files.items():
            with open(os.path.join(BASE_DIR, pf), "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=COLUMNS)
                writer.writeheader()
                writer.writerows(rows)
        print(f"Changed {changed}")
    elif command == "prices":
        for rarity in BANDS:
            print(f"{rarity:>10}: " + "  ".join(f"{r}={rating_price(rarity, r):,}" for r in range(1, 11)))
