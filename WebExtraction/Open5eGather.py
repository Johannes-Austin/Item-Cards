"""Downloads the magic items and spells from the Open5e API (https://api.open5e.com) into open5eItems.csv and
open5eSpells.csv.

Open5e serves openly licensed 5e content (the SRD, Kobold Press's OGL books, Level Up Advanced 5e...) as JSON.
Items whose name is already in items.csv (the wiki's items), and spells already in spells.csv, are left out, so the
two files only have new ones. The SRD is skipped entirely, since the wiki has all of it.
They use the items.csv / spells.csv columns; Source is the book's title and Notes says which license it was published under.

Run with:  python Open5eGather.py --cached   to reuse the downloads saved in raw_pages instead of downloading again
"""
import csv
import json
import os
import re
import sys

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
API = "https://api.open5e.com/v1"
headers = ["Name", "Rarity", "Attunement", "Type", "Source", "Description", "URL", "Notes"]
SPELL_COLUMNS = ["Level", "School", "CastingTime", "Range", "Components", "Duration", "Classes"]

# Class names as the page's spell filters know them; Open5e spells them a few ways. "Ritual Caster" is a feat, not a class.
CLASS_FIXES = {"sorceror": "Sorcerer", "ritual caster": None}


def path(name):
    return os.path.join(BASE_DIR, name)


def fetch_all(url):
    """Every result of a paged API list"""
    results = []
    while url:
        page = requests.get(url, timeout=60).json()
        results += page["results"]
        url = page.get("next")
        print(f"  {len(results)}/{page['count']}")
    return results


def download(cache_name, fetch):
    """The saved download in raw_pages with --cached, else a fresh one (which is saved)"""
    cache_file = os.path.join(BASE_DIR, "raw_pages", cache_name)
    if "--cached" in sys.argv and os.path.exists(cache_file):
        with open(cache_file, encoding="utf-8") as f:
            return json.load(f)
    data = fetch()
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return data


def name_key(name):
    """'Armor, +1' / 'armor +1' / 'Armor (+1)' -> 'armor 1'; used to spot items we already have"""
    return re.sub(r'[^a-z0-9]+', ' ', name.lower().replace("’", "'").replace("'", "")).strip()


def names_in(csv_name):
    with open(path(csv_name), encoding="utf-8-sig") as f:
        return [row["Name"] for row in csv.DictReader(f)]


def new_entries(entries, have):
    """The entries that aren't in the SRD, in `have`, or a second copy in another Open5e book; and how many were skipped"""
    kept, seen = [], set()
    for entry in entries:
        key = name_key(entry["name"])
        if entry["document__slug"] == "wotc-srd" or key in have or key in seen:
            continue
        seen.add(key)
        kept.append(entry)
    return kept, len(entries) - len(kept)


def write_csv(csv_name, columns, rows):
    with open(path(csv_name), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)


def attunement(value):
    """Open5e has '', 'requires attunement' or 'requires attunement by a cleric'"""
    value = (value or "").strip()
    return "" if value.lower() in ("", "no", "false") else value


def license_note(documents, entry):
    return f"Open5e: {documents.get(entry['document__slug'], {}).get('license', 'see source')}"


def fix_markdown(text):
    """Open5e's text is Markdown, but the card maker only knows *italic* and **bold**. Level Up's text italicises
    game terms with underscores, sometimes unevenly ("__levitate_ "), and escapes some punctuation ("d8\\.").
    '_prone_ , and' -> '*prone*, and'"""
    text = re.sub(r'\\([^\w\s])', r'\1', text)
    text = re.sub(r'(?<![\w_])_{1,2}([^_\n]+?)_{1,2}(?![\w_])', lambda m: f"*{m.group(1).strip()}*", text)
    # A closing underscore a letter or two early: "_The Traveling Ches_t" -> "*The Traveling Chest*" and
    # "“_tried to eat m_e”" -> "“*tried to eat me*”", but "_The Song of Creation i_s eternal" (the sentence carries on,
    # so the next word started inside) -> "*The Song of Creation* is eternal"
    def early_close(m):
        inside, rest = m.group(1).strip(), m.group(2)
        word = re.search(r'\s(\w{1,2})$', inside)
        carries_on = re.match(r' \w', m.string[m.end():])
        return f"*{inside[:word.start()]}* {word.group(1)}{rest}" if word and carries_on else f"*{inside}{rest}*"
    text = re.sub(r'(?<![\w_])_([^_\n]+?)_(\w{1,3})\b', early_close, text)
    text = re.sub(r'(?<=\*) +(?=[,.;:)])', '', text)
    # Links to other Open5e pages ("[true seeing](https://api.open5e.com/spells/true-seeing)") -> "*true seeing*"
    text = re.sub(r'\[([^\]\n]+)\]\([^)\n]*\)', r'*\1*', text)
    # "* " list items -> "• " (the cards would read the "*" as the start of italics), also "*You can..." with no space
    text = re.sub(r'^([ \t]*)\* ', r'\1• ', text, flags=re.M)
    text = re.sub(r'^([ \t]*)\*(?=[A-Z])(?![^\n]*\*)', r'\1• ', text, flags=re.M)
    # Kobold Press marks Deep Magic spells with "*" ("living shadows* (5 charges)"), which the cards would read as
    # italics between two marks: those items have no real italics, so the marks become daggers
    if re.search(r'marked with an asterisk \(\*\)', text):
        text = text.replace('an asterisk (*)', 'a dagger (†)').replace('*', '†')
    text = re.sub(r'\n[ \t]*\n(?:[ \t]*\n)+', '\n\n', text)   # at most one blank line in a row
    return re.sub(r'[ \t]{2,}', ' ', text).strip()


