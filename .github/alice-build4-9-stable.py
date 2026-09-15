#!/usr/bin/env python3
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Alice4.9 anchor missing: {label}")
    return text.replace(old, new, 1)

p = Path("app/build.gradle.kts")
s = p.read_text()
s = once(s, "versionCode = 64009", "versionCode = 64010", "versionCode")
s = once(
    s,
    'versionName = "3.15.2-alice4.8-stable-duck"',
    'versionName = "3.15.2-alice4.9-stable"',
    "versionName",
)
p.write_text(s)

print("Alice4.9 stable identity applied: 4.8 behavior preserved; custom autostart popup omitted")
