import re
import sys
import requests
import csv
import os
from bs4 import BeautifulSoup as bs

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
names_file = os.path.join(BASE_DIR, "itemNames.csv")
csv_file = os.path.join(BASE_DIR, "items.csv")

# Every downloaded page is saved here as raw HTML so it can be reviewed later (or re-parsed without re-downloading)
RAW_DIR = os.path.join(BASE_DIR, "raw_pages")
# Run with:  python DataGather.py --cached   to reuse saved pages instead of downloading them again
USE_CACHE = "--cached" in sys.argv

headers = ["Name", "Rarity", "Attunement", "Type", "Source", "Description", "URL", "Notes"]

STANDARD_RARITIES = {"common", "uncommon", "rare", "very rare", "legendary", "artifact"}

# Matches the type/rarity line of an item page, e.g. "Wondrous item, unique"
RARITY_WORDS = re.compile(r'\b(common|uncommon|rare|very rare|legendary|artifact|unique|varies|rarity)\b', re.IGNORECASE)

# Matches a single rarity word inside a rarity string (longest first so "very rare" isn't read as "rare")
RARITY_TOKEN = re.compile(r'\b(very rare|uncommon|common|rare|legendary|artifact)\b')

# Matches a variant heading at the start of a paragraph, e.g. "**Slumbering (Uncommon).** As a bonus action..."
VARIANT_HEADING = re.compile(
    r'^\*\*(?P<label>[^*]+?)\s*\((?P<rarity>common|uncommon|rare|very rare|legendary|artifact)\)\.?\s*\*\*\.?\s*(?P<rest>.*)$',
    re.IGNORECASE)

SOURCE_LINE = re.compile(r'^Sources?\s*(?::|\s-\s|\s–\s)\s*', re.IGNORECASE)

# The wiki names a few books differently from page to page. Each is corrected to the name the other pages use, so the
# card maker's source filter has one entry per book. A value with ", " counts under each of those books.
SOURCE_FIXES = {
    "Critical Role: Call of the Netherdeep": "Critical Role - Call of the Netherdeep",
    "Dungeons and Dragons - Honor Among Thieves.": "Dungeons and Dragons - Honor Among Thieves",
    "Lost Mine of Phandelver and Phandelver and Below = The Shattered Obelisk": "Lost Mine of Phandelver, Phandelver and Below - The Shattered Obelisk",
    "Lost Mine of Phandelver and Phandelver and Below: The Shattered Obelisk": "Lost Mine of Phandelver, Phandelver and Below - The Shattered Obelisk",
    # Tyranny of Dragons is the reissue of Hoard of the Dragon Queen and The Rise of Tiamat
    "Tyranny of the Dragonqueen (Errata)": "Tyranny of Dragons",
    "The Rise of Tiamat": "Tyranny of Dragons",
    "Acquisitions Inc.": "Acquisitions Incorporated",
    # The card maker splits sources at commas, so this one can't keep its own
    "Unearthed Arcana 66 - Fighter, Rogue, and Wizard": "Unearthed Arcana 66 - Fighter Rogue and Wizard",
}

def fix_source(text):
    """The page's source text as one or more book names separated by ", ":
    'Xanathar's Guide to Everything/Elemental Evil Player's Companion' -> 'Xanathar's Guide to Everything, Elemental Evil Player's Companion'"""
    books = []
    for part in text.split("/"):
        part = re.sub(r'\s+', ' ', part).strip()
        fixed = SOURCE_FIXES.get(part)
        for book in (fixed.split(", ") if fixed else [part]):
            if book and book not in books:
                books.append(book)
    return ", ".join(books) or "Unknown Source"

def clean_rarity(text):
    """Drops parenthesised notes and trailing punctuation: 'Common.' -> 'Common'"""
    return re.sub(r'\([^)]*\)', '', text).strip().strip('.,;:').strip()

# Matches a trailing bonus list in a page title, e.g. "Ammunition, +1, +2, or +3"
_BONUS_LIST = re.compile(r',\s*\+\d+(?:\s*,\s*\+\d+)*\s*,?\s*(?:or\s*)?\+\d+\s*$', re.IGNORECASE)

