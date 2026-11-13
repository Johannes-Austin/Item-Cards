"""Scrapes the wiki's regular (non-magic) equipment pages into mundaneItems.csv.

The pages are tables rather than one page per item, so each page has its own small parser below.
The CSV has the same columns as items.csv so the card maker can show these items on the same cards:
  Rarity      "mundane" (printed on the common card background)
  Attunement  the cost (mundane items never need attunement, so the card's attunement box shows the price)
  Type        the kind of item, e.g. "Martial Melee Weapon" or "Light Armor"
  Description stat lines such as "**Weight:** 3 lb." followed by the item's rules text

Run with:  python MundaneGather.py --cached   to reuse the pages saved in raw_pages instead of downloading them again
"""
import csv
import os
import re
import sys

from bs4 import BeautifulSoup as bs, NavigableString

# Downloading (and the raw_pages cache, including --cached) works the same as for magic items
from DataGather import fetch_page, tags_to_markdown, table_to_markdown, headers

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
csv_file = os.path.join(BASE_DIR, "mundaneItems.csv")

SITE = "https://dnd5e.wikidot.com/"
RARITY = "mundane"
PHB = "Player's Handbook"
DMG = "Dungeon Master's Guide"

# Section headings for setting-specific items, which the wiki doesn't always give a source line for
SETTING_SOURCES = {
    "Forgotten Realms": "Tomb of Annihilation",
    "Dragonlance": "Dragonlance: Shadow of the Dragon Queen",
    "Eberron": "Eberron - Rising from the Last War",
}
# Items that come from a different book than the rest of their page
ITEM_SOURCES = {
    "Spiked Armor": "Sword Coast Adventurer's Guide",
}

SMALL_WORDS = {"of", "and", "or", "the", "a", "an", "per", "to", "in", "on"}
EMPTY = {"", "-", "—", "–"}

items = []


# ==========================================
#  HELPERS
# ==========================================
def title_name(name):
    """'Crossbow, light' -> 'Crossbow, Light' (only first letters change, so "Alchemist's" stays as it is;
    words in brackets are left alone: 'Rope, Hemp (50 ft)')"""
    out, depth = [], 0
    for i, w in enumerate(name.split(" ")):
        if w and depth == 0 and w[0] != "(" and not (i and w.lower() in SMALL_WORDS):
            w = w[0].upper() + w[1:]
        depth += w.count("(") - w.count(")")
        out.append(w)
    return " ".join(out)


def clean(text):
    """Cell text with non-breaking spaces removed; a dash meaning 'nothing' becomes ''"""
    text = re.sub(r'\s+', ' ', (text or '').replace('\xa0', ' ')).strip()
    return '' if text in EMPTY else text


def clean_amount(text):
    """'3gp' -> '3 gp', '2lb.' -> '2 lb.'"""
    return re.sub(r'(\d)(gp|sp|cp|ep|pp|lbs?\.?|oz\.?)(?=\W|$)', r'\1 \2', clean(text))


def cell_text(cell):
    return clean(cell.get_text(" ", strip=True))


def page_content(slug):
    soup = bs(fetch_page(SITE + slug), "html.parser")
    return soup.find(id="page-content")


def stat_lines(*pairs):
    """('Weight', '2 lb.'), ... -> '**Weight:** 2 lb.' lines, leaving out empty values"""
    return [f"**{label}:** {clean_amount(value)}" for label, value in pairs if clean(value)]


def add_item(name, cost, item_type, source, description_lines, url, notes=""):
    name = title_name(clean(name).rstrip("*").strip())   # "Backpack*" has a footnote mark on the wiki
    if not name:
        return
    description = "\n".join(line for line in description_lines if line and line.strip())
    items.append([name, RARITY, clean_amount(cost), item_type, source, description, url, notes])


def section_heading(element, levels=("h1", "h2")):
    """The nearest heading of the given levels above an element"""
    heading = element.find_previous(list(levels))
    return heading.get_text(" ", strip=True) if heading else ""


def source_line_before(element, default):
    """A 'Source: ...' paragraph between the element and the heading above it, if there is one"""
    for sib in element.find_all_previous(["p", "h1", "h2", "h3"]):
        if sib.name != "p":
            break
        match = re.match(r'^\s*Source:\s*(.+)$', sib.get_text(" ", strip=True))
        if match:
            return match.group(1).strip()
    return default


