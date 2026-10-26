"""Build the static site served at spanish-anki.shafe.dev.

Writes public/spanish_conjugation.apkg (via create-anki-deck.py) and
public/cards.json, a compact copy of the same cards for the in-browser preview.
"""

import importlib.util
import json
import os
import re
import sqlite3
import zipfile

PUBLIC_DIR = "public"
DECK_FILE = "spanish_conjugation.apkg"


def load_deck_builder():
    spec = importlib.util.spec_from_file_location(
        "create_anki_deck", "create-anki-deck.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compress_deck(path):
    # genanki writes the .apkg uncompressed; Anki reads deflated archives too
    with zipfile.ZipFile(path) as src:
        entries = [(info, src.read(info)) for info in src.infolist()]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as dst:
        for info, content in entries:
            dst.writestr(info.filename, content)


def export_cards(path):
    con = sqlite3.connect("cards.db")
    rows = con.execute(
        "select verb, form, person, conjugation_id, conjugation,"
        " hypothetical_regular_conjugation, regularity_class, example_sentence"
        # Mirrors create-anki-deck.py, which skips rows with any of these missing
        " from cards where conjugation is not null and example_sentence is not null"
        " and hypothetical_regular_conjugation is not null"
        " and regularity_class is not null and audio_path is not null"
        " order by verb_id, form_id, person_id"
    ).fetchall()
    con.close()

    verbs, forms, persons, classes = [], [], [], []

    def index(values, value):
        if value not in values:
            values.append(value)
        return values.index(value)

    cards = []
    for verb, form, person, cid, conj, hypo, reg, sentence in rows:
        # Same rule as create-anki-deck.py: the conjugation must appear exactly once
        pattern = r"\b" + re.escape(conj) + r"\b"
        matches = list(re.finditer(pattern, sentence, re.IGNORECASE))
        if len(matches) != 1:
            continue
        start, end = matches[0].span()
        cards.append(
            [
                index(verbs, verb),
                index(forms, form),
                index(persons, person),
                index(classes, reg),
                cid,
                conj,
                hypo,
                sentence,
                start,
                end,
            ]
        )

    data = {
        "verbs": verbs,
        "forms": forms,
        "persons": persons,
        "classes": classes,
        "deckFile": DECK_FILE,
        "deckBytes": os.path.getsize(os.path.join(PUBLIC_DIR, DECK_FILE)),
        "cards": cards,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    return len(cards)


def main():
    os.makedirs(PUBLIC_DIR, exist_ok=True)
    deck_path = os.path.join(PUBLIC_DIR, DECK_FILE)
    load_deck_builder().main(output_file=deck_path)
    compress_deck(deck_path)
    count = export_cards(os.path.join(PUBLIC_DIR, "cards.json"))
    print(f"Wrote {count} cards to {PUBLIC_DIR}/cards.json")


if __name__ == "__main__":
    main()
