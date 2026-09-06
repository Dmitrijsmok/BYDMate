#!/usr/bin/env python3
from pathlib import Path

# Build65: production-readiness wizard after Build64 isolated the current failure to
# an unconfigured AI provider. This patch keeps the now-proven steering/mic/GigaAM path,
# adds a stage-by-stage production checklist + direct AI/TTS tests, persists first-press
# trace state for the wizard, and raises assistant PCM level before AudioTrack.write.

# ---------------------------------------------------------------------------
# 1) DiLink3E2EBridge: production snapshot + AI-only and TTS-only test seams.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3E2EBridge.kt')
s = p.read_text()

anchor = '''    data class AihubmixConfig(val apiKey: String, val model: String, val enabled: Boolean)\n'''
if anchor not in s:
    raise SystemExit('Build65: AihubmixConfig anchor not found')
insert = '''    data class ProductionSnapshot(\n        val enabled: Boolean,\n        val provider: String,\n        val baseUrl: String,\n        val model: String,\n        val apiKeyPresent: Boolean,\n    )\n\n'''
s = s.replace(anchor, anchor + insert, 1)

anchor = '''    fun warmUpTts() {\n'''
if anchor not in s:
    raise SystemExit('Build65: warmUpTts anchor not found')
methods = '''    suspend fun productionSnapshot(): ProductionSnapshot {\n        val repo = deps.settingsRepository()\n        return ProductionSnapshot(\n            enabled = repo.getString(SettingsRepository.KEY_AGENT_ENABLED, "false").toBoolean(),\n            provider = repo.getString(SettingsRepository.KEY_AGENT_PRIMARY_CONN, ""),\n            baseUrl = repo.getString(SettingsRepository.KEY_CUSTOM_BASE_URL, ""),\n            model = repo.getString(SettingsRepository.KEY_CUSTOM_MODEL, ""),\n            apiKeyPresent = repo.getString(SettingsRepository.KEY_CUSTOM_API_KEY, "").isNotBlank(),\n        )\n    }\n\n    suspend fun askOnly(prompt: String): Result {\n        val text = prompt.trim()\n        if (text.isBlank()) return Result(error = "Empty AI test prompt")\n        val t0 = SystemClock.elapsedRealtime()\n        DiLink3DebugLog.log(appContext, "BUILD65_AI_ONLY_START", "text=$text")\n        return when (val result = deps.agentOrchestrator().ask(text)) {\n            is AgentResult.Answer -> {\n                DiLink3DebugLog.log(appContext, "BUILD65_AI_ONLY_OK", "dt=${SystemClock.elapsedRealtime() - t0}ms text=${result.text}")\n                Result(answer = result.text)\n            }\n            is AgentResult.Error -> {\n                DiLink3DebugLog.log(appContext, "BUILD65_AI_ONLY_ERROR", "dt=${SystemClock.elapsedRealtime() - t0}ms message=${result.message}")\n                Result(error = result.message)\n            }\n            AgentResult.Disabled -> {\n                DiLink3DebugLog.log(appContext, "BUILD65_AI_ONLY_DISABLED")\n                Result(error = "Agent disabled")\n            }\n        }\n    }\n\n    suspend fun testTtsOnly(text: String = "Проверка громкости ассистента. Один, два, три."): Result {\n        val engine = deps.ttsEngine()\n        DiLink3DebugLog.log(\n            appContext,\n            "BUILD65_TTS_ONLY_START",\n            "ready=${engine.isReady()} speaking=${engine.speaking.value} audible=${engine.audible()} text=$text"\n        )\n        val accepted = runCatching { engine.speakOffline(text) }\n            .onFailure { DiLink3DebugLog.log(appContext, "BUILD65_TTS_ONLY_ERROR", "${it::class.java.simpleName}: ${it.message}") }\n            .getOrDefault(false)\n        kotlinx.coroutines.delay(900L)\n        val audibleNow = runCatching { engine.audible() }.getOrDefault(false)\n        DiLink3DebugLog.log(\n            appContext,\n            "BUILD65_TTS_ONLY_RESULT",\n            "accepted=$accepted speaking=${engine.speaking.value} audible=$audibleNow gain=1.50"\n        )\n        return if (accepted) Result(answer = "TTS accepted; audible=$audibleNow", spoken = true)\n        else Result(error = "TTS did not accept playback")\n    }\n\n'''
s = s.replace(anchor, methods + anchor, 1)
p.write_text(s)