def split_name_cell(cell):
    """A first cell like 'Acid (vial)<br>* <em>description</em><br>- Hemp (50 ft)<br>- Silk (50 feet)'
    -> ('Acid (vial)', 'description', ['Hemp (50 ft)', 'Silk (50 feet)'])"""
    lines, current = [], []
    for child in cell.children:
        if getattr(child, "name", None) == "br":
            lines.append(current)
            current = []
        else:
            current.append(child)
    lines.append(current)

    name, description, variants = "", [], []
    for parts in lines:
        texts = []
        for part in parts:
            if isinstance(part, NavigableString):
                texts.append(str(part))
            else:
                texts.append(tags_to_markdown(part) if part.name in ("em", "i", "strong", "b") else part.get_text())
        text = clean("".join(texts))
        if not text:
            continue
        if text.startswith("*") and not text.startswith("**"):
            # "* *Rope, whether made of hemp...*" -> the item's description (drop the outer italics)
            text = text.lstrip("* ").strip()
            if text.endswith("*") and not text.endswith("**"):
                text = text[:-1].strip()
            description.append(text)
        elif text.startswith("- "):
            variants.append(text[2:].strip())
        elif not name:
            name = text
        else:
            description.append(text)
    return name, "\n".join(description), variants


def cell_lines(cell):
    """The non-empty lines of a cell split at <br>, for rows that list several variants"""
    return [clean(x) for x in cell.get_text("\n").split("\n") if clean(x)]


def column_index(header_cells, *names):
    """Index of the first header cell whose text starts with one of the names, or None"""
    for i, cell in enumerate(header_cells):
        text = cell_text(cell).lower()
        if any(text.startswith(n.lower()) for n in names):
            return i
    return None


def section_paragraphs(heading, stop_levels):
    """Markdown text of everything after a heading up to the next heading of one of stop_levels (tables included)"""
    lines = []
    for sib in heading.find_next_siblings():
        if sib.name in stop_levels:
            break
        if sib.name == "p":
            text = tags_to_markdown(sib)
            if text and not text.startswith("Source:"):
                lines.append(text)
        elif sib.name == "table":
            lines.append(table_to_markdown(sib))
        elif sib.name in ("ul", "ol"):
            lines.extend("- " + tags_to_markdown(li) for li in sib.find_all("li"))
    return lines


# ==========================================
#  ADVENTURING GEAR
# ==========================================
GEAR_TYPES = {
    "Equipment Packs": "Equipment Pack",
    "Common Items": "Adventuring Gear",
    "Usable Items": "Adventuring Gear",
    "Clothes": "Clothes",
    "Arcane Focus": "Arcane Focus",
    "Druidic Focus": "Druidic Focus",
    "Holy Symbols": "Holy Symbol",
    "Containers": "Container",
}


def parse_adventuring_gear():
    url = SITE + "adventuring-gear"
    content = page_content("adventuring-gear")
    for table in content.find_all("table"):
        section = section_heading(table, ("h1",))
        setting = section_heading(table, ("h2",)) if section.startswith("Setting Specific") else ""
        item_type = GEAR_TYPES.get(section, "Adventuring Gear")
        source = source_line_before(table, SETTING_SOURCES.get(setting, PHB))

        rows = table.find_all("tr")
        head = rows[0].find_all(["th", "td"])
        cost_i, weight_i = column_index(head, "Cost"), column_index(head, "Weight")
        capacity_i, contents_i = column_index(head, "Capacity"), column_index(head, "Contents")

        for row in rows[1:]:
            cells = row.find_all("td")
            if not cells:
                continue
            # Magic items listed here (Potion of Healing) are already in the magic item list
            if cells[0].find("a", href=re.compile(r'wondrous-items')):
                continue
            name, description, variants = split_name_cell(cells[0])
            get = lambda i: cells[i] if i is not None and i < len(cells) else None

            if variants:
                # e.g. Rope: one row with "- Hemp (50 ft)" and "- Silk (50 feet)", and one cost/weight line for each
                costs = cell_lines(get(cost_i)) if get(cost_i) else []
                weights = cell_lines(get(weight_i)) if get(weight_i) else []
                for v, variant in enumerate(variants):
                    add_item(f"{name}, {variant}", costs[v] if v < len(costs) else "", item_type, source,
                             stat_lines(("Weight", weights[v] if v < len(weights) else "")) + [description], url)
                continue

            lines = stat_lines(
                ("Capacity", cell_text(get(capacity_i)) if get(capacity_i) else ""),
                ("Weight", cell_text(get(weight_i)) if get(weight_i) else ""))
            if get(contents_i):
                lines.append(f"**Contents:** {cell_text(get(contents_i))}")
            add_item(name, cell_text(get(cost_i)) if get(cost_i) else "", item_type, source, lines + [description], url)


