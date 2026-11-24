"""
COMP6210 Assignment 1 - Task 2.2: Club Contribution Analysis (MapReduce)
=========================================================================

Input:  player_data.txt (comma-separated, no header) - the output of task1_1.py
Output: the top 10 FIFA World Cup 2026 clubs by total_attack_score.

Three MapReduce steps:
  STEP 1 (per club, per player):
    - MAPPER: keep only "FIFA World Cup 2026" records. For each such
      record, emit ((club, player_name) -> that record's goals, assists).
    - COMBINER: pre-sum goals/assists for the same (club, player_name)
      pair within a mapper's local output, to cut shuffle traffic.
    - REDUCER: sum goals and assists across all of a player's World Cup
      records at that club, giving attack_score = total_goals +
      total_assists. Emit (club -> player_name, attack_score).

  STEP 2 (per club):
    - MAPPER: identity pass-through.
    - REDUCER: for a given club, count its distinct players
      (total_players), sum their attack_score values (total_attack_score),
      and find top_player (highest attack_score, ties broken by
      player_name ascending). Emit (None -> club summary), so every
      club's summary lands on the same key for the final global step.

  STEP 3 (global):
    - MAPPER: identity pass-through.
    - REDUCER: sort all club summaries by total_attack_score
      (descending), breaking ties by club name (ascending), and keep
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

TARGET_COMPETITION = "FIFA World Cup 2026"
KEY_SEP = "\x01"  # separates club/player_name inside a single string key


class MRClubContribution(MRJob):
    INPUT_PROTOCOL = RawValueProtocol
    INTERNAL_PROTOCOL = JSONProtocol
    OUTPUT_PROTOCOL = RawValueProtocol

    def steps(self):
        return [
            MRStep(mapper=self.mapper_extract_wc_records,
                   combiner=self.combiner_sum_goals_assists,
                   reducer=self.reducer_player_attack_score),
            MRStep(mapper=self.mapper_pass_through,
                   reducer=self.reducer_club_summary),
            MRStep(mapper=self.mapper_pass_through,
                   reducer=self.reducer_top10_clubs),
        ]

    # ---------------- STEP 1: attack_score per (club, player) ----------------
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
        key = record["club"] + KEY_SEP + record["player_name"]
        yield key, [goals, assists]

    def combiner_sum_goals_assists(self, key, values):
        goals = assists = 0.0
        for g, a in values:
            goals += g
            assists += a
        yield key, [goals, assists]

    def reducer_player_attack_score(self, key, values):
        club, player_name = key.split(KEY_SEP)
        goals = assists = 0.0
        for g, a in values:
            goals += g
            assists += a
        attack_score = goals + assists
        yield club, {"player_name": player_name, "attack_score": attack_score}

    # ---------------- STEP 2: per-club summary ----------------
    def mapper_pass_through(self, key, value):
        yield key, value

    def reducer_club_summary(self, club, players):
        players = list(players)
        total_players = len(players)
        total_attack_score = sum(p["attack_score"] for p in players)
        top_player = min(players, key=lambda p: (-p["attack_score"], p["player_name"]))
        yield None, {
            "club": club,
            "total_players": total_players,
            "total_attack_score": total_attack_score,
            "top_player": top_player["player_name"],
            "top_player_score": top_player["attack_score"],
        }

    # ---------------- STEP 3: top 10 clubs ----------------
    def reducer_top10_clubs(self, _, clubs):
        clubs = list(clubs)
        clubs.sort(key=lambda c: (-c["total_attack_score"], c["club"]))
        for c in clubs[:10]:
            yield None, ",".join([
                c["club"],
                str(int(c["total_players"])),
                str(int(round(c["total_attack_score"]))),
                c["top_player"],
                str(int(round(c["top_player_score"]))),
            ])


if __name__ == "__main__":
    MRClubContribution.run()