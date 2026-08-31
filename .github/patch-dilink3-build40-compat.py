from pathlib import Path

# Extracted from the successful build #40 workflow so build #41 can layer deeper diagnostics
# on the exact same known-good vehicle behavior.

# 1) Record known steering voice key even when passive logger flag is lost.
p = Path('app/src/main/kotlin/com/bydmate/app/MainActivity.kt')
s = p.read_text()
old = '''        if (micDiagArmed()) {\n            DiLink3DebugLog.log(applicationContext, "ACTIVITY_DISPATCH_KEY", describeDiagKey(event))\n            diagPrefs.edit()\n                .putInt("last_activity_keycode", event.keyCode)\n                .putInt("last_activity_key_action", event.action)\n                .putInt("last_activity_scancode", event.scanCode)\n                .putInt("last_activity_device_id", event.deviceId)\n                .putLong("last_activity_key_at_ms", System.currentTimeMillis())\n                .apply()\n        }'''
new = '''        if (micDiagArmed()) {\n            DiLink3DebugLog.log(applicationContext, "ACTIVITY_DISPATCH_KEY", describeDiagKey(event))\n        }\n        if (event.keyCode == 304) {\n            diagPrefs.edit()\n                .putInt("last_activity_keycode", event.keyCode)\n                .putInt("last_activity_key_action", event.action)\n                .putInt("last_activity_scancode", event.scanCode)\n                .putInt("last_activity_device_id", event.deviceId)\n                .putLong("last_activity_key_at_ms", System.currentTimeMillis())\n                .apply()\n            DiLink3DebugLog.log(applicationContext, "ACTIVITY_MIC_304_SEEN", "action=${event.action} scanCode=${event.scanCode} deviceId=${event.deviceId} source=${event.source}")\n        }'''
if old not in s:
    raise SystemExit('build40 MainActivity observation anchor not found')
s = s.replace(old, new, 1)
p.write_text(s)

# 2) Wizard: no synchronous GigaAM/TTS warm-up.
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()
old = '''    LaunchedEffect(Unit) {\n        val warmStart = SystemClock.elapsedRealtime()\n        DiLink3DebugLog.log(context, "WIZARD_WARMUP_START", "systemAsr=$systemAsrAvailable gigaReady=$gigaReady ttsReady=$ttsReady")\n        warmupStatus = "прогрев..."\n        runCatching { continuousAsr.warmUp() }\n            .onFailure { DiLink3DebugLog.log(context, "WIZARD_WARMUP_GIGAAM_ERROR", "${it::class.java.simpleName}: ${it.message}") }\n        e2eBridge.warmUpTts()\n        warmupStatus = "готов (${SystemClock.elapsedRealtime() - warmStart} мс)"\n        DiLink3DebugLog.log(context, "WIZARD_WARMUP_DONE", "dt=${SystemClock.elapsedRealtime() - warmStart}ms")\n        DiLink3DebugLog.log(context, "WIZARD_OPEN_STATE", "mic=$micGranted systemAsr=$systemAsrAvailable steeringConnected=${SteeringWheelKeyService.isConnected} gigaReady=$gigaReady ttsReady=$ttsReady")\n        aiReady = runCatching { e2eBridge.loadAihubmixConfig() }\n            .getOrNull()?.let { it.enabled && it.apiKey.isNotBlank() }\n    }'''
new = '''    LaunchedEffect(Unit) {\n        warmupStatus = "отключён: System ASR запускается по запросу"\n        DiLink3DebugLog.log(context, "WIZARD_WARMUP_SKIPPED", "reason=build39 stalls and duplicate TTS; systemAsr=$systemAsrAvailable gigaReady=$gigaReady ttsReady=$ttsReady")\n        DiLink3DebugLog.log(context, "WIZARD_OPEN_STATE", "mic=$micGranted systemAsr=$systemAsrAvailable steeringConnected=${SteeringWheelKeyService.isConnected} gigaReady=$gigaReady ttsReady=$ttsReady")\n        aiReady = runCatching { e2eBridge.loadAihubmixConfig() }\n            .getOrNull()?.let { it.enabled && it.apiKey.isNotBlank() }\n    }'''
if old not in s:
    raise SystemExit('build40 wizard warmup anchor not found')
s = s.replace(old, new, 1)

old = '''            SteeringWheelKeyService.clearDiagKey()\n            micDetectedCode = null\n            micDetectedAt = 0L'''
new = '''            SteeringWheelKeyService.clearDiagKey()\n            micDetectedCode = 304\n            micDetectedAt = 0L\n            diagPrefs.edit().putLong("last_activity_key_at_ms", 0L).apply()'''
if old not in s:
    raise SystemExit('build40 wizard step2 init anchor not found')
s = s.replace(old, new, 1)

old = '''                        Text(if (micDetectedCode != null) "✅ Android увидел кнопку: keyCode=$micDetectedCode" else "⏳ KeyEvent пока не обнаружен")'''
new = '''                        Text(if (micDetectedAt > 0L) "✅ Activity увидела кнопку: keyCode=${micDetectedCode ?: 304}" else "ℹ️ Из предыдущих логов известен keyCode=304. Текущий press пока не пришёл в Activity.")'''
if old not in s:
    raise SystemExit('build40 wizard key status anchor not found')
s = s.replace(old, new, 1)

