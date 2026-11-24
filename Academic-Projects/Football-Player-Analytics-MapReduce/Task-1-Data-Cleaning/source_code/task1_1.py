"""
COMP6210 Assignment 1 - Task 1.1: Data Import, Cleaning, and Extraction
========================================================================

This script:
  Step 1 - imports data.csv into MongoDB as a raw collection
  Step 2 - applies 6 cleaning rules IN ORDER, storing the result in a
           new "cleaned" collection (a record removed in one rule is
           never used by a later rule)
  Step 3 - extracts the required fields from the cleaned collection and
           writes them to player_data.txt, plus a cleaning_report.txt
           summarising what happened
"""

import re
import csv
import pandas as pd
from pymongo import MongoClient

CSV_PATH = "data.csv"
DB_NAME = "Assignment_1"
RAW_COLLECTION = "FIFA_players"
CLEANED_COLLECTION = "FIFA_players_cleaned"

# Fields treated as free text -> get whitespace cleanup in cleaning rule 1
STRING_FIELDS = ["player_name", "nationality", "club", "position", "season", "competition"]

# Fields checked for negative (invalid) values in cleaning rule 4
NUMERIC_CHECK_FIELDS = [
    "market_value_eur_m", "minutes_played", "goals", "assists",
    "shots_on_target", "tackles", "match_rating", "fouls_committed",
]

# The 5 values every competition name must be mapped to in cleaning rule 2
CANONICAL_COMPETITIONS = [
    "FIFA World Cup 2026", "Champions League", "Domestic Cup",
    "World Cup Qualifiers", "League",
]
# Lookup by lowercase so "LEAGUE", "league", " League " etc. all match
CANON_MAP = {c.lower(): c for c in CANONICAL_COMPETITIONS}

# Exact column order required for player_data.txt
OUTPUT_FIELDS_ORDER = [
    "player_name", "nationality", "club", "position", "market_value_eur_m",
    "competition", "match_id", "minutes_played", "goals", "assists", "match_rating",
]


def clean_string(value):
    """Trim leading/trailing spaces and collapse internal multiple spaces to one.
    e.g. "  Erling   Haaland " -> "Erling Haaland" """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return value
    return re.sub(r"\s+", " ", str(value).strip())


def standardize_competition(value):
    """Map any case/spacing variant of a competition name to its canonical form.
    e.g. "world cup Qualifiers" -> "World Cup Qualifiers" """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return value
    return CANON_MAP.get(str(value).lower(), value)


def is_missing(value):
    """True for None, NaN, or empty string - covers however pandas/pymongo
    represent a blank cell from the CSV."""
    return value is None or (isinstance(value, float) and pd.isna(value)) or value == ""


