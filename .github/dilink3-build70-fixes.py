#!/usr/bin/env python3
from pathlib import Path

FIELD_PACKAGE = "com.bydmate.app.dilink3prodtest"
FIELD_HELPER = "bydmate_h70"
FIELD_LOCK = "/data/local/tmp/bydmate_h70.lock"
FIELD_LOG = "/data/local/tmp/bydmate_h70.log"
VERSION_CODE = "60020"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Build70 anchor missing: {label}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# 1) Updateable field APK identity. Same package + signer as Build68/69,
#    monotonically higher versionCode so Android installs Build70 over Build69.
# ---------------------------------------------------------------------------
p = Path("app/build.gradle.kts")
s = p.read_text()
s = replace_once(
    s,
    "    signingConfigs {\n        if (keystorePropsFile.exists()) {\n",
    "    signingConfigs {\n"
    "        create(\"dilink3ProdTest\") {\n"
    "            storeFile = file(\"/tmp/dilink3-field-test.keystore\")\n"
    "            storePassword = \"dilink3debug\"\n"
    "            keyAlias = \"dilink3debug\"\n"
    "            keyPassword = \"dilink3debug\"\n"
    "        }\n"
    "        if (keystorePropsFile.exists()) {\n",
    "signingConfigs",
)
s = replace_once(
    s,
    "    buildTypes {\n        release {\n",
    "    buildTypes {\n"
    "        debug {\n"
    "            applicationIdSuffix = \".dilink3prodtest\"\n"
    "            versionNameSuffix = \"-dilink3-production-build70\"\n"
    "            signingConfig = signingConfigs.getByName(\"dilink3ProdTest\")\n"
    "        }\n"
    "        release {\n",
    "debug buildType",
)
s = replace_once(s, "        versionCode = 443", f"        versionCode = {VERSION_CODE}", "versionCode")
p.write_text(s)

m = Path("app/src/main/AndroidManifest.xml")
s = m.read_text()
s = replace_once(s, 'android:label="BYDMate"', 'android:label="BYDMate DiLink3 Build70"', "manifest label")
m.write_text(s)


# ---------------------------------------------------------------------------
# 2) FULL helper isolation for the side-by-side field APK.
#    Build69 retargeted APP_PACKAGE/components but still shared service/process/
#    lock/log names with normal BYDMate, so either APK could kill/reuse the
#    other's shell daemon. Build70 owns a completely separate helper namespace.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/helper/HelperBinderProtocol.kt")
s = p.read_text()
s = replace_once(s, 'const val SERVICE_NAME = "bydmate_helper"', f'const val SERVICE_NAME = "{FIELD_HELPER}"', "helper service name")
s = replace_once(s, 'const val PROCESS_NAME = "bydmate_helper"', f'const val PROCESS_NAME = "{FIELD_HELPER}"', "helper process name")
s = replace_once(s, 'const val APP_PACKAGE = "com.bydmate.app"', f'const val APP_PACKAGE = "{FIELD_PACKAGE}"', "helper app package")
s = replace_once(
    s,
    '"com.bydmate.app/com.bydmate.app.cluster.SteeringWheelKeyService"',
    f'"{FIELD_PACKAGE}/com.bydmate.app.cluster.SteeringWheelKeyService"',
    "a11y component",
)
s = replace_once(
    s,
    '"com.bydmate.app/com.bydmate.app.media.MediaSessionListenerService"',
    f'"{FIELD_PACKAGE}/com.bydmate.app.media.MediaSessionListenerService"',
    "notification-listener component",
)
p.write_text(s)

p = Path("app/src/main/kotlin/com/bydmate/app/helper/HelperDaemon.kt")
s = p.read_text()
s = replace_once(s, 'private const val LOCK_PATH = "/data/local/tmp/bydmate_helper.lock"', f'private const val LOCK_PATH = "{FIELD_LOCK}"', "helper lock")
p.write_text(s)

p = Path("app/src/main/kotlin/com/bydmate/app/data/autoservice/AdbOnDeviceClient.kt")
s = p.read_text()
s = replace_once(
    s,
    'private val PACKAGE_NAME_REGEX = Regex("""^com\\.bydmate\\.app$""")',
    'private val PACKAGE_NAME_REGEX = Regex("""^com\\.bydmate\\.app\\.dilink3prodtest$""")',
    "field appop package regex",
)
s = replace_once(s, 'private const val HELPER_PROCESS_NAME = "bydmate_helper"', f'private const val HELPER_PROCESS_NAME = "{FIELD_HELPER}"', "adb helper process")
s = replace_once(s, 'private const val HELPER_LOG_PATH = "/data/local/tmp/bydmate_helper.log"', f'private const val HELPER_LOG_PATH = "{FIELD_LOG}"', "adb helper log")
p.write_text(s)