# ---------------------------------------------------------------------------
# 2) Assistant loudness: +3.5 dB-ish PCM gain with hard float limiter.
# Every offline/online TTS path goes through writeSentence(), so one gain stage covers all
# assistant speech while leaving music/media volume untouched. The BYD Voice custom stream
# remains the route; we are not changing system stream volume.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/voice/SherpaTtsEngine.kt')
s = p.read_text()

old = '''            publish()\n            val written = write(samples)\n            if (!stillCurrent()) retract()\n            return written\n'''
if old not in s:
    raise SystemExit('Build65: writeSentence anchor not found')
new = '''            publish()\n            val written = write(applyOutputGain(samples, BUILD65_ASSISTANT_GAIN))\n            if (!stillCurrent()) retract()\n            return written\n'''
s = s.replace(old, new, 1)

anchor = '''        private const val DRAIN_POLL_MS = 20L\n'''
if anchor not in s:
    raise SystemExit('Build65: DRAIN_POLL_MS anchor not found')
gain_code = '''        // Build65 vehicle tuning: the custom BYD Voice route is subjectively quieter than\n        // the stock DiLink assistant. Raise only assistant PCM, not global media volume.\n        // Float PCM is hard-limited to keep AudioTrack input valid and prevent wrap/distortion.\n        internal const val BUILD65_ASSISTANT_GAIN = 1.50f\n\n        internal fun applyOutputGain(samples: FloatArray, gain: Float): FloatArray {\n            val g = if (gain.isFinite()) gain.coerceIn(0.5f, 2.0f) else 1.0f\n            if (g == 1.0f) return samples\n            return FloatArray(samples.size) { i -> (samples[i] * g).coerceIn(-0.98f, 0.98f) }\n        }\n\n'''
s = s.replace(anchor, gain_code + anchor, 1)
p.write_text(s)

# ---------------------------------------------------------------------------
# 3) VoiceController: persist parity stages so the production wizard can show an honest
# first-press checklist instead of requiring the user to mentally parse the log.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/voice/VoiceController.kt')
s = p.read_text()

anchor = '''        build64UtteranceSeen = false\n        val am = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager\n'''
if anchor not in s:
    raise SystemExit('Build65: Build64 dispatch state anchor not found')
replace = '''        build64UtteranceSeen = false\n        context.getSharedPreferences("build65_prod_wizard", Context.MODE_PRIVATE).edit()\n            .putString("last_ptt_source", source)\n            .putLong("last_ptt_ms", now)\n            .putBoolean("pcm_seen", false)\n            .putBoolean("speech_seen", false)\n            .putBoolean("utterance_seen", false)\n            .putString("utterance_text", "")\n            .putString("agent_error", "")\n            .apply()\n        val am = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager\n'''
s = s.replace(anchor, replace, 1)

anchor = '''                            build64PcmSeen = true\n                            DiLink3DebugLog.log(\n'''
if anchor not in s:
    raise SystemExit('Build65: PCM state anchor not found')
replace = '''                            build64PcmSeen = true\n                            context.getSharedPreferences("build65_prod_wizard", Context.MODE_PRIVATE)\n                                .edit().putBoolean("pcm_seen", true).apply()\n                            DiLink3DebugLog.log(\n'''
s = s.replace(anchor, replace, 1)

anchor = '''                            build64SpeechSeen = true\n                            DiLink3DebugLog.log(\n'''
if anchor not in s:
    raise SystemExit('Build65: speech state anchor not found')
replace = '''                            build64SpeechSeen = true\n                            context.getSharedPreferences("build65_prod_wizard", Context.MODE_PRIVATE)\n                                .edit().putBoolean("speech_seen", true).apply()\n                            DiLink3DebugLog.log(\n'''
s = s.replace(anchor, replace, 1)

