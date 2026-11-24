"""
COMP6210 Assignment 1 - Task 1.2: Data Organization (MapReduce)
================================================================

Input:  player_data.txt (comma-separated, no header) - the output of task1_1.py
Output: records grouped by competition (ascending alphabetically), and
        within each competition group, sorted by player_name then match_id
        (both ascending).

How the sort is done with MapReduce (steps + mapper + reducer only):
  Step 1
  - MAPPING: each mapper emits (competition, full_record), so competition
    is the key and all records for the same competition are grouped
    together in the shuffle.
  - REDUCING: the reducer sorts each competition's records by player_name
    and then match_id, and sends the sorted group on with the key None.
  Step 2
  - REDUCING: one reducer gets all the competition groups, sorts the
    competitions alphabetically and writes out the records. This keeps the
    competition order correct even if more than one reducer is used.
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

# 1) `pipes` (removed in Python 3.13) - pipes.quote == shlex.quote
if "pipes" not in sys.modules:
    try:
        import pipes  # noqa: F401  (works fine on Python < 3.13)
    except ModuleNotFoundError:
        fake_pipes = types.ModuleType("pipes")
        fake_pipes.quote = shlex.quote
        sys.modules["pipes"] = fake_pipes

# 2) `distutils` (removed in Python 3.12+) - mrjob only needs
#    distutils.spawn.find_executable (== shutil.which) and
#    distutils.version.LooseVersion (a simple dotted-version comparator).
if "distutils" not in sys.modules:
    try:
        import distutils  # noqa: F401  (works fine on Python < 3.12)
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
from mrjob.protocol import RawValueProtocol

# Column order matches task1_1.py's OUTPUT_FIELDS_ORDER for player_data.txt
FIELD_NAMES = [
    "player_name", "nationality", "club", "position", "market_value_eur_m",
    "competition", "match_id", "minutes_played", "goals", "assists", "match_rating",
]


class MRDataOrganization(MRJob):
    # Input/output are plain CSV text lines, not mrjob's default JSON
    INPUT_PROTOCOL = RawValueProtocol
    OUTPUT_PROTOCOL = RawValueProtocol

    def steps(self):
        return [
            MRStep(mapper=self.mapper, reducer=self.reducer),
            MRStep(reducer=self.reducer_sort_competitions),
        ]

    def mapper(self, _, line):
        line = line.strip()
        if not line:
            return
        row = next(csv.reader(io.StringIO(line)))
        if len(row) != len(FIELD_NAMES):
            return  # skip any malformed line
        record = dict(zip(FIELD_NAMES, row))
        competition = record["competition"]
        # key = competition -> groups all records for the same competition
        # together at the reducer
        yield competition, row

    def reducer(self, competition, rows):
        # `rows` holds every record for this one competition. Sort by
        # player_name (ascending), then match_id (ascending, numeric).
        rows = list(rows)
        rows.sort(key=lambda r: (r[0], int(float(r[6]))))
        # key None -> all competitions go to the same reducer in Step 2
        yield None, (competition, rows)

    def reducer_sort_competitions(self, _, groups):
        # Step 2: sort the competitions A-Z, then output each record
        for competition, rows in sorted(groups, key=lambda g: g[0]):
            for row in rows:
                yield None, ",".join(row)


if __name__ == "__main__":
    MRDataOrganization.run()