# ==========================================
#  ARMOR
# ==========================================
def parse_armor():
    url = SITE + "armor"
    content = page_content("armor")
    tables = content.find_all("table")

    # Don/Doff times by category: "Light Armor" -> ("1 minute", "1 minute")
    don_doff = {}
    for table in tables:
        head = [cell_text(c) for c in table.find("tr").find_all(["th", "td"])]
        if head[:1] == ["Category"]:
            for row in table.find_all("tr")[1:]:
                cells = [cell_text(c) for c in row.find_all(["td", "th"])]
                if len(cells) >= 3:
                    don_doff[cells[0]] = (cells[1], cells[2])

    for table in tables:
        rows = table.find_all("tr")
        head = rows[0].find_all(["th", "td"])
        if cell_text(head[0]) != "Name":
            continue
        category = section_heading(table, ("h2",))   # Light Armor, Medium Armor, Heavy Armor, Shield
        ac_i, str_i, stealth_i = column_index(head, "Armor Class"), column_index(head, "Strength"), column_index(head, "Stealth")
        weight_i, cost_i = column_index(head, "Weight"), column_index(head, "Cost")
        times = don_doff.get(category)

        for row in rows[1:]:
            cells = row.find_all("td")
            if not cells:
                continue
            name = cell_text(cells[0])
            lines = stat_lines(
                ("Armor Class", cell_text(cells[ac_i])),
                ("Strength", cell_text(cells[str_i])),
                ("Stealth", cell_text(cells[stealth_i])),
                ("Weight", cell_text(cells[weight_i])))
            if times:
                lines.append(f"**Don/Doff:** {times[0]} / {times[1]}")
            add_item(name, cell_text(cells[cost_i]), category, ITEM_SOURCES.get(title_name(name), PHB), lines, url)


# ==========================================
#  WEAPONS
# ==========================================
def special_weapon_rules(content):
    """The Special Weapons list: 'Lance' -> 'You have disadvantage when...'"""
    rules = {}
    for li in content.find_all("li"):
        lead = li.find("strong")
        if lead:
            name = lead.get_text(" ", strip=True).rstrip(".").strip()
            text = li.get_text(" ", strip=True)[len(lead.get_text(" ", strip=True)):].strip()
            rules[name.lower()] = text
    return rules


def parse_weapons():
    url = SITE + "weapons"
    content = page_content("weapons")
    special = special_weapon_rules(content)

    for table in content.find_all("table"):
        rows = table.find_all("tr")
        first = cell_text(rows[0].find(["th", "td"]))
        section = section_heading(table, ("h1",))
        setting = section_heading(table, ("h2",)) if section.startswith("Setting Specific") else ""
        source = source_line_before(table, SETTING_SOURCES.get(setting, PHB))

        if first == "Ammunition":
            head = rows[0].find_all(["th", "td"])
            cost_i, weight_i = column_index(head, "Cost"), column_index(head, "Weight")
            for row in rows[1:]:
                cells = row.find_all("td")
                if cells:
                    add_item(cell_text(cells[0]), cell_text(cells[cost_i]), "Ammunition", source,
                             stat_lines(("Weight", cell_text(cells[weight_i]))), url)
            continue

        if not first.endswith("Weapons"):
            continue   # the Weapon Properties table

        # A "Simple Melee Weapons" title row, a Name/Cost/... header row, then weapons; more title rows can follow
        weapon_type, head = "", None
        for row in rows:
            ths = row.find_all("th")
            if ths and len(ths) == 1:
                weapon_type = cell_text(ths[0]).rstrip("s")   # "Simple Melee Weapons" -> "Simple Melee Weapon"
                continue
            if ths:
                head = ths
                continue
            cells = row.find_all("td")
            if len(cells) == 1 and not cell_text(cells[0]) == "":
                weapon_type = cell_text(cells[0]).rstrip("s")
                continue
            if not cells or head is None:
                continue
            name, description, _ = split_name_cell(cells[0])
            get = lambda label: cell_text(cells[column_index(head, label)])
            lines = stat_lines(("Damage", get("Damage")), ("Properties", get("Properties")), ("Weight", get("Weight")))
            rule = special.get(name.lower())
            # The Hoopak's table cell has a short description and the Special Weapons list has its rules
            add_item(name, get("Cost"), weapon_type, source, lines + [description, rule], url)


# ==========================================
#  FIREARMS
# ==========================================
def parse_firearms():
    url = SITE + "firearms"
    content = page_content("firearms")

    # Property rules worth printing on the card of a firearm that has them
    property_rules = {}
    for table in content.find_all("table"):
        if cell_text(table.find("tr").find(["th", "td"])) == "Property":
            for row in table.find_all("tr")[1:]:
                cells = row.find_all("td")
                if len(cells) >= 2:
                    property_rules[cell_text(cells[0]).lower()] = cell_text(cells[1])

    for table in content.find_all("table"):
        rows = table.find_all("tr")
        if cell_text(rows[0].find(["th", "td"])) == "Property":
            continue
        era = section_heading(table, ("h1",)).replace(" Items", "")   # Renaissance, Modern, Futuristic
        head = rows[0].find_all(["th", "td"])
        in_ammunition = False
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if cell_text(cells[0]) == "Ammunition":
                in_ammunition = True
                continue
            get = lambda label: cell_text(cells[column_index(head, label)])
            name = cell_text(cells[0])
            if in_ammunition:
                # Each era has its own "Bullets (10)", so the era is added to the name
                add_item(f"{name}, {era}", get("Cost"), f"Ammunition ({era} Firearm)", DMG,
                         stat_lines(("Weight", get("Weight"))), url)
                continue
            properties = get("Properties")
            rules = [f"**{label.title()}.** {property_rules[label]}" for label in ("burst fire", "reload")
                     if label in properties.lower() and label in property_rules]
            add_item(name, get("Cost"), f"Martial Ranged Weapon ({era} Firearm)", DMG,
                     stat_lines(("Damage", get("Damage")), ("Properties", properties), ("Weight", get("Weight"))) + rules, url)