anchor = '''                            build64UtteranceSeen = true\n                            DiLink3DebugLog.log(\n'''
if anchor not in s:
    raise SystemExit('Build65: utterance state anchor not found')
replace = '''                            build64UtteranceSeen = true\n                            context.getSharedPreferences("build65_prod_wizard", Context.MODE_PRIVATE)\n                                .edit()\n                                .putBoolean("utterance_seen", true)\n                                .putString("utterance_text", ev.text)\n                                .apply()\n                            DiLink3DebugLog.log(\n'''
s = s.replace(anchor, replace, 1)

anchor = '''                DiLink3DebugLog.log(\n                    context,\n                    "BUILD64_AGENT_ERROR",\n                    "message=${result.message} transcript=$transcript source=$build64PttSource seq=$build64PttSeq"\n                )\n'''
if anchor not in s:
    raise SystemExit('Build65: Build64 agent error anchor not found')
replace = anchor + '''                context.getSharedPreferences("build65_prod_wizard", Context.MODE_PRIVATE)\n                    .edit().putString("agent_error", result.message).apply()\n'''
s = s.replace(anchor, replace, 1)
p.write_text(s)

# ---------------------------------------------------------------------------
# 4) Diagnostic UX: an explicit production wizard above the legacy lab.
# It checks configuration, hardware interception, GigaAM, direct AI, TTS loudness and E2E.
# Existing deep diagnostics remain below for failures; normal users need only this wizard.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()

s = s.replace('DiLink3 Build64 INPUT PARITY DIAG', 'DiLink3 Build65 PRODUCTION WIZARD', 1)

# Build65 state is inserted after the AIHubMix state that Build29/AIHubMix patch guarantees.
anchor = '    var aihubmixStatus by remember { mutableStateOf("not configured") }\n'
if anchor not in s:
    raise SystemExit('Build65: AIHubMix state anchor not found')
states = '''    var build65Snapshot by remember { mutableStateOf<DiLink3E2EBridge.ProductionSnapshot?>(null) }\n    var build65Refresh by remember { mutableLongStateOf(0L) }\n    var build65AiStatus by remember { mutableStateOf("not tested") }\n    var build65AiAnswer by remember { mutableStateOf("") }\n    var build65TtsStatus by remember { mutableStateOf("not tested") }\n    var build65TtsPassed by remember { mutableStateOf(false) }\n\n    LaunchedEffect(build65Refresh) {\n        build65Snapshot = runCatching { e2eBridge.productionSnapshot() }.getOrNull()\n    }\n'''
s = s.replace(anchor, anchor + states, 1)

# Replace the Build64 screen button block with a full wizard, keeping a source-aware screen PTT.
start = '''            Text("DiLink3 Build65 PRODUCTION WIZARD", style = MaterialTheme.typography.titleLarge)\n\n            Button(\n                onClick = {\n                    DiLink3DebugLog.log(context, "BUILD64_SCREEN_PTT_BUTTON", "action=press")\n                    voiceController.build64PttFrom("debug_screen_button")\n                },\n                modifier = Modifier.fillMaxWidth(),\n            ) { Text("ЗАПУСТИТЬ ГОЛОСОВУЮ КОМАНДУ С ЭКРАНА") }\n\n            Text(\n                "Эта кнопка запускает тот же VoiceController PTT путь, что и кнопка руля. В логе сравни BUILD64_PTT_DISPATCH source=debug_screen_button и source=steering. После одного распознанного запроса запись автоматически закрывается, поэтому следующее нажатие снова запускает новую команду.",\n                style = MaterialTheme.typography.bodySmall,\n            )\n\n'''
if start not in s:
    raise SystemExit('Build65: Build64 top controls anchor not found')

