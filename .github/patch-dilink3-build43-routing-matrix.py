from pathlib import Path

# Build43: replace the long wizard with a compact routing-focused diagnostic matrix.
# Already-proven items (mic permission/PCM, System ASR, AIHubMix, offline TTS, key identity,
# Activity-level consume failure) are no longer interactive steps.

# 1) Instrument AccessibilityService for unconditional 304 observation and diagnostic consume.
p = Path('app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt')
s = p.read_text()
needle = '    override fun onKeyEvent(event: KeyEvent): Boolean {\n        val isDown = event.action == KeyEvent.ACTION_DOWN\n'
replacement = '''    override fun onKeyEvent(event: KeyEvent): Boolean {
        val isDown = event.action == KeyEvent.ACTION_DOWN
        if (event.keyCode == 304) {
            last304AtMs = android.os.SystemClock.elapsedRealtime()
            last304Action = event.action
            last304DeviceId = event.deviceId
            last304ScanCode = event.scanCode
            val diag = applicationContext.getSharedPreferences("dilink3_diag", Context.MODE_PRIVATE)
            val consume304 = diag.getBoolean("build43_a11y_consume_304", false)
            Log.w(TAG, "BUILD43_A11Y_304 action=${event.action} deviceId=${event.deviceId} scanCode=${event.scanCode} consume=$consume304")
            if (consume304) return true
        }
'''
if needle not in s:
    raise SystemExit('build43 SteeringWheelKeyService onKeyEvent anchor not found')
s = s.replace(needle, replacement, 1)
companion = '    companion object {\n        const val TAG = "SteeringWheelKeySvc"\n'
companion_repl = '''    companion object {
        const val TAG = "SteeringWheelKeySvc"
        @Volatile var last304AtMs: Long = 0L
        @Volatile var last304Action: Int = -1
        @Volatile var last304DeviceId: Int = -1
        @Volatile var last304ScanCode: Int = -1
'''
if companion not in s:
    raise SystemExit('build43 companion anchor not found')
s = s.replace(companion, companion_repl, 1)
p.write_text(s)

