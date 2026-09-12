#!/usr/bin/env python3
from pathlib import Path


def once(text: str, old: str, new: str, name: str) -> str:
    if old not in text:
        raise SystemExit(f"Alice Build 1 anchor missing: {name}")
    return text.replace(old, new, 1)


# -----------------------------------------------------------------------------
# Build identity: clearly distinguish this test APK from upstream BYDMate.
# -----------------------------------------------------------------------------
p = Path("app/build.gradle.kts")
s = p.read_text()
s = once(s, "versionCode = 452", "versionCode = 61001", "versionCode")
s = once(s, 'versionName = "3.15.2"', 'versionName = "3.15.2-alice1"', "versionName")
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = once(s, 'android:label="BYDMate"', 'android:label="BYDMate Alice 1"', "app label")
p.write_text(s)


# -----------------------------------------------------------------------------
# Touch diagnostics.
# Log only DOWN/UP (not MOVE) so the recorder stays readable. Coordinates are
# both local and raw; screen dimensions make the trace useful across head units.
# -----------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/MainActivity.kt")
s = p.read_text()
s = once(
    s,
    "import android.util.Log\n",
    "import android.util.Log\nimport android.view.MotionEvent\n",
    "MotionEvent import",
)
s = once(
    s,
    "    @Inject lateinit var updateChecker: UpdateChecker\n",
    "    @Inject lateinit var updateChecker: UpdateChecker\n\n"
    "    private var aliceTouchSeq = 0L\n"
    "    private var aliceCurrentTouchSeq = 0L\n",
    "touch counters",
)
anchor = '''    private fun requestPermissionsIfNeeded() {\n'''
replacement = '''    override fun dispatchTouchEvent(ev: MotionEvent): Boolean {\n        val tracked = ev.actionMasked == MotionEvent.ACTION_DOWN ||\n            ev.actionMasked == MotionEvent.ACTION_UP ||\n            ev.actionMasked == MotionEvent.ACTION_CANCEL\n        if (ev.actionMasked == MotionEvent.ACTION_DOWN) {\n            aliceCurrentTouchSeq = ++aliceTouchSeq\n        }\n        val actionName = when (ev.actionMasked) {\n            MotionEvent.ACTION_DOWN -> "DOWN"\n            MotionEvent.ACTION_UP -> "UP"\n            MotionEvent.ACTION_CANCEL -> "CANCEL"\n            else -> ev.actionMasked.toString()\n        }\n        if (tracked) {\n            val dm = resources.displayMetrics\n            Log.i(\n                "AliceBuild1",\n                "TOUCH seq=$aliceCurrentTouchSeq action=$actionName " +\n                    "x=${ev.x.toInt()} y=${ev.y.toInt()} " +\n                    "rawX=${ev.rawX.toInt()} rawY=${ev.rawY.toInt()} " +\n                    "screen=${dm.widthPixels}x${dm.heightPixels} pointers=${ev.pointerCount}"\n            )\n        }\n        val consumed = super.dispatchTouchEvent(ev)\n        if (tracked) {\n            Log.i(\n                "AliceBuild1",\n                "TOUCH_RESULT seq=$aliceCurrentTouchSeq action=$actionName consumed=$consumed"\n            )\n        }\n        return consumed\n    }\n\n    private fun requestPermissionsIfNeeded() {\n'''
s = once(s, anchor, replacement, "dispatchTouchEvent")
p.write_text(s)


