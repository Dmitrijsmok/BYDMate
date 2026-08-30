from pathlib import Path

# Final UI override for the DiLink3 diagnostic build.
# Earlier workflow patches keep their deep logging hooks; this patch replaces only the
# user-facing panel with a short guided wizard + an independent non-destructive batch test.

panel = r'''package com.bydmate.app.ui.diagnostics

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioManager
import android.os.Bundle
import android.os.SystemClock
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
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
import androidx.core.content.ContextCompat
import com.bydmate.app.cluster.SteeringWheelKeyService
import com.bydmate.app.voice.AudioCapture
import com.bydmate.app.voice.ContinuousAsr
import com.bydmate.app.voice.DiLink3AudioSourceProbe
import com.bydmate.app.voice.TtsModelManager
import com.bydmate.app.voice.TtsVoiceCatalog
import com.bydmate.app.voice.VoiceController
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private data class BatchSummary(val ok: Int, val warn: Int, val fail: Int, val detail: String)

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
    val voicePrefs = remember { context.getSharedPreferences("voice", Context.MODE_PRIVATE) }
    val diagPrefs = remember { context.getSharedPreferences("dilink3_diag", Context.MODE_PRIVATE) }
    val e2eBridge = remember { DiLink3E2EBridge(context.applicationContext) }
    val audioManager = remember { context.getSystemService(Context.AUDIO_SERVICE) as AudioManager }

    var expanded by remember { mutableStateOf(false) }
    var step by remember { mutableStateOf(1) }
    var batchRunning by remember { mutableStateOf(false) }
    var batchSummary by remember { mutableStateOf<BatchSummary?>(null) }
    var batchDetailVisible by remember { mutableStateOf(false) }
    var micDetectedCode by remember { mutableStateOf<Int?>(null) }
    var micDetectedAt by remember { mutableStateOf(0L) }
    var stockAssistantAnswer by remember { mutableStateOf<Boolean?>(null) }
    var blockTestRunning by remember { mutableStateOf(false) }
    var blockWorked by remember { mutableStateOf<Boolean?>(null) }
    var e2eStatus by remember { mutableStateOf("Ожидает запуска") }
    var e2eHeard by remember { mutableStateOf("") }
    var e2eAnswer by remember { mutableStateOf("") }
    var e2eError by remember { mutableStateOf("") }
    var e2eListening by remember { mutableStateOf(false) }
    var userHeardTts by remember { mutableStateOf<Boolean?>(null) }
    var aiReady by remember { mutableStateOf<Boolean?>(null) }

    val micGranted = ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
    val systemAsrAvailable = remember { SpeechRecognizer.isRecognitionAvailable(context) }
    val selectedVoiceId = voicePrefs.getString("tts_voice", TtsModelManager.DEFAULT_VOICE_ID) ?: TtsModelManager.DEFAULT_VOICE_ID
    val selectedVoice = TtsVoiceCatalog.byId(selectedVoiceId)
    val ttsReady = ttsModelManager.isReady(selectedVoice)
    val gigaReady = continuousAsr.isReady()

    val recognizer = remember(systemAsrAvailable) {
        if (systemAsrAvailable) SpeechRecognizer.createSpeechRecognizer(context) else null
    }

    DisposableEffect(Unit) {
        onDispose {
            runCatching { recognizer?.cancel() }
            runCatching { recognizer?.destroy() }
            diagPrefs.edit().putBoolean("mic_button_block_native", false).apply()
            blockTestRunning = false
        }
    }

    LaunchedEffect(Unit) {
        DiLink3DebugLog.log(context, "WIZARD_OPEN_STATE", "mic=$micGranted systemAsr=$systemAsrAvailable steeringConnected=${SteeringWheelKeyService.isConnected} gigaReady=$gigaReady ttsReady=$ttsReady")
        aiReady = runCatching { e2eBridge.loadAihubmixConfig() }
            .getOrNull()?.let { it.enabled && it.apiKey.isNotBlank() }
    }

    LaunchedEffect(recognizer) {
        recognizer?.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) {
                e2eListening = true
                e2eStatus = "Говорите"
                DiLink3DebugLog.log(context, "WIZARD_E2E_ASR_READY")
            }
            override fun onBeginningOfSpeech() {
                e2eStatus = "Речь обнаружена"
                DiLink3DebugLog.log(context, "WIZARD_E2E_SPEECH_BEGIN")
            }
            override fun onRmsChanged(rmsdB: Float) = Unit
            override fun onBufferReceived(buffer: ByteArray?) = Unit
            override fun onEndOfSpeech() {
                e2eStatus = "Распознаю..."
                DiLink3DebugLog.log(context, "WIZARD_E2E_SPEECH_END")
            }
            override fun onError(error: Int) {
                e2eListening = false
                e2eStatus = "Ошибка распознавания"
                e2eError = "SpeechRecognizer error=$error"
                DiLink3DebugLog.log(context, "WIZARD_E2E_ASR_ERROR", e2eError)
            }
            override fun onResults(results: Bundle?) {
                e2eListening = false
                val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty().trim()
                e2eHeard = text
                DiLink3DebugLog.log(context, "WIZARD_E2E_ASR_FINAL", "text=$text")
                if (text.isBlank()) {
                    e2eStatus = "Ничего не распознано"
                    e2eError = "empty transcript"
                    return
                }
                e2eStatus = "Жду ответ AI..."
                scope.launch {
                    val result = runCatching { e2eBridge.askAndSpeak(text) }
                        .getOrElse { t -> DiLink3E2EBridge.Result(error = "${t::class.java.simpleName}: ${t.message}") }
                    e2eAnswer = result.answer.orEmpty()
                    e2eError = result.error.orEmpty()
                    e2eStatus = when {
                        result.error != null -> "Ошибка AI/TTS"
                        result.spoken -> "Ответ отправлен в TTS"
                        else -> "Ответ есть, TTS не запущен"
                    }
                    DiLink3DebugLog.log(context, "WIZARD_E2E_RESULT", "spoken=${result.spoken} error=${result.error ?: "none"} answer=${result.answer.orEmpty()}")
                }
            }
            override fun onPartialResults(partialResults: Bundle?) = Unit
            override fun onEvent(eventType: Int, params: Bundle?) = Unit
        })
    }

    LaunchedEffect(step) {
        if (step == 2) {
            SteeringWheelKeyService.clearDiagKey()
            micDetectedCode = null
            micDetectedAt = 0L
            stockAssistantAnswer = null
            diagPrefs.edit().putBoolean("mic_button_logger_armed", true).apply()
            SteeringWheelKeyService.learnMode = false
            DiLink3DebugLog.log(context, "WIZARD_MIC_TEST_ARMED", "passive=true")
            while (step == 2) {
                val at = SteeringWheelKeyService.lastDiagKeyAtMs
                if (at > micDetectedAt && SteeringWheelKeyService.lastDiagKeyCode != null) {
                    micDetectedAt = at
                    micDetectedCode = SteeringWheelKeyService.lastDiagKeyCode
                    DiLink3DebugLog.log(context, "WIZARD_MIC_KEY_DETECTED", "keyCode=$micDetectedCode action=${SteeringWheelKeyService.lastDiagKeyAction}")
                }
                delay(250)
            }
        }
    }

    fun startSystemE2E() {
        if (!micGranted || !systemAsrAvailable || recognizer == null) {
            e2eStatus = "System ASR недоступен"
            e2eError = "micGranted=$micGranted systemAsr=$systemAsrAvailable"
            DiLink3DebugLog.log(context, "WIZARD_E2E_START_BLOCKED", e2eError)
            return
        }
        e2eHeard = ""
        e2eAnswer = ""
        e2eError = ""
        userHeardTts = null
        e2eStatus = "Запускаю микрофон..."
        val lang = voicePrefs.getString("voice_lang", "RU")?.uppercase().orEmpty()
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)
            when (lang) {
                "EN", "EN-US" -> putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-US")
                "LV", "LV-LV" -> putExtra(RecognizerIntent.EXTRA_LANGUAGE, "lv-LV")
                else -> putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ru-RU")
            }
        }
        DiLink3DebugLog.log(context, "WIZARD_E2E_START", "lang=$lang")
        runCatching { recognizer.startListening(intent) }
            .onSuccess { e2eListening = true }
            .onFailure { t ->
                e2eListening = false
                e2eStatus = "Ошибка запуска"
                e2eError = "${t::class.java.simpleName}: ${t.message}"
                DiLink3DebugLog.log(context, "WIZARD_E2E_START_ERROR", e2eError)
            }
    }

    fun runBatch() {
        if (batchRunning) return
        batchRunning = true
        batchSummary = null
        batchDetailVisible = false
        scope.launch {
            val started = SystemClock.elapsedRealtime()
            var ok = 0
            var warn = 0
            var fail = 0
            val short = mutableListOf<String>()
            fun start(name: String) = DiLink3DebugLog.log(context, "BATCH_CHECK_START", name)
            fun pass(name: String, detail: String) {
                ok++; short += "✅ $name"
                DiLink3DebugLog.log(context, "BATCH_CHECK_OK", "$name | $detail")
            }
            fun attention(name: String, detail: String) {
                warn++; short += "⚠️ $name"
                DiLink3DebugLog.log(context, "BATCH_CHECK_WARN", "$name | $detail")
            }
            fun failure(name: String, detail: String) {
                fail++; short += "❌ $name"
                DiLink3DebugLog.log(context, "BATCH_CHECK_FAIL", "$name | $detail")
            }
            DiLink3DebugLog.log(context, "BATCH_START", "package=${context.packageName}")

            start("APP")
            runCatching {
                val pi = context.packageManager.getPackageInfo(context.packageName, 0)
                "package=${context.packageName} versionName=${pi.versionName} versionCode=${pi.longVersionCode}"
            }.onSuccess { pass("APP", it) }.onFailure { failure("APP", it.toString()) }

            start("MIC_PERMISSION")
            if (micGranted) pass("MIC_PERMISSION", "granted") else failure("MIC_PERMISSION", "RECORD_AUDIO denied")

            start("STEERING_SERVICE")
            if (SteeringWheelKeyService.isConnected) pass("STEERING_SERVICE", "runtime connected")
            else attention("STEERING_SERVICE", "runtime NOT connected; DiLink has no Accessibility UI")

            start("INPUT_DEVICES")
            runCatching {
                val devices = InputDevice.getDeviceIds().mapNotNull { InputDevice.getDevice(it) }
                devices.joinToString(" || ") { "id=${it.id} name=${it.name} sources=0x${it.sources.toString(16)} vendor=${it.vendorId} product=${it.productId}" }
            }.onSuccess { detail ->
                if (detail.isBlank()) attention("INPUT_DEVICES", "none visible") else pass("INPUT_DEVICES", detail)
            }.onFailure { failure("INPUT_DEVICES", it.toString()) }

            start("SYSTEM_ASR")
            if (systemAsrAvailable) pass("SYSTEM_ASR", "available") else failure("SYSTEM_ASR", "SpeechRecognizer unavailable")

            start("MIC_PCM")
            runCatching { DiLink3AudioSourceProbe.run() }
                .onSuccess { results ->
                    val readable = results.filter { it.read == "OK" }
                    val detail = results.joinToString(" || ") { it.summary() }
                    if (readable.isNotEmpty()) pass("MIC_PCM", "readable=${readable.size}; $detail") else failure("MIC_PCM", detail)
                }
                .onFailure { failure("MIC_PCM", "${it::class.java.simpleName}: ${it.message}") }

            start("ANDROID_TTS")
            runCatching {
                context.packageManager.queryIntentServices(Intent(TextToSpeech.Engine.INTENT_ACTION_TTS_SERVICE), 0)
                    .mapNotNull { it.serviceInfo?.packageName }.distinct()
            }.onSuccess { engines ->
                if (engines.isEmpty()) attention("ANDROID_TTS", "no Android TTS service")
                else pass("ANDROID_TTS", "engines=${engines.joinToString()}")
            }.onFailure { failure("ANDROID_TTS", it.toString()) }

            start("LOCAL_TTS_MODEL")
            if (ttsReady) pass("LOCAL_TTS_MODEL", "voice=${selectedVoice.id} engine=${selectedVoice.engine}")
            else attention("LOCAL_TTS_MODEL", "voice=${selectedVoice.id} not ready")

            start("GIGAAM")
            if (gigaReady) pass("GIGAAM", "ready") else attention("GIGAAM", "model not ready; System ASR can still be used")

            start("AUDIO")
            runCatching {
                val outputs = if (android.os.Build.VERSION.SDK_INT >= 23) {
                    audioManager.getDevices(AudioManager.GET_DEVICES_OUTPUTS).joinToString { "${it.id}:${it.type}:${it.productName}" }
                } else "sdk<23"
                "mode=${audioManager.mode} music=${audioManager.getStreamVolume(AudioManager.STREAM_MUSIC)}/${audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)} outputs=$outputs"
            }.onSuccess { pass("AUDIO", it) }.onFailure { failure("AUDIO", it.toString()) }

            start("AIHUBMIX")
            runCatching { e2eBridge.loadAihubmixConfig() }
                .onSuccess { cfg ->
                    if (cfg.enabled && cfg.apiKey.isNotBlank()) pass("AIHUBMIX", "enabled model=${cfg.model}")
                    else attention("AIHUBMIX", "not configured/enabled")
                }
                .onFailure { failure("AIHUBMIX", "${it::class.java.simpleName}: ${it.message}") }

            attention("INTERACTIVE_E2E", "not auto-run: requires speech and audible confirmation in wizard")
            val elapsed = SystemClock.elapsedRealtime() - started
            DiLink3DebugLog.log(context, "BATCH_END", "passed=$ok warnings=$warn failed=$fail durationMs=$elapsed")
            batchSummary = BatchSummary(ok, warn, fail, short.joinToString("\n"))
            batchRunning = false
        }
    }

    if (!expanded) {
        Card(modifier = modifier.fillMaxWidth()) {
            Button(
                onClick = {
                    expanded = true
                    DiLink3DebugLog.log(context, "WIZARD_OPENED")
                },
                modifier = Modifier.fillMaxWidth().padding(8.dp),
            ) { Text("ОТКРЫТЬ ДИАГНОСТИКУ") }
        }
        return
    }

    Card(modifier = modifier.fillMaxWidth()) {
        Column(modifier = Modifier.fillMaxWidth()) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text("DiLink3 диагностика · шаг $step/5", style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                Button(onClick = {
                    diagPrefs.edit().putBoolean("mic_button_block_native", false).apply()
                    expanded = false
                    DiLink3DebugLog.log(context, "WIZARD_CLOSED", "step=$step")
                }) { Text("ЗАКРЫТЬ") }
            }

            Column(
                modifier = Modifier.fillMaxWidth().padding(12.dp).verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                when (step) {
                    1 -> {
                        Text("1. Базовая проверка", style = MaterialTheme.typography.titleSmall)
                        StatusLine("Микрофон", micGranted)
                        StatusLine("Android System ASR", systemAsrAvailable)
                        StatusLine("Сервис кнопок руля", SteeringWheelKeyService.isConnected)
                        StatusLine("Локальная TTS-модель", ttsReady)
                        StatusLine("AIHubMix", aiReady == true)
                        if (!SteeringWheelKeyService.isConnected) {
                            Text("Сервис кнопок сейчас не подключён. На DiLink нет меню Accessibility — это зафиксировано и будет проверяться дальше без поиска скрытых настроек.", style = MaterialTheme.typography.bodySmall)
                        }
                        Button(onClick = {
                            DiLink3DebugLog.log(context, "WIZARD_STEP_CONFIRMED", "step=1")
                            step = 2
                        }, modifier = Modifier.fillMaxWidth()) { Text("ПРОДОЛЖИТЬ") }
                    }
                    2 -> {
                        Text("2. Кнопка микрофона на руле", style = MaterialTheme.typography.titleSmall)
                        Text("Нажмите физическую кнопку микрофона один раз. Логирование уже включено автоматически.")
                        Text(if (micDetectedCode != null) "✅ Android увидел кнопку: keyCode=$micDetectedCode" else "⏳ KeyEvent пока не обнаружен")
                        Text("Появился штатный BYD Assistant?")
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(onClick = {
                                stockAssistantAnswer = true
                                DiLink3DebugLog.log(context, "WIZARD_STOCK_ASSISTANT", "appeared=true keyCode=${micDetectedCode ?: -1}")
                            }) { Text("ДА") }
                            Button(onClick = {
                                stockAssistantAnswer = false
                                DiLink3DebugLog.log(context, "WIZARD_STOCK_ASSISTANT", "appeared=false keyCode=${micDetectedCode ?: -1}")
                            }) { Text("НЕТ") }
                        }
                        if (stockAssistantAnswer != null) {
                            Text(if (stockAssistantAnswer == true) "Зафиксировано: штатный ассистент появился." else "Зафиксировано: штатный ассистент не появился.")
                            Button(onClick = {
                                DiLink3DebugLog.log(context, "WIZARD_STEP_CONFIRMED", "step=2 keyCode=${micDetectedCode ?: -1}")
                                step = if (micDetectedCode != null) 3 else 4
                            }, modifier = Modifier.fillMaxWidth()) { Text("ПРОДОЛЖИТЬ") }
                        }
                    }
                    3 -> {
                        Text("3. Проверка блокировки BYD Assistant", style = MaterialTheme.typography.titleSmall)
                        Text("Кнопка найдена как keyCode=${micDetectedCode ?: -1}. Этот тест временно блокирует только эту кнопку и автоматически выключается после ответа.")
                        if (!blockTestRunning && blockWorked == null) {
                            Button(onClick = {
                                val key = micDetectedCode ?: return@Button
                                diagPrefs.edit()
                                    .putInt("mic_button_block_keycode", key)
                                    .putBoolean("mic_button_block_native", true)
                                    .apply()
                                blockTestRunning = true
                                DiLink3DebugLog.log(context, "WIZARD_BLOCK_TEST_ARMED", "keyCode=$key")
                            }, modifier = Modifier.fillMaxWidth()) { Text("НАЧАТЬ ТЕСТ БЛОКИРОВКИ") }
                        } else if (blockTestRunning) {
                            Text("Теперь нажмите кнопку микрофона один раз. Появился BYD Assistant?")
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Button(onClick = {
                                    blockWorked = false
                                    blockTestRunning = false
                                    diagPrefs.edit().putBoolean("mic_button_block_native", false).apply()
                                    DiLink3DebugLog.log(context, "WIZARD_BLOCK_RESULT", "blocked=false stockAssistantAppeared=true")
                                }) { Text("ДА") }
                                Button(onClick = {
                                    blockWorked = true
                                    blockTestRunning = false
                                    diagPrefs.edit().putBoolean("mic_button_block_native", false).apply()
                                    DiLink3DebugLog.log(context, "WIZARD_BLOCK_RESULT", "blocked=true stockAssistantAppeared=false")
                                }) { Text("НЕТ") }
                            }
                        } else {
                            Text(if (blockWorked == true) "✅ Штатный ассистент удалось заблокировать." else "⚠️ Штатный ассистент всё равно появился.")
                            Button(onClick = { step = 4 }, modifier = Modifier.fillMaxWidth()) { Text("ПРОДОЛЖИТЬ") }
                        }
                    }
                    4 -> {
                        Text("4. System ASR → AI → TTS", style = MaterialTheme.typography.titleSmall)
                        if (micDetectedCode == null) {
                            Text("Кнопка не пришла как Android KeyEvent. Это уже зафиксировано; данный голосовой тест независим от кнопки.", style = MaterialTheme.typography.bodySmall)
                        }
                        Button(onClick = {
                            if (e2eListening) {
                                runCatching { recognizer?.cancel() }
                                e2eListening = false
                                e2eStatus = "Остановлено"
                            } else startSystemE2E()
                        }, modifier = Modifier.fillMaxWidth()) {
                            Text(if (e2eListening) "ОСТАНОВИТЬ" else "СКАЗАТЬ ФРАЗУ BYDMATE")
                        }
                        Text("Статус: $e2eStatus")
                        if (e2eHeard.isNotBlank()) Text("Вы сказали: $e2eHeard")
                        if (e2eAnswer.isNotBlank()) Text("AI: $e2eAnswer")
                        if (e2eError.isNotBlank()) Text("Ошибка: $e2eError")
                        if (e2eAnswer.isNotBlank()) {
                            Text("Вы услышали голосовой ответ BYDMate?")
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Button(onClick = {
                                    userHeardTts = true
                                    DiLink3DebugLog.log(context, "WIZARD_TTS_USER_CONFIRM", "audible=true")
                                }) { Text("ДА") }
                                Button(onClick = {
                                    userHeardTts = false
                                    DiLink3DebugLog.log(context, "WIZARD_TTS_USER_CONFIRM", "audible=false")
                                }) { Text("НЕТ") }
                            }
                        }
                        if (userHeardTts != null || e2eError.isNotBlank()) {
                            Button(onClick = { step = 5 }, modifier = Modifier.fillMaxWidth()) { Text("К ИТОГУ") }
                        }
                    }
                    else -> {
                        Text("5. Итог", style = MaterialTheme.typography.titleSmall)
                        Text("Кнопка Android KeyEvent: ${if (micDetectedCode != null) "ДА, keyCode=$micDetectedCode" else "НЕТ"}")
                        Text("Штатный BYD Assistant при первом тесте: ${when (stockAssistantAnswer) { true -> "ДА"; false -> "НЕТ"; null -> "не подтверждено" }}")
                        if (micDetectedCode != null) Text("Блокировка штатного ассистента: ${when (blockWorked) { true -> "СРАБОТАЛА"; false -> "НЕ СРАБОТАЛА"; null -> "не проверялась" }}")
                        Text("System ASR: ${if (systemAsrAvailable) "доступен" else "недоступен"}")
                        Text("TTS слышен пользователю: ${when (userHeardTts) { true -> "ДА"; false -> "НЕТ"; null -> "не подтверждено" }}")
                        Button(onClick = {
                            DiLink3DebugLog.log(context, "WIZARD_FINISH", "keyCode=${micDetectedCode ?: -1} stock=$stockAssistantAnswer block=$blockWorked ttsAudible=$userHeardTts")
                            DiLink3DebugLog.shareToTelegram(context)
                        }, modifier = Modifier.fillMaxWidth()) { Text("ОТПРАВИТЬ ЛОГ") }
                        Button(onClick = {
                            step = 1
                            micDetectedCode = null
                            stockAssistantAnswer = null
                            blockWorked = null
                            userHeardTts = null
                            DiLink3DebugLog.log(context, "WIZARD_RESTART")
                        }, modifier = Modifier.fillMaxWidth()) { Text("НАЧАТЬ ВИЗАРД ЗАНОВО") }
                    }
                }

                if (step >= 2) {
                    Text("Независимая пакетная проверка", style = MaterialTheme.typography.titleSmall)
                    Text("Безопасная проверка системы. Не меняет кнопку руля и не включает блокировку.", style = MaterialTheme.typography.bodySmall)
                    Button(onClick = { runBatch() }, enabled = !batchRunning, modifier = Modifier.fillMaxWidth()) {
                        Text(if (batchRunning) "ПРОВЕРЯЮ..." else "ЗАПУСТИТЬ ПАКЕТНУЮ ДИАГНОСТИКУ")
                    }
                    batchSummary?.let { summary ->
                        Text("✅ ${summary.ok}   ⚠️ ${summary.warn}   ❌ ${summary.fail}")
                        Button(onClick = { batchDetailVisible = !batchDetailVisible }, modifier = Modifier.fillMaxWidth()) {
                            Text(if (batchDetailVisible) "СКРЫТЬ КРАТКИЙ РЕЗУЛЬТАТ" else "ПОКАЗАТЬ КРАТКИЙ РЕЗУЛЬТАТ")
                        }
                        if (batchDetailVisible) Text(summary.detail, style = MaterialTheme.typography.bodySmall)
                        Button(onClick = {
                            DiLink3DebugLog.log(context, "BATCH_LOG_SHARE")
                            DiLink3DebugLog.shareToTelegram(context)
                        }, modifier = Modifier.fillMaxWidth()) { Text("ОТПРАВИТЬ ЛОГ") }
                    }
                }
            }
        }
    }
}

@Composable
private fun StatusLine(label: String, ok: Boolean) {
    Text("${if (ok) "✅" else "⚠️"} $label: ${if (ok) "OK" else "требует внимания"}")
}
'''

