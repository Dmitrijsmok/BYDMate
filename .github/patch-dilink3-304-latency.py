from pathlib import Path

# Final DiLink3 diagnostic refinements based on real vehicle logs:
# - the steering microphone arrives directly in MainActivity as KEYCODE_AUTO_MEDIA_VOICE (304)
# - Accessibility service may be disconnected and is not required for foreground interception
# - wizard must detect Activity KeyEvents, not only SteeringWheelKeyService
# - blocking test must consume 304 in MainActivity
# - warm GigaAM/TTS early and trace user-perceived latency through first audible TTS audio

# ---------------------------------------------------------------------------
# MainActivity: persist foreground key observations and optionally consume keyCode 304.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/MainActivity.kt')
s = p.read_text()
needle = '''    override fun dispatchKeyEvent(event: KeyEvent): Boolean {\n        if (micDiagArmed()) {\n            DiLink3DebugLog.log(applicationContext, "ACTIVITY_DISPATCH_KEY", describeDiagKey(event))\n        }\n        return super.dispatchKeyEvent(event)\n    }'''
replacement = '''    override fun dispatchKeyEvent(event: KeyEvent): Boolean {\n        val diagPrefs = applicationContext.getSharedPreferences("dilink3_diag", Context.MODE_PRIVATE)\n        if (micDiagArmed()) {\n            DiLink3DebugLog.log(applicationContext, "ACTIVITY_DISPATCH_KEY", describeDiagKey(event))\n            diagPrefs.edit()\n                .putInt("last_activity_keycode", event.keyCode)\n                .putInt("last_activity_key_action", event.action)\n                .putInt("last_activity_scancode", event.scanCode)\n                .putInt("last_activity_device_id", event.deviceId)\n                .putLong("last_activity_key_at_ms", System.currentTimeMillis())\n                .apply()\n        }\n        val interceptEnabled = diagPrefs.getBoolean("activity_mic_intercept_enabled", false)\n        val interceptKey = diagPrefs.getInt("activity_mic_intercept_keycode", 304)\n        if (interceptEnabled && event.keyCode == interceptKey) {\n            DiLink3DebugLog.log(\n                applicationContext,\n                "MIC_304_INTERCEPTED",\n                "action=${event.action} keyCode=${event.keyCode} keyName=${KeyEvent.keyCodeToString(event.keyCode)} scanCode=${event.scanCode} deviceId=${event.deviceId} source=${event.source}"\n            )\n            return true\n        }\n        return super.dispatchKeyEvent(event)\n    }'''
if needle not in s:
    raise SystemExit('MainActivity dispatchKeyEvent insertion point not found')
s = s.replace(needle, replacement, 1)
p.write_text(s)
print('Added MainActivity keyCode 304 observation + reversible consume path')

# ---------------------------------------------------------------------------
# DiLink3E2EBridge: expose physical TTS state for precise latency polling.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3E2EBridge.kt')
s = p.read_text()
needle = '''    fun warmUpTts() {\n        val started = SystemClock.elapsedRealtime()'''
replacement = '''    fun ttsAudible(): Boolean = runCatching { deps.ttsEngine().audible() }.getOrDefault(false)\n\n    fun ttsSpeaking(): Boolean = runCatching { deps.ttsEngine().speaking.value }.getOrDefault(false)\n\n    fun warmUpTts() {\n        val started = SystemClock.elapsedRealtime()'''
if needle not in s:
    raise SystemExit('DiLink3E2EBridge warmUp insertion point not found')
s = s.replace(needle, replacement, 1)
p.write_text(s)
print('Exposed TTS audible/speaking state for latency trace')

# ---------------------------------------------------------------------------
# Wizard: Activity-key detection, foreground block test, warmup, latency trace.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()

needle = '''    var aiReady by remember { mutableStateOf<Boolean?>(null) }\n'''
replacement = '''    var aiReady by remember { mutableStateOf<Boolean?>(null) }\n    var warmupStatus by remember { mutableStateOf("запускается...") }\n    var e2eCycleStartMs by remember { mutableStateOf(0L) }\n    var e2eSpeechEndMs by remember { mutableStateOf(0L) }\n    var e2eAsrFinalMs by remember { mutableStateOf(0L) }\n    var ttsFirstAudioMs by remember { mutableStateOf<Long?>(null) }\n'''
if needle not in s:
    raise SystemExit('wizard state insertion point not found')
s = s.replace(needle, replacement, 1)