# ==========================================
#  EXPLOSIVES
# ==========================================
def parse_explosives():
    url = SITE + "explosives"
    content = page_content("explosives")

    # Rules text by h3 heading: Bomb, Gunpowder, Dynamite, Grenades
    rules = {h.get_text(" ", strip=True).lower(): section_paragraphs(h, ("h1", "h2", "h3"))
             for h in content.find_all("h3")}

    def rules_for(name):
        lower = name.lower()
        for key in rules:
            if lower.startswith(key.rstrip("s")):
                return rules[key]
        return []

    for table in content.find_all("table"):
        rows = table.find_all("tr")
        head = rows[0].find_all(["th", "td"])
        era = cell_text(head[0]).replace(" Item", "")   # Renaissance, Modern
        for row in rows[1:]:
            cells = row.find_all("td")
            if not cells:
                continue
            name = cell_text(cells[0])
            add_item(name, cell_text(cells[column_index(head, "Cost")]), f"Explosive ({era})", DMG,
                     stat_lines(("Weight", cell_text(cells[column_index(head, "Weight")]))) + rules_for(name), url)


# ==========================================
#  POISONS
# ==========================================
def parse_poisons():
    content = page_content("poisons")
    for table in content.find_all("table"):
        rows = table.find_all("tr")
        head = rows[0].find_all(["th", "td"])
        if cell_text(head[0]) != "Poisons":
            continue
        for row in rows[1:]:
            cells = row.find_all("td")
            if not cells:
                continue
            link = cells[0].find("a")
            name = cell_text(cells[0])
            poison_type = cell_text(cells[column_index(head, "Type")])
            cost = cell_text(cells[column_index(head, "Price")])
            url = SITE + link["href"].lstrip("/") if link else SITE + "poisons"

            # Each poison has its own page: "Source: ...", "*Poison (injury), 200 gp*", then the rules
            source, lines = DMG, []
            if link:
                page = bs(fetch_page(url), "html.parser").find(id="page-content")
                for p in page.find_all("p"):
                    text = p.get_text(" ", strip=True)
                    if text.startswith("Source:"):
                        source = text[len("Source:"):].strip()
                    elif re.match(r'^Poison \(', text):
                        continue
                    elif text:
                        lines.append(tags_to_markdown(p))
            add_item(name, f"{cost} per dose" if cost else "", f"Poison ({poison_type.title()})", source, lines, url)


# ==========================================
#  TOOLS
# ==========================================
def heading_key(text):
    """Matches tool names to headings: "Alchemist's supplies" and "Alchemist's Supplies" -> "alchemist's supplies";
    plural headings ("Musical Instruments") match singular names"""
    text = text.lower().replace("’", "'").strip()
    return re.sub(r's$', '', text)


def parse_tools():
    url = SITE + "tools"
    content = page_content("tools")

    # Two sets of descriptions, both under h4 headings: the short PHB ones, then the longer Xanathar's ones
    phb, xge, current = {}, {}, None
    for el in content.find_all(["h2", "h3", "h4"]):
        text = el.get_text(" ", strip=True)
        if el.name in ("h2", "h3"):
            current = phb if "PHB" in text else xge if "XGE" in text else None
        elif current is not None:
            current[heading_key(text)] = section_paragraphs(el, ("h1", "h2", "h3", "h4"))
    # Headings that cover a whole group of tools under a slightly different name
    xge.setdefault(heading_key("Gaming Set"), xge.get(heading_key("Gaming Kit"), []))

    table = content.find("table")
    rows = table.find_all("tr")
    head = rows[0].find_all(["th", "td"])
    cost_i, weight_i = column_index(head, "Cost"), column_index(head, "Weight")
    group = ""
    for row in rows[1:]:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        name = cell_text(cells[0])
        cost = cell_text(cells[cost_i]) if cost_i < len(cells) else ""
        weight = cell_text(cells[weight_i]) if weight_i < len(cells) else ""
        if not cost and not weight:
            group = name   # Artisan's tools, Gaming set, Musical instrument, Miscellaneous
            continue

        group_type = "" if group == "Miscellaneous" else title_name(group)
        key, group_key = heading_key(name), heading_key(group)
        description = []
        if key in phb:
            description += phb[key]
        elif group_key in phb:
            description += phb[group_key]
        if key in xge:
            description += ["**Xanathar's Guide to Everything**"] + xge[key]
        elif group_key in xge:
            description += ["**Xanathar's Guide to Everything**"] + xge[group_key]
        add_item(name, cost, group_type or "Tool", PHB, stat_lines(("Weight", weight)) + description, url)