# 2) Replace diagnostic panel with compact, high-yield matrix.
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
panel = r'''package com.bydmate.app.ui.diagnostics

import android.app.role.RoleManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioManager
import android.os.Build
import android.os.SystemClock
import android.provider.Settings
import android.view.InputDevice
import android.view.KeyCharacterMap
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.bydmate.app.cluster.ClusterEntryPoint
import com.bydmate.app.cluster.SteeringWheelKeyService
import com.bydmate.app.voice.AudioCapture
import com.bydmate.app.voice.ContinuousAsr
import com.bydmate.app.voice.TtsModelManager
import com.bydmate.app.voice.VoiceController
import dagger.hilt.android.EntryPointAccessors
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private data class MatrixResult(val ok: Int, val warn: Int, val detail: String)

@Composable
fun DiLink3VoiceDebugPanel(
    voiceController: VoiceController,
    continuousAsr: ContinuousAsr,
    audioCapture: AudioCapture,
    ttsModelManager: TtsModelManager,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val diagPrefs = remember { context.getSharedPreferences("dilink3_diag", Context.MODE_PRIVATE) }
    val pm = remember { context.packageManager }
    val audio = remember { context.getSystemService(Context.AUDIO_SERVICE) as AudioManager }
    val ep = remember { EntryPointAccessors.fromApplication(context.applicationContext, ClusterEntryPoint::class.java) }
    val helper = remember { ep.helperClient() }
    val bootstrap = remember { ep.helperBootstrap() }

    var expanded by remember { mutableStateOf(false) }
    var matrixRunning by remember { mutableStateOf(false) }
    var matrix by remember { mutableStateOf<MatrixResult?>(null) }
    var a11yReady by remember { mutableStateOf<Boolean?>(null) }
    var interactiveMode by remember { mutableStateOf("idle") }
    var pressSeenAt by remember { mutableStateOf(0L) }
    var assistantQuestion by remember { mutableStateOf(false) }
    var assistantDisabled by remember { mutableStateOf(false) }
    var lastOutcome by remember { mutableStateOf("") }

    DisposableEffect(Unit) {
        onDispose {
            diagPrefs.edit().putBoolean("build43_a11y_consume_304", false).apply()
            if (assistantDisabled) {
                scope.launch { runCatching { helper.setAppHidden("com.byd.autovoice", false) } }
            }
        }
    }

    LaunchedEffect(Unit) {
        DiLink3DebugLog.log(context, "BUILD43_OPEN", "package=${context.packageName}")
        val helperOk = runCatching { bootstrap.ensureRunning() }.getOrDefault(false)
        val enableOk = if (helperOk) runCatching { helper.enableAccessibilityService() }.getOrDefault(false) else false
        repeat(30) {
            if (SteeringWheelKeyService.isConnected) return@repeat
            delay(100)
        }
        a11yReady = SteeringWheelKeyService.isConnected
        DiLink3DebugLog.log(context, "BUILD43_A11Y_BOOT", "helper=$helperOk enable=$enableOk connected=${SteeringWheelKeyService.isConnected}")
    }

    LaunchedEffect(interactiveMode) {
        if (interactiveMode == "idle") return@LaunchedEffect
        pressSeenAt = SteeringWheelKeyService.last304AtMs
        assistantQuestion = false
        val started = SystemClock.elapsedRealtime()
        while (interactiveMode != "idle" && SystemClock.elapsedRealtime() - started < 15000L) {
            val at = SteeringWheelKeyService.last304AtMs
            if (at > pressSeenAt) {
                pressSeenAt = at
                assistantQuestion = true
                DiLink3DebugLog.log(context, "BUILD43_INTERACTIVE_PRESS", "mode=$interactiveMode action=${SteeringWheelKeyService.last304Action} deviceId=${SteeringWheelKeyService.last304DeviceId} scanCode=${SteeringWheelKeyService.last304ScanCode}")
                break
            }
            delay(100)
        }
    }

    fun runMatrix() {
        if (matrixRunning) return
        matrixRunning = true
        matrix = null
        scope.launch {
            var ok = 0
            var warn = 0
            val lines = mutableListOf<String>()
            fun pass(name: String, d: String) { ok++; lines += "✅ $name: $d"; DiLink3DebugLog.log(context, "BUILD43_MATRIX_OK", "$name | $d") }
            fun attention(name: String, d: String) { warn++; lines += "⚠️ $name: $d"; DiLink3DebugLog.log(context, "BUILD43_MATRIX_WARN", "$name | $d") }
            DiLink3DebugLog.log(context, "BUILD43_MATRIX_START")

            // 1. Helper + live Accessibility binding.
            val helperOk = runCatching { bootstrap.ensureRunning() }.getOrDefault(false)
            if (helperOk) pass("HELPER", "alive") else attention("HELPER", "unavailable")
            if (SteeringWheelKeyService.isConnected) pass("A11Y_BIND", "connected") else attention("A11Y_BIND", "not connected")
            val svcFlags = SteeringWheelKeyService.instance?.serviceInfo?.flags
            if (svcFlags != null) pass("A11Y_FLAGS", "0x${svcFlags.toString(16)} filterKey=${(svcFlags and 32) != 0}") else attention("A11Y_FLAGS", "service instance absent")

            // 2. Secure routing state.
            val secureKeys = listOf("assistant", "voice_interaction_service", "voice_recognition_service", "enabled_accessibility_services", "enabled_notification_listeners", "default_input_method")
            secureKeys.forEach { key ->
                val value = runCatching { Settings.Secure.getString(context.contentResolver, key) }.getOrNull().orEmpty()
                pass("SECURE_$key", value.ifBlank { "<empty>" })
            }

            // 3. Android Assistant role holders (API 29+).
            if (Build.VERSION.SDK_INT >= 29) {
                val holders = runCatching {
                    val rm = context.getSystemService(RoleManager::class.java)
                    rm?.getRoleHolders(RoleManager.ROLE_ASSISTANT).orEmpty()
                }.getOrDefault(emptyList())
                pass("ROLE_ASSISTANT", holders.joinToString().ifBlank { "<none>" })
            }

            // 4. Intent resolver matrix.
            val actions = listOf(
                Intent.ACTION_ASSIST,
                Intent.ACTION_VOICE_COMMAND,
                "android.speech.action.RECOGNIZE_SPEECH",
                "android.speech.action.WEB_SEARCH"
            )
            actions.forEach { action ->
                val i = Intent(action)
                val resolved = runCatching { pm.resolveActivity(i, PackageManager.MATCH_DEFAULT_ONLY)?.activityInfo }
                    .getOrNull()?.let { "${it.packageName}/${it.name}" }.orEmpty()
                val all = runCatching { pm.queryIntentActivities(i, PackageManager.MATCH_ALL) }.getOrDefault(emptyList())
                    .mapNotNull { it.activityInfo?.let { ai -> "${ai.packageName}/${ai.name}" } }.distinct()
                pass("RESOLVE_${action.substringAfterLast('.')}", "default=${resolved.ifBlank { "<none>" }} all=${all.joinToString().ifBlank { "<none>" }}")
            }
            val mediaReceivers = runCatching { pm.queryBroadcastReceivers(Intent(Intent.ACTION_MEDIA_BUTTON), PackageManager.MATCH_ALL) }
                .getOrDefault(emptyList()).mapNotNull { it.activityInfo?.let { ai -> "${ai.packageName}/${ai.name}" } }.distinct()
            pass("MEDIA_BUTTON_RECEIVERS", mediaReceivers.joinToString().ifBlank { "<none>" })

            // 5. BYD assistant package family inventory.
            listOf("com.byd.autovoice", "com.byd.autovoice.engine", "com.byd.autovoice.tts").forEach { pkg ->
                val pi = runCatching { pm.getPackageInfo(pkg, PackageManager.GET_ACTIVITIES or PackageManager.GET_SERVICES or PackageManager.GET_RECEIVERS) }.getOrNull()
                if (pi == null) {
                    attention("PKG_$pkg", "not installed")
                } else {
                    val app = pi.applicationInfo
                    val acts = pi.activities?.joinToString { "${it.name}[e=${it.enabled}]" }.orEmpty()
                    val svcs = pi.services?.joinToString { "${it.name}[e=${it.enabled}]" }.orEmpty()
                    val recs = pi.receivers?.joinToString { "${it.name}[e=${it.enabled}]" }.orEmpty()
                    pass("PKG_$pkg", "enabled=${app?.enabled} system=${app?.let { (it.flags and android.content.pm.ApplicationInfo.FLAG_SYSTEM) != 0 }} v=${pi.versionName}; activities=$acts; services=$svcs; receivers=$recs")
                }
            }

            // 6. Physical input source inventory and 304 support.
            val devices = InputDevice.getDeviceIds().toList().mapNotNull { InputDevice.getDevice(it) }
            devices.forEach { d ->
                val has304 = runCatching { KeyCharacterMap.deviceHasKey(304) }.getOrDefault(false)
                pass("INPUT_${d.id}", "name=${d.name} src=0x${d.sources.toString(16)} vendor=${d.vendorId} product=${d.productId} descriptor=${d.descriptor} globalHas304=$has304")
            }

            // 7. Current audio state, useful to correlate assistant taking the mic.
            pass("AUDIO_STATE", "mode=${audio.mode} musicActive=${audio.isMusicActive} speaker=${audio.isSpeakerphoneOn} micMute=${audio.isMicrophoneMute}")

            matrix = MatrixResult(ok, warn, lines.joinToString("\n"))
            matrixRunning = false
            DiLink3DebugLog.log(context, "BUILD43_MATRIX_END", "ok=$ok warn=$warn")
        }
    }

    fun arm(mode: String, consume: Boolean) {
        diagPrefs.edit().putBoolean("build43_a11y_consume_304", consume).apply()
        interactiveMode = mode
        assistantQuestion = false
        lastOutcome = ""
        DiLink3DebugLog.log(context, "BUILD43_INTERACTIVE_ARM", "mode=$mode consume=$consume a11y=${SteeringWheelKeyService.isConnected}")
    }

    fun finishInteractive(assistantAppeared: Boolean) {
        val mode = interactiveMode
        lastOutcome = "$mode: BYD Assistant ${if (assistantAppeared) "ОТКРЫЛСЯ" else "НЕ открылся"}"
        DiLink3DebugLog.log(context, "BUILD43_INTERACTIVE_RESULT", "mode=$mode assistantAppeared=$assistantAppeared a11y=${SteeringWheelKeyService.isConnected}")
        diagPrefs.edit().putBoolean("build43_a11y_consume_304", false).apply()
        interactiveMode = "idle"
        assistantQuestion = false
        if (mode == "assistant_disabled") {
            scope.launch {
                val restored = runCatching { helper.setAppHidden("com.byd.autovoice", false) }.getOrDefault(false)
                assistantDisabled = false
                DiLink3DebugLog.log(context, "BUILD43_ASSISTANT_RESTORE", "restored=$restored")
            }
        }
    }

    if (!expanded) {
        Card(modifier = modifier.fillMaxWidth()) {
            Button(onClick = { expanded = true }, modifier = Modifier.fillMaxWidth().padding(8.dp)) {
                Text("ОТКРЫТЬ DILINK3 ROUTING LAB")
            }
        }
        return
    }

    Column(
        modifier = modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text("DiLink3 Routing Lab — build 43", style = MaterialTheme.typography.titleLarge)
        Text("Уже подтверждено и больше не тестируем: keyCode 304 / scanCode 290; Activity видит DOWN+UP; Activity consume не блокирует BYD Assistant; System ASR, AI и TTS работают. Сейчас проверяем только реальный системный маршрут кнопки.")
        Text("A11y connected: ${a11yReady ?: SteeringWheelKeyService.isConnected}")

        Button(onClick = { runMatrix() }, enabled = !matrixRunning, modifier = Modifier.fillMaxWidth()) {
            Text(if (matrixRunning) "ЗАПУСКАЮ 7 ГРУПП ТЕСТОВ..." else "1. ЗАПУСТИТЬ ВСЮ МАТРИЦУ")
        }
        matrix?.let {
            Text("Matrix: ${it.ok} OK / ${it.warn} WARN")
            Text(it.detail, style = MaterialTheme.typography.bodySmall)
        }

        Text("Интерактивные тесты — каждый требует только одного нажатия физической кнопки микрофона.", style = MaterialTheme.typography.titleMedium)
        Button(onClick = { arm("passive_a11y", false) }, enabled = interactiveMode == "idle", modifier = Modifier.fillMaxWidth()) {
            Text("2. PASSIVE: A11Y ВИДИТ 304?")
        }
        Button(onClick = { arm("a11y_consume", true) }, enabled = interactiveMode == "idle" && SteeringWheelKeyService.isConnected, modifier = Modifier.fillMaxWidth()) {
            Text("3. A11Y CONSUME 304")
        }
        Button(onClick = {
            scope.launch {
                val ready = runCatching { bootstrap.ensureRunning() }.getOrDefault(false)
                val disabled = if (ready) runCatching { helper.setAppHidden("com.byd.autovoice", true) }.getOrDefault(false) else false
                assistantDisabled = disabled
                DiLink3DebugLog.log(context, "BUILD43_ASSISTANT_DISABLE", "helper=$ready disabled=$disabled")
                if (disabled) arm("assistant_disabled", false) else lastOutcome = "Не удалось временно отключить BYD Assistant family"
            }
        }, enabled = interactiveMode == "idle" && !assistantDisabled, modifier = Modifier.fillMaxWidth()) {
            Text("4. TEMP DISABLE BYD ASSISTANT + TEST")
        }

        if (interactiveMode != "idle") {
            Text("Режим: $interactiveMode. Нажми физическую кнопку микрофона один раз.")
        }
        if (assistantQuestion) {
            Text("304 зафиксирован. Открылся штатный BYD Assistant?")
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { finishInteractive(true) }) { Text("ДА") }
                Button(onClick = { finishInteractive(false) }) { Text("НЕТ") }
            }
        }
        if (lastOutcome.isNotBlank()) Text("Результат: $lastOutcome")

        if (assistantDisabled && interactiveMode == "idle") {
            Button(onClick = {
                scope.launch {
                    val restored = runCatching { helper.setAppHidden("com.byd.autovoice", false) }.getOrDefault(false)
                    assistantDisabled = !restored
                    lastOutcome = "BYD Assistant restore=$restored"
                }
            }, modifier = Modifier.fillMaxWidth()) { Text("ВОССТАНОВИТЬ BYD ASSISTANT") }
        }
    }
}
'''
p.write_text(panel)
print('Build43 routing matrix panel written')
