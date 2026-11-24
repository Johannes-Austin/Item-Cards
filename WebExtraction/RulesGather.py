"""Builds rules.csv, the cards on the page's Rules tab, from the official rules text of the System Reference Document 5.1.

The SRD 5.1 is Wizards of the Coast's free copy of the core 5e (2014) rules, released under the Creative Commons
Attribution 4.0 license, so its text can be reused as long as it is credited (the Notes column does that). It comes
from the D&D 5e SRD API (https://www.dnd5eapi.co), a free API that serves it as JSON: its rules sections and conditions.

A few rules people look up often aren't in the SRD (the Dungeon Master's Guide weather rules: extreme cold and heat,
wind and rain, frigid water, high altitude). Those cards are short summaries in our own words, with the DMG as source.

Each card is listed in RULES below: its name, its category (the Rules tab's filter) and the SRD sections it's made of.
To add a card, add a line there and run this again, then build.

Run with:  python RulesGather.py --cached   to reuse the downloads saved in raw_pages instead of downloading again
"""
import csv
import json
import os
import re
import sys
import time

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRD_API = "https://www.dnd5eapi.co"
CACHE = os.path.join(BASE_DIR, "raw_pages", "rules_srd.json")
headers = ["Name", "Rarity", "Attunement", "Type", "Source", "Description", "URL", "Notes"]

SRD_SOURCE = "System Reference Document 5.1"
SRD_URL = "https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf"
SRD_CREDIT = ("This work includes material taken from the System Reference Document 5.1 (\"SRD 5.1\") by Wizards of "
              "the Coast LLC, available at https://dnd.wizards.com/resources/systems-reference-document. The SRD 5.1 is "
              "licensed under the Creative Commons Attribution 4.0 International License, available at "
              "https://creativecommons.org/licenses/by/4.0/legalcode.")

# (card name, category, parts). A part is ("rule", index, heading), a section of the SRD API's /rules (heading: only
# that #### part of it, None for all of it), or ("condition", index). Several parts on one card each get a heading.
RULES = [
    *[(name.title(), "Condition", [("condition", name)]) for name in
      ["blinded", "charmed", "deafened", "exhaustion", "frightened", "grappled", "incapacitated", "invisible",
       "paralyzed", "petrified", "poisoned", "prone", "restrained", "stunned", "unconscious"]],

    ("Swimming, Climbing & Crawling", "Movement", [("rule", "special-types-of-movement", "Climbing, Swimming, and Crawling")]),
    ("Jumping", "Movement", [("rule", "special-types-of-movement", "Jumping")]),
    ("Falling", "Movement", [("rule", "falling", None)]),
    ("Flying Movement", "Movement", [("rule", "flying-movement", None)]),
    ("Difficult Terrain", "Movement", [("rule", "difficult-terrain", None)]),
    ("Being Prone", "Movement", [("rule", "being-prone", None)]),
    ("Moving Around Other Creatures", "Movement", [("rule", "moving-around-other-creatures", None)]),
    ("Breaking Up Your Move", "Movement", [("rule", "breaking-up-your-move", None)]),
    ("Creature Size & Squeezing", "Movement", [("rule", "creature-size", None)]),
    ("Travel Pace", "Movement", [("rule", "speed", "Travel Pace")]),
    ("Suffocating", "Movement", [("rule", "suffocating", None)]),

    ("Surprise", "Combat", [("rule", "surprise", None)]),
    ("Cover", "Combat", [("rule", "cover", None)]),
    ("Opportunity Attacks", "Combat", [("rule", "melee-attacks", "Opportunity Attacks")]),
    ("Two-Weapon Fighting", "Combat", [("rule", "melee-attacks", "Two-Weapon Fighting")]),
    ("Grappling", "Combat", [("rule", "melee-attacks", "Grappling")]),
    ("Shoving a Creature", "Combat", [("rule", "melee-attacks", "Shoving a Creature")]),
    ("Unseen Attackers & Targets", "Combat", [("rule", "unseen-attackers-and-targets", None)]),
    ("Ranged Attacks", "Combat", [("rule", "ranged-attacks", None)]),
    ("Rolling 1 or 20 & Critical Hits", "Combat", [("rule", "attack-rolls", "Rolling 1 or 20"), ("rule", "damage-rolls", "Critical Hits")]),
    ("Damage Resistance & Vulnerability", "Combat", [("rule", "damage-resistance-and-vulnerability", None)]),
    ("Death Saving Throws", "Combat", [("rule", "dropping-to-0-hit-points", "Instant Death"),
                                       ("rule", "dropping-to-0-hit-points", "Death Saving Throws"),
                                       ("rule", "dropping-to-0-hit-points", "Stabilizing a Creature")]),
    ("Concentration", "Combat", [("rule", "duration", "Concentration")]),
    ("Mounted Combat", "Combat", [("rule", "mounting-and-dismounting", None), ("rule", "controlling-a-mount", None)]),
    ("Underwater Combat", "Combat", [("rule", "underwater-combat", None)]),

    ("Dash", "Action", [("rule", "dash", None)]),
    ("Disengage", "Action", [("rule", "disengage", None)]),
    ("Dodge", "Action", [("rule", "dodge", None)]),
    ("Help", "Action", [("rule", "help", None)]),
    ("Hide & Hiding", "Action", [("rule", "hide", None), ("rule", "dexterity", "Hiding")]),
    ("Ready", "Action", [("rule", "ready", None)]),
    ("Search", "Action", [("rule", "search", None)]),
    ("Use an Object", "Action", [("rule", "use-an-object", None)]),

    ("Bonus Action Spells", "Spellcasting", [("rule", "casting-time", "Bonus Action")]),
    ("Spell Components", "Spellcasting", [("rule", "components", None)]),

    ("Vision & Light", "Environment", [("rule", "vision-and-light", None)]),
    ("Food & Water", "Environment", [("rule", "food-and-water", None)]),

    ("Short Rest", "Resting", [("rule", "short-rest", None)]),
    ("Long Rest", "Resting", [("rule", "long-rest", None)]),

    ("Advantage & Disadvantage", "Checks", [("rule", "advantage-and-disadvantage", None)]),
    ("Typical Difficulty Classes", "Checks", [("rule", "typical-difficulty-classes", None)]),
    ("Contests", "Checks", [("rule", "contests", None)]),
    ("Passive Checks", "Checks", [("rule", "passive-checks", None)]),
    ("Working Together & Group Checks", "Checks", [("rule", "working-together", None)]),
]

