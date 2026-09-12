#!/usr/bin/env python3
from pathlib import Path


def once(s: str, old: str, new: str, name: str) -> str:
    if old not in s:
        raise SystemExit(f"Build95 anchor missing: {name}")
    return s.replace(old, new, 1)

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
p = Path("app/build.gradle.kts")
s = p.read_text()
s = once(s, "versionCode = 60044", "versionCode = 60045", "versionCode")
s = once(s, 'versionNameSuffix = "-dilink3-production-build94"', 'versionNameSuffix = "-dilink3-production-build95"', "versionName")
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = once(s, 'android:label="BYDMate DiLink3 Build94"', 'android:label="BYDMate DiLink3 Build95"', "label")
p.write_text(s)

p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text().replace('SectionHeader(text = "Assistant Lab · Build94")', 'SectionHeader(text = "Assistant Lab · Build95")', 1)
# Ownership is independent from the local BYDMate ASR master switch in the Alice field build.
s = once(
    s,
    '''                    options = listOf("BYD Assistant", "BYDMate"),
                    selectedIndex = if (state.dilink3SteeringAssistant) 1 else 0,
                    onSelect = { index -> viewModel.setDiLink3SteeringAssistant(index == 1) },
                    enabled = state.voiceEnabled,
''',
    '''                    options = listOf("BYD Assistant", "BYDMate / Alice"),
                    selectedIndex = if (state.dilink3SteeringAssistant) 1 else 0,
                    onSelect = { index -> viewModel.setDiLink3SteeringAssistant(index == 1) },
                    enabled = true,
''',
    "steering ownership UI",
)
p.write_text(s)

# ---------------------------------------------------------------------------
# Make the steering ownership toggle a real independent switch.
# Build94 accidentally required voiceEnabled=true, so the UI could look changed while the
# synchronous SharedPreferences gate stayed false. That made both 304 and 327 fall through to BYD.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsViewModel.kt")
s = p.read_text()

s = once(
    s,
    '''            val dilink3SteeringAssistant = settingsRepository.getString(
                SettingsRepository.KEY_DILINK3_STEERING_ASSISTANT, "false"
            ) == "true"
            // AccessibilityService reads the synchronous mirror, while Room remains the
            // canonical setting used by config backup/restore.
            appContext.getSharedPreferences("voice", Context.MODE_PRIVATE)
                .edit().putBoolean(
                    SettingsRepository.KEY_DILINK3_STEERING_ASSISTANT,
                    dilink3SteeringAssistant,
                ).apply()
''',
    '''            // Build95 Alice field migration: steering ownership is independent from the
            // local BYDMate voice master. The synchronous SharedPreferences value is authoritative
            // for the key filter; initialize this field build to BYDMate/Alice ownership once,
            // then preserve the user's toggle across process/vehicle restarts.
            val steeringPrefs = appContext.getSharedPreferences("voice", Context.MODE_PRIVATE)
            val ownerInitKey = "build95_steering_owner_initialized"
            val roomSteeringOwnership = settingsRepository.getString(
                SettingsRepository.KEY_DILINK3_STEERING_ASSISTANT, "false"
            ) == "true"
            val dilink3SteeringAssistant = if (!steeringPrefs.getBoolean(ownerInitKey, false)) {
                steeringPrefs.edit()
                    .putBoolean(SettingsRepository.KEY_DILINK3_STEERING_ASSISTANT, true)
                    .putBoolean(ownerInitKey, true)
                    .apply()
                true
            } else if (steeringPrefs.contains(SettingsRepository.KEY_DILINK3_STEERING_ASSISTANT)) {
                steeringPrefs.getBoolean(SettingsRepository.KEY_DILINK3_STEERING_ASSISTANT, roomSteeringOwnership)
            } else {
                roomSteeringOwnership
            }
            // Keep Room aligned for backup/restore/UI, but never overwrite the live key-filter
            // preference with a stale Room value during startup.
            if (dilink3SteeringAssistant != roomSteeringOwnership) {
                settingsRepository.setString(
                    SettingsRepository.KEY_DILINK3_STEERING_ASSISTANT,
                    dilink3SteeringAssistant.toString(),
                )
            }
            steeringPrefs.edit()
                .putBoolean(SettingsRepository.KEY_DILINK3_STEERING_ASSISTANT, dilink3SteeringAssistant)
                .putBoolean(ownerInitKey, true)
                .apply()
''',
    "ownership load/migration",
)

s = once(
    s,
    '''            // A disabled voice pipeline must never leave the factory button swallowed.
            if (!enabled) {
                _uiState.update { it.copy(dilink3SteeringAssistant = false) }
                settingsRepository.setString(
                    SettingsRepository.KEY_DILINK3_STEERING_ASSISTANT, "false"
                )
                appContext.getSharedPreferences("voice", Context.MODE_PRIVATE)
                    .edit().putBoolean(
                        SettingsRepository.KEY_DILINK3_STEERING_ASSISTANT, false
                    ).apply()
            }
''',
    '''            // Build95: local ASR/TTS and physical steering ownership are independent.
            // Turning local BYDMate voice off must not silently hand 304/327 back to the stock
            // assistant while Alice owns the steering button.
''',
    "do not clear ownership with voice master",
)

