#!/usr/bin/env python3
from pathlib import Path

# Build65: production-readiness wizard on top of the proven Build64 pipeline.

# 1) E2E bridge: read production config and provide isolated AI/TTS tests.
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3E2EBridge.kt')
s = p.read_text()
anchor = '    data class AihubmixConfig(val apiKey: String, val model: String, val enabled: Boolean)\n'
if anchor not in s:
    raise SystemExit('Build65: AihubmixConfig anchor not found')
if 'data class ProductionSnapshot(' not in s:
    s = s.replace(anchor, anchor + '''\n    data class ProductionSnapshot(\n        val enabled: Boolean,\n        val provider: String,\n        val baseUrl: String,\n        val model: String,\n        val credentialsPresent: Boolean,\n    )\n''', 1)
anchor = '    fun warmUpTts() {\n'
if anchor not in s:
    raise SystemExit('Build65: warmUpTts anchor not found')
if 'suspend fun productionSnapshot()' not in s:
    s = s.replace(anchor, '''    suspend fun productionSnapshot(): ProductionSnapshot {\n        val repo = deps.settingsRepository()\n        return ProductionSnapshot(\n            enabled = repo.getString(SettingsRepository.KEY_AGENT_ENABLED, "false").toBoolean(),\n            provider = repo.getString(SettingsRepository.KEY_AGENT_PRIMARY_CONN, ""),\n            baseUrl = repo.getString(SettingsRepository.KEY_CUSTOM_BASE_URL, ""),\n            model = repo.getString(SettingsRepository.KEY_CUSTOM_MODEL, ""),\n            credentialsPresent = repo.getString(SettingsRepository.KEY_CUSTOM_API_KEY, "").isNotBlank(),\n        )\n    }\n\n    suspend fun askOnly(prompt: String): Result {\n        DiLink3DebugLog.log(appContext, "BUILD65_AI_ONLY_START", "chars=${prompt.length}")\n        return when (val result = deps.agentOrchestrator().ask(prompt)) {\n            is AgentResult.Answer -> {\n                DiLink3DebugLog.log(appContext, "BUILD65_AI_ONLY_OK", "chars=${result.text.length}")\n                Result(answer = result.text)\n            }\n            is AgentResult.Error -> {\n                DiLink3DebugLog.log(appContext, "BUILD65_AI_ONLY_ERROR", "message=${result.message}")\n                Result(error = result.message)\n            }\n            AgentResult.Disabled -> Result(error = "Agent disabled")\n        }\n    }\n\n    suspend fun testTtsOnly(): Result {\n        val engine = deps.ttsEngine()\n        val accepted = runCatching { engine.speakOffline("Проверка громкости ассистента. Один, два, три.") }.getOrDefault(false)\n        kotlinx.coroutines.delay(900L)\n        val audibleNow = runCatching { engine.audible() }.getOrDefault(false)\n        DiLink3DebugLog.log(appContext, "BUILD65_TTS_ONLY_RESULT", "accepted=$accepted audible=$audibleNow gain=1.50")\n        return if (accepted) Result(answer = "accepted", spoken = true) else Result(error = "TTS playback rejected")\n    }\n\n''' + anchor, 1)
p.write_text(s)

# 2) Raise only assistant PCM level before AudioTrack.write; preserve BYD Voice route.
p = Path('app/src/main/kotlin/com/bydmate/app/voice/SherpaTtsEngine.kt')
s = p.read_text()
old = '''            publish()\n            val written = write(samples)\n            if (!stillCurrent()) retract()\n            return written\n'''
if old in s:
    s = s.replace(old, '''            publish()\n            val written = write(applyOutputGain(samples, BUILD65_ASSISTANT_GAIN))\n            if (!stillCurrent()) retract()\n            return written\n''', 1)
elif 'applyOutputGain(samples, BUILD65_ASSISTANT_GAIN)' not in s:
    raise SystemExit('Build65: TTS write anchor not found')
anchor = '        private const val DRAIN_POLL_MS = 20L\n'
if anchor not in s:
    raise SystemExit('Build65: TTS drain anchor not found')
if 'BUILD65_ASSISTANT_GAIN' not in s:
    s = s.replace(anchor, '''        internal const val BUILD65_ASSISTANT_GAIN = 1.50f\n        internal fun applyOutputGain(samples: FloatArray, gain: Float): FloatArray {\n            val g = if (gain.isFinite()) gain.coerceIn(0.5f, 2.0f) else 1.0f\n            if (g == 1.0f) return samples\n            return FloatArray(samples.size) { i -> (samples[i] * g).coerceIn(-0.98f, 0.98f) }\n        }\n\n''' + anchor, 1)
p.write_text(s)