# Not in the SRD: the Dungeon Master's Guide's weather rules, summarized in our own words
DMG_SOURCE = "Dungeon Master's Guide (summary)"
DMG_RULES = [
    ("Extreme Cold", "Environment", """
• At 0 °F (−18 °C) or colder, a creature without cold weather gear makes a DC 10 Constitution save at the end of each hour, gaining 1 level of exhaustion on a failure.
• Cold weather gear, resistance or immunity to cold damage, or being adapted to cold climates means automatic success."""),
    ("Extreme Heat", "Environment", """
• At 100 °F (38 °C) or hotter, a creature without access to drinkable water makes a Constitution save at the end of each hour: DC 5, rising by 1 for each hour after the first. Failure: 1 level of exhaustion.
• Disadvantage on the save in medium or heavy armor or heavy clothing.
• Resistance or immunity to fire damage, or being adapted to hot climates, means automatic success."""),
    ("Wind & Precipitation", "Environment", """
**Strong wind:** disadvantage on ranged weapon attacks and on Wisdom (Perception) checks that rely on hearing. Puts out open flames and disperses fog. A creature flying without magic must land at the end of its turn or fall.
**Heavy rain or snow:** the area is lightly obscured (disadvantage on Perception checks that rely on sight); disadvantage on Perception checks that rely on hearing; puts out open flames."""),
    ("Frigid Water", "Environment", """
• A creature can stay in frigid water for a number of minutes equal to its Constitution score with no ill effects.
• Each minute after that: DC 10 Constitution save or 1 level of exhaustion.
• Resistance or immunity to cold damage, or being adapted to cold water, means automatic success."""),
    ("High Altitude", "Environment", """
• Above 10,000 feet, each hour of travel counts as 2 hours toward the limit before a forced march (see **Travel Pace**).
• Creatures can get used to it after 30 days or more at that height, but not above 20,000 feet unless they are native to such places."""),
]


