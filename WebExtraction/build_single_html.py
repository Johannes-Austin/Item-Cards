"""
Builds a single-file version of the card maker by embedding items.csv (magic items),
mundaneItems.csv (regular items), spells.csv (spells), and open5eItems.csv and open5eSpells.csv
(secondary items and spells from third-party books) into template.html.

    python build_single_html.py
    python build_single_html.py --csv MyOtherItems.csv --out index.html

The page still has its "choose file" box, so anyone can add more items from their own CSV;
the built-in items are always kept. The card background images (common.png, rare.png, ...)
are NOT embedded: keep them in the same folder as the output HTML (e.g. on GitHub Pages).

Only the Python standard library is used.
"""
import argparse
import csv
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# index.html (the finished card maker) goes in the main CardHTML folder (next to the card background images), not in WebExtraction.
# If this script is run from a folder named WebExtraction, that means its parent folder.
OUT_DIR = os.path.dirname(HERE) if os.path.basename(HERE).lower() == "webextraction" else HERE

EXPECTED_COLUMNS = ["Name", "Rarity", "Attunement", "Type", "Source", "Description", "URL", "Notes"]


def placeholder(element_id):
    """The element in index.html that holds an embedded CSV text (as a JSON string)"""
    return re.compile(r'(<script id="' + element_id + r'" type="application/json">)(.*?)(</script>)', re.DOTALL)


def read_csv_text(path):
    """Reads the CSV as text. UTF-8 if valid, otherwise Windows-1252 (what the wiki export sometimes is)."""
    with open(path, "rb") as f:
        raw = f.read()
    try:
        return raw.decode("utf-8-sig"), "UTF-8"
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace"), "Windows-1252"


def check_csv(path):
    """Reads a CSV and checks it has items; returns (text, encoding, item count)"""
    csv_text, encoding = read_csv_text(path)
    reader = csv.DictReader(io.StringIO(csv_text, newline=""))
    columns = reader.fieldnames or []
    if "Name" not in columns:
        sys.exit(f"Error: {path} has no 'Name' column (found: {', '.join(columns) or 'nothing'}).")
    missing = [c for c in EXPECTED_COLUMNS if c not in columns]
    if missing:
        print(f"Warning: {path} is missing these columns: {', '.join(missing)}")
    item_count = sum(1 for row in reader if (row.get("Name") or "").strip())
    if item_count == 0:
        sys.exit(f"Error: {path} has no items.")
    return csv_text, encoding, item_count


def main():
    parser = argparse.ArgumentParser(description="Embed items.csv, mundaneItems.csv, spells.csv, open5eItems.csv and open5eSpells.csv into the card maker HTML to make one file.")
    parser.add_argument("--template", default=os.path.join(HERE, "template.html"), help="the card maker template HTML (default: template.html)")
    parser.add_argument("--csv", default=os.path.join(HERE, "items.csv"), help="the magic items CSV to embed (default: items.csv)")
    parser.add_argument("--mundane-csv", default=os.path.join(HERE, "mundaneItems.csv"), help="the regular items CSV to embed (default: mundaneItems.csv; skipped if it doesn't exist)")
    parser.add_argument("--spells-csv", default=os.path.join(HERE, "spells.csv"), help="the spells CSV to embed (default: spells.csv; skipped if it doesn't exist)")
    parser.add_argument("--secondary-csv", default=os.path.join(HERE, "open5eItems.csv"), help="the secondary (third-party) items CSV to embed (default: open5eItems.csv; skipped if it doesn't exist)")
    parser.add_argument("--secondary-spells-csv", default=os.path.join(HERE, "open5eSpells.csv"), help="the secondary (third-party) spells CSV to embed (default: open5eSpells.csv; skipped if it doesn't exist)")
    parser.add_argument("--out", default=os.path.join(OUT_DIR, "index.html"), help="the HTML file to create (default: index.html in the main CardHTML folder)")
    args = parser.parse_args()

    for label, path in (("Template HTML", args.template), ("Items CSV", args.csv)):
        if not os.path.exists(path):
            sys.exit(f"Error: {label} not found: {path}")

    if os.path.abspath(args.out) == os.path.abspath(args.template):
        sys.exit("Error: the output file would overwrite the template. Choose a different --out name.")

    # (element id, CSV path, label) for each CSV to embed. The regular items, spells and secondary items are optional.
    embeds = [("embeddedCsv", args.csv, "magic items")]
    for element_id, path, label, bat in (("embeddedMundaneCsv", args.mundane_csv, "regular items", "RunMundaneGather.BAT"),
                                         ("embeddedSpellsCsv", args.spells_csv, "spells", "RunSpellGather.BAT"),
                                         ("embeddedSecondaryCsv", args.secondary_csv, "secondary items", "RunOpen5eGather.BAT"),
                                         ("embeddedSecondarySpellsCsv", args.secondary_spells_csv, "secondary spells", "RunOpen5eGather.BAT")):
        if os.path.exists(path):
            embeds.append((element_id, path, label))
        else:
            print(f"Warning: {path} not found, so the page will have no {label}. Run {bat} to create it.")

    with open(args.template, "r", encoding="utf-8", newline="") as f:
        output = f.read()

    results = []
    for element_id, path, label in embeds:
        csv_text, encoding, item_count = check_csv(path)
        pattern = placeholder(element_id)
        if not pattern.search(output):
            sys.exit(f'Error: could not find <script id="{element_id}" ...> in the template. Is it the updated template.html?')
        # "<" is written as < so nothing in the data can ever be mistaken for HTML (e.g. "</script>")
        payload = json.dumps(csv_text, ensure_ascii=False).replace("<", "\\u003c")
        output = pattern.sub(lambda m: m.group(1) + payload + m.group(3), output, count=1)
        results.append((element_id, path, label, csv_text, encoding, item_count))

    with open(args.out, "w", encoding="utf-8", newline="") as f:
        f.write(output)

    # --- Verify by reading the output back ---
    with open(args.out, "r", encoding="utf-8", newline="") as f:
        written = f.read()
    for element_id, path, label, csv_text, encoding, item_count in results:
        embedded = json.loads(placeholder(element_id).search(written).group(2))
        if embedded != csv_text:
            sys.exit(f"Error: the embedded {label} do not match {path}. Something went wrong; the output should not be used.")
        print(f"Embedded {item_count} {label} from {path} (read as {encoding}).")

    size_kb = os.path.getsize(args.out) / 1024
    print(f"Created {os.path.abspath(args.out)} ({size_kb:,.0f} KB).")
    print("Keep the card background images (common.png, uncommon.png, rare.png, very-rare.png, legendary.png, artifact.png)")
    print("in the same folder as this HTML file.")


if __name__ == "__main__":
    main()
