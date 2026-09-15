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
                com.bydmate.app.data.repository.SettingsRepository.KEY_ALICE_ENABLED
            ).collect { raw ->
                val enabled = raw == "true"
                Log.i(TAG, "BRIDGE_ENABLE_CHANGED enabled=$enabled")
                if (enabled) alicePollingManager.start() else alicePollingManager.stop()
            }
        }
'''
s = once(s, old, new, "TrackingService Alice polling startup")
p.write_text(s)

# CommandTranslator already owns the validated window action names, but 4.9 only
# exposes fixed 0/100/vent values. Yandex openable/range can request any 0..100%.
p = Path("app/src/main/kotlin/com/bydmate/app/data/vehicle/CommandTranslator.kt")
s = p.read_text()
s = once(
    s,
    '''        FRIDGE_HEAT_REGEX.matchEntire(stripped)?.let { m ->
            val c = m.groupValues[1].toIntOrNull() ?: return emptyList()
            return fridgeHeat(c.coerceIn(FRIDGE_HEAT_MIN, FRIDGE_HEAT_MAX))
        }
        return emptyList()
''',
    '''        FRIDGE_HEAT_REGEX.matchEntire(stripped)?.let { m ->
            val c = m.groupValues[1].toIntOrNull() ?: return emptyList()
            return fridgeHeat(c.coerceIn(FRIDGE_HEAT_MIN, FRIDGE_HEAT_MAX))
        }
        // Alice 5.0 / Smart Home: arbitrary side-window aperture. Fixed 0/100
        // commands were already matched by [table] above and therefore keep using
        // their dedicated open/close channels; 1..99 use the validated % fids.
        WINDOW_POSITION_REGEX.matchEntire(stripped)?.let { m ->
            val pct = m.groupValues[2].toIntOrNull() ?: return emptyList()
            if (pct !in 0..100) return emptyList()
            val action = when (m.groupValues[1]) {
                "主驾" -> "window_driver_pos"
                "副驾" -> "window_passenger_pos"
                "后左" -> "window_rear_left_pos"
                "后右" -> "window_rear_right_pos"
                else -> return emptyList()
            }
            return listOf(Resolved(action, pct))
        }
        return emptyList()
''',
    "dynamic window resolution",
)
s = once(
    s,
    '''    private val FRIDGE_HEAT_REGEX = Regex("""冰箱制热(\\d+)度""")
    private const val FRIDGE_COOL_MIN = -6
''',
    '''    private val FRIDGE_HEAT_REGEX = Regex("""冰箱制热(\\d+)度""")
    private val WINDOW_POSITION_REGEX = Regex("""(主驾|副驾|后左|后右)打开(\\d+)""")
    private const val FRIDGE_COOL_MIN = -6
''',
    "window regex",
)
s = once(
    s,
    '''    private val DYNAMIC_ACTIONS = setOf("ac_temp_main")
''',
    '''    private val DYNAMIC_ACTIONS = setOf(
        "ac_temp_main",
        "window_driver_pos",
        "window_passenger_pos",
        "window_rear_left_pos",
        "window_rear_right_pos",
    )
''',
    "dynamic window action invariant",
)
p.write_text(s)

# Correct the old settings hint: 5.0 uses a held long-poll request for low-latency
# command delivery, and vehicle writes no longer use D+.
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text()
s = s.replace(
    'SettingHint("Polling опрашивает Worker каждую секунду\\nи выполняет команды через D+ API")',
    'SettingHint("Command Bridge держит защищённое long-poll соединение с Worker\\nи выполняет только разрешённые команды через BYDMate Helper")',
)
p.write_text(s)

# Build 1 instruments the legacy polling implementation. Replace it only now, after
# the complete 4.9 patch chain has consumed its anchors, with the hardened 5.0 bridge.
Path("app/src/main/kotlin/com/bydmate/app/data/remote/AlicePollingManager.kt").write_text(
    Path(".github/alice-build5-0-polling.kt.txt").read_text()
)

print("Alice 5.0 command bridge applied: version 64011, live toggle, long-poll, windows")
