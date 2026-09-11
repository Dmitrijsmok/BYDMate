#!/usr/bin/env python3
from pathlib import Path

def once(s, old, new, name):
    if old not in s:
        raise SystemExit(f"Build91 anchor missing: {name}")
    return s.replace(old, new, 1)

p = Path("app/build.gradle.kts")
s = p.read_text()
s = once(s, "versionCode = 60040", "versionCode = 60041", "version")
s = once(s, 'versionNameSuffix = "-dilink3-production-build90"', 'versionNameSuffix = "-dilink3-production-build91"', "suffix")
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = once(s, 'android:label="BYDMate DiLink3 Build90"', 'android:label="BYDMate DiLink3 Build91"', "label")
p.write_text(s)

p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text().replace('SectionHeader(text = "Assistant Lab · Build90")', 'SectionHeader(text = "Assistant Lab · Build91")', 1)
p.write_text(s)

print("Build91 identity applied")
