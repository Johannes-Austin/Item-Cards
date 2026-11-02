"""
Builds a single-file version of the card maker by embedding items.csv (magic items),
mundaneItems.csv (regular items), spells.csv (spells), and open5eItems.csv and open5eSpells.csv
(secondary items and spells from third-party books) into template.html.

    python build_single_html.py
    python build_single_html.py --csv MyOtherItems.csv --out index.html

The page still has its "choose file" box, so anyone can add more items from their own CSV;
the built-in items are always kept. The card background images (common.png, rare.png, ...)
are NOT embedded: keep them in the same folder as the output HTML (e.g. on GitHub Pages).

Personal items (griffonsSaddlebag.csv) are embedded encrypted, so only someone with the passphrase can see them
in the page. The passphrase is typed when building (or set in the CARDMAKER_PASSPHRASE environment variable);
it is never saved. Without it, the encrypted copy already in index.html is kept.

Only the Python standard library is used, plus the "cryptography" package for the personal items.
"""
import argparse
import base64
import csv
import getpass
import gzip
import hashlib
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


# --- Personal items: embedded encrypted, unlocked in the page with a passphrase ---
# AES-256-GCM with a key made from the passphrase by PBKDF2-SHA256; the page decrypts it with the browser's Web Crypto.
PERSONAL_ITERATIONS = 600_000
PASSPHRASE_ENV = "CARDMAKER_PASSPHRASE"


def personal_key(passphrase, salt, iterations):
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, iterations, dklen=32)


def encrypt_personal(csv_text, passphrase, item_count):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM   # only needed when there are personal items
    salt, iv = os.urandom(16), os.urandom(12)
    data = AESGCM(personal_key(passphrase, salt, PERSONAL_ITERATIONS)).encrypt(iv, gzip.compress(csv_text.encode("utf-8")), None)
    b64 = lambda raw: base64.b64encode(raw).decode("ascii")
    return {"v": 1, "iterations": PERSONAL_ITERATIONS, "salt": b64(salt), "iv": b64(iv), "count": item_count, "data": b64(data)}


def decrypt_personal(payload, passphrase):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    raw = lambda name: base64.b64decode(payload[name])
    key = personal_key(passphrase, raw("salt"), payload["iterations"])
    return gzip.decompress(AESGCM(key).decrypt(raw("iv"), raw("data"), None)).decode("utf-8")


def ask_passphrase():
    """The passphrase from CARDMAKER_PASSPHRASE, or typed (twice) when run by hand; None to skip"""
    if os.environ.get(PASSPHRASE_ENV):
        return os.environ[PASSPHRASE_ENV]
    if not sys.stdin.isatty():
        return None
    print("\nThe personal items are embedded encrypted. Type the passphrase that unlocks them in the page")
    print("(nothing shows as you type), or just press Enter to keep the ones already in index.html.")
    first = getpass.getpass("Passphrase: ")
    if not first:
        return None
    if getpass.getpass("Type it again: ") != first:
        sys.exit("Error: the two passphrases don't match. Nothing was built.")
    return first


def main():
    parser = argparse.ArgumentParser(description="Embed items.csv, mundaneItems.csv, spells.csv, open5eItems.csv and open5eSpells.csv into the card maker HTML to make one file.")
    parser.add_argument("--template", default=os.path.join(HERE, "template.html"), help="the card maker template HTML (default: template.html)")
    parser.add_argument("--csv", default=os.path.join(HERE, "items.csv"), help="the magic items CSV to embed (default: items.csv)")
    parser.add_argument("--mundane-csv", default=os.path.join(HERE, "mundaneItems.csv"), help="the regular items CSV to embed (default: mundaneItems.csv; skipped if it doesn't exist)")
    parser.add_argument("--spells-csv", default=os.path.join(HERE, "spells.csv"), help="the spells CSV to embed (default: spells.csv; skipped if it doesn't exist)")
    parser.add_argument("--secondary-csv", default=os.path.join(HERE, "open5eItems.csv"), help="the secondary (third-party) items CSV to embed (default: open5eItems.csv; skipped if it doesn't exist)")
    parser.add_argument("--secondary-spells-csv", default=os.path.join(HERE, "open5eSpells.csv"), help="the secondary (third-party) spells CSV to embed (default: open5eSpells.csv; skipped if it doesn't exist)")
    parser.add_argument("--personal-csv", default=os.path.join(HERE, "griffonsSaddlebag.csv"), help="personal items to embed encrypted, unlocked with a passphrase (default: griffonsSaddlebag.csv; skipped if it doesn't exist)")
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

    # Personal items: encrypted with the passphrase. Without one, the encrypted copy already in index.html is kept,
    # so a rebuild never drops them by accident (but it also won't pick up changes to the CSV).
    personal_pattern = placeholder("embeddedPersonal")
    personal, passphrase, personal_note = None, None, ""
    if os.path.exists(args.personal_csv):
        passphrase = ask_passphrase()
        if passphrase:
            csv_text, encoding, item_count = check_csv(args.personal_csv)
            personal = encrypt_personal(csv_text, passphrase, item_count)
            personal_note = f"Embedded {item_count} personal items from {args.personal_csv}, encrypted."
    if personal is None and os.path.exists(args.out):
        with open(args.out, "r", encoding="utf-8") as f:
            previous = personal_pattern.search(f.read())
        kept = json.loads(previous.group(2)) if previous else None
        if kept:
            personal = kept
            personal_note = (f"Kept the {kept.get('count', '?')} encrypted personal items already in index.html "
                             f"(set {PASSPHRASE_ENV} or type the passphrase to update them from the CSV).")
    if personal is not None:
        output = personal_pattern.sub(lambda m: m.group(1) + json.dumps(personal) + m.group(3), output, count=1)
    elif os.path.exists(args.personal_csv):
        personal_note = "Warning: no passphrase, so the personal items are not in the page."

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
    if passphrase and personal is not None:
        embedded = json.loads(personal_pattern.search(written).group(2))
        if decrypt_personal(embedded, passphrase) != check_csv(args.personal_csv)[0]:
            sys.exit("Error: the encrypted personal items don't decrypt back to the CSV. The output should not be used.")
    if personal_note:
        print(personal_note)

    size_kb = os.path.getsize(args.out) / 1024
    print(f"Created {os.path.abspath(args.out)} ({size_kb:,.0f} KB).")
    print("Keep the card background images (common.png, uncommon.png, rare.png, very-rare.png, legendary.png, artifact.png)")
    print("in the same folder as this HTML file.")


if __name__ == "__main__":
    main()
