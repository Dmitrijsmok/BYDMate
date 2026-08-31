from pathlib import Path

panel = r'''package com.bydmate.app.ui.diagnostics

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.provider.Settings
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.view.InputDevice
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

@Composable
@Suppress("UNUSED_PARAMETER")
fun DiLink3VoiceDebugPanel(
    voiceController: VoiceController,
    continuousAsr: ContinuousAsr,
    audioCapture: AudioCapture,
    ttsModelManager: TtsModelManager,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val pm = context.packageManager
    val scope = rememberCoroutineScope()
    val diagPrefs = remember { context.getSharedPreferences("dilink3_diag", Context.MODE_PRIVATE) }
    val entry = remember {
        EntryPointAccessors.fromApplication(context.applicationContext, ClusterEntryPoint::class.java)
    }
    val helper = remember { entry.helperClient() }
    val bootstrap = remember { entry.helperBootstrap() }

    var status by remember { mutableStateOf("Готово. Выберите тест.") }
    var watcherRunning by remember { mutableStateOf(false) }
    var lastKeyAt by remember { mutableStateOf(0L) }

    fun log(tag: String, detail: String = "") {
        DiLink3DebugLog.log(context, tag, detail)
    }

    fun componentNameOfActivity(intent: Intent): String {
        return runCatching {
            val ri = pm.resolveActivity(intent, PackageManager.MATCH_DEFAULT_ONLY)
            ri?.activityInfo?.let { "${it.packageName}/${it.name}" } ?: "none"
        }.getOrElse { "ERROR:${it::class.java.simpleName}:${it.message}" }
    }

    fun secure(name: String): String = runCatching {
        Settings.Secure.getString(context.contentResolver, name) ?: ""
    }.getOrElse { "ERROR:${it::class.java.simpleName}" }

    fun packageState(pkg: String): String = runCatching {
        @Suppress("DEPRECATION")
        val pi = pm.getPackageInfo(pkg,
            PackageManager.GET_ACTIVITIES or PackageManager.GET_SERVICES or PackageManager.GET_RECEIVERS or PackageManager.GET_PROVIDERS)
        val ai = pi.applicationInfo
        val enabled = ai?.enabled
        val uid = ai?.uid
        val activities = pi.activities?.size ?: 0
        val services = pi.services?.size ?: 0
        val receivers = pi.receivers?.size ?: 0
        val providers = pi.providers?.size ?: 0
        "pkg=$pkg enabled=$enabled uid=$uid version=${pi.versionName} activities=$activities services=$services receivers=$receivers providers=$providers"
    }.getOrElse { "pkg=$pkg absentOrError=${it::class.java.simpleName}:${it.message}" }

    fun systemSnapshot() {
        val assistant = secure("assistant")
        val vis = secure("voice_interaction_service")
        val recognizer = secure("voice_recognition_service")
        val enabledA11y = secure("enabled_accessibility_services")
        val a11yEnabled = secure("accessibility_enabled")
        val assist = componentNameOfActivity(Intent(Intent.ACTION_ASSIST))
        val voiceCmd = componentNameOfActivity(Intent(Intent.ACTION_VOICE_COMMAND))
        val rec = componentNameOfActivity(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH))
        log("LAB_SYSTEM_SNAPSHOT", "assistant=$assistant voiceInteraction=$vis voiceRecognizer=$recognizer accessibilityEnabled=$a11yEnabled enabledA11y=$enabledA11y resolveAssist=$assist resolveVoiceCommand=$voiceCmd resolveRecognize=$rec steeringConnected=${SteeringWheelKeyService.isConnected}")
        status = "Снимок системы записан"
    }

    fun scanVoicePackages() {
        scope.launch {
            status = "Сканирую BYD voice-пакеты..."
            val lines = runCatching {
                @Suppress("DEPRECATION")
                pm.getInstalledPackages(PackageManager.GET_SERVICES or PackageManager.GET_RECEIVERS)
                    .filter {
                        val p = it.packageName.lowercase()
                        p.contains("byd") && (p.contains("voice") || p.contains("vr") || p.contains("assistant") || p.contains("speech") || p.contains("tts"))
                    }
                    .sortedBy { it.packageName }
                    .map { pi ->
                        val ai = pi.applicationInfo
                        "${pi.packageName}|enabled=${ai?.enabled}|uid=${ai?.uid}|svc=${pi.services?.size ?: 0}|rcv=${pi.receivers?.size ?: 0}|ver=${pi.versionName}"
                    }
            }.getOrElse { listOf("ERROR:${it::class.java.simpleName}:${it.message}") }
            lines.forEach { log("LAB_VOICE_PACKAGE", it) }
            log("LAB_VOICE_PACKAGE_SUMMARY", "count=${lines.size}")
            status = "Voice-пакеты: ${lines.size}; см. лог"
        }
    }

    fun dumpPackageComponents(pkg: String) {
        scope.launch {
            status = "Читаю компоненты $pkg..."
            runCatching {
                @Suppress("DEPRECATION")
                pm.getPackageInfo(pkg, PackageManager.GET_ACTIVITIES or PackageManager.GET_SERVICES or PackageManager.GET_RECEIVERS or PackageManager.GET_PROVIDERS)
            }.onSuccess { pi ->
                log("LAB_PACKAGE_STATE", packageState(pkg))
                pi.activities.orEmpty().forEach { log("LAB_COMPONENT", "pkg=$pkg type=activity name=${it.name} enabled=${it.enabled} exported=${it.exported} permission=${it.permission}") }
                pi.services.orEmpty().forEach { log("LAB_COMPONENT", "pkg=$pkg type=service name=${it.name} enabled=${it.enabled} exported=${it.exported} permission=${it.permission}") }
                pi.receivers.orEmpty().forEach { log("LAB_COMPONENT", "pkg=$pkg type=receiver name=${it.name} enabled=${it.enabled} exported=${it.exported} permission=${it.permission}") }
                pi.providers.orEmpty().forEach { log("LAB_COMPONENT", "pkg=$pkg type=provider name=${it.name} enabled=${it.enabled} exported=${it.exported} permission=${it.readPermission ?: it.writePermission}") }
                status = "$pkg: компоненты записаны"
            }.onFailure {
                log("LAB_PACKAGE_ERROR", "pkg=$pkg ${it::class.java.simpleName}:${it.message}")
                status = "$pkg не найден или недоступен"
            }
        }
    }

    fun dumpIntentRouting() {
        val intents = listOf(
            "ASSIST" to Intent(Intent.ACTION_ASSIST),
            "VOICE_COMMAND" to Intent(Intent.ACTION_VOICE_COMMAND),
            "RECOGNIZE_SPEECH" to Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH),
            "WEB_SEARCH" to Intent(Intent.ACTION_WEB_SEARCH),
        )
        intents.forEach { (name, intent) ->
            val resolved = componentNameOfActivity(intent)
            val all = runCatching {
                pm.queryIntentActivities(intent, PackageManager.MATCH_ALL).joinToString(";") { ri ->
                    ri.activityInfo?.let { "${it.packageName}/${it.name}" } ?: "?"
                }
            }.getOrElse { "ERROR:${it::class.java.simpleName}" }
            log("LAB_INTENT_ROUTE", "action=$name resolved=$resolved candidates=$all")
        }
        status = "Intent routing записан"
    }

    fun dumpInputDevices() {
        val devices = InputDevice.getDeviceIds().toList().mapNotNull { InputDevice.getDevice(it) }
        devices.forEach {
            log("LAB_INPUT_DEVICE", "id=${it.id} name=${it.name} descriptor=${it.descriptor} sources=0x${it.sources.toString(16)} vendor=${it.vendorId} product=${it.productId} keyboardType=${it.keyboardType}")
        }
        status = "Input devices: ${devices.size}; см. лог"
    }

    fun helperStatus(tryRecovery: Boolean) {
        scope.launch {
            status = if (tryRecovery) "Пробую поднять helper..." else "Проверяю helper..."
            val healthyBefore = runCatching { bootstrap.isHealthy() }.getOrDefault(false)
            val daemonVersionBefore = runCatching { helper.daemonVersion() }.getOrNull()
            val failureBefore = bootstrap.lastSpawnFailure()
            log("LAB_HELPER_BEFORE", "healthy=$healthyBefore daemonVersion=$daemonVersionBefore failure=$failureBefore")
            var ensured: Boolean? = null
            var enableA11y: Boolean? = null
            if (tryRecovery) {
                ensured = runCatching { bootstrap.ensureRunning() }.getOrDefault(false)
                if (ensured) enableA11y = runCatching { helper.enableAccessibilityService() }.getOrDefault(false)
                delay(1500)
            }
            val healthyAfter = runCatching { bootstrap.isHealthy() }.getOrDefault(false)
            val daemonVersionAfter = runCatching { helper.daemonVersion() }.getOrNull()
            val failureAfter = bootstrap.lastSpawnFailure()
            log("LAB_HELPER_AFTER", "recovery=$tryRecovery ensured=$ensured enableA11y=$enableA11y healthy=$healthyAfter daemonVersion=$daemonVersionAfter failure=$failureAfter steeringConnected=${SteeringWheelKeyService.isConnected}")
            status = "Helper: before=$healthyBefore after=$healthyAfter ensured=$ensured a11y=$enableA11y"
        }
    }

    fun arm304(mode: String) {
        diagPrefs.edit()
            .putBoolean("mic_button_logger_armed", true)
            .putBoolean("mic_button_block_native", false)
            .apply()
        SteeringWheelKeyService.clearDiagKey()
        lastKeyAt = 0L
        watcherRunning = true
        log("LAB_304_ARMED", "mode=$mode instruction=${if (mode == "long") "hold 3 seconds" else "short press 3 times"}")
        status = if (mode == "long") "Удерживайте кнопку микрофона ~3 сек" else "Нажмите кнопку микрофона 3 раза"
        scope.launch {
            val started = android.os.SystemClock.elapsedRealtime()
            while (android.os.SystemClock.elapsedRealtime() - started < 12000L) {
                val at = SteeringWheelKeyService.lastDiagKeyAtMs
                if (at > lastKeyAt) {
                    lastKeyAt = at
                    log("LAB_304_OBSERVED", "mode=$mode keyCode=${SteeringWheelKeyService.lastDiagKeyCode} action=${SteeringWheelKeyService.lastDiagKeyAction} connected=${SteeringWheelKeyService.isConnected} elapsed=${android.os.SystemClock.elapsedRealtime() - started}")
                }
                delay(50)
            }
            watcherRunning = false
            log("LAB_304_WINDOW_END", "mode=$mode connected=${SteeringWheelKeyService.isConnected} lastKeyCode=${SteeringWheelKeyService.lastDiagKeyCode} lastAction=${SteeringWheelKeyService.lastDiagKeyAction}")
            status = "Тест 304 завершён; экспортируйте лог"
        }
    }

    fun watchA11yConnection() {
        scope.launch {
            status = "Слежу за Accessibility 15 секунд..."
            val start = android.os.SystemClock.elapsedRealtime()
            var prev = SteeringWheelKeyService.isConnected
            log("LAB_A11Y_WATCH_START", "connected=$prev enabled=${secure("enabled_accessibility_services")}")
            while (android.os.SystemClock.elapsedRealtime() - start < 15000L) {
                val now = SteeringWheelKeyService.isConnected
                if (now != prev) {
                    log("LAB_A11Y_CONNECTION_CHANGE", "connected=$now afterMs=${android.os.SystemClock.elapsedRealtime() - start}")
                    prev = now
                }
                delay(100)
            }
            log("LAB_A11Y_WATCH_END", "connected=${SteeringWheelKeyService.isConnected}")
            status = "Accessibility watcher завершён"
        }
    }

    fun launchIntent(action: String) {
        val intent = Intent(action).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        val resolved = componentNameOfActivity(intent)
        log("LAB_MANUAL_INTENT", "action=$action resolved=$resolved")
        runCatching { context.startActivity(intent) }
            .onSuccess { status = "Запущен $action; отметьте что открылось" }
            .onFailure {
                log("LAB_MANUAL_INTENT_ERROR", "action=$action ${it::class.java.simpleName}:${it.message}")
                status = "Ошибка запуска $action"
            }
    }

    fun runPassivePack() {
        systemSnapshot()
        dumpIntentRouting()
        dumpInputDevices()
        scanVoicePackages()
        log("LAB_PACKAGE_STATE", packageState("com.byd.vrassistant"))
        log("LAB_PACKAGE_STATE", packageState("com.byd.autovoice"))
        log("LAB_PACKAGE_STATE", packageState("com.byd.autovoice.engine"))
        log("LAB_PACKAGE_STATE", packageState("com.byd.autovoice.tts"))
        scope.launch {
            val healthy = runCatching { bootstrap.isHealthy() }.getOrDefault(false)
            val version = runCatching { helper.daemonVersion() }.getOrNull()
            log("LAB_PASSIVE_HELPER", "healthy=$healthy daemonVersion=$version failure=${bootstrap.lastSpawnFailure()} steeringConnected=${SteeringWheelKeyService.isConnected}")
        }
        status = "Пассивный пакет запущен; см. лог"
    }

    DisposableEffect(Unit) {
        diagPrefs.edit().putBoolean("mic_button_block_native", false).apply()
        onDispose {
            watcherRunning = false
            diagPrefs.edit().putBoolean("mic_button_block_native", false).apply()
        }
    }

    LaunchedEffect(Unit) {
        log("LAB_OPEN", "package=${context.packageName} steeringConnected=${SteeringWheelKeyService.isConnected} systemAsr=${SpeechRecognizer.isRecognitionAvailable(context)}")
    }

    Card(modifier = modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(10.dp).verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text("DiLink3 Voice Test Lab #43", style = MaterialTheme.typography.titleLarge)
            Text("Старые подтверждённые шаги убраны. Здесь независимые тесты, которые можно запускать в любом порядке.")
            Text(status, style = MaterialTheme.typography.bodyMedium)
            if (watcherRunning) Text("● Идёт наблюдение за кнопкой 304")

            Button(onClick = { runPassivePack() }, modifier = Modifier.fillMaxWidth()) { Text("1. ВСЕ ПАССИВНЫЕ ПРОВЕРКИ") }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                Button(onClick = { systemSnapshot() }, modifier = Modifier.weight(1f)) { Text("Система") }
                Button(onClick = { dumpIntentRouting() }, modifier = Modifier.weight(1f)) { Text("Intent routing") }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                Button(onClick = { scanVoicePackages() }, modifier = Modifier.weight(1f)) { Text("Voice-пакеты") }
                Button(onClick = { dumpInputDevices() }, modifier = Modifier.weight(1f)) { Text("Input devices") }
            }

            Button(onClick = { dumpPackageComponents("com.byd.vrassistant") }, modifier = Modifier.fillMaxWidth()) { Text("2. КОМПОНЕНТЫ com.byd.vrassistant") }
            Button(onClick = { dumpPackageComponents("com.byd.autovoice") }, modifier = Modifier.fillMaxWidth()) { Text("3. КОМПОНЕНТЫ com.byd.autovoice") }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                Button(onClick = { helperStatus(false) }, modifier = Modifier.weight(1f)) { Text("Helper status") }
                Button(onClick = { helperStatus(true) }, modifier = Modifier.weight(1f)) { Text("Helper recovery + A11Y") }
            }

            Button(onClick = { watchA11yConnection() }, modifier = Modifier.fillMaxWidth()) { Text("4. WATCH ACCESSIBILITY 15s") }
            Button(onClick = { arm304("short") }, enabled = !watcherRunning, modifier = Modifier.fillMaxWidth()) { Text("5. 304: 3 КОРОТКИХ НАЖАТИЯ") }
            Button(onClick = { arm304("long") }, enabled = !watcherRunning, modifier = Modifier.fillMaxWidth()) { Text("6. 304: ДЛИННОЕ НАЖАТИЕ 3s") }

            Text("Экспериментальные маршруты. Они ничего не меняют в настройках, но могут открыть системный/Google/BYD экран.", style = MaterialTheme.typography.bodySmall)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                Button(onClick = { launchIntent(Intent.ACTION_VOICE_COMMAND) }, modifier = Modifier.weight(1f)) { Text("VOICE_COMMAND") }
                Button(onClick = { launchIntent(Intent.ACTION_ASSIST) }, modifier = Modifier.weight(1f)) { Text("ACTION_ASSIST") }
            }

            Text("После серии тестов просто экспортируйте один лог. Особо важны LAB_*, SYSTEM_ASSISTANT_ROUTING и A11Y_KEY_*.", style = MaterialTheme.typography.bodySmall)
        }
    }
}
'''

p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
p.write_text(panel)
print('build43 test lab panel installed')

# Reduce the extremely noisy Accessibility window trace from build42. Keep BYD voice windows
# and key-specific traces; SystemUI / our own Compose churn obscures timing in exported logs.
svc = Path('app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt')
if svc.exists():
    s = svc.read_text()
    old = '''            DiLink3DebugLog.log(applicationContext, "A11Y_WINDOW_TRACE", detail)'''
    if old in s:
        new = '''            val pkgName = event.packageName?.toString().orEmpty()\n            if (pkgName.contains("vrassistant", ignoreCase = true) ||\n                pkgName.contains("autovoice", ignoreCase = true) ||\n                pkgName.contains("voice", ignoreCase = true)) {\n                DiLink3DebugLog.log(applicationContext, "A11Y_WINDOW_TRACE", detail)\n            }'''
        s = s.replace(old, new, 1)
        svc.write_text(s)
        print('build43 A11Y trace noise filter installed')
    else:
        print('build43 A11Y trace filter anchor not found; leaving source unchanged')
