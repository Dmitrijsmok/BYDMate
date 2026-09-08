#!/usr/bin/env python3
from pathlib import Path
import re

VERSION_CODE = "60023"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Build73 anchor missing: {label}")
    return text.replace(old, new, 1)

# 1) Field identity.
p = Path("app/build.gradle.kts")
s = p.read_text()
s = replace_once(s, "        versionCode = 60022", f"        versionCode = {VERSION_CODE}", "versionCode")
s = replace_once(s, '            versionNameSuffix = "-dilink3-production-build72"', '            versionNameSuffix = "-dilink3-production-build73"', "versionNameSuffix")
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = replace_once(s, 'android:label="BYDMate DiLink3 Build72"', 'android:label="BYDMate DiLink3 Build73"', "manifest label")
p.write_text(s)

# 2) Restore proven Build66 connection semantics in user-facing copy: generic custom/OpenAI-compatible,
# not OpenRouter-only. Build66 stored Base URL + key + model in the custom slot and selected it primary.
for values_dir, ru in (("values", True), ("values-en", False)):
    p = Path(f"app/src/main/res/{values_dir}/strings.xml")
    if not p.exists():
        continue
    s = p.read_text()
    if ru:
        s = re.sub(r'<string name="agent_enable_desc">.*?</string>', '<string name="agent_enable_desc">Свободные вопросы и команды через выбранный AI-провайдер. API key и модель берутся из раздела «Интеграции».</string>', s, count=1)
        s = re.sub(r'<string name="agent_model_shared_caption">.*?</string>', '<string name="agent_model_shared_caption">Провайдер, API key и модель для агента настраиваются в разделе Интеграции</string>', s, count=1)
    else:
        s = re.sub(r'<string name="agent_enable_desc">.*?</string>', '<string name="agent_enable_desc">Free-form questions and commands through the selected AI provider. API key and model come from Integrations.</string>', s, count=1)
        s = re.sub(r'<string name="agent_model_shared_caption">.*?</string>', '<string name="agent_model_shared_caption">Provider, API key and model for the agent are configured in Integrations</string>', s, count=1)
    p.write_text(s)

# 3) LLM transport: if streaming fails before ANY user-visible delta, retry the exact same
# request non-streaming. This is safe (nothing has been spoken yet) and recreates the proven
# Build66 direct-AI behaviour for providers whose SSE/tool streaming differs slightly.
p = Path("app/src/main/kotlin/com/bydmate/app/agent/LlmAgentBackend.kt")
s = p.read_text()
old = '''        suspend fun attempt(conn: LlmConnection): Result<AgentReply> {
            val first = call(conn, wire, tools, guarded, withExtras = true)
            if (first.isSuccess || forwarded || !rejectedExtras(conn, first, guarded != null)) return first
            Log.w(TAG, "provider ${conn.id} rejected request extras (HTTP 400), retrying plain")
            return call(conn, wire, tools, guarded, withExtras = false)
        }
'''
new = '''        suspend fun attempt(conn: LlmConnection): Result<AgentReply> {
            val first = call(conn, wire, tools, guarded, withExtras = true)
            if (first.isSuccess || forwarded) return first

            // Build73: the field-proven Build66 wizard used the same custom connection but its
            // direct AI test did not depend on streamed SSE. If streaming fails BEFORE the first
            // delta, no reply has reached the driver, so one non-streaming retry is safe and
            // restores compatibility with OpenAI-compatible providers whose tool streaming
            // dialect differs. A failure after a delta still fails fast to prevent duplicates.
            if (guarded != null) {
                Log.w(TAG, "stream failed before first delta for ${conn.id}; retrying non-streaming")
                val raw = call(conn, wire, tools, null, withExtras = true)
                if (raw.isSuccess) return raw
                if (!rejectedExtras(conn, raw, false)) return raw
                Log.w(TAG, "provider ${conn.id} rejected non-stream extras (HTTP 400), retrying plain")
                return call(conn, wire, tools, null, withExtras = false)
            }

            if (!rejectedExtras(conn, first, false)) return first
            Log.w(TAG, "provider ${conn.id} rejected request extras (HTTP 400), retrying plain")
            return call(conn, wire, tools, null, withExtras = false)
        }
'''
s = replace_once(s, old, new, "stream-to-raw fallback")
old = '''    private fun userMessage(e: Throwable?): String = when {
        e is LlmHttpException && (e.code == 401 || e.code == 403) ->
            "Ключ подключения не подходит, проверь настройки"
        e is LlmHttpException && e.code == 429 -> "Лимит запросов исчерпан, попробуй позже"
        e is LlmHttpException && e.code >= 500 -> "Сервер модели недоступен, попробуй позже"
        else -> "Нет связи с сервером, скажи простую команду"
    }
'''
new = '''    private fun userMessage(e: Throwable?): String = when {
        e is LlmHttpException && (e.code == 401 || e.code == 403) ->
            "Ключ подключения не подходит, проверь настройки"
        e is LlmHttpException && e.code == 400 ->
            "Модель отклонила запрос BYDMate, HTTP 400"
        e is LlmHttpException && e.code == 404 ->
            "Модель или API-адрес не найдены, HTTP 404"
        e is LlmHttpException && e.code == 429 -> "Лимит запросов исчерпан, HTTP 429"
        e is LlmHttpException && e.code >= 500 -> "Сервер модели недоступен, HTTP ${e.code}"
        e is LlmHttpException -> "Ошибка API, HTTP ${e.code}"
        e is java.net.SocketTimeoutException -> "API не ответил вовремя: timeout"
        e is java.io.IOException -> "Ошибка соединения: ${e.message ?: e.javaClass.simpleName}"
        else -> "Ошибка соединения с моделью: ${e?.message ?: "неизвестная ошибка"}"
    }
'''
s = replace_once(s, old, new, "precise LLM errors")
p.write_text(s)

