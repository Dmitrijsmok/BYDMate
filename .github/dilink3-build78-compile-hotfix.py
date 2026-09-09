#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Build78 hotfix anchor missing: {label}")
    return text.replace(old, new, 1)

p = Path("app/src/main/kotlin/com/bydmate/app/voice/SherpaTtsEngine.kt")
s = p.read_text()
s = replace_once(
    s,
    "VoiceTimingDiagnostics.noteSynthEnd(it.size)",
    "VoiceTimingDiagnostics.noteSynthEnd(it?.size ?: 0)",
    "nullable cached synthesis result",
)
p.write_text(s)

p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text()
s = replace_once(
    s,
    "HorizontalDivider(color = Border, modifier = Modifier.padding(vertical = 6.dp))",
    "HorizontalDivider(color = TextMuted, modifier = Modifier.padding(vertical = 6.dp))",
    "existing theme divider color",
)
p.write_text(s)

print("Build78 compile hotfix applied")