# ---------------------------------------------------------------------------
# 3) Restore the field-validated Build49 behaviour explicitly:
#    DiLink3 ON => consume keyCode 327 EARLY, before any other routing;
#    304 remains the BYDMate trigger. OFF => both pass through to BYD.
#    Persist tiny field diagnostics so the car UI tells us what actually arrived.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt")
s = p.read_text()
s = replace_once(
    s,
    '        Log.d(TAG, "connected; filtering steering-wheel keys")\n',
    '        Log.d(TAG, "connected; filtering steering-wheel keys")\n'
    '        applicationContext.getSharedPreferences("build70_debug", Context.MODE_PRIVATE).edit()\n'
    '            .putBoolean("a11y_connected", true)\n'
    '            .putLong("a11y_connected_at", System.currentTimeMillis())\n'
    '            .apply()\n'
    '        Log.i(TAG, "BUILD70_A11Y_CONNECTED helper=bydmate_h70")\n',
    "a11y connected marker",
)
anchor = '        val diLink3Takeover = diLink3Platform && voiceEnabled\n        when (diLink3AssistantDecision(event.keyCode, isDown, diLink3Takeover, voiceEnabled)) {\n'
replacement = '''        val diLink3Takeover = diLink3Platform && voiceEnabled

        // Build70: make the proven Build49 blocker an explicit EARLY gate. One physical
        // DiLink3 mic press emits 304 + companion 327. Field testing proved that swallowing
        // 327 is what suppresses the stock BYD Assistant. This gate exists only while the
        // BYDMate Assistant master switch (voiceEnabled) is ON; OFF remains fail-open.
        if (diLink3Takeover && event.keyCode == DILINK3_STOCK_ASSISTANT_KEYCODE) {
            val dbg = applicationContext.getSharedPreferences("build70_debug", Context.MODE_PRIVATE)
            dbg.edit()
                .putLong("last_327_ms", System.currentTimeMillis())
                .putInt("last_327_action", event.action)
                .apply()
            Log.i(TAG, "BUILD70_327_CONSUMED action=${event.action} scanCode=${event.scanCode} isDown=$isDown")
            return true
        }
        if (diLink3Takeover && event.keyCode == DILINK3_MIC_KEYCODE && isDown) {
            applicationContext.getSharedPreferences("build70_debug", Context.MODE_PRIVATE).edit()
                .putLong("last_304_ms", System.currentTimeMillis())
                .apply()
            Log.i(TAG, "BUILD70_304_TRIGGER scanCode=${event.scanCode}")
        }

        when (diLink3AssistantDecision(event.keyCode, isDown, diLink3Takeover, voiceEnabled)) {
'''
s = replace_once(s, anchor, replacement, "early 327 gate")
s = replace_once(
    s,
    '''    override fun onUnbind(intent: Intent?): Boolean {
        instance = null
        isConnected = false
        Log.d(TAG, "unbound; star key filter inactive")
''',
    '''    override fun onUnbind(intent: Intent?): Boolean {
        instance = null
        isConnected = false
        applicationContext.getSharedPreferences("build70_debug", Context.MODE_PRIVATE).edit()
            .putBoolean("a11y_connected", false).apply()
        Log.i(TAG, "BUILD70_A11Y_UNBOUND")
        Log.d(TAG, "unbound; star key filter inactive")
''',
    "a11y unbind marker",
)
s = replace_once(
    s,
    '''    override fun onDestroy() {
        instance = null
        isConnected = false
        super.onDestroy()
''',
    '''    override fun onDestroy() {
        instance = null
        isConnected = false
        applicationContext.getSharedPreferences("build70_debug", Context.MODE_PRIVATE).edit()
            .putBoolean("a11y_connected", false).apply()
        super.onDestroy()
''',
    "a11y destroy marker",
)
p.write_text(s)