wizard = '''            Text("DiLink3 Build65 PRODUCTION WIZARD", style = MaterialTheme.typography.titleLarge)\n\n            val build65Prefs = context.getSharedPreferences("build65_prod_wizard", Context.MODE_PRIVATE)\n            val build61Prefs = context.getSharedPreferences("build61_voice_trace", Context.MODE_PRIVATE)\n            val build65LastSource = build65Prefs.getString("last_ptt_source", "").orEmpty()\n            val build65Pcm = build65Prefs.getBoolean("pcm_seen", false)\n            val build65Speech = build65Prefs.getBoolean("speech_seen", false)\n            val build65Utterance = build65Prefs.getBoolean("utterance_seen", false)\n            val build65UtteranceText = build65Prefs.getString("utterance_text", "").orEmpty()\n            val build65AgentError = build65Prefs.getString("agent_error", "").orEmpty()\n            val build65AssistantText = build61Prefs.getString("last_assistant", "").orEmpty()\n            val build65SteeringConnected = com.bydmate.app.cluster.SteeringWheelKeyService.isConnected\n            val build65AiConfigured = build65Snapshot?.let {\n                it.enabled && it.provider == "custom" && it.baseUrl.isNotBlank() && it.model.isNotBlank() && it.apiKeyPresent\n            } ?: false\n            val build65CoreReady = micGranted && voiceEnabled && voiceLang.uppercase().startsWith("RU") &&\n                asrReady && ttsEnabled && ttsReady && build65SteeringConnected && build65AiConfigured\n            val build65ProductionReady = build65CoreReady && build65AiStatus.startsWith("PASS") && build65TtsPassed &&\n                build65Pcm && build65Speech && build65Utterance && build65AgentError.isBlank()\n\n            Text("PRODUCTION READINESS", style = MaterialTheme.typography.titleSmall)\n            DebugRow("1. RECORD_AUDIO", if (micGranted) "PASS" else "FAIL - grant microphone permission")\n            DebugRow("2. Steering Accessibility", if (build65SteeringConnected) "PASS - service connected" else "FAIL - activate steering blocker/service")\n            DebugRow("3. Voice enabled / RU", if (voiceEnabled && voiceLang.uppercase().startsWith("RU")) "PASS - $voiceLang" else "FAIL - enable Voice and select RU")\n            DebugRow("4. GigaAM", if (asrReady) "PASS - model ready" else "FAIL - GigaAM model not ready")\n            DebugRow("5. TTS", if (ttsEnabled && ttsReady) "PASS - $selectedVoiceId; PCM gain x1.50" else "FAIL - enable/download TTS voice")\n            DebugRow(\n                "6. AI provider",\n                build65Snapshot?.let { snap ->\n                    if (build65AiConfigured) "PASS - ${snap.provider} / ${snap.model} / key=yes"\n                    else "FAIL - enabled=${snap.enabled} provider=${snap.provider.ifBlank { "<none>" }} url=${snap.baseUrl.ifBlank { "<none>" }} model=${snap.model.ifBlank { "<none>" }} key=${if (snap.apiKeyPresent) "yes" else "NO"}"\n                } ?: "checking..."\n            )\n\n            Button(\n                onClick = { build65Refresh++ },\n                modifier = Modifier.fillMaxWidth(),\n            ) { Text("ОБНОВИТЬ СТАТУС ВИЗАРДА") }\n\n            Text("TEST A - AI БЕЗ МИКРОФОНА", style = MaterialTheme.typography.titleSmall)\n            Button(\n                enabled = build65AiConfigured,\n                onClick = {\n                    build65AiStatus = "testing..."\n                    build65AiAnswer = ""\n                    scope.launch {\n                        val r = e2eBridge.askOnly("Ответь одним коротким словом: готово")\n                        if (r.error != null) {\n                            build65AiStatus = "FAIL: ${r.error}"\n                        } else {\n                            build65AiAnswer = r.answer.orEmpty()\n                            build65AiStatus = "PASS"\n                        }\n                    }\n                },\n                modifier = Modifier.fillMaxWidth(),\n            ) { Text("ПРОВЕРИТЬ AI НАПРЯМУЮ") }\n            DebugRow("AI-only", build65AiStatus)\n            DebugRow("AI answer", build65AiAnswer.ifBlank { "<none>" })\n\n            Text("TEST B - TTS И ГРОМКОСТЬ", style = MaterialTheme.typography.titleSmall)\n            Text(\n                "Build65 усиливает только PCM речи ассистента в 1.50 раза (~+3.5 dB) перед BYD Voice AudioTrack. Музыкальную громкость не меняем. Сравни фразу с громкостью штатного ассистента.",\n                style = MaterialTheme.typography.bodySmall,\n            )\n            Button(\n                enabled = ttsEnabled && ttsReady,\n                onClick = {\n                    build65TtsStatus = "testing..."\n                    build65TtsPassed = false\n                    scope.launch {\n                        val r = e2eBridge.testTtsOnly()\n                        build65TtsPassed = r.error == null\n                        build65TtsStatus = if (r.error == null) "PASS - проверь громкость на слух" else "FAIL: ${r.error}"\n                    }\n                },\n                modifier = Modifier.fillMaxWidth(),\n            ) { Text("ПРОИГРАТЬ ТЕСТ ГРОМКОСТИ") }\n            DebugRow("TTS test", build65TtsStatus)\n\n            Text("TEST C - ТОТ ЖЕ PTT С ЭКРАНА", style = MaterialTheme.typography.titleSmall)\n            Button(\n                enabled = build65CoreReady && !listening,\n                onClick = {\n                    DiLink3DebugLog.log(context, "BUILD65_WIZARD_SCREEN_PTT", "action=press")\n                    voiceController.build64PttFrom("build65_wizard_screen")\n                },\n                modifier = Modifier.fillMaxWidth(),\n            ) { Text("ЗАПУСТИТЬ КОМАНДУ С ЭКРАНА") }\n\n            Text("TEST D - ФИЗИЧЕСКАЯ КНОПКА РУЛЯ", style = MaterialTheme.typography.titleSmall)\n            Text("Нажми микрофон на руле ОДИН раз и скажи обычный вопрос. После ответа нажми «Обновить статус визарда».", style = MaterialTheme.typography.bodySmall)\n            DebugRow("Last PTT source", build65LastSource.ifBlank { "<none>" })\n            DebugRow("PCM", if (build65Pcm) "PASS" else "waiting")\n            DebugRow("Speech detected", if (build65Speech) "PASS" else "waiting")\n            DebugRow("GigaAM utterance", if (build65Utterance) "PASS - $build65UtteranceText" else "waiting")\n            DebugRow("Agent route", if (build65AgentError.isBlank() && build65Utterance) "no captured error" else build65AgentError.ifBlank { "waiting" })\n            DebugRow("Assistant text", build65AssistantText.ifBlank { "<none>" })\n\n            DebugRow(\n                "PRODUCTION CANDIDATE",\n                if (build65ProductionReady) "READY - все ключевые этапы пройдены"\n                else "NOT READY - исправь FAIL/waiting выше; глубокие диагностические тесты остаются ниже"\n            )\n\n            Text(\n                "UX для production: одно нажатие = одна команда; короткий beep подтверждает захват; видимые состояния Слушаю/Думаю/Ответ; авто-закрытие микрофона после одной фразы; barge-in вторым нажатием; текст «что услышал/что ответил»; понятная ошибка AI вместо общего «не получилось»; отдельная Voice-громкость без изменения музыки. Визард проверяет именно эти зависимости перед выпуском production APK.",\n                style = MaterialTheme.typography.bodySmall,\n            )\n\n'''
s = s.replace(start, wizard, 1)

# Update explanatory paragraph if present.
s = s.replace(
    'Build64 сравнивает физическую кнопку и кнопку на экране через один и тот же PTT-вход. Первый press трассируется до PCM, SpeechStart и Utterance с задержками. Также логируется точный AgentResult.Error и состояние TTS. Старые карточки очищаются при открытии экрана.',
    'Build65 добавляет production-readiness wizard: hardware -> PCM -> GigaAM -> AI provider -> direct AI -> TTS -> screen PTT -> steering PTT. Глубокий Build64 trace оставлен ниже для разбора любого FAIL.',
    1,
)

p.write_text(s)
print('Build65 installed: production wizard + AI-only/TTS-only tests + persisted PTT stages + assistant PCM gain x1.50')