# Build94 source may have older/newer wording in the KDoc, so patch only the actual behavior line.
s = once(
    s,
    '''        if (enabled && !_uiState.value.voiceEnabled) return
''',
    '',
    "independent setter guard",
)

# Mark the migration initialized whenever the user explicitly changes the switch.
s = once(
    s,
    '''            appContext.getSharedPreferences("voice", Context.MODE_PRIVATE)
                .edit().putBoolean(
                    SettingsRepository.KEY_DILINK3_STEERING_ASSISTANT, enabled
                ).apply()
''',
    '''            appContext.getSharedPreferences("voice", Context.MODE_PRIVATE)
                .edit()
                .putBoolean(SettingsRepository.KEY_DILINK3_STEERING_ASSISTANT, enabled)
                .putBoolean("build95_steering_owner_initialized", true)
                .apply()
''',
    "setter mirror",
)
p.write_text(s)

# ---------------------------------------------------------------------------
# Steering/Alice routing.
# One source of truth for persistent ownership: voice/dilink3_steering_assistant.
# Build95 initializes it ON once, then the user's BYD Assistant / BYDMate-Alice toggle wins.
# Explicit one-shot Alice tests are allowed even while ownership is OFF.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/assistantlab/AssistantLab.kt")
s = p.read_text().replace("Build94", "Build95")

s = once(
    s,
    '''    private fun steeringOwnershipEnabled(context: Context): Boolean {
        val p = context.applicationContext.getSharedPreferences("voice", Context.MODE_PRIVATE)
        return if (p.contains("dilink3_steering_assistant")) {
            p.getBoolean("dilink3_steering_assistant", false)
        } else p.getBoolean("voice_enabled", false)
    }
''',
    '''    private fun steeringOwnershipEnabled(context: Context): Boolean {
        val p = context.applicationContext.getSharedPreferences("voice", Context.MODE_PRIVATE)
        val initKey = "build95_steering_owner_initialized"
        if (!p.getBoolean(initKey, false)) {
            p.edit()
                .putBoolean("dilink3_steering_assistant", true)
                .putBoolean(initKey, true)
                .apply()
            add("ALICE95 steering ownership migration -> ON")
            return true
        }
        return p.getBoolean("dilink3_steering_assistant", false)
    }
''',
    "ownership gate",
)

s = once(
    s,
    '''    fun shouldHardBlockStock327(context: Context, event: KeyEvent): Boolean {
        if (event.keyCode != 327) return false
        if (!steeringOwnershipEnabled(context)) return false
        val now = android.os.SystemClock.elapsedRealtime()
        val block = aliceTestMode || now < aliceHard327UntilElapsed
        if (!block) return false
        add("ALICE HARD 327 BLOCK action=${event.action} scan=${event.scanCode}; stopped before BYD dispatch")
        return true
    }
''',
    '''    fun shouldHardBlockStock327(context: Context, event: KeyEvent): Boolean {
        if (event.keyCode != 327) return false
        val now = android.os.SystemClock.elapsedRealtime()
        val hardWindow = now < aliceHard327UntilElapsed
        val owner = steeringOwnershipEnabled(context)
        val block = hardWindow || owner
        if (!block) {
            add("ALICE95 327 PASS owner=false hardWindow=false")
            return false
        }
        add("ALICE95 327 BLOCK owner=$owner hardWindow=$hardWindow action=${event.action} scan=${event.scanCode}")
        return true
    }
''',
    "327 blocker",
)

s = once(
    s,
    '''    fun maybeHandleSteering(context: Context, event: KeyEvent): Boolean {
        if (event.keyCode != MIC_KEYCODE) return false
        if (!steeringOwnershipEnabled(context)) return false
        if (!active && !aliceTestMode) return false
''',
    '''    fun maybeHandleSteering(context: Context, event: KeyEvent): Boolean {
        if (event.keyCode != MIC_KEYCODE) return false
        val explicitRoute = consume304UntilUp || armedTarget != null
        val owner = steeringOwnershipEnabled(context)
        if (!owner && !explicitRoute) {
            add("ALICE95 304 PASS owner=false aliceMode=$aliceTestMode action=${event.action}")
            return false
        }
        if (!active && !aliceTestMode && !explicitRoute) return false
''',
    "304 ownership/one-shot route",
)

# Make the persistent Alice mode status explicit in traces whenever a 304 is actually selected.
s = once(
    s,
    '''        add("KEY 304 route=${if (oneShot != null) "one-shot" else "alice-test"} target=${target.title}")
''',
    '''        add("ALICE95 304 ROUTE owner=$owner mode=${if (oneShot != null) "one-shot" else "alice-test"} target=${target.title}")
''',
    "304 route trace",
)
p.write_text(s)

print("Build95 applied: deterministic steering ownership + working toggle + Alice/327 routing")