def download():
    """The SRD sections RULES needs: {"rule": {index: text}, "condition": {index: text}}"""
    data = {"rule": {}, "condition": {}}
    wanted = {(kind, key) for _, _, parts in RULES for kind, key, *_ in parts}
    for kind, key in sorted(wanted):
        print(f"  {kind}: {key}")
        if kind == "rule":
            data[kind][key] = requests.get(f"{SRD_API}/api/2014/rules/{key}", timeout=60).json()["desc"]
        else:
            data[kind][key] = "\n".join(requests.get(f"{SRD_API}/api/2014/conditions/{key}", timeout=60).json()["desc"])
        time.sleep(0.2)
    return data


def part_text(text, heading):
    """The part of a section under one heading (up to the next heading of the same or a higher level), or all of it"""
    if not heading:
        return text
    lines = text.split("\n")
    start = next((i for i, line in enumerate(lines) if re.match(rf"^#+\s*{re.escape(heading)}\s*$", line.strip())), None)
    if start is None:
        sys.exit(f"Error: no '{heading}' heading in the SRD text. The source may have changed; check RULES.")
    level = len(re.match(r"^(#+)", lines[start].strip()).group(1))
    end = next((i for i in range(start + 1, len(lines))
                if (m := re.match(r"^(#+)\s", lines[i].strip())) and len(m.group(1)) <= level), len(lines))
    return "\n".join(lines[start + 1:end])


def tidy(text):
    """The SRD's markdown, the way the cards show it: "- " lists as bullets, Exhaustion's "1 - ..." levels as a table,
    no blank lines between paragraphs (the card puts each on its own line anyway)"""
    lines = []
    # "***Forced March.***" -> bold (the cards know ** and *), and no pointers to the book's appendix
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"**\1**", text)
    text = re.sub(r"\s*\((see (the )?|as explained in )appendix [^)]*\)", "", text, flags=re.I)
    text = re.sub(r"a condition described in appendix [\w-]+", "a condition (see Prone)", text, flags=re.I)
    for line in text.replace("\r", "").split("\n"):
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^[-*]\s+", "• ", line)
        level = re.match(r"^(\d) - (.+)$", line)
        if level:
            if not lines or not lines[-1].startswith("|"):
                lines += ["| Level | Effect |", "| --- | --- |"]
            line = f"| {level.group(1)} | {level.group(2)} |"
        lines.append(line)
    return "\n".join(lines)


def main():
    cached = "--cached" in sys.argv
    if cached and os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            data = json.load(f)
    else:
        print("Downloading the SRD rules...")
        data = download()
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    if "speed" not in data.get("rule", {}):
        sys.exit("Error: the saved download is from an older version of this script. Run it without --cached.")
    rows = []
    for name, category, parts in RULES:
        texts = []
        for kind, key, *rest in parts:
            heading = rest[0] if rest else None
            text = tidy(part_text(data[kind][key], heading))
            # several parts on one card: each after its own heading ("mounting-and-dismounting" -> Mounting and Dismounting)
            title = heading or re.sub(r"\b(And|Or|A|The|Of|To)\b", lambda m: m.group(1).lower(), key.replace("-", " ").title())
            texts.append(text if len(parts) == 1 else f"#### {title}\n{text}")
        rows.append({"Name": name, "Rarity": "rule", "Attunement": "", "Type": category, "Source": SRD_SOURCE,
                     "Description": "\n".join(texts), "URL": SRD_URL, "Notes": SRD_CREDIT})
    # The DMG's weather rules go with the SRD's environment rules
    after = max(i for i, row in enumerate(rows) if row["Type"] == "Environment") + 1
    rows[after:after] = [{"Name": name, "Rarity": "rule", "Attunement": "", "Type": category, "Source": DMG_SOURCE,
                          "Description": text.strip("\n"), "URL": "", "Notes": "Not in the SRD; summarized in our own words."}
                         for name, category, text in DMG_RULES]

    with open(os.path.join(BASE_DIR, "rules.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rules to rules.csv ({len(rows) - len(DMG_RULES)} from the SRD 5.1, {len(DMG_RULES)} DMG summaries).")


if __name__ == "__main__":
    main()