# ==========================================
#  MOUNTS AND VEHICLES
# ==========================================
SPELLJAMMER = "Spelljammer: Adventures in Space - Astral Adventurer's Guide"
DRAWN_VEHICLES = {"Carriage", "Cart", "Chariot", "Sled", "Wagon"}
NOT_ITEMS = {"Stabling (per day)"}   # a service, not something to carry around


def rule_paragraph(content, start):
    """The text of the page's paragraph starting with e.g. 'Barding.' or 'An animal pulling', or ''"""
    for p in content.find_all("p"):
        text = tags_to_markdown(p)
        if text.replace("*", "").startswith(start):
            return text
    return ""


def parse_mounts_vehicles():
    url = SITE + "mounts-vehicles"
    content = page_content("mounts-vehicles")
    tables = content.find_all("table")
    drawn_rule = rule_paragraph(content, "An animal pulling")

    # Mounts and other animals: Speed and Carrying Capacity
    rows = tables[0].find_all("tr")
    head = rows[0].find_all(["th", "td"])
    cost_i, speed_i, carry_i = column_index(head, "Cost"), column_index(head, "Speed"), column_index(head, "Carrying")
    for row in rows[1:]:
        cells = row.find_all("td")
        if cells:
            add_item(cell_text(cells[0]), cell_text(cells[cost_i]), "Mount", PHB,
                     stat_lines(("Speed", cell_text(cells[speed_i])), ("Carrying Capacity", cell_text(cells[carry_i]))), url)

    # Tack, harness and drawn vehicles. "Saddle" is a group row for the four kinds of saddle below it
    rules = {"Barding": rule_paragraph(content, "Barding."), "Saddle": rule_paragraph(content, "Saddles.")}
    rows = tables[1].find_all("tr")
    head = rows[0].find_all(["th", "td"])
    cost_i, weight_i = column_index(head, "Cost"), column_index(head, "Weight")
    group = ""
    for row in rows[1:]:
        cells = row.find_all("td")
        if not cells:
            continue
        name, cost, weight = cell_text(cells[0]), cell_text(cells[cost_i]), cell_text(cells[weight_i])
        if not cost and not weight:
            group = name
            continue
        if name in NOT_ITEMS:
            continue
        if group == "Saddle" and name in ("Exotic", "Military", "Pack", "Riding"):
            name, extra = f"Saddle, {name}", rules["Saddle"]
        else:
            group, extra = "", rules.get(name, "")
        if name == "Barding":
            # Costs and weighs a multiple of the armor it's made from
            cost, lines = "×4 armor cost", ["**Weight:** ×2 armor weight"]
        else:
            lines = stat_lines(("Weight", weight))
        item_type = "Drawn Vehicle" if name in DRAWN_VEHICLES else "Tack and Harness"
        add_item(name, cost, item_type, PHB, lines + [extra or (drawn_rule if item_type == "Drawn Vehicle" else "")], url)

    # Waterborne vehicles: Speed; keelboats and rowboats are rowed
    rowed_rule = rule_paragraph(content, "Rowed Vessels.")
    rows = tables[2].find_all("tr")
    head = rows[0].find_all(["th", "td"])
    cost_i, speed_i = column_index(head, "Cost"), column_index(head, "Speed")
    for row in rows[1:]:
        cells = row.find_all("td")
        if cells:
            name = cell_text(cells[0])
            add_item(name, cell_text(cells[cost_i]), "Waterborne Vehicle", PHB,
                     stat_lines(("Speed", cell_text(cells[speed_i])))
                     + [rowed_rule if name in ("Keelboat", "Rowboat") else ""], url)

    # Spelljamming ships: a stat table, and each ship's description in a tab named after it
    descriptions = {}
    tabs = content.find("div", class_="yui-navset")
    if tabs:
        names = [cell_text(li) for li in tabs.select("ul.yui-nav li")]
        panels = tabs.select_one("div.yui-content").find_all("div", recursive=False)
        for name, panel in zip(names, panels):
            descriptions[name.lower()] = [tags_to_markdown(p) for p in panel.find_all("p") if tags_to_markdown(p)]
    if len(tables) > 3:
        rows = tables[3].find_all("tr")
        head = rows[0].find_all(["th", "td"])
        labels = [cell_text(c) for c in head]
        cost_i = column_index(head, "Cost")
        for row in rows[1:]:
            cells = row.find_all("td")
            if not cells:
                continue
            name = cell_text(cells[0])
            stats = [(labels[i], cell_text(cells[i])) for i in range(1, len(cells)) if i != cost_i and i < len(labels)]
            add_item(name, cell_text(cells[cost_i]), "Spelljamming Ship", SPELLJAMMER,
                     stat_lines(*stats) + descriptions.get(name.lower(), []), url)