# ---------------------------------------------------------------------------
# 4) Restore a persistent GigaAM background-status/debug line.
#    Progress alone was insufficient: unpack/publish/VAD can look like a frozen
#    download. Store phase next to progress so Settings can leave/re-enter safely.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/voice/GigaAmModelManager.kt")
s = p.read_text()
s = replace_once(s, 'import android.content.Context\n', 'import android.content.Context\nimport android.util.Log\n', "GigaAM Log import")
old = '''    data class StatusSnapshot(
        val progress: Int,
        val active: Boolean,
        val failed: Boolean,
    )

    fun statusSnapshot(): StatusSnapshot {
        if (isReady()) return StatusSnapshot(progress = 100, active = false, failed = false)
        return StatusSnapshot(
  progress = provisioningPrefs.getInt("progress", -1),
  active = provisioningPrefs.getBoolean("active", false),
  failed = provisioningPrefs.getBoolean("failed", false),
        )
    }

    private fun setProvisioningState(progress: Int, active: Boolean, failed: Boolean) {
        provisioningPrefs.edit()
  .putInt("progress", progress)
  .putBoolean("active", active)
  .putBoolean("failed", failed)
  .apply()
    }
'''
new = '''    data class StatusSnapshot(
        val progress: Int,
        val active: Boolean,
        val failed: Boolean,
        val phase: String,
    )

    fun statusSnapshot(): StatusSnapshot {
        if (isReady() && !provisioningPrefs.getBoolean("active", false)) {
            return StatusSnapshot(progress = 100, active = false, failed = false, phase = "ready")
        }
        return StatusSnapshot(
  progress = provisioningPrefs.getInt("progress", -1),
  active = provisioningPrefs.getBoolean("active", false),
  failed = provisioningPrefs.getBoolean("failed", false),
  phase = (provisioningPrefs.getString("phase", "idle") ?: "idle").ifBlank { "idle" },
        )
    }

    private fun setProvisioningState(progress: Int, active: Boolean, failed: Boolean, phase: String) {
        val previousPhase = provisioningPrefs.getString("phase", "") ?: ""
        provisioningPrefs.edit()
  .putInt("progress", progress)
  .putBoolean("active", active)
  .putBoolean("failed", failed)
  .putString("phase", phase)
  .apply()
        if (previousPhase != phase) {
            Log.i("GigaAMProvisioning", "phase=$phase progress=$progress active=$active failed=$failed")
        }
    }
'''
s = replace_once(s, old, new, "GigaAM status snapshot")

s = s.replace(
    'setProvisioningState(100, active = false, failed = false)',
    'setProvisioningState(100, active = false, failed = false, phase = "ready")',
)
s = replace_once(
    s,
    '        setProvisioningState(statusSnapshot().progress.coerceAtLeast(0), active = true, failed = false)\n',
    '        setProvisioningState(\n'
    '            statusSnapshot().progress.coerceAtLeast(0),\n'
    '            active = true,\n'
    '            failed = false,\n'
    '            phase = if (isModelComplete(baseDir())) "downloading Silero VAD" else "starting GigaAM download",\n'
    '        )\n',
    "GigaAM initial phase",
)
s = replace_once(
    s,
    '          setProvisioningState(overall, active = true, failed = false)\n',
    '          setProvisioningState(overall, active = true, failed = false, phase = "downloading GigaAM model")\n',
    "GigaAM model download phase",
)
s = replace_once(
    s,
    '      coroutineContext.ensureActive()\n      diskMutex.withLock {\n',
    '      coroutineContext.ensureActive()\n'
    '      setProvisioningState(93, active = true, failed = false, phase = "unpacking GigaAM archive")\n'
    '      diskMutex.withLock {\n',
    "GigaAM unpack phase",
)
s = replace_once(
    s,
    '              check(isModelComplete(staging)) { "unpack produced incomplete model dir" }\n              target.deleteRecursively()\n',
    '              check(isModelComplete(staging)) { "unpack produced incomplete model dir" }\n'
    '              setProvisioningState(95, active = true, failed = false, phase = "publishing GigaAM model")\n'
    '              target.deleteRecursively()\n',
    "GigaAM publish model phase",
)
s = replace_once(
    s,
    '      setProvisioningState(96, active = true, failed = false)\n',
    '      setProvisioningState(96, active = true, failed = false, phase = "GigaAM model ready; preparing VAD")\n',
    "GigaAM model ready phase",
)
s = replace_once(
    s,
    '  if (!isVadComplete()) {\n      downloadToFileResume(VAD_URL, vadPart()) { pct ->\n',
    '  if (!isVadComplete()) {\n'
    '      setProvisioningState(97, active = true, failed = false, phase = "downloading Silero VAD")\n'
    '      downloadToFileResume(VAD_URL, vadPart()) { pct ->\n',
    "VAD download start phase",
)
s = replace_once(
    s,
    '          setProvisioningState(overall, active = true, failed = false)\n',
    '          setProvisioningState(overall, active = true, failed = false, phase = "downloading Silero VAD")\n',
    "VAD progress phase",
)
# This is the second ensureActive + diskMutex occurrence, now uniquely preceded by VAD callback.
old = '''      }
      coroutineContext.ensureActive()
      diskMutex.withLock {
          coroutineContext.ensureActive()
          check(vadPart().length() > 0) { "downloaded VAD file is empty" }
'''
new = '''      }
      coroutineContext.ensureActive()
      setProvisioningState(99, active = true, failed = false, phase = "publishing Silero VAD")
      diskMutex.withLock {
          coroutineContext.ensureActive()
          check(vadPart().length() > 0) { "downloaded VAD file is empty" }
'''
s = replace_once(s, old, new, "VAD publish phase")
s = replace_once(
    s,
    '  setProvisioningState(statusSnapshot().progress.coerceAtLeast(0), active = false, failed = true)\n',
    '  setProvisioningState(\n'
    '      statusSnapshot().progress.coerceAtLeast(0),\n'
    '      active = false,\n'
    '      failed = true,\n'
    '      phase = "error: " + (error.message ?: error.javaClass.simpleName).take(120),\n'
    '  )\n',
    "GigaAM error phase",
)
p.write_text(s)