# 4) Runtime trace persisted for the SETTINGS SCREEN, not logcat.
p = Path("app/src/main/kotlin/com/bydmate/app/voice/VoiceController.kt")
s = p.read_text()
old = '''    fun onPttPressed() {
        if (!gate.isEnabled()) return
'''
new = '''    fun onPttPressed() {
        if (!gate.isEnabled()) return
        context.getSharedPreferences("build73_voice_runtime", Context.MODE_PRIVATE).edit()
            .putLong("ptt_at", System.currentTimeMillis())
            .putString("stage", "PTT")
            .putBoolean("asr_ready", continuousAsr.isReady())
            .putBoolean("asr_files_ready", continuousAsr.filesReady())
            .putBoolean("tts_ready", ttsEngine.isReady())
            .putString("transcript", "")
            .putString("answer", "")
            .putString("agent_error", "")
            .apply()
'''
s = replace_once(s, old, new, "PTT runtime prefs")
old = '''                        is ContinuousAsrEvent.Utterance -> {
                            val decodeMs = System.currentTimeMillis() - lastEventMs
'''
new = '''                        is ContinuousAsrEvent.Utterance -> {
                            val decodeMs = System.currentTimeMillis() - lastEventMs
                            context.getSharedPreferences("build73_voice_runtime", Context.MODE_PRIVATE).edit()
                                .putString("stage", "ASR_OK")
                                .putString("transcript", ev.text)
                                .putLong("asr_at", System.currentTimeMillis())
                                .apply()
'''
s = replace_once(s, old, new, "ASR runtime prefs")
old = '''        val queue = if (gate.ttsEnabled()) runCatching { ttsEngine.startQueue() }.getOrNull() else null
'''
new = '''        context.getSharedPreferences("build73_voice_runtime", Context.MODE_PRIVATE).edit()
            .putString("stage", "AGENT_REQUEST")
            .putLong("agent_started_at", System.currentTimeMillis())
            .putString("agent_error", "")
            .apply()
        val queue = if (gate.ttsEnabled()) runCatching { ttsEngine.startQueue() }.getOrNull() else null
'''
s = replace_once(s, old, new, "agent request runtime prefs")
old = '''            is AgentResult.Answer -> {
                // Gated on queuedAny (an actual successful enqueue), not "sentences arrived": the
'''
new = '''            is AgentResult.Answer -> {
                context.getSharedPreferences("build73_voice_runtime", Context.MODE_PRIVATE).edit()
                    .putString("stage", "AGENT_OK")
                    .putString("answer", result.text)
                    .putString("agent_error", "")
                    .putLong("agent_finished_at", System.currentTimeMillis())
                    .apply()
                // Gated on queuedAny (an actual successful enqueue), not "sentences arrived": the
'''
s = replace_once(s, old, new, "agent answer runtime prefs")
old = '''            AgentResult.Disabled -> {
                earcon.fail(); _state.value = VoiceUiState.NotUnderstood(transcript)
'''
new = '''            AgentResult.Disabled -> {
                context.getSharedPreferences("build73_voice_runtime", Context.MODE_PRIVATE).edit()
                    .putString("stage", "AGENT_DISABLED")
                    .putString("agent_error", "Агент выключен или не настроен")
                    .putLong("agent_finished_at", System.currentTimeMillis())
                    .apply()
                earcon.fail(); _state.value = VoiceUiState.NotUnderstood(transcript)
'''
s = replace_once(s, old, new, "agent disabled runtime prefs")
old = '''            is AgentResult.Error -> {
                earcon.fail(); _state.value = VoiceUiState.Blocked(result.message)
'''
new = '''            is AgentResult.Error -> {
                context.getSharedPreferences("build73_voice_runtime", Context.MODE_PRIVATE).edit()
                    .putString("stage", "AGENT_ERROR")
                    .putString("agent_error", result.message)
                    .putLong("agent_finished_at", System.currentTimeMillis())
                    .apply()
                earcon.fail(); _state.value = VoiceUiState.Blocked(result.message)
'''
s = replace_once(s, old, new, "agent error runtime prefs")
p.write_text(s)