# ==========================================
#  GEMSTONES AND ART OBJECTS (written here, not scraped: the wiki has no page for them)
# ==========================================
# Gemstones at the Dungeon Master's Guide's values, with a short description of each stone's look
GEMSTONES = {
    "10 gp": [("Azurite", "Opaque, mottled deep blue."), ("Banded Agate", "Translucent, striped brown, blue, white or red."),
              ("Blue Quartz", "Transparent pale blue."), ("Eye Agate", "Translucent rings of gray, white, brown, blue or green."),
              ("Hematite", "Opaque gray-black."), ("Lapis Lazuli", "Opaque light or dark blue flecked with yellow."),
              ("Malachite", "Opaque, banded light and dark green."), ("Moss Agate", "Translucent pink or yellow-white with mossy gray or green markings."),
              ("Obsidian", "Opaque black."), ("Rhodochrosite", "Opaque light pink."),
              ("Tiger Eye", "Translucent brown with a golden center."), ("Turquoise", "Opaque light blue-green.")],
    "50 gp": [("Bloodstone", "Opaque dark gray with red flecks."), ("Carnelian", "Opaque orange to red-brown."),
              ("Chalcedony", "Opaque white."), ("Chrysoprase", "Translucent green."), ("Citrine", "Transparent pale yellow-brown."),
              ("Jasper", "Opaque blue, black or brown."), ("Moonstone", "Translucent white with a pale blue glow."),
              ("Onyx", "Opaque bands of black and white, or pure black or white."), ("Quartz", "Transparent white, smoky gray or yellow."),
              ("Sardonyx", "Opaque bands of red and white."), ("Star Rose Quartz", "Translucent rosy stone with a white star at its center."),
              ("Zircon", "Transparent pale blue-green.")],
    "100 gp": [("Amber", "Transparent watery gold to rich gold."), ("Amethyst", "Transparent deep purple."),
               ("Chrysoberyl", "Transparent yellow-green to pale green."), ("Coral", "Opaque crimson."),
               ("Garnet", "Transparent red, brown-green or violet."), ("Jade", "Translucent light green, deep green or white."),
               ("Jet", "Opaque deep black."), ("Pearl", "Opaque lustrous white, yellow or pink."),
               ("Spinel", "Transparent red, red-brown or deep green."), ("Tourmaline", "Transparent pale green, blue, brown or red.")],
    "500 gp": [("Alexandrite", "Transparent dark green."), ("Aquamarine", "Transparent pale blue-green."),
               ("Black Pearl", "Opaque pure black."), ("Blue Spinel", "Transparent deep blue."),
               ("Peridot", "Transparent rich olive green."), ("Topaz", "Transparent golden yellow.")],
    "1,000 gp": [("Black Opal", "Translucent dark green with black mottling and golden flecks."),
                 ("Blue Sapphire", "Transparent blue-white to medium blue."), ("Emerald", "Transparent deep bright green."),
                 ("Fire Opal", "Translucent fiery red."), ("Opal", "Translucent pale blue with green and golden mottling."),
                 ("Star Ruby", "Translucent ruby with a white star at its center."),
                 ("Star Sapphire", "Translucent blue sapphire with a white star at its center."),
                 ("Yellow Sapphire", "Transparent fiery yellow or yellow-green.")],
    "5,000 gp": [("Black Sapphire", "Translucent lustrous black with glowing highlights."),
                 ("Diamond", "Transparent blue-white, canary, pink, brown or blue."),
                 ("Jacinth", "Transparent fiery orange."), ("Ruby", "Transparent clear red to deep crimson.")],
}
# Art objects at the Dungeon Master's Guide's value tiers. These pieces are this project's own, not the DMG's list.
ART_OBJECTS = {
    "25 gp": ["Pewter tankard etched with a hunting scene", "Carved wooden bear with glass eyes", "Silver thimble engraved with roses",
              "Painted clay mask of a laughing jester", "Copper hand mirror with a polished face", "Embroidered linen picture of a village",
              "Brass compass in a tooled leather case", "Bone comb carved with leaping fish", "Painted wooden chess set, two pieces missing",
              "Silk ribbon strung with tiny silver bells"],
    "250 gp": ["Gold signet ring of a forgotten noble house", "Three-armed silver candelabrum", "Ivory hairpin carved as a heron",
               "Small tapestry of a knight at a river crossing", "Bronze astrolabe engraved with star charts",
               "Enamelled snuffbox painted with a mountain lake", "Silver drinking horn with a gilded rim", "Jade figurine of a sleeping cat",
               "Illuminated prayer book with gilt pages", "Pair of silver spurs set with small garnets"],
    "750 gp": ["Gold-plated hand bell with an ebony handle", "Silver chalice set with moonstones",
               "Oil painting of a stormy harbor in a gilt frame", "Marble bust of a stern magistrate",
               "Gold dragonfly brooch with amber wings", "Silk ceremonial robe embroidered with gold thread",
               "Silver music box that plays a lullaby", "Ceremonial obsidian dagger with a gold-wire grip",
               "Crystal decanter with a silver stopper", "Ivory and gold game board with its pieces"],
    "2,500 gp": ["Gold crown set with small emeralds", "Red leather scabbard with jewelled gold fittings",
                 "Platinum bracelet set with sapphires", "Gold-threaded tapestry of a royal wedding",
                 "Gold statuette of a rearing horse with ruby eyes", "Silver tiara strung with pearls",
                 "Ancient bronze war helm inlaid with gold", "Jade dragon carving on a teak stand",
                 "Gold-leaf portrait of a long-dead queen", "Lace mantilla woven with mithral thread"],
    "7,500 gp": ["Platinum scepter crowned with a great diamond", "Jewelled crown of a fallen empire",
                 "Gold idol with fire opal eyes", "Gold and platinum orrery with gemstone planets",
                 "Platinum necklace studded with diamonds", "Set of gold goblets crusted with rubies",
                 "Masterpiece painting of an empire's founding", "Gold music box inlaid with black sapphires",
                 "Ceremonial gold armor of a dragon-king", "Black pearl diadem on a platinum band"],
}