# -----------------------------------------------------------------------------
# Smart Home test visibility + exact version-tap acknowledgement.
# The original 7-tap code is NOT deleted; Alice 1 simply shows the section so a
# failed hidden gesture can never block the test. We still log every version tap.
# -----------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text()
old = '''        var selected by rememberSaveable { mutableStateOf(SettingsSection.VOICE) }\n        val hiddenSelected = selected == SettingsSection.SMART_HOME\n        val safeSelected = if (hiddenSelected && !state.devModeUnlocked) {\n            SettingsSection.VOICE\n        } else {\n            selected\n        }\n'''
new = '''        var selected by rememberSaveable { mutableStateOf(SettingsSection.VOICE) }\n        // Alice Build 1: expose Smart Home unconditionally for diagnostics.\n        // The author's 7-tap unlock remains intact and is still traced separately.\n        val smartHomeUnlockedForTest = true\n        val safeSelected = selected\n'''
s = once(s, old, new, "Smart Home visibility block")
s = once(
    s,
    "                smartHomeUnlocked = state.devModeUnlocked,\n",
    "                smartHomeUnlocked = smartHomeUnlockedForTest,\n",
    "Smart Home rail flag",
)
p.write_text(s)

p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsViewModel.kt")
s = p.read_text()
s = once(
    s,
    '''        versionTapCount++\n        if (versionTapCount >= 7) {\n            _uiState.update { it.copy(devModeUnlocked = true) }\n            versionTapCount = 0\n        }\n''',
    '''        versionTapCount++\n        Log.i("AliceBuild1", "VERSION_TAP count=$versionTapCount")\n        if (versionTapCount >= 7) {\n            _uiState.update { it.copy(devModeUnlocked = true) }\n            Log.i("AliceBuild1", "VERSION_TAP_UNLOCK smartHome=true")\n            versionTapCount = 0\n        }\n''',
    "version tap trace",
)
s = once(
    s,
    '''    fun saveAliceSettings() {\n        val state = _uiState.value\n        viewModelScope.launch {\n''',
    '''    fun saveAliceSettings() {\n        val state = _uiState.value\n        Log.i(\n            "AliceBuild1",\n            "SMART_HOME_SAVE endpointSet=${state.aliceEndpoint.isNotBlank()} apiKeySet=${state.aliceApiKey.isNotBlank()}"\n        )\n        viewModelScope.launch {\n''',
    "Smart Home save trace",
)
s = once(
    s,
    '''    fun toggleAlice(enabled: Boolean) {\n        _uiState.update { it.copy(aliceEnabled = enabled) }\n''',
    '''    fun toggleAlice(enabled: Boolean) {\n        Log.i("AliceBuild1", "SMART_HOME_POLLING_TOGGLE enabled=$enabled")\n        _uiState.update { it.copy(aliceEnabled = enabled) }\n''',
    "Smart Home toggle trace",
)
p.write_text(s)


# -----------------------------------------------------------------------------
# Existing author LogRecorder / Share Logs remains the owner of the log file.
# Only widen its tag filter so Alice Build 1 diagnostics are present in the same
# file the user already knows how to start/stop/share.
# -----------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/diagnostics/LogRecorder.kt")
s = p.read_text()
s = once(
    s,
    '''            "-s", "BootReceiver:*",\n            "TrackingService:*", "TripTracker:*",\n''',
    '''            "-s", "BootReceiver:*",\n            // Alice Build 1 diagnostics: touch → settings → Smart Home polling.\n            "AliceBuild1:*", "MainActivity:*", "AlicePolling:*", "SettingsViewModel:*",\n            "TrackingService:*", "TripTracker:*",\n''',
    "LogRecorder Alice tags",
)
p.write_text(s)