# 3) Persist physical/screen PTT stages for visible readiness checks.
p = Path('app/src/main/kotlin/com/bydmate/app/voice/VoiceController.kt')
s = p.read_text()
anchor = '''        build64UtteranceSeen = false\n        val am = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager\n'''
if anchor not in s:
    raise SystemExit('Build65: PTT state anchor not found')
s = s.replace(anchor, '''        build64UtteranceSeen = false\n        context.getSharedPreferences("build65_prod_wizard", Context.MODE_PRIVATE).edit()\n            .putString("last_ptt_source", source).putBoolean("pcm_seen", false)\n            .putBoolean("speech_seen", false).putBoolean("utterance_seen", false)\n            .putString("utterance_text", "").putString("agent_error", "").apply()\n        val am = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager\n''', 1)
for old, new in [
    ('                            build64PcmSeen = true\n', '                            build64PcmSeen = true\n                            context.getSharedPreferences("build65_prod_wizard", Context.MODE_PRIVATE).edit().putBoolean("pcm_seen", true).apply()\n'),
    ('                            build64SpeechSeen = true\n', '                            build64SpeechSeen = true\n                            context.getSharedPreferences("build65_prod_wizard", Context.MODE_PRIVATE).edit().putBoolean("speech_seen", true).apply()\n'),
    ('                            build64UtteranceSeen = true\n', '                            build64UtteranceSeen = true\n                            context.getSharedPreferences("build65_prod_wizard", Context.MODE_PRIVATE).edit().putBoolean("utterance_seen", true).putString("utterance_text", ev.text).apply()\n'),
]:
    if old not in s:
        raise SystemExit('Build65: stage anchor not found')
    s = s.replace(old, new, 1)
anchor = '''                DiLink3DebugLog.log(\n                    context,\n                    "BUILD64_AGENT_ERROR",\n                    "message=${result.message} transcript=$transcript source=$build64PttSource seq=$build64PttSeq"\n                )\n'''
if anchor not in s:
    raise SystemExit('Build65: agent error anchor not found')
s = s.replace(anchor, anchor + '                context.getSharedPreferences("build65_prod_wizard", Context.MODE_PRIVATE).edit().putString("agent_error", result.message).apply()\n', 1)
p.write_text(s)

# 4) Production wizard UI above existing Build64 deep diagnostics.
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()
ctx = '    val context = LocalContext.current\n'
if ctx not in s:
    raise SystemExit('Build65: LocalContext anchor not found')
if 'val build65Bridge = remember { DiLink3E2EBridge(context.applicationContext) }' not in s:
    s = s.replace(ctx, ctx + '''    val build65Bridge = remember { DiLink3E2EBridge(context.applicationContext) }\n    var build65Snapshot by remember { mutableStateOf<DiLink3E2EBridge.ProductionSnapshot?>(null) }\n    var build65Refresh by remember { mutableLongStateOf(0L) }\n    var build65AiStatus by remember { mutableStateOf("not tested") }\n    var build65AiAnswer by remember { mutableStateOf("") }\n    var build65TtsStatus by remember { mutableStateOf("not tested") }\n    var build65TtsPassed by remember { mutableStateOf(false) }\n    LaunchedEffect(build65Refresh) { build65Snapshot = runCatching { build65Bridge.productionSnapshot() }.getOrNull() }\n''', 1)
old_title = '            Text("DiLink3 Build64 INPUT PARITY DIAG", style = MaterialTheme.typography.titleLarge)\n'
if old_title not in s:
    raise SystemExit('Build65: Build64 title anchor not found')