p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
p.write_text(panel)
print('Replaced noisy DiLink3 panel with guided wizard + batch diagnostics')

# Expose the last raw key observed by the already-injected passive logger so the wizard can
# advance automatically without showing technical trace rows.
svc = Path('app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt')
s = svc.read_text()
needle = '''        if (micLoggerArmed) {\n            val device = runCatching { event.device }.getOrNull()'''
replacement = '''        if (micLoggerArmed) {\n            lastDiagKeyCode = event.keyCode\n            lastDiagKeyAction = event.action\n            lastDiagKeyAtMs = System.currentTimeMillis()\n            val device = runCatching { event.device }.getOrNull()'''
if needle not in s:
    raise SystemExit('wizard key observation insertion point not found')
s = s.replace(needle, replacement, 1)

needle = '''        /** Live service instance for on-demand window reads'''
replacement = '''        @Volatile\n        var lastDiagKeyCode: Int? = null\n            private set\n\n        @Volatile\n        var lastDiagKeyAction: Int = -1\n            private set\n\n        @Volatile\n        var lastDiagKeyAtMs: Long = 0L\n            private set\n\n        fun clearDiagKey() {\n            lastDiagKeyCode = null\n            lastDiagKeyAction = -1\n            lastDiagKeyAtMs = 0L\n        }\n\n        /** Live service instance for on-demand window reads'''
if needle not in s:
    raise SystemExit('wizard companion insertion point not found')
s = s.replace(needle, replacement, 1)
svc.write_text(s)
print('Added wizard-visible passive key observation state')
