#!/usr/bin/env python3
from pathlib import Path

VERSION_CODE = "60027"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Build77 anchor missing: {label}")
    return text.replace(old, new, 1)


# 1) Field identity: monotonic update over Build76.
p = Path("app/build.gradle.kts")
s = p.read_text()
s = replace_once(s, "        versionCode = 60026", f"        versionCode = {VERSION_CODE}", "versionCode")
s = replace_once(
    s,
    '            versionNameSuffix = "-dilink3-production-build76"',
    '            versionNameSuffix = "-dilink3-production-build77"',
    "versionNameSuffix",
)
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = replace_once(
    s,
    'android:label="BYDMate DiLink3 Build76"',
    'android:label="BYDMate DiLink3 Build77"',
    "manifest label",
)
p.write_text(s)


# 2) Add Supertonic speaker sid=0 as a separate selectable Russian voice.
#    It reuses the already-supported Supertonic archive/model and differs only
#    by speakerId. Existing voices remain untouched.
p = Path("app/src/main/kotlin/com/bydmate/app/voice/TtsVoiceCatalog.kt")
s = p.read_text()
old = '''        TtsVoice(
            id = "sofia", labelRes = R.string.settings_tts_voice_sofia, url = SUPERTONIC_URL,
            gender = TtsGender.FEMALE, engine = TtsVoiceEngine.SUPERTONIC,
            modelDirId = "supertonic-ru", speakerId = 3, sizeMb = 145,
        ),
'''
new = old + '''        TtsVoice(
            id = "marusya", labelRes = R.string.settings_tts_voice_marusya, url = SUPERTONIC_URL,
            gender = TtsGender.FEMALE, engine = TtsVoiceEngine.SUPERTONIC,
            modelDirId = "supertonic-ru", speakerId = 0, sizeMb = 145,
        ),
'''
s = replace_once(s, old, new, "Supertonic sid=0 Marusya voice")
p.write_text(s)


# 3) UI labels. Russian name intentionally stays "Маруся"; English locale uses
#    transliteration but points to the exact same sid=0 voice.
for values_dir, name in (
    ("values", "Маруся"),
    ("values-en", "Marusya"),
):
    p = Path(f"app/src/main/res/{values_dir}/strings.xml")
    if not p.exists():
        continue
    s = p.read_text()
    if 'name="settings_tts_voice_marusya"' not in s:
        s = replace_once(
            s,
            "</resources>",
            f'    <string name="settings_tts_voice_marusya">{name}</string>\n</resources>',
            f"Marusya label {values_dir}",
        )
    p.write_text(s)

print("Build77 applied: Supertonic sid=0 added as Marusya")
