"""Copies The Griffon's Saddlebag's item art into ../GriffonsArt, one image per item, named after the item.

The art comes from Patreon pages you saved yourself in Chrome ("Save page as", "Webpage, Complete") while signed in,
e.g. the creator's posts filtered to the Art tag. Each post's first image is the item's art (e.g.
"Spider-Silk-Laces_800_Flat.png"), and Chrome saves it in the page's "_files" folder. An image Chrome didn't save is
downloaded from the address in the page.

The art is for your own use: .gitignore keeps GriffonsArt out of the repository.

    python GriffonsArt.py "C:\\Users\\Austin\\Downloads\\The Griffon's Saddlebag _ Posts _ Patreon.html" [more saved pages...]
"""
import csv
import difflib
import os
import re
import shutil
import sys
import time
import urllib.parse

import requests
from bs4 import BeautifulSoup as bs

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ART_DIR = os.path.join(os.path.dirname(BASE_DIR), "GriffonsArt")
ITEMS_CSV = os.path.join(BASE_DIR, "griffonsSaddlebag.csv")
RENAMED = " (Griffon's Saddlebag)"


def name_key(name):
    """Lowercase letters and digits only, with doubled letters made single so a typo like "Switcherooo" still matches"""
    key = re.sub(r'[^a-z0-9]+', ' ', name.lower().replace("’", "").replace("'", "")).strip()
    return re.sub(r'([a-z])\1+', r'\1', key)


def find_item(title, items):
    """The item a post is about: its title, or the title without extra words after a dash ("Criir's Scepter — End of
    Year 5!"), or a near-identical name for a typo or plural ("Thundrous Flail", "Rust Arrows")"""
    for candidate in (title, re.split(r'\s+[—–-]\s+', title)[0]):
        key = name_key(candidate)
        if key in items:
            return items[key]
        close = difflib.get_close_matches(key, items.keys(), n=1, cutoff=0.9)
        if close:
            return items[close[0]]
    return None


def file_name(item_name):
    """The item's name, minus characters Windows doesn't allow in file names"""
    return re.sub(r'[<>:"/\\|?*]', '', item_name).strip()


def first_image(card, page_dir):
    """(local path or URL) of a post's first gallery image, or None"""
    img = card.select_one('[data-tag=gallery-image] img, img[data-tag=gallery-image]')
    if not img or not img.get("src"):
        return None
    src = urllib.parse.unquote(img["src"])
    if src.startswith("http"):
        return src
    return os.path.normpath(os.path.join(page_dir, src))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    with open(ITEMS_CSV, encoding="utf-8") as f:
        items = {name_key(r["Name"].replace(RENAMED, "")): r["Name"] for r in csv.DictReader(f)}
    os.makedirs(ART_DIR, exist_ok=True)

    copied, downloaded, no_item, no_image, failed, loose = 0, 0, [], [], [], set()
    for page in sys.argv[1:]:
        with open(page, encoding="utf-8", errors="replace") as f:
            soup = bs(f.read(), "html.parser")
        for card in soup.select("[data-tag=post-card]"):
            title = card.select_one("[data-tag=post-title]").get_text(" ", strip=True)
            item = find_item(title, items)
            if not item:
                no_item.append(title)
                continue
            if name_key(item.replace(RENAMED, "")) != name_key(title):
                loose.add(f"{title} -> {item}")
            source = first_image(card, os.path.dirname(os.path.abspath(page)))
            if not source:
                no_image.append(title)
                continue
            ext = os.path.splitext(urllib.parse.urlparse(source).path)[1].lower() or ".png"
            target = os.path.join(ART_DIR, file_name(item) + ext)
            try:
                if source.startswith("http"):
                    response = requests.get(source, timeout=60)
                    response.raise_for_status()
                    with open(target, "wb") as out:
                        out.write(response.content)
                    downloaded += 1
                    time.sleep(0.5)   # gently
                elif os.path.exists(source):
                    shutil.copyfile(source, target)
                    copied += 1
                else:
                    no_image.append(title)
            except Exception as e:
                failed.append(f"{title} ({e})")

    print(f"Saved art for {copied + downloaded} items in {ART_DIR} ({copied} copied, {downloaded} downloaded).")
    if loose:
        print(f"\n{len(loose)} posts matched an item with a slightly different name (check these):\n  " + "\n  ".join(sorted(loose)))
    if no_item:
        print(f"\n{len(no_item)} posts don't match an item name: {', '.join(no_item)}")
    if no_image:
        print(f"\n{len(no_image)} posts have no saved first image: {', '.join(no_image)}")
    if failed:
        print(f"\n{len(failed)} downloads failed: {', '.join(failed)}")
