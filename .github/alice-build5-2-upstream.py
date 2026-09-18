#!/usr/bin/env python3
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Alice5.2 anchor missing: {label}")
    return text.replace(old, new, 1)

# Final identity over the validated 4.9 Alice baseline.
p = Path("app/build.gradle.kts")
s = p.read_text()
s = once(s, "versionCode = 64010", "versionCode = 64013", "versionCode")
s = once(
    s,
    'versionName = "3.15.2-alice4.9-stable"',
    'versionName = "3.15.5-alice5.2-upstream-rebase"',
    "versionName",
)
p.write_text(s)

# Upstream v3.15.5 now owns fan 1..7 and airflow-direction mappings. Do NOT patch
# those tables here. Keep only the missing flow-only OFF mapping used by Alice.
p = Path("app/src/main/kotlin/com/bydmate/app/data/vehicle/CommandTranslator.kt")
s = p.read_text()
if '"关闭空调通风" to Resolved("ac_flow_only_off",  0)' not in s:
    s = once(
        s,
        '''        "打开空调通风" to Resolved("ac_flow_only_on",   1),  // competitor val=1
        "吹前挡"      to Resolved("defrost_front_on",  1),  // competitor val=1
''',
        '''        "打开空调通风" to Resolved("ac_flow_only_on",   1),  // competitor val=1
        "关闭空调通风" to Resolved("ac_flow_only_off",  0),  // competitor val=0
        "吹前挡"      to Resolved("defrost_front_on",  1),  // competitor val=1
''',
        "flow-only off command",
    )
p.write_text(s)