block = '''            Text("DiLink3 Build65 PRODUCTION WIZARD", style = MaterialTheme.typography.titleLarge)\n\n            val b65 = context.getSharedPreferences("build65_prod_wizard", Context.MODE_PRIVATE)\n            val b61 = context.getSharedPreferences("build61_voice_trace", Context.MODE_PRIVATE)\n            val b65Tick = build65Refresh\n            val pttSource = b65.getString("last_ptt_source", "").orEmpty()\n            val pcmOk = b65.getBoolean("pcm_seen", false)\n            val speechOk = b65.getBoolean("speech_seen", false)\n            val utteranceOk = b65.getBoolean("utterance_seen", false)\n            val utteranceText = b65.getString("utterance_text", "").orEmpty()\n            val agentError = b65.getString("agent_error", "").orEmpty()\n            val assistantText = b61.getString("last_assistant", "").orEmpty()\n            val steeringOk = com.bydmate.app.cluster.SteeringWheelKeyService.isConnected\n            val aiOk = build65Snapshot?.let { it.enabled && it.provider == "custom" && it.baseUrl.isNotBlank() && it.model.isNotBlank() && it.credentialsPresent } ?: false\n            val coreOk = micGranted && voiceEnabled && asrReady && ttsEnabled && ttsReady && steeringOk && aiOk\n            val productionOk = coreOk && build65AiStatus.startsWith("PASS") && build65TtsPassed && pcmOk && speechOk && utteranceOk && agentError.isBlank()\n\n            Text("PRODUCTION READINESS", style = MaterialTheme.typography.titleMedium)\n            DebugRow("1. Microphone", if (micGranted) "PASS" else "FAIL")\n            DebugRow("2. Steering service", if (steeringOk) "PASS" else "FAIL")\n            DebugRow("3. Voice enabled", if (voiceEnabled) "PASS" else "FAIL")\n            DebugRow("4. GigaAM", if (asrReady) "PASS" else "FAIL")\n            DebugRow("5. TTS", if (ttsEnabled && ttsReady) "PASS - gain x1.50" else "FAIL")\n            DebugRow("6. AI provider", build65Snapshot?.let { if (aiOk) "PASS - ${it.provider}/${it.model}" else "FAIL - configure Settings > Integrations" } ?: "checking...")\n\n            Button(onClick = { build65Refresh++ }, modifier = Modifier.fillMaxWidth()) { Text("ОБНОВИТЬ СТАТУС ВИЗАРДА") }\n\n            Text("TEST A - AI БЕЗ МИКРОФОНА", style = MaterialTheme.typography.titleMedium)\n            Button(enabled = aiOk, onClick = {\n                build65AiStatus = "testing..."; build65AiAnswer = ""\n                scope.launch {\n                    val r = build65Bridge.askOnly("Ответь одним коротким словом: готово")\n                    if (r.error != null) build65AiStatus = "FAIL: ${r.error}" else { build65AiStatus = "PASS"; build65AiAnswer = r.answer.orEmpty() }\n                }\n            }, modifier = Modifier.fillMaxWidth()) { Text("ПРОВЕРИТЬ AI НАПРЯМУЮ") }\n            DebugRow("AI test", build65AiStatus)\n            DebugRow("AI answer", build65AiAnswer.ifBlank { "<none>" })\n\n            Text("TEST B - ГРОМКОСТЬ TTS", style = MaterialTheme.typography.titleMedium)\n            Text("Речь ассистента усилена x1.50 (~+3.5 dB), музыка не меняется.", style = MaterialTheme.typography.bodySmall)\n            Button(enabled = ttsEnabled && ttsReady, onClick = {\n                build65TtsStatus = "testing..."; build65TtsPassed = false\n                scope.launch { val r = build65Bridge.testTtsOnly(); build65TtsPassed = r.error == null; build65TtsStatus = if (r.error == null) "PASS - сравни со штатным ассистентом" else "FAIL: ${r.error}" }\n            }, modifier = Modifier.fillMaxWidth()) { Text("ПРОИГРАТЬ ТЕСТ ГРОМКОСТИ") }\n            DebugRow("TTS test", build65TtsStatus)\n\n            Text("TEST C - SCREEN PTT", style = MaterialTheme.typography.titleMedium)\n            Button(enabled = coreOk && !listening, onClick = { voiceController.build64PttFrom("build65_wizard_screen") }, modifier = Modifier.fillMaxWidth()) { Text("ЗАПУСТИТЬ КОМАНДУ С ЭКРАНА") }\n\n            Text("TEST D - STEERING PTT", style = MaterialTheme.typography.titleMedium)\n            Text("Нажми микрофон на руле один раз, скажи вопрос и обнови статус.", style = MaterialTheme.typography.bodySmall)\n            DebugRow("PTT source", pttSource.ifBlank { "<none>" })\n            DebugRow("PCM", if (pcmOk) "PASS" else "waiting")\n            DebugRow("Speech", if (speechOk) "PASS" else "waiting")\n            DebugRow("GigaAM", if (utteranceOk) "PASS - $utteranceText" else "waiting")\n            DebugRow("Agent", if (agentError.isBlank() && utteranceOk) "no captured error" else agentError.ifBlank { "waiting" })\n            DebugRow("Assistant text", assistantText.ifBlank { "<none>" })\n            DebugRow("PRODUCTION CANDIDATE", if (productionOk) "READY" else "NOT READY")\n\n            Text("Production UX: одно нажатие = одна команда; beep; Слушаю/Думаю/Ответ; авто-закрытие после одной фразы; второе нажатие = barge-in; видимый распознанный текст и ответ; конкретная AI-ошибка; отдельная громкость речи без изменения музыки.", style = MaterialTheme.typography.bodySmall)\n\n'''
s = s.replace(old_title, block, 1)
p.write_text(s)

print('Build65 installed: production wizard + direct AI/TTS tests + assistant gain + PTT checklist')