def base_item_name(name):
    """'Ammunition, +1, +2, or +3' -> 'Ammunition' so each variant can be named 'Ammunition, +1' etc."""
    return _BONUS_LIST.sub('', name).strip()

def custom_split(input_str):
    parts = []
    current_part = ''
    inside_parentheses = False

    for char in input_str:
        if char == '(':
            inside_parentheses = True
            current_part += char
        elif char == ')':
            inside_parentheses = False
            current_part += char
        elif char == ',' and not inside_parentheses:
            parts.append(current_part.strip())
            current_part = ''
        else:
            current_part += char

    if current_part:
        parts.append(current_part.strip())

    return parts

def tags_to_markdown(element):
    """Converts bold and italic tags into clean Markdown formatting."""
    for tag in element.find_all(['strong', 'b', 'em', 'i']):
        if tag.name in ['strong', 'b']:
            tag.replace_with(f"**{tag.get_text()}**")
        elif tag.name in ['em', 'i']:
            tag.replace_with(f"*{tag.get_text()}*")
    return element.get_text().strip()

def table_to_markdown(table_element):
    """Converts an HTML table element into a structured Markdown plain text table.

    A leading "title row" (one filled cell above the real header row, e.g. "Potions of Healing")
    is written as a bold line above the table, and no data columns are dropped.
    """
    rows = table_element.find_all('tr')
    if not rows:
        return ""

    all_rows = []
    for row in rows:
        cells = [tags_to_markdown(cell).replace("\n", " ").replace("|", "\\|")
                 for cell in row.find_all(['th', 'td'])]
        if cells:
            all_rows.append(cells)

    if not all_rows:
        return ""

    markdown_lines = []

    # Title row: only the first cell has text, and the next row is the real header
    first = all_rows[0]
    if (len(all_rows) > 1
            and first[0].strip()
            and not any(c.strip() for c in first[1:])
            and (len(first) > 1 or len(all_rows[1]) > 1)):
        markdown_lines.append(f"**{first[0].replace('**', '').strip()}**")
        all_rows = all_rows[1:]

    width = max(len(r) for r in all_rows)

    def pad(cells):
        return cells + [""] * (width - len(cells))

    headers_list = pad(all_rows[0])
    markdown_lines.append("| " + " | ".join(headers_list) + " |")
    markdown_lines.append("| " + " | ".join(["---"] * width) + " |")

    for cells in all_rows[1:]:
        markdown_lines.append("| " + " | ".join(pad(cells)) + " |")

    return "\n".join(markdown_lines)

# ==========================================
#  SPLITTING "RARITY VARIES" ITEMS
# ==========================================
def split_markdown_row(line):
    """'| a | b |' -> ['a', 'b'] (respects escaped pipes)."""
    parts = re.split(r'(?<!\\)\|', line.strip())
    parts = parts[1:-1] if line.strip().endswith('|') else parts[1:]
    return [p.strip().replace('\\|', '|') for p in parts]

def find_table_blocks(lines):
    """Returns (start, end) index pairs for runs of consecutive markdown table lines."""
    blocks = []
    start = None
    for i, line in enumerate(lines):
        is_row = line.lstrip().startswith('|')
        if is_row and start is None:
            start = i
        elif not is_row and start is not None:
            blocks.append((start, i))
            start = None
    if start is not None:
        blocks.append((start, len(lines)))
    return blocks

