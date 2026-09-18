#!/usr/bin/env python3
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Alice5.5 anchor missing: {label}")
    return text.replace(old, new, 1)


# Final identity for the v3.17.1 rebase. The complete Alice 5.4 feature stack has
# already been applied on top of the upstream 3.17.1 source tree.
p = Path("app/build.gradle.kts")
s = p.read_text()
s = once(s, "versionCode = 64015", "versionCode = 64016", "versionCode")
s = once(
    s,
    'versionName = "3.16.0-alice5.4-sunroof-percent"',
    'versionName = "3.17.1-alice5.5-upstream-rebase"',
    "versionName",
)
p.write_text(s)

print("Alice 5.5 final identity applied: upstream v3.17.1 + Alice 5.4 feature stack")