# Make the Smart Home toggle live. If upstream already changed this exact block,
# fail loudly rather than guessing around service lifecycle code.
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
new = '''        // Alice command bridge: observe the switch continuously so enabling or
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
if "BRIDGE_ENABLE_CHANGED enabled=" not in s:
    s = once(s, old, new, "TrackingService Alice polling startup")
p.write_text(s)

# Install the hardened long-poll manager after all earlier Alice patches consumed
# the legacy implementation anchors.
Path("app/src/main/kotlin/com/bydmate/app/data/remote/AlicePollingManager.kt").write_text(
    Path(".github/alice-build5-0-polling.kt.txt").read_text()
)

# Extend the polling manager with local app/media actions, stricter remote trunk
# safety, and the expanded v3.15.5 telemetry fields.
p = Path("app/src/main/kotlin/com/bydmate/app/data/remote/AlicePollingManager.kt")
s = p.read_text()
s = once(
    s,
    '''    private val sharedAdaptiveLoop: com.bydmate.app.data.loop.SharedAdaptiveLoop,
    private val vehicleApi: VehicleApi,
) {
''',
    '''    private val sharedAdaptiveLoop: com.bydmate.app.data.loop.SharedAdaptiveLoop,
    private val vehicleApi: VehicleApi,
    private val appCommandDispatcher: AliceAppCommandDispatcher,
) {
''',
    "AlicePollingManager app dispatcher injection",
)

s = once(
    s,
    '''            val resolved = AliceBridgeCommandTranslator.resolve(cmd)
            if (resolved == null) {
                val requested = cmd.optString("action", "<missing>")
                Log.w(TAG, "BRIDGE_COMMAND_REJECTED id=$id action=$requested reason=unsupported_or_invalid")
                rememberResult(id, requested, false, "unsupported_or_invalid")
                results += AckResult(id, false, "unsupported_or_invalid")
                continue
            }

            val command = resolved.vehicleCommand
''',
    '''            val requested = cmd.optString("action", "<missing>").trim().lowercase()

            val appResult = appCommandDispatcher.dispatch(cmd)
            if (appResult != null) {
                val success = appResult.isSuccess
                val error = appResult.exceptionOrNull()?.message
                Log.i(TAG, "BRIDGE_APP_COMMAND_RECEIVED id=$id action=$requested")
                rememberResult(id, requested, success, error)
                Log.i(TAG, "BRIDGE_APP_COMMAND_RESULT id=$id action=$requested success=$success" +
                    (error?.let { " error=${it.take(160)}" } ?: ""))
                results += AckResult(id, success, error?.take(240))
                continue
            }

            val resolved = AliceBridgeCommandTranslator.resolve(cmd)
            if (resolved == null) {
                Log.w(TAG, "BRIDGE_COMMAND_REJECTED id=$id action=$requested reason=unsupported_or_invalid")
                rememberResult(id, requested, false, "unsupported_or_invalid")
                results += AckResult(id, false, "unsupported_or_invalid")
                continue
            }

            val command = resolved.vehicleCommand

            // Remote Alice invocation: opening the rear tailgate requires a known standstill.
            if (resolved.action == "trunk.rear.open") {
                val speed = latestData?.speed
                if (speed == null || speed > 0) {
                    val reason = if (speed == null) "rear_trunk_speed_unknown" else "rear_trunk_moving:$speed"
                    Log.w(TAG, "BRIDGE_COMMAND_REJECTED id=$id action=${resolved.action} reason=$reason")
                    rememberResult(id, resolved.action, false, reason)
                    results += AckResult(id, false, reason)
                    continue
                }
            }
''',
    "AlicePollingManager app and trunk dispatch",
)

s = once(
    s,
    '''                data.windowFL?.let { put("windowFL", it) }
                data.windowFR?.let { put("windowFR", it) }
                data.windowRL?.let { put("windowRL", it) }
                data.windowRR?.let { put("windowRR", it) }
                data.sunroof?.let { put("sunroof", it) }
                data.trunk?.let { put("trunk", it) }
                data.lockFL?.let { put("lockFL", it) }
                data.acStatus?.let { put("acStatus", it) }
                data.acTemp?.let { put("acTemp", it) }
                data.acCirc?.let { put("acCirc", it) }
                data.insideTemp?.let { put("insideTemp", it) }
''',
    '''                data.soc?.let { put("soc", it) }
                data.speed?.let { put("speed", it) }
                data.gear?.let { put("gear", it) }
                data.powerState?.let { put("powerState", it) }
                data.exteriorTemp?.let { put("exteriorTemp", it) }
                data.insideTemp?.let { put("insideTemp", it) }

                data.acStatus?.let { put("acStatus", it) }
                data.acTemp?.let { put("acTemp", it) }
                data.fanLevel?.let { put("fanLevel", it) }
                data.acCirc?.let { put("acCirc", it) }
                data.acDefrostFront?.let { put("acDefrostFront", it) }
                data.acWindMode?.let { put("acWindMode", it) }
                data.acCtrlMode?.let { put("acCtrlMode", it) }

                data.windowFL?.let { put("windowFL", it) }
                data.windowFR?.let { put("windowFR", it) }
                data.windowRL?.let { put("windowRL", it) }
                data.windowRR?.let { put("windowRR", it) }
                data.doorFL?.let { put("doorFL", it) }
                data.doorFR?.let { put("doorFR", it) }
                data.doorRL?.let { put("doorRL", it) }
                data.doorRR?.let { put("doorRR", it) }
                data.sunroof?.let { put("sunroof", it) }
                data.trunk?.let { put("trunk", it) }
                data.hood?.let { put("hood", it) }
                data.lockFL?.let { put("lockFL", it) }

                data.seatHeatDriver?.let { put("seatHeatDriver", it) }
                data.seatVentDriver?.let { put("seatVentDriver", it) }
                data.seatHeatPassenger?.let { put("seatHeatPassenger", it) }
                data.seatVentPassenger?.let { put("seatVentPassenger", it) }

                data.driveMode?.let { put("driveMode", it) }
                data.drl?.let { put("drl", it) }
                data.lightLow?.let { put("lightLow", it) }
                data.turnSignal?.let { put("turnSignal", it) }
''',
    "expanded bridge telemetry",
)
p.write_text(s)

# Update the settings hint if the older wording still exists.
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text()
s = s.replace(
    'SettingHint("Polling опрашивает Worker каждую секунду\\nи выполняет команды через D+ API")',
    'SettingHint("Command Bridge держит защищённое long-poll соединение с Worker\\nи выполняет только разрешённые команды через BYDMate Helper")',
)
p.write_text(s)

print("Alice 5.2 upstream bridge applied: v3.15.5 core + Alice semantic bridge")