def split_by_rarity_table(base_name, description):
    """If the description has a table with a 'Rarity' column, return one
    (name, rarity, description) tuple per row. Returns [] if it can't be split."""
    lines = description.split("\n")

    for start, end in find_table_blocks(lines):
        rows = [split_markdown_row(l) for l in lines[start:end]]
        if len(rows) < 4:  # header + separator + at least 2 data rows
            continue

        header = rows[0]
        if not all(re.fullmatch(r':?-{2,}:?', c) for c in rows[1]):
            continue

        rarity_col = next((i for i, h in enumerate(header) if h.strip().lower() == 'rarity'), None)
        if rarity_col is None:
            continue

        variants = []
        shared = []   # rows that apply to every variant (e.g. an "All" row with a rarity of "-")
        for row in rows[2:]:
            row = row + [''] * (len(header) - len(row))
            rarity = row[rarity_col].strip().lower()
            if rarity not in STANDARD_RARITIES:
                others = [f"**{h.strip()}:** {v.strip()}" for i, (h, v) in enumerate(zip(header, row))
                          if i != rarity_col and h.strip() and v.strip()]
                if others:
                    shared.append(" · ".join(others))
                continue
            variants.append((row, rarity))

        if len(variants) < 2:
            continue

        # Remove the table (and its bold title line, if any) from the shared description text
        remove_from = start
        if start > 0 and re.fullmatch(r'\*\*[^*]+\*\*', lines[start - 1].strip()):
            remove_from = start - 1
        rest = "\n".join(lines[:remove_from] + lines[end:]).strip()

        first_header = header[0].strip()
        results = []
        for row, rarity in variants:
            if rarity_col == 0:
                # Rarity is the first column (e.g. Rarity | Bonus): label by the short next column (+1) or the rarity itself
                second = row[1].strip() if len(row) > 1 else ''
                if re.fullmatch(r'[+-]\d+', second):
                    label, skip_cols = second, {0, 1}
                else:
                    label, skip_cols = rarity.title(), {0}
                variant_name = f"{base_name}, {label}"
            elif first_header.endswith(('…', '...')):
                # Header like "Potion of …" -> "Potion of Greater healing"
                prefix = first_header.rstrip('….').strip()
                variant_name = f"{prefix} {row[0].strip()}"
                skip_cols = {0, rarity_col}
            else:
                label = row[0].strip() or rarity.title()
                variant_name = f"{base_name}, {label}"
                skip_cols = {0, rarity_col}

            details = [f"**{h.strip()}:** {v.strip()}" for i, (h, v) in enumerate(zip(header, row))
                       if i not in skip_cols and h.strip() and v.strip()]

            parts = []
            if details:
                parts.append(" · ".join(details))
            parts.extend(shared)
            if rest:
                parts.append(rest)
            results.append((variant_name, rarity, "\n".join(parts)))

        return results

    return []

def split_by_labeled_variants(base_name, description):
    """Splits items whose variants are paragraphs that start with a bold 'Name (Rarity).' label
    (Ioun Stone, Dragon Vessel, Figurine of Wondrous Power...). Each variant keeps its own paragraph(s),
    followed by the shared intro text. Returns (name, rarity, description) tuples, or [] if the page
    doesn't follow that layout."""
    intro = []
    sections = []   # each: [label, rarity, [lines]]
    for line in description.split("\n"):
        m = VARIANT_HEADING.match(line.strip())
        if m:
            sections.append([m.group('label').strip(), m.group('rarity').lower(), [m.group('rest').strip()]])
        elif sections:
            sections[-1][2].append(line)
        else:
            intro.append(line)

    if len(sections) < 2:
        return []

    intro_text = "\n".join(intro).strip()
    words = base_name.split()
    last_word = words[-1].lower() if words else ""

    results = []
    for label, rarity, body_lines in sections:
        body = "\n".join(body_lines).strip()
        # "Azorius Keyrune" already says what it is, so don't write "Guild Keyrune, Azorius Keyrune"
        if last_word and last_word in label.lower().split():
            variant_name = label
        else:
            variant_name = f"{base_name}, {label}"
        results.append((variant_name, rarity, "\n".join(p for p in (body, intro_text) if p)))
    return results

