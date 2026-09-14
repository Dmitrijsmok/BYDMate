#!/usr/bin/env python3
from pathlib import Path

source_path = Path(".github/alice-build4-5-build95-recovery.py")
source = source_path.read_text()
start_marker = "# ---------------------------------------------------------------------------\n# 2) Helper daemon:"
end_marker = "# ---------------------------------------------------------------------------\n# 3) Absolutely no Alice/Yandex boot prewarm."
start = source.find(start_marker)
end = source.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit("Alice4.5 wrapper could not isolate obsolete helper section")
source = source[:start] + source[end:]
exec(compile(source, str(source_path), "exec"), {"__name__": "__main__"})