needle = '''            diagPrefs.edit().putBoolean("mic_button_block_native", false).apply()\n            blockTestRunning = false'''
replacement = '''            diagPrefs.edit()\n                .putBoolean("mic_button_block_native", false)\n                .putBoolean("activity_mic_intercept_enabled", false)\n                .apply()\n            blockTestRunning = false'''
if needle not in s:
    raise SystemExit('wizard dispose cleanup insertion point not found')
s = s.replace(needle, replacement, 1)

needle = '''    LaunchedEffect(Unit) {\n        DiLink3DebugLog.log(context, "WIZARD_OPEN_STATE", "mic=$micGranted systemAsr=$systemAsrAvailable steeringConnected=${SteeringWheelKeyService.isConnected} gigaReady=$gigaReady ttsReady=$ttsReady")\n        aiReady = runCatching { e2eBridge.loadAihubmixConfig() }\n            .getOrNull()?.let { it.enabled && it.apiKey.isNotBlank() }\n    }'''
replacement = '''    LaunchedEffect(Unit) {\n        val warmStart = SystemClock.elapsedRealtime()\n        DiLink3DebugLog.log(context, "WIZARD_WARMUP_START", "systemAsr=$systemAsrAvailable gigaReady=$gigaReady ttsReady=$ttsReady")\n        warmupStatus = "прогрев..."\n        runCatching { continuousAsr.warmUp() }\n            .onFailure { DiLink3DebugLog.log(context, "WIZARD_WARMUP_GIGAAM_ERROR", "${it::class.java.simpleName}: ${it.message}") }\n        e2eBridge.warmUpTts()\n        warmupStatus = "готов (${SystemClock.elapsedRealtime() - warmStart} мс)"\n        DiLink3DebugLog.log(context, "WIZARD_WARMUP_DONE", "dt=${SystemClock.elapsedRealtime() - warmStart}ms")\n        DiLink3DebugLog.log(context, "WIZARD_OPEN_STATE", "mic=$micGranted systemAsr=$systemAsrAvailable steeringConnected=${SteeringWheelKeyService.isConnected} gigaReady=$gigaReady ttsReady=$ttsReady")\n        aiReady = runCatching { e2eBridge.loadAihubmixConfig() }\n            .getOrNull()?.let { it.enabled && it.apiKey.isNotBlank() }\n    }'''
if needle not in s:
    raise SystemExit('wizard warmup insertion point not found')
s = s.replace(needle, replacement, 1)

needle = '''            override fun onReadyForSpeech(params: Bundle?) {\n                e2eListening = true\n                e2eStatus = "Говорите"\n                DiLink3DebugLog.log(context, "WIZARD_E2E_ASR_READY")\n            }'''
replacement = '''            override fun onReadyForSpeech(params: Bundle?) {\n                e2eListening = true\n                e2eStatus = "Говорите"\n                DiLink3DebugLog.log(context, "WIZARD_E2E_ASR_READY", "fromStart=${SystemClock.elapsedRealtime() - e2eCycleStartMs}ms")\n            }'''
s = s.replace(needle, replacement, 1)

needle = '''            override fun onEndOfSpeech() {\n                e2eStatus = "Распознаю..."\n                DiLink3DebugLog.log(context, "WIZARD_E2E_SPEECH_END")\n            }'''
replacement = '''            override fun onEndOfSpeech() {\n                e2eSpeechEndMs = SystemClock.elapsedRealtime()\n                e2eStatus = "Распознаю..."\n                DiLink3DebugLog.log(context, "WIZARD_E2E_SPEECH_END", "fromStart=${e2eSpeechEndMs - e2eCycleStartMs}ms")\n            }'''
s = s.replace(needle, replacement, 1)

needle = '''                e2eHeard = text\n                DiLink3DebugLog.log(context, "WIZARD_E2E_ASR_FINAL", "text=$text")'''
replacement = '''                e2eHeard = text\n                e2eAsrFinalMs = SystemClock.elapsedRealtime()\n                DiLink3DebugLog.log(context, "WIZARD_E2E_ASR_FINAL", "text=$text fromStart=${e2eAsrFinalMs - e2eCycleStartMs}ms fromSpeechEnd=${if (e2eSpeechEndMs > 0) e2eAsrFinalMs - e2eSpeechEndMs else -1}ms")'''
if needle not in s:
    raise SystemExit('wizard ASR final timing insertion point not found')
s = s.replace(needle, replacement, 1)