def item_row(item, documents):
    return [item["name"].strip(), (item.get("rarity") or "").strip().lower(), attunement(item.get("requires_attunement")),
            (item.get("type") or "").strip(), item.get("document__title", "").strip(), fix_markdown(item.get("desc") or ""),
            f"https://open5e.com/magic-items/{item['slug']}", license_note(documents, item)]


def ordinal(n):
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n, 'th') }"


def spell_row(spell, documents):
    """The spells.csv columns, written the way SpellGather.py writes the wiki's spells"""
    level = int(spell.get("level_int") or 0)
    school = (spell.get("school") or "").strip().title()
    ritual = spell.get("ritual") == "yes"
    item_type = (f"{school} Cantrip" if level == 0 else f"{ordinal(level)}-level {school}") + (" (Ritual)" if ritual else "")

    # Paragraphs are one line each in spells.csv, with "At Higher Levels" as a bold line at the end
    description = re.sub(r'\n\s*\n+', '\n', fix_markdown(spell.get("desc") or ""))
    if (spell.get("higher_level") or "").strip():
        description += "\n**At Higher Levels.** " + re.sub(r'\n\s*\n+', '\n', fix_markdown(spell["higher_level"]))

    components = (spell.get("components") or "").strip()
    if (spell.get("material") or "").strip() and "M" in components:
        components += f" ({spell['material'].strip()})"
    duration = (spell.get("duration") or "").strip()
    if spell.get("concentration") == "yes" and "concentration" not in duration.lower():
        duration = "Concentration, " + duration[0].lower() + duration[1:] if duration else "Concentration"

    classes = []
    for name in (spell.get("dnd_class") or "").split(","):
        name = CLASS_FIXES.get(name.strip().lower(), name.strip())
        if name and name not in classes:
            classes.append(name)

    return [spell["name"].strip(), "spell", "", item_type, spell.get("document__title", "").strip(), description,
            f"https://open5e.com/spells/{spell['slug']}", license_note(documents, spell),
            str(level), school, (spell.get("casting_time") or "").strip(), (spell.get("range") or "").strip(),
            components, duration, ", ".join(classes)]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print("Reading the Open5e books...")
    documents = download("open5e_documents.json", lambda: {d["slug"]: d for d in fetch_all(f"{API}/documents/?limit=100")})

    print("Reading the Open5e magic items...")
    items = download("open5e_magicitems.json", lambda: fetch_all(f"{API}/magicitems/?limit=500"))
    names = names_in("items.csv")
    have = {name_key(name) for name in names}
    # Items the wiki splits into variants ("Ioun Stone (Awareness)", "Belt of Giant Strength, Hill") count as had
    # under their plain name too, so Level Up's one "Ioun Stone" entry isn't added beside them
    have |= {name_key(re.split(r',\s|\s\(', name)[0]) for name in names}
    kept, skipped = new_entries(items, have)
    write_csv("open5eItems.csv", headers, [item_row(item, documents) for item in kept])
    print(f"{len(items)} Open5e magic items, {skipped} in the SRD, already in items.csv or repeated.")
    print(f"Wrote {len(kept)} new items to {path('open5eItems.csv')}\n")

    print("Reading the Open5e spells...")
    spells = download("open5e_spells.json", lambda: fetch_all(f"{API}/spells/?limit=500"))
    # The wiki's Unearthed Arcana spells end in "(UA)"; the finished version of a UA spell counts as had too
    have = {name_key(re.sub(r'\s*\(UA\)\s*$', '', name)) for name in names_in("spells.csv")}
    kept, skipped = new_entries(spells, have)
    write_csv("open5eSpells.csv", headers + SPELL_COLUMNS, [spell_row(spell, documents) for spell in kept])
    print(f"{len(spells)} Open5e spells, {skipped} in the SRD, already in spells.csv or repeated.")
    print(f"Wrote {len(kept)} new spells to {path('open5eSpells.csv')}")
