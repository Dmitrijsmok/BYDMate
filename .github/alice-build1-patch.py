#!/usr/bin/env python3
from pathlib import Path


def once(text: str, old: str, new: str, name: str) -> str:
    if old not in text:
        raise SystemExit(f"Alice Build 1 anchor missing: {name}")
    return text.replace(old, new, 1)


# -----------------------------------------------------------------------------
# Build identity: clearly distinguish this test APK from upstream BYDMate.
# v3.15.5 upstream starts at versionCode 464 / versionName 3.15.5. The rest of
# the historical Alice patch chain still uses its established internal 61001+
# identity sequence, so only the input anchor changes here.
# -----------------------------------------------------------------------------
p = Path("app/build.gradle.kts")
s = p.read_text()
s = once(s, "versionCode = 464", "versionCode = 61001", "versionCode")
s = once(s, 'versionName = "3.15.5"', 'versionName = "3.15.2-alice1"', "versionName")
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
    "import androidx.lifecycle.ViewModel\n",
    "import androidx.lifecycle.ViewModel\nimport android.util.Log\n",
    "Log import",
)
p.write_text(s)

print("Alice Build 1 patch applied")