needle = '''                    DiLink3DebugLog.log(context, "WIZARD_E2E_RESULT", "spoken=${result.spoken} error=${result.error ?: "none"} answer=${result.answer.orEmpty()}")\n                }'''
replacement = '''                    val resultAt = SystemClock.elapsedRealtime()\n                    DiLink3DebugLog.log(context, "WIZARD_E2E_RESULT", "spoken=${result.spoken} error=${result.error ?: "none"} fromAsrFinal=${if (e2eAsrFinalMs > 0) resultAt - e2eAsrFinalMs else -1}ms fromStart=${if (e2eCycleStartMs > 0) resultAt - e2eCycleStartMs else -1}ms answer=${result.answer.orEmpty()}")\n                    if (result.spoken) {\n                        val pollStarted = SystemClock.elapsedRealtime()\n                        ttsFirstAudioMs = null\n                        scope.launch {\n                            var firstAudioLogged = false\n                            val timeoutAt = pollStarted + 15_000L\n                            while (SystemClock.elapsedRealtime() < timeoutAt) {\n                                if (e2eBridge.ttsAudible()) {\n                                    val now = SystemClock.elapsedRealtime()\n                                    ttsFirstAudioMs = now\n                                    DiLink3DebugLog.log(\n                                        context,\n                                        "E2E_TTS_FIRST_AUDIO",\n                                        "fromResult=${now - resultAt}ms fromAsrFinal=${if (e2eAsrFinalMs > 0) now - e2eAsrFinalMs else -1}ms fromSpeechEnd=${if (e2eSpeechEndMs > 0) now - e2eSpeechEndMs else -1}ms fromStart=${if (e2eCycleStartMs > 0) now - e2eCycleStartMs else -1}ms"\n                                    )\n                                    firstAudioLogged = true\n                                    break\n                                }\n                                delay(20)\n                            }\n                            if (!firstAudioLogged) {\n                                DiLink3DebugLog.log(context, "E2E_TTS_FIRST_AUDIO_TIMEOUT", "waited=${SystemClock.elapsedRealtime() - pollStarted}ms speaking=${e2eBridge.ttsSpeaking()} audible=${e2eBridge.ttsAudible()}")\n                            } else {\n                                val doneTimeout = SystemClock.elapsedRealtime() + 30_000L\n                                while (SystemClock.elapsedRealtime() < doneTimeout && (e2eBridge.ttsAudible() || e2eBridge.ttsSpeaking())) delay(25)\n                                DiLink3DebugLog.log(context, "E2E_TTS_DONE", "fromFirstAudio=${ttsFirstAudioMs?.let { SystemClock.elapsedRealtime() - it } ?: -1}ms totalFromStart=${if (e2eCycleStartMs > 0) SystemClock.elapsedRealtime() - e2eCycleStartMs else -1}ms")\n                            }\n                        }\n                    }\n                }'''
if needle not in s:
    raise SystemExit('wizard TTS timing insertion point not found')
s = s.replace(needle, replacement, 1)

needle = '''            while (step == 2) {\n                val at = SteeringWheelKeyService.lastDiagKeyAtMs\n                if (at > micDetectedAt && SteeringWheelKeyService.lastDiagKeyCode != null) {\n                    micDetectedAt = at\n                    micDetectedCode = SteeringWheelKeyService.lastDiagKeyCode\n                    DiLink3DebugLog.log(context, "WIZARD_MIC_KEY_DETECTED", "keyCode=$micDetectedCode action=${SteeringWheelKeyService.lastDiagKeyAction}")\n                }\n                delay(250)\n            }'''
replacement = '''            while (step == 2) {\n                val serviceAt = SteeringWheelKeyService.lastDiagKeyAtMs\n                val activityAt = diagPrefs.getLong("last_activity_key_at_ms", 0L)\n                if (activityAt > micDetectedAt) {\n                    micDetectedAt = activityAt\n                    micDetectedCode = diagPrefs.getInt("last_activity_keycode", -1).takeIf { it >= 0 }\n                    DiLink3DebugLog.log(context, "WIZARD_MIC_KEY_DETECTED", "source=Activity keyCode=$micDetectedCode action=${diagPrefs.getInt("last_activity_key_action", -1)} scanCode=${diagPrefs.getInt("last_activity_scancode", -1)} deviceId=${diagPrefs.getInt("last_activity_device_id", -1)}")\n                } else if (serviceAt > micDetectedAt && SteeringWheelKeyService.lastDiagKeyCode != null) {\n                    micDetectedAt = serviceAt\n                    micDetectedCode = SteeringWheelKeyService.lastDiagKeyCode\n                    DiLink3DebugLog.log(context, "WIZARD_MIC_KEY_DETECTED", "source=Accessibility keyCode=$micDetectedCode action=${SteeringWheelKeyService.lastDiagKeyAction}")\n                }\n                delay(100)\n            }'''
if needle not in s:
    raise SystemExit('wizard key polling insertion point not found')