def parse_treasure():
    for value, gems in GEMSTONES.items():
        for name, look in gems:
            add_item(name, value, f"Gemstone ({value})", DMG, [f"**Value:** {value}", look], "")
    for value, pieces in ART_OBJECTS.items():
        for name in pieces:
            # (added directly: these read as descriptions, so they keep their sentence case)
            items.append([name, RARITY, value, f"Art Object ({value})", "Card Maker Treasure", f"**Value:** {value}", "", ""])


# ==========================================
#  SPELL COMPONENTS (written here from the costly material components in spells.csv)
# ==========================================
# (component, value in gp, [(spell, whether the spell consumes it)]). Components that are already regular items
# (a holy symbol, a book) and open-ended ones (Incite Greed's "a gem", Imprisonment's special component) are left out.
SPELL_COMPONENTS = [
    ("Mansion charms: ivory portal, polished marble and silver spoon", 15, [("Mordenkainen's Magnificent Mansion", False)]),
    ("Replica of yourself", 5, [("Project Image", False)]),
    ("Lead-based ink", 10, [("Illusory Script", True)]),
    ("Jade dust", 10, [("Magic Mouth", True)]),
    ("Jade dust", 25, [("Programmed Illusion", False)]),
    ("Small silver rod", 10, [("Guards and Wards", False)]),
    ("Charcoal, incense and herbs", 10, [("Find Familiar", True)]),
    ("Gold dust", 25, [("Arcane Lock", True), ("Immovable Object", True)]),
    ("Powdered silver", 25, [("Ceremony", True)]),
    ("Divination tokens (marked sticks or bones)", 25, [("Augury", False)]),
    ("Diamond dust", 25, [("Nondetection", True)]),
    ("Incense and sacrificial offering", 25, [("Divination", True)]),
    ("Eye ointment of mushroom, saffron and fat", 25, [("True Seeing", True)]),
    ("Diamond", 50, [("Chromatic Orb", False)]),
    ("Ruby dust", 50, [("Continual Flame", True)]),
    ("Pair of platinum rings", 100, [("Warding Bond", False)]),
    ("Tiny replica chest", 50, [("Leomund's Secret Chest", False)]),
    ("Gem-infused chalks and inks", 50, [("Teleportation Circle", True)]),
    ("Four ivory strips", 200, [("Legend Lore", False)]),
    ("Pearl", 100, [("Identify", False)]),
    ("White pearl", 100, [("Fortune's Favor", True)]),
    ("Jeweled horn or glass eye", 100, [("Clairvoyance", False)]),
    ("Powdered silver and iron", 100, [("Magic Circle", True)]),
    ("Diamond dust", 100, [("Stoneskin", True), ("Greater Restoration", True)]),
    ("Sunburst pendant", 100, [("Dawn", False)]),
    ("Divinatory tools", 100, [("Find the Path", False)]),
    ("Tiny silver cage", 100, [("Soul Cage", False)]),
    ("Ornately carved bar of silver", 100, [("Astral Projection", True)]),
    ("Black onyx stone", 150, [("Create Undead", False)]),
    ("Undead eyeball encased in a gem", 150, [("Shadow Of Moil", False)]),
    ("Gilded acorn", 200, [("Summon Beast", False)]),
    ("Incense and powdered diamond", 200, [("Glyph of Warding", True)]),
    ("Incense", 250, [("Legend Lore", True)]),
    ("Miniature platinum sword", 250, [("Mordenkainen's Sword", False)]),
    ("Forked metal rod", 250, [("Plane Shift", False)]),
    ("Spool of platinum cord", 250, [("Tether Essence", True)]),
    ("Diamond", 300, [("Revivify", True)]),
    ("Gilded flower", 300, [("Summon Fey", False)]),
    ("Crystal vial of tears", 300, [("Summon Shadowspawn", False)]),
    ("Gilded skull", 300, [("Summon Undead", False)]),
    ("Gilded playing card", 400, [("Spirit Of Death", False)]),
    ("Platinum-inlaid vial", 400, [("Summon Aberration", False)]),
    ("Ornate stone and metal lockbox", 400, [("Summon Construct", False)]),
    ("Gold-inlaid vial", 400, [("Summon Elemental", False)]),
    ("Diamond", 500, [("Raise Dead", True), ("Mighty Fortress", True)]),
    ("Golden reliquary", 500, [("Summon Celestial", False)]),
    ("Dragon-engraved object", 500, [("Summon Draconic Spirit", False)]),
    ("Crushed black pearl", 500, [("Circle of Death", False)]),
    ("Platinum-plated dragon scale", 500, [("Fizban's Platinum Shield", False)]),
    ("Ornamental gem container", 500, [("Magic Jar", False)]),
    ("Outer Planes symbol", 500, [("Tasha's Otherworldly Guise", False)]),
    ("Vial of quicksilver", 500, [("Create Magen", True)]),
    ("Dragon statuette", 500, [("Draconic Transformation", False)]),
    ("Adamantine piece", 500, [("Invulnerability", True)]),
    ("Ruby vial", 600, [("Summon Fiend", False)]),
    ("Ruby", 999, [("Infernal Calling", False)]),
    ("Agate", 1000, [("Awaken", True)]),
    ("Herbs, oils and incense", 1000, [("Hallow", True)]),
    ("Jewel", 1000, [("Planar Binding", True)]),
    ("Rare oils and unguents", 1000, [("Reincarnate", True)]),
    ("Scrying focus", 1000, [("Scrying", False)]),
    ("Jewel-encrusted dagger", 1000, [("Create Homunculus", False)]),
    ("Sapphire", 1000, [("Drawmij's Instant Summons", False)]),
    ("Powdered ruby", 1000, [("Forbiddance", False)]),
    ("Gem-encrusted bowl", 1000, [("Heroes' Feast", True)]),
    ("Diamond", 1000, [("Resurrection", True), ("Clone", True)]),
    ("Powdered diamond and opal", 1000, [("Symbol", True)]),
    ("Jacinth", 1000, [("Astral Projection", True)]),
    ("Tiny reliquary", 1000, [("Holy Aura", False)]),
    ("Ivory statuette of yourself", 1500, [("Contingency", False)]),
    ("Intricate crystal rod", 1500, [("Create Magen", False)]),
    ("Ruby dust", 1500, [("Forcecage", False)]),
    ("Powdered ruby", 1500, [("Simulacrum", True)]),
    ("Jade circlet", 1500, [("Shapechange", False)]),
    ("Sealable clone vessel", 2000, [("Clone", False)]),
    ("Exquisite chest of rare materials", 5000, [("Leomund's Secret Chest", False)]),
    ("Crystal rod", 5000, [("Create Spelljamming Helm", True)]),
    ("Diamond, emerald, ruby and sapphire dust", 5000, [("Sequester", True)]),
    ("Diamond", 5000, [("Gate", False)]),
    ("Hourglass of diamond dust", 5000, [("Time Ravage", True)]),
    ("Holy water and diamonds", 25000, [("True Resurrection", True)]),
]


