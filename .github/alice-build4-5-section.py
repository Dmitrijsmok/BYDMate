#!/usr/bin/env python3
import sys
from pathlib import Path

which = sys.argv[1] if len(sys.argv) > 1 else ""
source_path = Path(".github/alice-build4-5-build95-recovery.py")
source = source_path.read_text()
markers = {
    "1": "# ---------------------------------------------------------------------------\n# 1) Identity:",
    "2": "# ---------------------------------------------------------------------------\n# 2) Helper daemon:",
    "3": "# ---------------------------------------------------------------------------\n# 3) Absolutely no Alice/Yandex boot prewarm.",
    "4": "# ---------------------------------------------------------------------------\n# 4) Steering/Alice state machine.",
}
if which not in {"1", "3", "4"}:
    raise SystemExit("usage: alice-build4-5-section.py 1|3|4")
header_end = source.find(markers["1"])
if header_end < 0:
    raise SystemExit("Alice4.5 section header missing")
header = source[:header_end]
start = source.find(markers[which])
if start < 0:
    raise SystemExit(f"Alice4.5 section {which} start missing")
if which == "1":
    end = source.find(markers["2"], start)
elif which == "3":
    end = source.find(markers["4"], start)
else:
    end = len(source)
if end < 0:
    raise SystemExit(f"Alice4.5 section {which} end missing")
code = header + source[start:end]

# Alice4.2 boot-prewarm inserted aliceBootPrewarm=false into cancelAliceClick().
# The original 4.5 patch was written against the 4.1 three-line reset anchor;
# normalize that expected old block to the actual generated 4.4 source.
if which == "4":
    old_literal = '''        aliceColdEntryClicked = false
        aliceCandidateDumped = false
        aliceClickGeneration++
'''
    actual_literal = '''        aliceColdEntryClicked = false
        aliceCandidateDumped = false
        aliceBootPrewarm = false
        aliceClickGeneration++
'''
    code = code.replace(repr(old_literal), repr(actual_literal))

exec(compile(code, f"{source_path}#section{which}", "exec"), {"__name__": "__main__"})
