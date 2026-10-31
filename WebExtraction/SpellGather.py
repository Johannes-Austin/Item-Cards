"""Scrapes the wiki's spell list and every spell's own page into spells.csv.

The spell list (https://dnd5e.wikidot.com/spells) has one table per level with a link to each spell's page.
Each spell page has the source, a "3rd-level evocation (ritual)" line, the casting time, range, components
and duration, the spell's text, and a "Spell Lists." line naming the classes.

spells.csv has the items.csv columns, so spells use the same cards, plus spell columns the page filters on:
  Rarity      "spell"
  Type        "3rd-level Evocation" / "Evocation Cantrip" (with "(Ritual)" for rituals)
  Description the spell's text, including "At Higher Levels" (the card adds the casting time, range... above it)
  Level       0 for cantrips, else 1-9
  School, CastingTime, Range, Components, Duration, Classes ("Sorcerer, Wizard")

Run with:  python SpellGather.py --cached   to reuse the pages saved in raw_pages instead of downloading them again
"""
import csv
import os
import re
import sys
import time

from bs4 import BeautifulSoup as bs

# Downloading (and the raw_pages cache, including --cached) works the same as for magic items
from DataGather import fetch_page, tags_to_markdown, table_to_markdown, headers

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
csv_file = os.path.join(BASE_DIR, "spells.csv")
SITE = "https://dnd5e.wikidot.com"

SPELL_COLUMNS = ["Level", "School", "CastingTime", "Range", "Components", "Duration", "Classes"]


def clean(text):
    return re.sub(r'\s+', ' ', (text or '').replace('\xa0', ' ')).strip()


def fetch(url, tries=3):
    """fetch_page with a few retries, since one hiccup shouldn't lose a spell"""
    for attempt in range(tries):
        try:
            return fetch_page(url)
        except Exception as e:
            if attempt == tries - 1:
                raise
            print(f"    retrying {url} ({e})")
            time.sleep(2)


def spell_list():
    """[(level, name, school, url)] from the spell list page, in the wiki's order (by level, then name)"""
    content = bs(fetch(SITE + "/spells"), "html.parser").find(id="page-content")
    spells = []
    for level, table in enumerate(content.find_all("table")):
        for row in table.find_all("tr")[1:]:
            cells = row.find_all("td")
            link = cells[0].find("a") if cells else None
            if not link:
                continue
            # The school cell can carry a tag for a sub-type, e.g. "Transmutation T" (technomagic) or "Evocation DG"
            school = clean(cells[1].get_text(" ", strip=True)).split(" ")[0]
            href = link["href"]
            spells.append((level, clean(cells[0].get_text(" ", strip=True)), school,
                           href if href.startswith("http") else SITE + href))
    return spells


STAT_LABELS = ("Casting Time", "Range", "Components", "Duration")
STAT_LINE = re.compile(r'^(' + "|".join(STAT_LABELS) + r')\s*:', re.I)


def stat(stats_ps, label):
    """'**Range:** 150 feet' -> '150 feet' from the casting time / range / components / duration paragraph(s);
    most pages have one paragraph with all four, a few have one paragraph each"""
    for p in stats_ps:
        match = re.search(label + r'\s*:\s*(.+)', p.get_text("\n"))
        if match:
            return clean(match.group(1))
    return ""


def class_lists():
    """Spell name (lowercase) -> classes, from the wiki's per-class spell list pages. Used for the few spell pages
    that have no "Spell Lists." line."""
    classes = {}
    for name in ("Artificer", "Bard", "Cleric", "Druid", "Paladin", "Ranger", "Sorcerer", "Warlock", "Wizard"):
        try:
            content = bs(fetch(f"{SITE}/spells:{name.lower()}"), "html.parser").find(id="page-content")
        except Exception as e:
            print(f"  Could not read the {name} spell list: {e!r}")
            continue
        for table in content.find_all("table"):
            for row in table.find_all("tr")[1:]:
                link = row.find("a")
                if link:
                    classes.setdefault(clean(link.get_text()).lower(), []).append(name)
    return classes


def parse_spell(level, name, school, url, listed_classes):
    content = bs(fetch(url), "html.parser").find(id="page-content")
    paragraphs = content.find_all(["p", "table", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6"], recursive=False)

    source, type_line, stats_ps, classes, description = "", "", [], None, []
    for el in paragraphs:
        text = clean(el.get_text(" ", strip=True))
        if el.name == "p" and text.startswith("Source:") and not source:
            source = text[len("Source:"):].strip()
        elif el.name == "p" and not type_line and el.find("em") and re.search(r'cantrip|level', text, re.I) and len(text) < 80:
            type_line = text
        elif el.name == "p" and not description and STAT_LINE.match(text):
            stats_ps.append(el)
        elif el.name == "p" and re.match(r'^Spell Lists?\s*[.:]', text):
            # Class names are links; "(Optional)" marks Tasha's optional class spells. A few spells list "None".
            classes = [clean(a.get_text()) for a in el.find_all("a")]
            if not classes:
                classes = [c.strip() for c in re.sub(r'^Spell Lists?\s*[.:]', '', text).split(",")
                           if c.strip() and c.strip().lower() != "none"]
        elif el.name == "p":
            if text:
                description.append(tags_to_markdown(el))
        elif el.name == "table":
            description.append(table_to_markdown(el))
        elif el.name in ("ul", "ol"):
            description.extend("- " + tags_to_markdown(li) for li in el.find_all("li", recursive=False))
        elif text:
            description.append(f"**{text}**")

    # "3rd-level evocation (ritual)" -> "3rd-level Evocation (Ritual)"; "evocation cantrip" -> "Evocation Cantrip"
    item_type = re.sub(r'\b(cantrip|ritual|[a-z]+(?=\s+cantrip)|(?<=level )[a-z]+)\b',
                       lambda m: m.group(1).capitalize(), type_line) if type_line else (
        f"{school} Cantrip" if level == 0 else f"Level {level} {school}")
    if item_type:
        item_type = item_type[0].upper() + item_type[1:]

    get = lambda label: stat(stats_ps, label)
    if classes is None:
        # No "Spell Lists." line on the page: use the class spell list pages instead
        classes = listed_classes.get(re.sub(r'\s*\(UA\)$', '', name).lower(), [])
    # Optional class spells keep the note in the class list ("Druid (Optional)") but filter as the class
    class_names = ", ".join(re.sub(r'\s*\(optional\)', ' (Optional)', c, flags=re.I) for c in classes)

    row = [name, "spell", "", item_type, source, "\n".join(description), url, ""]
    row += [str(level), school, get("Casting Time"), get("Range"), get("Components"), get("Duration"), class_names]
    return row


if __name__ == "__main__":
    print("Reading the spell list...")
    spells = spell_list()
    print(f"Found {len(spells)} spells. Reading the class spell lists...")
    listed_classes = class_lists()
    print("Reading each spell's page...")

    rows, failed = [], []
    for i, (level, name, school, url) in enumerate(spells, 1):
        try:
            rows.append(parse_spell(level, name, school, url, listed_classes))
            if i % 25 == 0 or i == len(spells):
                print(f"  {i}/{len(spells)}  {name}")
        except Exception as e:
            failed.append(name)
            print(f"  FAILED {name} ({url}): {e!r}")

    with open(csv_file, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers + SPELL_COLUMNS)
        writer.writerows(rows)
    print(f"\nFinished! Wrote {len(rows)} spells to {csv_file}")
    if failed:
        print(f"{len(failed)} spells could not be read: {', '.join(failed)}")
