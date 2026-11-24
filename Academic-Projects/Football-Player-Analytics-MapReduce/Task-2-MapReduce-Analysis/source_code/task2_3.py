"""
COMP6210 Assignment 1 - Task 2.3: World Cup vs Club Performance Gap (MapReduce)
=================================================================================

Input:  player_data.txt (comma-separated, no header) - the output of task1_1.py
Output: the top 10 players by performance_gap (World Cup per-90 minus
        combined-club per-90), descending.

Two MapReduce steps:
  STEP 1 (per player):
    - MAPPER: tag each record "WC" if competition is
      "FIFA World Cup 2026", or "CLUB" if competition is one of
      League / Champions League / Domestic Cup (World Cup Qualifiers
      records are excluded, per the task definition). Emit
      (player_name -> tagged record).
    - REDUCER: for a given player, sum performance_points and
      minutes_played separately across their WC records and their CLUB
      records. Only keep players with worldcup_minutes >= 180 and
      club_minutes >= 180; compute worldcup_per90, club_per90 and
      performance_gap = worldcup_per90 - club_per90. Emit
      (None -> player summary), so all qualifying players land on the
      same key for the final global step.

  STEP 2 (global):
    - MAPPER: identity pass-through.
    - REDUCER: sort all player summaries by performance_gap
      (descending), breaking ties by player_name (ascending), and keep
      only the top 10.
"""

import csv
import io
import sys
import shlex
import shutil
import types
import re as _re

# --- Compatibility shims for Python 3.13 ---------------------------------
if "pipes" not in sys.modules:
    try:
        import pipes  # noqa: F401
    except ModuleNotFoundError:
        fake_pipes = types.ModuleType("pipes")
        fake_pipes.quote = shlex.quote
        sys.modules["pipes"] = fake_pipes

if "distutils" not in sys.modules:
    try:
        import distutils  # noqa: F401
    except ModuleNotFoundError:
        class _LooseVersion:
            def __init__(self, vstring):
                self.vstring = vstring
                self.version = [int(p) if p.isdigit() else p
                                 for p in _re.split(r"[.\-_]", vstring)]

            def _cmp(self, other):
                other = other.version if isinstance(other, _LooseVersion) else _LooseVersion(str(other)).version
                return (self.version > other) - (self.version < other)

            def __eq__(self, other): return self._cmp(other) == 0
            def __lt__(self, other): return self._cmp(other) < 0
            def __le__(self, other): return self._cmp(other) <= 0
            def __gt__(self, other): return self._cmp(other) > 0
            def __ge__(self, other): return self._cmp(other) >= 0
            def __str__(self): return self.vstring

        fake_distutils = types.ModuleType("distutils")
        fake_spawn = types.ModuleType("distutils.spawn")
        fake_spawn.find_executable = lambda name, path=None: shutil.which(name, path=path)
        fake_version = types.ModuleType("distutils.version")
        fake_version.LooseVersion = _LooseVersion

        fake_distutils.spawn = fake_spawn
        fake_distutils.version = fake_version
        sys.modules["distutils"] = fake_distutils
        sys.modules["distutils.spawn"] = fake_spawn
        sys.modules["distutils.version"] = fake_version
# --------------------------------------------------------------------------

from mrjob.job import MRJob
from mrjob.step import MRStep
from mrjob.protocol import RawValueProtocol, JSONProtocol

FIELD_NAMES = [
    "player_name", "nationality", "club", "position", "market_value_eur_m",
    "competition", "match_id", "minutes_played", "goals", "assists", "match_rating",
]

WORLD_CUP = "FIFA World Cup 2026"
CLUB_COMPETITIONS = {"League", "Champions League", "Domestic Cup"}


class MRPerformanceGap(MRJob):
    INPUT_PROTOCOL = RawValueProtocol
    INTERNAL_PROTOCOL = JSONProtocol
    OUTPUT_PROTOCOL = RawValueProtocol

    def steps(self):
        return [
            MRStep(mapper=self.mapper_tag_wc_or_club,
                   reducer=self.reducer_compute_gap),
            MRStep(reducer=self.reducer_top10_players),
        ]

    # ---------------- STEP 1: per-player WC vs CLUB aggregation ----------------
    def mapper_tag_wc_or_club(self, _, line):
        line = line.strip()
        if not line:
            return
        row = next(csv.reader(io.StringIO(line)))
        if len(row) != len(FIELD_NAMES):
            return  # skip any malformed line
        record = dict(zip(FIELD_NAMES, row))

        competition = record["competition"]
        if competition == WORLD_CUP:
            group = "WC"
        elif competition in CLUB_COMPETITIONS:
            group = "CLUB"
        else:
            return  # World Cup Qualifiers records are not used in this task

        goals = float(record["goals"] or 0)
        assists = float(record["assists"] or 0)
        rating = float(record["match_rating"] or 0)
        minutes = float(record["minutes_played"] or 0)
        performance_points = goals * 4 + assists * 3 + rating

        yield record["player_name"], {
            "group": group,
            "nationality": record["nationality"],
            "club": record["club"],
            "performance_points": performance_points,
            "minutes_played": minutes,
        }

    def reducer_compute_gap(self, player_name, records):
        records = list(records)
        wc_points = sum(r["performance_points"] for r in records if r["group"] == "WC")
        wc_minutes = sum(r["minutes_played"] for r in records if r["group"] == "WC")
        club_points = sum(r["performance_points"] for r in records if r["group"] == "CLUB")
        club_minutes = sum(r["minutes_played"] for r in records if r["group"] == "CLUB")

        if wc_minutes < 180 or club_minutes < 180:
            return

        worldcup_per90 = wc_points / wc_minutes * 90
        club_per90 = club_points / club_minutes * 90
        performance_gap = worldcup_per90 - club_per90

        # "club" is the player's club competition club; fall back to any
        # record if a CLUB-tagged one isn't present (shouldn't happen here
        # since club_minutes >= 180 already guarantees at least one).
        club = next((r["club"] for r in records if r["group"] == "CLUB"), records[-1]["club"])
        nationality = records[-1]["nationality"]

        yield None, {
            "player_name": player_name,
            "nationality": nationality,
            "club": club,
            "performance_gap": round(performance_gap, 4),
        }

    # ---------------- STEP 2: top 10 players ----------------
    def reducer_top10_players(self, _, players):
        players = list(players)
        players.sort(key=lambda p: (-p["performance_gap"], p["player_name"]))
        for p in players[:10]:
            yield None, ",".join([
                p["player_name"], p["nationality"], p["club"],
                f'{p["performance_gap"]:.4f}',
            ])


if __name__ == "__main__":
    MRPerformanceGap.run()