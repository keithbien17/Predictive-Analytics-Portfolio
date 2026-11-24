"""
COMP6210 Assignment 1 - Task 2.1: Value-for-Money Players by Position (MapReduce)
===================================================================================

Input:  player_data.txt (comma-separated, no header) - the output of task1_1.py
Output: for each position, the top three FIFA World Cup 2026 players by
        value_score (descending), among players with total_minutes >= 180
        and a valid avg_market_value > 0.

Two MapReduce steps:
  STEP 1 (per player):
    - MAPPER: keep only "FIFA World Cup 2026" records. For each such
      record, emit (player_name -> that record's relevant fields).
    - REDUCER: for a given player, sum performance_points and
      minutes_played across all of their World Cup records, and average
      their non-NA market_value_eur_m values. Compute performance_per90
      and value_score = performance_per90 / avg_market_value. Players
      who fail total_minutes >= 180 or avg_market_value > 0 are dropped
      here. Emit (position -> player_name, nationality, club, value_score).

  STEP 2 (per position):
    - MAPPER: identity pass-through of Step 1's output.
    - REDUCER: for a given position, sort all candidate players by
      value_score (descending), breaking ties by player_name (ascending),
      and keep only the top three.
"""

import csv
import io
import sys
import shlex
import shutil
import types
import re as _re

# --- Compatibility shims for Python 3.13 ---------------------------------
# mrjob (last released 2020) still imports two modules the standard library
# removed in recent Python versions. We register lightweight stand-ins
# *before* mrjob is imported, so it works without needing an older Python.

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

# Column order matches task1_1.py's OUTPUT_FIELDS_ORDER for player_data.txt
FIELD_NAMES = [
    "player_name", "nationality", "club", "position", "market_value_eur_m",
    "competition", "match_id", "minutes_played", "goals", "assists", "match_rating",
]

TARGET_COMPETITION = "FIFA World Cup 2026"


class MRValueForMoney(MRJob):
    # Plain CSV text lines in, plain CSV text lines out. JSON only used
    # internally between the mapper and reducer of each step.
    INPUT_PROTOCOL = RawValueProtocol
    INTERNAL_PROTOCOL = JSONProtocol
    OUTPUT_PROTOCOL = RawValueProtocol

    def steps(self):
        return [
            MRStep(mapper=self.mapper_extract_wc_records,
                   reducer=self.reducer_compute_value_score),
            MRStep(mapper=self.mapper_pass_through,
                   reducer=self.reducer_top3_per_position),
        ]

    # ---------------- STEP 1: per-player aggregation ----------------
    def mapper_extract_wc_records(self, _, line):
        line = line.strip()
        if not line:
            return
        row = next(csv.reader(io.StringIO(line)))
        if len(row) != len(FIELD_NAMES):
            return  # skip any malformed line
        record = dict(zip(FIELD_NAMES, row))
        if record["competition"] != TARGET_COMPETITION:
            return

        goals = float(record["goals"] or 0)
        assists = float(record["assists"] or 0)
        rating = float(record["match_rating"] or 0)
        minutes = float(record["minutes_played"] or 0)
        market_value = None if record["market_value_eur_m"] in ("", "NA") else float(record["market_value_eur_m"])  # None if "NA"
        performance_points = goals * 4 + assists * 3 + rating

        yield record["player_name"], {
            "nationality": record["nationality"],
            "club": record["club"],
            "position": record["position"],
            "performance_points": performance_points,
            "minutes_played": minutes,
            "market_value": market_value,
        }

    def reducer_compute_value_score(self, player_name, records):
        records = list(records)
        total_performance_points = sum(r["performance_points"] for r in records)
        total_minutes = sum(r["minutes_played"] for r in records)
        market_values = [r["market_value"] for r in records if r["market_value"] is not None]

        if total_minutes < 180 or not market_values:
            return

        avg_market_value = sum(market_values) / len(market_values)
        if avg_market_value <= 0:
            return

        performance_per90 = total_performance_points / total_minutes * 90
        value_score = performance_per90 / avg_market_value

        last = records[-1]
        yield last["position"], {
            "player_name": player_name,
            "nationality": last["nationality"],
            "club": last["club"],
            "value_score": round(value_score, 4),
        }

    # ---------------- STEP 2: top 3 per position ----------------
    def mapper_pass_through(self, position, player):
        yield position, player

    def reducer_top3_per_position(self, position, players):
        players = list(players)
        players.sort(key=lambda p: (-p["value_score"], p["player_name"]))
        for p in players[:3]:
            yield None, ",".join([
                position, p["player_name"], p["nationality"], p["club"],
                f'{p["value_score"]:.4f}',
            ])


if __name__ == "__main__":
    MRValueForMoney.run()