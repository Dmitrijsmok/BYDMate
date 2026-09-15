#!/usr/bin/env python3
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Alice5.0 anchor missing: {label}")
    return text.replace(old, new, 1)

# Identity: 5.0 is an update over 4.9, package name remains unchanged.
p = Path("app/build.gradle.kts")
s = p.read_text()
s = once(s, "versionCode = 64010", "versionCode = 64011", "versionCode")
s = once(
    s,
    'versionName = "3.15.2-alice4.9-stable"',
    'versionName = "3.15.2-alice5.0-command-bridge"',
    "versionName",
)
p.write_text(s)

# Make the Smart Home toggle live. 4.9 only sampled alice_enabled once when
# TrackingService started, which made enabling the bridge look broken until a restart.
p = Path("app/src/main/kotlin/com/bydmate/app/service/TrackingService.kt")
s = p.read_text()
old = '''        // Start Smart Home polling if configured
        serviceScope.launch {
            val enabled = settingsRepository.getString(
                com.bydmate.app.data.repository.SettingsRepository.KEY_ALICE_ENABLED, "false"
            ) == "true"
            if (enabled) alicePollingManager.start()
        }
'''
new = '''        // Alice 5.0 command bridge: observe the switch continuously so enabling or
        // disabling Smart Home takes effect immediately without restarting BYDMate/DiLink.
        serviceScope.launch {
            settingsRepository.observeString(
                com.bydmate.app.data.repository.SettingsRepository.KEY_ALICE_ENABLED,
                "false"
            ).collect { raw ->
                val enabled = raw == "true"
                Log.i(TAG, "BRIDGE_ENABLE_CHANGED enabled=$enabled")
                if (enabled) alicePollingManager.start() else alicePollingManager.stop()
            }
        }
'''
s = once(s, old, new, "TrackingService Alice polling startup")
p.write_text(s)

# Correct the old settings hint: polling is 2.5 s and vehicle writes no longer use D+.
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text()
s = s.replace(
    'SettingHint("Polling опрашивает Worker каждую секунду\\nи выполняет команды через D+ API")',
    'SettingHint("Command Bridge опрашивает Worker примерно каждые 2,5 с\\nи выполняет только разрешённые команды через BYDMate Helper")',
)
p.write_text(s)

# Build 1 instruments the legacy polling implementation. Replace it only now, after
# the complete 4.9 patch chain has consumed its anchors, with the hardened 5.0 bridge.
Path("app/src/main/kotlin/com/bydmate/app/data/remote/AlicePollingManager.kt").write_text(
    Path(".github/alice-build5-0-polling.kt.txt").read_text()
)

print("Alice 5.0 command bridge applied: version 64011, live toggle, safe semantic polling")