def main():
    client = MongoClient("localhost:27017")
    db = client[DB_NAME]

    # =====================================================================
    # STEP 1: Import the dataset
    # Read data.csv with pandas (utf-8-sig handles the BOM at the start of
    # the file), then load every row as-is into MongoDB. This raw
    # collection is never modified - it's our untouched source of truth.
    # =====================================================================
    raw_col = db[RAW_COLLECTION]
    raw_col.drop()
    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
    records = df.to_dict(orient="records")
    raw_col.insert_many(records)
    print(f"Imported {len(records)} raw records into {DB_NAME}.{RAW_COLLECTION}")

    # =====================================================================
    # STEP 2: Clean the data
    # We pull the raw docs into a plain Python list and work through the
    # 6 rules in order. Each rule operates on whatever survived the rule
    # before it, so a record dropped in rule 3 can never affect rule 5's
    # nationality-inference grouping, etc.
    # =====================================================================
    docs = list(raw_col.find())
    for d in docs:
        d.pop("_id", None)  # don't carry Mongo's internal id through the pipeline

    # Snapshot "before cleaning" stats now, before anything is touched -
    # the report needs these raw-data counts, not post-cleaning ones.
    before_total = len(docs)
    before_unknown_nationality = sum(1 for d in docs if d.get("nationality") == "Unknown")
    before_missing_market_value = sum(1 for d in docs if is_missing(d.get("market_value_eur_m")))

    # --- Rule 1: String standardization ---------------------------------
    # For every string field on every record, trim the ends and collapse
    # any run of internal whitespace to a single space. We also track how
    # many *records* had at least one field actually change, for the report.
    standardized_count = 0
    for d in docs:
        changed = False
        for f in STRING_FIELDS:
            if f in d and not is_missing(d[f]):
                new_val = clean_string(d[f])
                if new_val != d[f]:
                    changed = True
                d[f] = new_val
        if changed:
            standardized_count += 1

    # --- Rule 2: Competition standardization ----------------------------
    # Runs after rule 1 so values are already trimmed/collapsed; this step
    # only needs to fix casing/wording differences (e.g. "CHAMPIONS LEAGUE"
    # -> "Champions League"). Unrecognised values are left as-is; they will
    # be caught as "missing identifiers" if they don't match a canonical
    # name AND the field is otherwise unusable - but per the spec we only
    # standardise known variants here, we don't invent new removals.
    for d in docs:
        d["competition"] = standardize_competition(d.get("competition"))

    # --- Rule 3: Missing identifiers -> remove --------------------------
    # Must run AFTER string/competition standardisation, so a value that
    # only *looked* missing due to stray spaces has already been fixed.
    # Any record still missing player_name, competition, or match_id is
    # unusable as a record and is dropped for good.
    docs = [
        d for d in docs
        if not is_missing(d.get("player_name"))
        and not is_missing(d.get("competition"))
        and not is_missing(d.get("match_id"))
    ]

    # --- Rule 4: Invalid numeric values -> remove -----------------------
    # A negative value in any of these fields doesn't make sense for a
    # match record (e.g. you can't play -5 minutes), so the whole record
    # is dropped rather than trying to "fix" the number.
    def has_negative(d):
        for f in NUMERIC_CHECK_FIELDS:
            v = d.get(f)
            if v is not None and not is_missing(v) and v < 0:
                return True
        return False

    docs = [d for d in docs if not has_negative(d)]

    # --- Rule 5: Unknown nationality inference --------------------------
    # Group the SURVIVING records (after rules 3-4) by (player_name, age,
    # club) - these three together should identify the same real player.
    # If every non-"Unknown" nationality within a group agrees, we trust
    # it and fill in "Unknown" with that value. If the group has more than
    # one distinct known nationality (data disagrees), we leave "Unknown"
    # alone rather than guess.
    groups = {}
    for d in docs:
        key = (d.get("player_name"), d.get("age"), d.get("club"))
        groups.setdefault(key, []).append(d)

    for key, group in groups.items():
        known = {d["nationality"] for d in group
                 if d.get("nationality") != "Unknown" and not is_missing(d.get("nationality"))}
        if len(known) == 1:
            inferred = next(iter(known))
            for d in group:
                if d.get("nationality") == "Unknown":
                    d["nationality"] = inferred

    # --- Rule 6: Missing market value -> fill with group average -------
    # Group by (competition, player_name) - the same player can have a
    # different market value per competition/season, so we only average
    # within that specific combination. If there's no known value at all
    # for that group, we can't compute an average, so we store "NA"
    # exactly as the spec requires, instead of leaving it blank.
    mv_groups = {}
    for d in docs:
        key = (d.get("competition"), d.get("player_name"))
        mv_groups.setdefault(key, []).append(d)

    for key, group in mv_groups.items():
        known_vals = [d["market_value_eur_m"] for d in group if not is_missing(d.get("market_value_eur_m"))]
        avg = round(sum(known_vals) / len(known_vals), 4) if known_vals else None
        for d in group:
            if is_missing(d.get("market_value_eur_m")):
                d["market_value_eur_m"] = avg if avg is not None else "NA"

    after_total = len(docs)

    # Store everything that survived all 6 rules as the cleaned collection.
    cleaned_col = db[CLEANED_COLLECTION]
    cleaned_col.drop()
    if docs:
        cleaned_col.insert_many(docs)
    print(f"Stored {after_total} cleaned records into {DB_NAME}.{CLEANED_COLLECTION}")

    # =====================================================================
    # STEP 3: Extract fields -> player_data.txt
    # Pull each cleaned document from Mongo (not the in-memory `docs` list,
    # to prove the data really is in the cleaned collection) and write out
    # only the 11 required fields, in the exact order requested, comma-
    # separated, one record per line.
    # =====================================================================
    def fmt(field, value):
        # match_id/minutes_played/goals/assists arrive from pandas as
        # floats whenever the source column contained any NaN (pandas
        # upcasts the whole int column to float). Print them as plain
        # integers when they're whole numbers, matching the sample output.
        if field in ("match_id", "minutes_played", "goals", "assists") and isinstance(value, float):
            return int(value)
        return value

    with open("player_data.txt", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for d in cleaned_col.find():
            row = [fmt(field, d.get(field, "")) for field in OUTPUT_FIELDS_ORDER]
            writer.writerow(row)
    print("Wrote player_data.txt")

    # =====================================================================
    # cleaning_report.txt
    # All 5 numbers required by the spec. Note the "before cleaning" stats
    # were captured at the very top of Step 2, before any rule ran.
    # =====================================================================
    with open("cleaning_report.txt", "w", encoding="utf-8") as f:
        f.write(f"Total records before cleaning: {before_total}\n")
        f.write(f"Total records after cleaning: {after_total}\n")
        f.write(f"Records with nationality = 'Unknown' before cleaning: {before_unknown_nationality}\n")
        f.write(f"Records with missing market_value_eur_m before cleaning: {before_missing_market_value}\n")
        f.write(f"Records whose string fields were standardized: {standardized_count}\n")
    print("Wrote cleaning_report.txt")


if __name__ == "__main__":
    main()