p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsViewModel.kt")
s = p.read_text()
s = replace_once(
    s,
    '    val gigaAmDownloadProgress: Int = -1,   // -1 = idle, 0..100 = downloading\n    val gigaAmDownloadFailed: Boolean = false,\n',
    '    val gigaAmDownloadProgress: Int = -1,   // -1 = idle, 0..100 = downloading\n'
    '    val gigaAmDownloadPhase: String = "idle",\n'
    '    val gigaAmDownloadFailed: Boolean = false,\n',
    "Settings GigaAM phase field",
)
s = replace_once(
    s,
    '''              gigaAmModelReady = gigaAmModelManager.isReady(),
              gigaAmDownloadProgress = if (status.active) status.progress.coerceAtLeast(0) else -1,
              gigaAmDownloadFailed = status.failed,
''',
    '''              gigaAmModelReady = gigaAmModelManager.isReady(),
              gigaAmDownloadProgress = if (status.active) status.progress.coerceAtLeast(0) else -1,
              gigaAmDownloadPhase = status.phase,
              gigaAmDownloadFailed = status.failed,
''',
    "Settings GigaAM phase observer",
)
p.write_text(s)

p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text()
anchor = '''        Column(modifier = Modifier.padding(horizontal = 12.dp)) {
            val gigaAmDownloading = state.gigaAmDownloadProgress >= 0
'''
replacement = '''        Column(modifier = Modifier.padding(horizontal = 12.dp)) {
            // Build70 field diagnostics stay visible while testing on the car. This is deliberately
            // tiny: it proves that our FIELD accessibility service is bound and whether the two
            // edges from the physical mic button actually reached it.
            val build70Context = LocalContext.current
            var build70DebugTick by remember { mutableStateOf(0) }
            LaunchedEffect(Unit) {
                while (true) {
                    delay(1000)
                    build70DebugTick++
                }
            }
            val build70Now = remember(build70DebugTick) { System.currentTimeMillis() }
            val build70Prefs = build70Context.getSharedPreferences("build70_debug", Context.MODE_PRIVATE)
            val build70Last304 = build70Prefs.getLong("last_304_ms", 0L)
            val build70Last327 = build70Prefs.getLong("last_327_ms", 0L)
            val build70A11y = SteeringWheelKeyService.isConnected
            val build70Age304 = if (build70Last304 > 0L) "${(build70Now - build70Last304).coerceAtLeast(0L) / 1000}s ago" else "none"
            val build70Age327 = if (build70Last327 > 0L) "${(build70Now - build70Last327).coerceAtLeast(0L) / 1000}s ago" else "none"
            Text(
                "Build70 debug: helper=bydmate_h70 | A11y=${if (build70A11y) "CONNECTED" else "OFF"} | 304=$build70Age304 | 327 BLOCKED=$build70Age327",
                color = TextMuted,
                fontSize = 11.sp,
                modifier = Modifier.padding(vertical = 6.dp),
            )

            val gigaAmDownloading = state.gigaAmDownloadProgress >= 0
'''
s = replace_once(s, anchor, replacement, "Build70 visible steering diagnostics")
s = replace_once(
    s,
    '                    stringResource(R.string.settings_voice_model_downloading, state.gigaAmDownloadProgress),\n',
    '                    "GigaAM debug: ${state.gigaAmDownloadPhase} · ${state.gigaAmDownloadProgress}%",\n',
    "visible GigaAM phase",
)
# Preserve the phase after a failed background job too, instead of collapsing to an unexplained red state.
s = replace_once(
    s,
    '''            if (gigaAmDownloading) {
                Text(
                    "GigaAM debug: ${state.gigaAmDownloadPhase} · ${state.gigaAmDownloadProgress}%",
                    color = TextSecondary, fontSize = 12.sp,
                    modifier = Modifier.padding(vertical = 8.dp),
                )
''',
    '''            if (gigaAmDownloading) {
                Text(
                    "GigaAM debug: ${state.gigaAmDownloadPhase} · ${state.gigaAmDownloadProgress}%",
                    color = TextSecondary, fontSize = 12.sp,
                    modifier = Modifier.padding(vertical = 8.dp),
                )
''',
    "GigaAM debug block verification",
)
p.write_text(s)

print("Build70 fixes applied: version 60020, isolated field helper, early 327 blocker, persistent GigaAM phase diagnostics")