# 5) The compatibility button now checks the SAME conditions as a real voice request:
# full BYDMate tool schema + streaming transport. No tool is executed by this probe.
p = Path("app/src/main/kotlin/com/bydmate/app/agent/AgentOrchestrator.kt")
s = p.read_text()
anchor = '''    /** Fast-path (NLU) commands execute without ever going through [ask], so the agent's memory
'''
probe = '''    /** Build73 field probe: exact live-agent transport shape (full BYDMate tool schemas +
     * streaming callback) without executing any returned tool and without touching history. */
    suspend fun probeLiveTransport(): AgentResult {
        if (!settingsRepository.isAgentEnabled()) return AgentResult.Disabled
        if (!backend.isConfigured()) return AgentResult.Error("Агент не настроен")
        val messages = listOf(
            AgentMessage.System(buildSystemPrompt()),
            AgentMessage.User("Проверка соединения. Ответь только одним словом: готово. Не вызывай инструменты."),
        )
        return backend.chat(messages, tools.schemas(), onDelta = { }).fold(
            onSuccess = { reply ->
                val text = reply.content?.trim().orEmpty()
                if (text.isNotEmpty() || reply.toolCalls.isNotEmpty()) AgentResult.Answer(text.ifEmpty { "tool_call" })
                else AgentResult.Error("Пустой ответ модели")
            },
            onFailure = { e -> AgentResult.Error((e as? LlmError)?.userMessage ?: (e.message ?: "Ошибка API")) },
        )
    }

'''
s = replace_once(s, anchor, probe + anchor, "live transport probe")
p.write_text(s)

p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsViewModel.kt")
s = p.read_text()
start = s.find('    fun testAgentCompatibility(connId: String) {')
end_marker = '    /** Re-read actual model files and persisted provisioning state. */'
end = s.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit("Build73 anchor missing: testAgentCompatibility block")
replacement = '''    fun testAgentCompatibility(connId: String) {
        if (_uiState.value.connTestRunning != null) return
        _uiState.update { it.copy(connTestRunning = connId) }
        viewModelScope.launch {
            val conn = runCatching { llmConnectionResolver.get(connId) }.getOrNull()
            val previousPrimary = _uiState.value.primaryConn.ifBlank { "openrouter" }
            val wasEnabled = settingsRepository.isAgentEnabled()
            var compatible = false
            val text = if (conn == null) {
                appContext.getString(R.string.settings_agent_compat_not_configured)
            } else {
                settingsRepository.setString(SettingsRepository.KEY_AGENT_PRIMARY_CONN, conn.id)
                if (!wasEnabled) settingsRepository.setString(SettingsRepository.KEY_AGENT_ENABLED, "true")
                when (val result = agentOrchestrator.probeLiveTransport()) {
                    is AgentResult.Answer -> {
                        compatible = true
                        appContext.getString(R.string.settings_agent_compat_ok_primary)
                    }
                    is AgentResult.Error -> result.message
                    AgentResult.Disabled -> appContext.getString(R.string.settings_agent_compat_not_configured)
                }
            }
            if (!wasEnabled) settingsRepository.setString(SettingsRepository.KEY_AGENT_ENABLED, "false")
            if (compatible && conn != null) {
                settingsRepository.setString(SettingsRepository.KEY_AGENT_PRIMARY_CONN, conn.id)
                _uiState.update { it.copy(primaryConn = conn.id) }
            } else {
                settingsRepository.setString(SettingsRepository.KEY_AGENT_PRIMARY_CONN, previousPrimary)
            }
            _uiState.update { it.copy(
                connTestRunning = null,
                connTestResults = it.connTestResults + (connId to text),
            ) }
        }
    }

'''
s = s[:start] + replacement + s[end:]
p.write_text(s)