s = s.replace(
    '''DiLink3DebugLog.log(context, "WIZARD_STOCK_ASSISTANT", "appeared=true keyCode=${micDetectedCode ?: -1}")''',
    '''DiLink3DebugLog.log(context, "WIZARD_STOCK_ASSISTANT", "appeared=true keyCode=${micDetectedCode ?: 304} activityObserved=${micDetectedAt > 0L}")''',
    1,
)
s = s.replace(
    '''DiLink3DebugLog.log(context, "WIZARD_STOCK_ASSISTANT", "appeared=false keyCode=${micDetectedCode ?: -1}")''',
    '''DiLink3DebugLog.log(context, "WIZARD_STOCK_ASSISTANT", "appeared=false keyCode=${micDetectedCode ?: 304} activityObserved=${micDetectedAt > 0L}")''',
    1,
)

old = '''                                    .putInt("activity_mic_intercept_keycode", key)\n                                    .putBoolean("activity_mic_intercept_enabled", true)\n                                    .apply()'''
new = '''                                    .putInt("activity_mic_intercept_keycode", key)\n                                    .putBoolean("activity_mic_intercept_enabled", true)\n                                    .putLong("last_activity_key_at_ms", 0L)\n                                    .apply()'''
if old not in s:
    raise SystemExit('build40 block arm anchor not found')
s = s.replace(old, new, 1)

s = s.replace(
    '''DiLink3DebugLog.log(context, "WIZARD_BLOCK_RESULT", "blocked=false stockAssistantAppeared=true")''',
    '''DiLink3DebugLog.log(context, "WIZARD_BLOCK_RESULT", "blocked=false stockAssistantAppeared=true activityEventSeen=${diagPrefs.getLong("last_activity_key_at_ms", 0L) > 0L}")''',
    1,
)
s = s.replace(
    '''DiLink3DebugLog.log(context, "WIZARD_BLOCK_RESULT", "blocked=true stockAssistantAppeared=false")''',
    '''DiLink3DebugLog.log(context, "WIZARD_BLOCK_RESULT", "blocked=true stockAssistantAppeared=false activityEventSeen=${diagPrefs.getLong("last_activity_key_at_ms", 0L) > 0L}")''',
    1,
)

old = '''        e2eStatus = "Запускаю микрофон..."\n        val lang = voicePrefs.getString("voice_lang", "RU")?.uppercase().orEmpty()'''
new = '''        e2eStatus = "Запускаю микрофон..."\n        val audioModeBefore = audioManager.mode\n        if (audioModeBefore == AudioManager.MODE_IN_COMMUNICATION) {\n            runCatching { audioManager.mode = AudioManager.MODE_NORMAL }\n            DiLink3DebugLog.log(context, "AUDIO_MODE_RESET_BEFORE_ASR", "from=$audioModeBefore to=${audioManager.mode}")\n        } else {\n            DiLink3DebugLog.log(context, "AUDIO_MODE_BEFORE_ASR", "mode=$audioModeBefore")\n        }\n        val lang = voicePrefs.getString("voice_lang", "RU")?.uppercase().orEmpty()'''
if old not in s:
    raise SystemExit('build40 audio mode start anchor not found')
s = s.replace(old, new, 1)

old = '''                DiLink3DebugLog.log(context, "WIZARD_E2E_ASR_ERROR", e2eError)'''
new = '''                DiLink3DebugLog.log(context, "WIZARD_E2E_ASR_ERROR", "$e2eError audioMode=${audioManager.mode} hint=${if (error == 7) "check BYD Assistant / mic contention" else "none"}")'''
if old not in s:
    raise SystemExit('build40 ASR error anchor not found')
s = s.replace(old, new, 1)

old = '''                e2eHeard = text\n                e2eAsrFinalMs = SystemClock.elapsedRealtime()'''
new = '''                e2eHeard = text\n                DiLink3DebugLog.log(context, "AUDIO_MODE_AT_ASR_FINAL", "mode=${audioManager.mode}")\n                e2eAsrFinalMs = SystemClock.elapsedRealtime()'''
if old not in s:
    raise SystemExit('build40 ASR final audio anchor not found')
s = s.replace(old, new, 1)
p.write_text(s)

# 3) Log actual TTS router selected for every E2E answer.
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3E2EBridge.kt')
s = p.read_text()
old = '''                val speakStart = SystemClock.elapsedRealtime()\n                val spoken = runCatching { deps.ttsEngine().speakOffline(result.text) }'''
new = '''                val speakStart = SystemClock.elapsedRealtime()\n                val tts = deps.ttsEngine()\n                DiLink3DebugLog.log(appContext, "E2E_TTS_REQUEST", "source=wizard engineClass=${tts::class.java.simpleName} ready=${tts.isReady()} chars=${result.text.length} text=${result.text}")\n                val spoken = runCatching { tts.speakOffline(result.text) }'''
if old not in s:
    raise SystemExit('build40 TTS request anchor not found')
s = s.replace(old, new, 1)
s = s.replace(
    '''"accepted=$spoken call=${SystemClock.elapsedRealtime() - speakStart}ms ai=${aiMs}ms speaking=${deps.ttsEngine().speaking.value} audible=${deps.ttsEngine().audible()}",''',
    '''"accepted=$spoken call=${SystemClock.elapsedRealtime() - speakStart}ms ai=${aiMs}ms engineClass=${tts::class.java.simpleName} speaking=${tts.speaking.value} audible=${tts.audible()}",''',
    1,
)
p.write_text(s)

print('Applied reusable build40 vehicle fixes')