def append_row(new_line):
    """Appends one item row to items.csv (writes the header row if the file is new)."""
    try:
        file_exists = os.path.exists(csv_file) and os.path.getsize(csv_file) > 0
        with open(csv_file, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(headers)
            writer.writerow(new_line)
            file.flush()

        print(f"Data successfully added: {new_line[0]}")

    except Exception as e:
        print(f"File writing error on {new_line[0]}: {str(e)}")

def raw_page_path(URL):
    """http://dnd5e.wikidot.com/wondrous-items:ammunition -> raw_pages/wondrous-items_ammunition.html"""
    slug = re.sub(r'^https?://[^/]+/', '', URL)
    slug = re.sub(r'[^A-Za-z0-9._-]+', '_', slug).strip('_') or 'page'
    return os.path.join(RAW_DIR, slug + ".html")

def fetch_page(URL):
    """Returns the page HTML, using a saved copy when --cached is set, and saving every fresh download."""
    path = raw_page_path(URL)

    if USE_CACHE and os.path.exists(path):
        with open(path, mode='r', encoding='utf-8') as f:
            return f.read()

    req = requests.get(URL, timeout=10)
    req.raise_for_status()

    try:
        os.makedirs(RAW_DIR, exist_ok=True)
        with open(path, mode='w', encoding='utf-8') as f:
            f.write(req.text)
    except Exception as e:
        print(f"Could not save raw page for {URL}: {str(e)}")

    return req.text

def my_function(URL, name):
    notes = ""
    fullName = name
    
    try:
        html = fetch_page(URL)
    except Exception as e:
        print(f"Network error skipping {name}: {str(e)}")
        return

    soup = bs(html, 'html.parser')
    content_box = soup.find('div', id='page-content')
    if not content_box:
        print(f"Warning: Could not find page-content for {name}")
        return

    clean_lines = []
    # Capture a comprehensive structural blueprint of layout elements
    target_tags = ['p', 'li', 'table', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr']
    
    for element in content_box.find_all(target_tags):
        # Avoid processing child elements twice if they are nested inside a table
        if element.find_parent('table') and element.name != 'table':
            continue
            
        if element.name == 'table':
            notes = notes + "Table parsed automatically. "
            table_md = table_to_markdown(element)
            if table_md:
                clean_lines.append(table_md)
                
        elif element.name == 'hr':
            clean_lines.append("---")
            
        elif element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            level = int(element.name[1])
            text = tags_to_markdown(element)
            if text:
                header_md = f"{'#' * level} {text}"
                if element.find_parent('blockquote'):
                    header_md = f"> {header_md}"
                clean_lines.append(header_md)
                
        elif element.name == 'p':
            text = tags_to_markdown(element)
            if text:
                if element.find_parent('blockquote'):
                    text = f"> {text}"
                clean_lines.append(text)
                
        elif element.name == 'li':
            text = tags_to_markdown(element)
            if text:
                li_md = f"• {text}"
                if element.find_parent('blockquote'):
                    li_md = f"> {li_md}"
                clean_lines.append(li_md)

    if not clean_lines:
        print(f"Warning: No valid elements parsed for {name}")
        return

    # --- RESILIENT DATA HARVESTING ---
    # Find the "Source:" metadata position dynamically instead of guessing index 0 and 1
    source_idx = -1
    source = "Unknown Source"
    for idx, line in enumerate(clean_lines):
        normalized = line.replace("**", "").replace("*", "").strip()
        # Usually "Source: X", but some pages have "Source - X" or "Sources: X"
        match = SOURCE_LINE.match(normalized)
        if match:
            source_idx = idx
            source = normalized[match.end():].strip()
            break

    # Extract our metadata and descriptions relative to where the Source identifier was found
    if source_idx != -1 and source_idx + 1 < len(clean_lines):
        line1 = clean_lines[source_idx + 1]
        description_lines = clean_lines[source_idx + 2:]
    else:
        # No "Source:" line found. Look for the type/rarity line (e.g. "Wondrous item, unique") in the first few lines.
        type_idx = -1
        for idx, line in enumerate(clean_lines[:4]):
            normalized = line.replace("**", "").replace("*", "").strip()
            if len(normalized) < 150 and "," in normalized and RARITY_WORDS.search(normalized):
                type_idx = idx
                break

        if type_idx != -1:
            source = "Unknown Source"
            line1 = clean_lines[type_idx]
            description_lines = clean_lines[type_idx + 1:]
            notes = notes + "No source line on page. "
        else:
            # Emergency index fallback if structure is atypical
            source = clean_lines[0].replace("Source:", "").replace("**", "").replace("*", "").strip()
            line1 = clean_lines[1] if len(clean_lines) > 1 else "Unknown Type, Common"
            description_lines = clean_lines[2:] if len(clean_lines) > 2 else []
    source = fix_source(source)

    # Clean up markdown styling from structural metadata elements for property calculations
    line1_clean = line1.replace("**", "").replace("*", "")

    # Extract attunement status
    match = re.search(r'\(([^)]*Attunement[^)]*)\)', line1_clean, re.IGNORECASE)
    if match:
        attuenement = re.sub(r'^requires attunement', 'Requires Attunement', match.group(1).strip(), flags=re.IGNORECASE)
        line1 = re.sub(r'\s*\([^)]*Attunement[^)]*\)', '', line1, flags=re.IGNORECASE)
    else:
        attuenement = "No Attunement"
        
    line1 = re.sub(r'\bor\b', '', line1)
    line1_clean = line1.replace("**", "").replace("*", "")
    
    line1Parts = custom_split(line1_clean)
    itemType = line1Parts[0] if len(line1Parts) > 0 else "Unknown Type"
    description = "\n".join(description_lines)

    # Items whose rarity varies become one item per variant: a row of their rarity table (Potion of Giant Strength),
    # or one per "**Name (Rarity).**" paragraph (Ioun Stone, Dragon Vessel, Figurine of Wondrous Power...)
    if len(line1Parts) == 2:
        listed_rarity = clean_rarity(line1Parts[1]).lower()
        if listed_rarity not in STANDARD_RARITIES:
            split_note = "Split from rarity table. "
            split_items = split_by_rarity_table(base_item_name(name), description)
            if not split_items:
                split_note = "Split from labeled variants. "
                split_items = split_by_labeled_variants(base_item_name(name), description)
            if split_items:
                for variant_name, variant_rarity, variant_desc in split_items:
                    append_row([variant_name, variant_rarity, attuenement, itemType, source,
                                variant_desc, URL, notes + split_note])
                return

    if len(line1Parts) > 2:
        notes = notes + "Multiple items. "
        
    loop_limit = max(2, len(line1Parts))
    for i in range(1, loop_limit):
        if i < len(line1Parts):
            sub_match = re.search(r'\((.*?)\)', line1Parts[i])
            if sub_match:
                extracted_text = sub_match.group(1)
                fullName = f"{base_item_name(name)}, {extracted_text}"

            rairity = clean_rarity(line1Parts[i])
        else:
            rairity = "Unknown Rarity"

        # One entry listing several rarities ("common or uncommon") becomes one item per rarity
        tokens = RARITY_TOKEN.findall(rairity.lower())
        leftover = re.sub(r'[\s,/&]|\band\b|\bor\b', '', RARITY_TOKEN.sub('', rairity.lower()))
        if len(tokens) >= 2 and not leftover:
            for token in tokens:
                append_row([f"{base_item_name(name)}, {token.title()}", token, attuenement, itemType, source,
                            description, URL, notes + "Multiple rarities. "])
            continue

        new_line = [fullName, rairity, attuenement, itemType, source, description, URL, notes]
        append_row(new_line)
            
# ==========================================
#  MAIN EXECUTION LOOP 
# ==========================================
if __name__ == "__main__":
    print(f"Starting parsing process using source file: {names_file}...")
    
    if not os.path.exists(names_file):
        print(f"Error: Could not locate master input file: {names_file}")
    else:
        try:
            if os.path.exists(csv_file):
                os.remove(csv_file)
                
            with open(names_file, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f)
                row_count = 0
                for row in reader:
                    if len(row) >= 2:
                        url_to_scrape = row[0].strip()
                        item_name = row[1].strip()
                        if url_to_scrape.lower().startswith("http"):
                            my_function(url_to_scrape, item_name)
                            row_count += 1
                
                print(f"\nFinished! Cleanly parsed {row_count} items into database.")

        except Exception as e:
            print(f"Fatal execution crash reading file loops: {str(e)}")
