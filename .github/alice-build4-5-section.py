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
# Rewrite the OLD literal inside the patch program so it matches generated 4.4.
if which == "4":
    old_source_literal = """'''        aliceColdEntryClicked = false
        aliceCandidateDumped = false
        aliceClickGeneration++
'''"""
    actual_source_literal = """'''        aliceColdEntryClicked = false
        aliceCandidateDumped = false
        aliceBootPrewarm = false
        aliceClickGeneration++
'''"""
    if old_source_literal not in code:
        raise SystemExit("Alice4.5 section4 cancel literal missing")
    code = code.replace(old_source_literal, actual_source_literal, 1)

exec(compile(code, f"{source_path}#section{which}", "exec"), {"__name__": "__main__"})
