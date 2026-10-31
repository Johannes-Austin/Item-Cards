"""
Builds a single-file version of the card maker by embedding items.csv into template.html.

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

# The element in index.html that holds the embedded CSV text (as a JSON string)
PLACEHOLDER = re.compile(r'(<script id="embeddedCsv" type="application/json">)(.*?)(</script>)', re.DOTALL)


def read_csv_text(path):
    """Reads the CSV as text. UTF-8 if valid, otherwise Windows-1252 (what the wiki export sometimes is)."""
    with open(path, "rb") as f:
        raw = f.read()
    try:
        return raw.decode("utf-8-sig"), "UTF-8"
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace"), "Windows-1252"


def main():
    parser = argparse.ArgumentParser(description="Embed items.csv into the card maker HTML to make one file.")
    parser.add_argument("--template", default=os.path.join(HERE, "template.html"), help="the card maker template HTML (default: template.html)")
    parser.add_argument("--csv", default=os.path.join(HERE, "items.csv"), help="the items CSV to embed (default: items.csv)")
    parser.add_argument("--out", default=os.path.join(OUT_DIR, "index.html"), help="the HTML file to create (default: index.html in the main CardHTML folder)")
    args = parser.parse_args()

    for label, path in (("Template HTML", args.template), ("Items CSV", args.csv)):
        if not os.path.exists(path):
            sys.exit(f"Error: {label} not found: {path}")

    if os.path.abspath(args.out) == os.path.abspath(args.template):
        sys.exit("Error: the output file would overwrite the template. Choose a different --out name.")

    # --- Read and check the CSV ---
    csv_text, encoding = read_csv_text(args.csv)
    reader = csv.DictReader(io.StringIO(csv_text, newline=""))
    columns = reader.fieldnames or []
    if "Name" not in columns:
        sys.exit(f"Error: {args.csv} has no 'Name' column (found: {', '.join(columns) or 'nothing'}).")
    missing = [c for c in EXPECTED_COLUMNS if c not in columns]
    if missing:
        print(f"Warning: the CSV is missing these columns: {', '.join(missing)}")
    item_count = sum(1 for row in reader if (row.get("Name") or "").strip())
    if item_count == 0:
        sys.exit("Error: the CSV has no items.")

    # --- Embed it ---
    with open(args.template, "r", encoding="utf-8", newline="") as f:
        template = f.read()
    if not PLACEHOLDER.search(template):
        sys.exit('Error: could not find <script id="embeddedCsv" ...> in the template. Is it the updated template.html?')

    # "<" is written as \u003c so nothing in the data can ever be mistaken for HTML (e.g. "</script>")
    payload = json.dumps(csv_text, ensure_ascii=False).replace("<", "\\u003c")
    output = PLACEHOLDER.sub(lambda m: m.group(1) + payload + m.group(3), template, count=1)

    with open(args.out, "w", encoding="utf-8", newline="") as f:
        f.write(output)

    # --- Verify by reading the output back ---
    with open(args.out, "r", encoding="utf-8", newline="") as f:
        written = f.read()
    embedded = json.loads(PLACEHOLDER.search(written).group(2))
    if embedded != csv_text:
        sys.exit("Error: the embedded data does not match the CSV. Something went wrong; the output should not be used.")

    size_kb = os.path.getsize(args.out) / 1024
    print(f"Embedded {item_count} items from {args.csv} (read as {encoding}).")
    print(f"Created {os.path.abspath(args.out)} ({size_kb:,.0f} KB).")
    print("Keep the card background images (common.png, uncommon.png, rare.png, very-rare.png, legendary.png, artifact.png)")
    print("in the same folder as this HTML file.")


if __name__ == "__main__":
    main()
