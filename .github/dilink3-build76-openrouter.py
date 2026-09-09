#!/usr/bin/env python3
from pathlib import Path

VERSION_CODE = "60026"
DEFAULT_OPENROUTER_MODEL = "inclusionai/ling-3.0-flash-fin:free"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Build76 anchor missing: {label}")
    return text.replace(old, new, 1)


# 1) Field identity: monotonic update over Build75.
p = Path("app/build.gradle.kts")
s = p.read_text()
s = replace_once(s, "        versionCode = 60025", f"        versionCode = {VERSION_CODE}", "versionCode")
s = replace_once(
    s,
    '            versionNameSuffix = "-dilink3-production-build75"',
    '            versionNameSuffix = "-dilink3-production-build76"',
    "versionNameSuffix",
)
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = replace_once(
    s,
    'android:label="BYDMate DiLink3 Build75"',
    'android:label="BYDMate DiLink3 Build76"',
    "manifest label",
)
p.write_text(s)


# 2) OpenRouter: use the fastest model from the user's live BYDMate benchmark
#    only as the DEFAULT for an empty/new configuration. Existing selections stay
#    untouched and the existing model picker remains the source of truth for users
#    who want another OpenRouter model.
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsViewModel.kt")
s = p.read_text()
s = replace_once(
    s,
    '        /** Slug verified in the live OpenRouter catalog (2026-07-08). */\n'
    '        internal const val DEFAULT_OPENROUTER_MODEL = "google/gemini-3.1-flash-lite"',
    '        /** Fastest passing model in the live BYDMate OpenRouter tool-call benchmark (2026-09-09). */\n'
    f'        internal const val DEFAULT_OPENROUTER_MODEL = "{DEFAULT_OPENROUTER_MODEL}"',
    "OpenRouter default model",
)
p.write_text(s)

print(f"Build76 applied: OpenRouter default={DEFAULT_OPENROUTER_MODEL}; model picker preserved")
