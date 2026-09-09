#!/usr/bin/env python3
from pathlib import Path

VERSION_CODE = "60030"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Build80 anchor missing: {label}")
    return text.replace(old, new, 1)


# 1) Monotonic upgrade over installed Build79; same package/signing path is preserved by workflow.
p = Path("app/build.gradle.kts")
s = p.read_text()
s = replace_once(s, "        versionCode = 60029", f"        versionCode = {VERSION_CODE}", "versionCode")
s = replace_once(
    s,
    '            versionNameSuffix = "-dilink3-production-build79"',
    '            versionNameSuffix = "-dilink3-production-build80"',
    "versionNameSuffix",
)
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = replace_once(
    s,
    'android:label="BYDMate DiLink3 Build79"',
    'android:label="BYDMate DiLink3 Build80"',
    "manifest label",
)
p.write_text(s)


# 2) Crash fix: do not query vendor/non-standard stream ids while Compose renders Settings.
#    On DiLink 3 the framework is vendor-modified; probing stream ids 15/16/17 at UI launch is unsafe.
#    Keep the safe runtime route measurement populated only after AudioTrack creation.
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text()
old = '''            val _diagTick = diagRefresh // explicit read keeps the polling recomposition dependency
            val diagContext = LocalContext.current
            val diagAudio = diagContext.getSystemService(Context.AUDIO_SERVICE) as? android.media.AudioManager
            fun streamState(id: Int): String = if (diagAudio == null) "—" else runCatching {
                val cur = diagAudio.getStreamVolume(id)
                val max = diagAudio.getStreamMaxVolume(id)
                val muted = runCatching { diagAudio.isStreamMute(id) }.getOrDefault(false)
                "$cur/$max" + if (muted) " mute" else ""
            }.getOrElse { "n/a" }
            fun runtimeAudioConst(className: String, fieldName: String): String = runCatching {
                Class.forName(className).getField(fieldName).getInt(null).toString()
            }.getOrElse { "—" }

            HorizontalDivider(color = TextMuted, modifier = Modifier.padding(vertical = 6.dp))
'''
new = '''            val _diagTick = diagRefresh // explicit read keeps the polling recomposition dependency

            HorizontalDivider(color = TextMuted, modifier = Modifier.padding(vertical = 6.dp))
'''
s = replace_once(s, old, new, "remove launch-time AudioManager probes")

old = '''            Text(
                "Audio route: ${diag.audioRoute.ifBlank { "—" }} · media(3)=${streamState(3)} · s15=${streamState(15)} · s16=${streamState(16)} · s17=${streamState(17)}",
                color = TextMuted, fontSize = 10.sp,
            )
            Text(
                "Framework streams: AudioManager NAVI=${runtimeAudioConst("android.media.AudioManager", "STREAM_NAVI")} " +
                    "BTTS=${runtimeAudioConst("android.media.AudioManager", "STREAM_BTTS")} · " +
                    "AudioSystem NAVI=${runtimeAudioConst("android.media.AudioSystem", "STREAM_NAVI")} " +
                    "BTTS=${runtimeAudioConst("android.media.AudioSystem", "STREAM_BTTS")}",
                color = TextMuted, fontSize = 10.sp,
            )
'''
new = '''            Text(
                "Audio route: ${diag.audioRoute.ifBlank { "—" }}",
                color = TextMuted, fontSize = 10.sp,
            )
'''
s = replace_once(s, old, new, "safe audio route panel")
p.write_text(s)

print("Build80 applied: launch-time vendor audio probes removed; deep voice diagnostics retained")
