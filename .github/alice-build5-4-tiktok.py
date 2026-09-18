#!/usr/bin/env python3
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Alice5.4 TikTok anchor missing: {label}")
    return text.replace(old, new, 1)


p = Path("app/src/main/kotlin/com/bydmate/app/data/remote/AliceAppCommandDispatcher.kt")
s = p.read_text()

old = '''        const val ACTION_MEDIA_CENTER_OPEN = "app.media_center.open"
        const val ACTION_PHONE_OPEN = "app.phone.open"
'''
new = '''        const val ACTION_MEDIA_CENTER_OPEN = "app.media_center.open"
        const val ACTION_TIKTOK_OPEN = "app.tiktok.open"
        const val ACTION_PHONE_OPEN = "app.phone.open"
'''
s = once(s, old, new, "TikTok action constant")

old = '''            ACTION_MEDIA_CENTER_OPEN to AppTarget(
                packages = listOf("com.byd.mediacenter"),
                labelKeywords = listOf("медиацентр", "media center", "player", "плеер"),
            ),
            ACTION_PHONE_OPEN to AppTarget(
'''
new = '''            ACTION_MEDIA_CENTER_OPEN to AppTarget(
                packages = listOf("com.byd.mediacenter"),
                labelKeywords = listOf("медиацентр", "media center", "player", "плеер"),
            ),
            ACTION_TIKTOK_OPEN to AppTarget(
                packages = listOf(
                    "com.zhiliaoapp.musically",
                    "com.ss.android.ugc.trill",
                    "com.ss.android.ugc.aweme",
                ),
                labelKeywords = listOf("tiktok", "tik tok", "тикток", "тик ток"),
            ),
            ACTION_PHONE_OPEN to AppTarget(
'''
s = once(s, old, new, "TikTok app target")

p.write_text(s)

print("Alice 5.4 TikTok applied: app.tiktok.open -> package candidates + launcher-label fallback")