def parse_spell_components():
    spells_csv = os.path.join(BASE_DIR, "spells.csv")
    with open(spells_csv, encoding="utf-8-sig") as f:
        spell_sources = {r["Name"]: r["Source"] for r in csv.DictReader(f)}
    for name, value, uses in SPELL_COMPONENTS:
        cost = f"{value:,} gp"
        used_by = ", ".join(f"{spell}{' (consumed)' if consumed else ''}" for spell, consumed in uses)
        sources = []
        for spell, _ in uses:
            for source in (spell_sources.get(spell) or PHB).split(", "):
                if source not in sources:
                    sources.append(source)
        items.append([f"{name[0].upper()}{name[1:]} ({cost})", RARITY, cost, "Spell Component", ", ".join(sources),
                      f"**Value:** {cost}\n**Used by:** {used_by}", "", ""])


# ==========================================
#  MAIN
# ==========================================
if __name__ == "__main__":
    print("Scraping regular items...")
    for parse in (parse_adventuring_gear, parse_armor, parse_weapons, parse_firearms,
                  parse_explosives, parse_poisons, parse_tools, parse_mounts_vehicles,
                  parse_treasure, parse_spell_components):
        before = len(items)
        try:
            parse()
            print(f"  {parse.__name__[len('parse_'):]}: {len(items) - before} items")
        except Exception as e:
            print(f"  {parse.__name__[len('parse_'):]} failed: {e!r}")

    # Later pages win if two items share a name
    seen = {}
    for item in items:
        seen[item[0].lower()] = item
    with open(csv_file, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(seen.values())
    print(f"\nFinished! Wrote {len(seen)} items to {csv_file}")