# -----------------------------------------------------------------------------
# Early boot guard carried forward from the proven Build 95 idea. Accessibility
# recovery remains upstream; this only starts TrackingService immediately before
# WorkManager so the steering/mic interception has the earliest possible chance
# to bind after ignition boot/wake.
# -----------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/service/BootReceiver.kt")
s = p.read_text()
anchor = '''        logBootEvent(context, intent.action ?: "unknown")\n\n        // Use WorkManager — guaranteed execution (like BydConnect)\n'''
replacement = '''        logBootEvent(context, intent.action ?: "unknown")\n\n        // Alice Build 1: early guard for the mic/voice accessibility path. WorkManager\n        // remains the normal guaranteed path below; TrackingService.start() is idempotent.\n        if (\n            intent.action == Intent.ACTION_BOOT_COMPLETED ||\n            intent.action == "android.intent.action.QUICKBOOT_POWERON" ||\n            intent.action == "android.intent.action.LOCKED_BOOT_COMPLETED" ||\n            intent.action == Intent.ACTION_USER_PRESENT\n        ) {\n            try {\n                TrackingService.start(context)\n                ChainLog.append(context, "Alice1 direct TrackingService start OK: ${intent.action}")\n                Log.i(TAG, "Alice1 early boot guard started TrackingService: ${intent.action}")\n            } catch (e: Exception) {\n                ChainLog.append(context, "Alice1 direct TrackingService start failed: ${e.message}")\n                Log.w(TAG, "Alice1 early boot guard failed; WorkManager fallback follows", e)\n            }\n        }\n\n        // Use WorkManager — guaranteed execution (like BydConnect)\n'''
s = once(s, anchor, replacement, "early boot guard")
p.write_text(s)


# -----------------------------------------------------------------------------
# Smart Home transport trace. Keep AlicePolling's normal logs and add one concise
# AliceBuild1 line for each meaningful command transition. No API key or endpoint
# is logged.
# -----------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/data/remote/AlicePollingManager.kt")
s = p.read_text()
s = once(
    s,
    '''            Log.i(TAG, "Polling started")\n            while (true) {\n''',
    '''            Log.i(TAG, "Polling started")\n            Log.i("AliceBuild1", "ALICE_POLL_STARTED intervalMs=$POLL_INTERVAL_MS")\n            while (true) {\n''',
    "poll start trace",
)
s = once(
    s,
    '''        Log.i(TAG, "Received ${commands.length()} command(s) (${elapsed}ms)")\n\n        val ackIds = mutableListOf<String>()\n''',
    '''        Log.i(TAG, "Received ${commands.length()} command(s) (${elapsed}ms)")\n        Log.i("AliceBuild1", "ALICE_BATCH count=${commands.length()} latencyMs=$elapsed")\n\n        val ackIds = mutableListOf<String>()\n''',
    "poll batch trace",
)
s = once(
    s,
    '''            Log.i(TAG, "Executing: '$command' (id=$id)")\n            // Alice bypasses ActionDispatcher (raw vehicleApi), so the door-unlock\n''',
    '''            Log.i(TAG, "Executing: '$command' (id=$id)")\n            Log.i("AliceBuild1", "ALICE_COMMAND id=$id command='$command'")\n            // Alice bypasses ActionDispatcher (raw vehicleApi), so the door-unlock\n''',
    "command trace",
)
s = once(
    s,
    '''                Log.w(TAG, "Blocked: '$command' → $unlockBlock")\n                ackIds.add(id)\n''',
    '''                Log.w(TAG, "Blocked: '$command' → $unlockBlock")\n                Log.w("AliceBuild1", "ALICE_COMMAND_BLOCKED id=$id reason=$unlockBlock")\n                ackIds.add(id)\n''',
    "blocked command trace",
)
s = once(
    s,
    '''            Log.i(TAG, "Result: $command → ${if (success) "OK" else "FAIL: ${result.exceptionOrNull()?.message}"}")\n            // Crowd-validation: ack regardless of success. Unmapped/Unsupported commands\n''',
    '''            Log.i(TAG, "Result: $command → ${if (success) "OK" else "FAIL: ${result.exceptionOrNull()?.message}"}")\n            Log.i(\n                "AliceBuild1",\n                "ALICE_COMMAND_RESULT id=$id success=$success error=${result.exceptionOrNull()?.message ?: "-"}"\n            )\n            // Crowd-validation: ack regardless of success. Unmapped/Unsupported commands\n''',
    "command result trace",
)
p.write_text(s)

print("Alice Build 1 patch applied")