# 6) Visible runtime block directly in the existing DiLink3 recognition card.
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text()
anchor = '''            Text(
                stringResource(R.string.settings_dilink3_debug_codes, build70Age304, build70Age327),
                color = TextMuted,
                fontSize = 10.sp,
                modifier = Modifier.padding(bottom = 6.dp),
            )
'''
block = anchor + '''            val runtimePrefs = remember(context) {
                context.getSharedPreferences("build73_voice_runtime", Context.MODE_PRIVATE)
            }
            var runtimeTick by remember { mutableStateOf(0) }
            LaunchedEffect(Unit) {
                while (true) {
                    kotlinx.coroutines.delay(750L)
                    runtimeTick++
                }
            }
            val runtimeRefresh = runtimeTick
            val runtimeStage = runtimePrefs.getString("stage", "WAITING").orEmpty()
            val runtimeTranscript = runtimePrefs.getString("transcript", "").orEmpty()
            val runtimeAnswer = runtimePrefs.getString("answer", "").orEmpty()
            val runtimeError = runtimePrefs.getString("agent_error", "").orEmpty()
            val runtimeAsr = runtimePrefs.getBoolean("asr_ready", false)
            val runtimeFiles = runtimePrefs.getBoolean("asr_files_ready", false)
            val runtimeTts = runtimePrefs.getBoolean("tts_ready", false)
            val runtimePttAt = runtimePrefs.getLong("ptt_at", 0L)
            val runtimeAge = if (runtimePttAt > 0L) ((System.currentTimeMillis() - runtimePttAt) / 1000L).coerceAtLeast(0L) else -1L
            val runtimeProvider = when (state.primaryConn.ifBlank { "openrouter" }) {
                "custom" -> state.customName.ifBlank { "Custom" }
                "zai" -> "z.ai"
                else -> "OpenRouter"
            }
            val runtimeModel = when (state.primaryConn.ifBlank { "openrouter" }) {
                "custom" -> state.customModel
                "zai" -> "GLM"
                else -> state.openRouterModel
            }
            Text(
                "Voice Agent runtime",
                color = TextPrimary,
                fontSize = 12.sp,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.padding(top = 6.dp),
            )
            Text("Маршрут: $runtimeProvider · ${runtimeModel.ifBlank { "<модель не выбрана>" }}", color = TextMuted, fontSize = 11.sp)
            Text("ASR: ${if (runtimeAsr) "готов" else if (runtimeFiles) "файлы есть, runtime заблокирован" else "не готов"} · TTS: ${if (runtimeTts) "готов" else "не готов"}", color = TextMuted, fontSize = 11.sp)
            Text("Этап: $runtimeStage${if (runtimeAge >= 0) " · ${runtimeAge}s ago" else ""}", color = TextMuted, fontSize = 11.sp)
            if (runtimeTranscript.isNotBlank()) Text("Распознано: $runtimeTranscript", color = TextMuted, fontSize = 11.sp)
            if (runtimeAnswer.isNotBlank()) Text("Ответ: $runtimeAnswer", color = AccentGreen, fontSize = 11.sp)
            if (runtimeError.isNotBlank()) Text("Ошибка API: $runtimeError", color = SocRed, fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
            Text("TTS source: ${state.ttsSource} · voice: ${state.ttsVoice}", color = TextMuted, fontSize = 10.sp, modifier = Modifier.padding(bottom = 8.dp))
'''
s = replace_once(s, anchor, block, "visible voice runtime block")
p.write_text(s)

print("Build73 fixes applied")