s = s.replace(needle, replacement, 1)

needle = '''        userHeardTts = null\n        e2eStatus = "Запускаю микрофон..."'''
replacement = '''        userHeardTts = null\n        ttsFirstAudioMs = null\n        e2eCycleStartMs = SystemClock.elapsedRealtime()\n        e2eSpeechEndMs = 0L\n        e2eAsrFinalMs = 0L\n        e2eStatus = "Запускаю микрофон..."'''
if needle not in s:
    raise SystemExit('wizard cycle start insertion point not found')
s = s.replace(needle, replacement, 1)

needle = '''                        StatusLine("Сервис кнопок руля", SteeringWheelKeyService.isConnected)\n                        StatusLine("Локальная TTS-модель", ttsReady)'''
replacement = '''                        Text("ℹ️ Прогрев: $warmupStatus")\n                        Text("ℹ️ Кнопка руля: Activity KeyEvent + сервис (если доступен)")\n                        StatusLine("Локальная TTS-модель", ttsReady)'''
if needle not in s:
    raise SystemExit('wizard base status insertion point not found')
s = s.replace(needle, replacement, 1)

needle = '''                        if (!SteeringWheelKeyService.isConnected) {\n                            Text("Сервис кнопок сейчас не подключён. На DiLink нет меню Accessibility — это зафиксировано и будет проверяться дальше без поиска скрытых настроек.", style = MaterialTheme.typography.bodySmall)\n                        }'''
replacement = '''                        if (!SteeringWheelKeyService.isConnected) {\n                            Text("Accessibility-сервис не подключён, но это не блокирует тест: на этой машине кнопка уже приходит напрямую в Activity.", style = MaterialTheme.typography.bodySmall)\n                        }'''
s = s.replace(needle, replacement, 1)

needle = '''                                diagPrefs.edit()\n                                    .putInt("mic_button_block_keycode", key)\n                                    .putBoolean("mic_button_block_native", true)\n                                    .apply()'''
replacement = '''                                diagPrefs.edit()\n                                    .putInt("mic_button_block_keycode", key)\n                                    .putBoolean("mic_button_block_native", true)\n                                    .putInt("activity_mic_intercept_keycode", key)\n                                    .putBoolean("activity_mic_intercept_enabled", true)\n                                    .apply()'''
if needle not in s:
    raise SystemExit('wizard block arm insertion point not found')
s = s.replace(needle, replacement, 1)

s = s.replace('diagPrefs.edit().putBoolean("mic_button_block_native", false).apply()', 'diagPrefs.edit().putBoolean("mic_button_block_native", false).putBoolean("activity_mic_intercept_enabled", false).apply()')
s = s.replace('Text("Кнопка найдена как keyCode=${micDetectedCode ?: -1}. Этот тест временно блокирует только эту кнопку и автоматически выключается после ответа.")', 'Text("Кнопка найдена как keyCode=${micDetectedCode ?: -1}. Тест временно consumes DOWN/UP прямо в Activity и параллельно включает сервисный блок, если Accessibility когда-либо подключится.")')
s = s.replace('Text("Сервис кнопок сейчас не подключён. На DiLink нет меню Accessibility — это зафиксировано и будет проверяться дальше без поиска скрытых настроек.", style = MaterialTheme.typography.bodySmall)', 'Text("Accessibility-сервис не подключён; для foreground-теста это не проблема, потому что Activity уже видит keyCode 304.", style = MaterialTheme.typography.bodySmall)')

needle = '''                        if (e2eAnswer.isNotBlank()) Text("AI: $e2eAnswer")\n                        if (e2eError.isNotBlank()) Text("Ошибка: $e2eError")'''
replacement = '''                        if (e2eAnswer.isNotBlank()) Text("AI: $e2eAnswer")\n                        ttsFirstAudioMs?.let { first ->\n                            Text("Первый слышимый TTS: ${if (e2eSpeechEndMs > 0) first - e2eSpeechEndMs else -1} мс после конца речи")\n                        }\n                        if (e2eError.isNotBlank()) Text("Ошибка: $e2eError")'''
if needle not in s:
    raise SystemExit('wizard TTS timing UI insertion point not found')
s = s.replace(needle, replacement, 1)

p.write_text(s)
print('Refined wizard: Activity key detection, 304 block test, warmup and TTS first-audio timing')
