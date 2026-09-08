#!/usr/bin/env python3
from pathlib import Path

VERSION_CODE = "60022"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Build72 anchor missing: {label}")
    return text.replace(old, new, 1)


def replace_between(text: str, start: str, end: str, replacement: str, label: str) -> str:
    i = text.find(start)
    if i < 0:
        raise SystemExit(f"Build72 start anchor missing: {label}")
    j = text.find(end, i + len(start))
    if j < 0:
        raise SystemExit(f"Build72 end anchor missing: {label}")
    return text[:i] + replacement + text[j:]


# ---------------------------------------------------------------------------
# 1) Field APK identity. Same package/signer, monotonic update over Build71.
# ---------------------------------------------------------------------------
p = Path("app/build.gradle.kts")
s = p.read_text()
s = replace_once(s, "        versionCode = 60021", f"        versionCode = {VERSION_CODE}", "versionCode")
s = replace_once(
    s,
    '            versionNameSuffix = "-dilink3-production-build71"',
    '            versionNameSuffix = "-dilink3-production-build72"',
    "versionNameSuffix",
)
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = replace_once(
    s,
    'android:label="BYDMate DiLink3 Build71"',
    'android:label="BYDMate DiLink3 Build72"',
    "manifest label",
)
p.write_text(s)


# ---------------------------------------------------------------------------
# 2) Provider presets: give each well-known provider a sensible agent model.
#    Live /models is still used, but users no longer see a blank picker merely
#    because a provider hides/limits its model-list endpoint before auth.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text()
for old, new, label in (
    ('CustomPreset("OpenAI", "https://api.openai.com/v1", "", R.string.settings_preset_hint_openai)',
     'CustomPreset("OpenAI", "https://api.openai.com/v1", "gpt-5.6-luna", R.string.settings_preset_hint_openai)', "OpenAI default"),
    ('CustomPreset("Groq", "https://api.groq.com/openai/v1", "", R.string.settings_preset_hint_groq)',
     'CustomPreset("Groq", "https://api.groq.com/openai/v1", "openai/gpt-oss-20b", R.string.settings_preset_hint_groq)', "Groq default"),
    ('CustomPreset("xAI / Grok", "https://api.x.ai/v1", "", R.string.settings_preset_hint_xai)',
     'CustomPreset("xAI / Grok", "https://api.x.ai/v1", "grok-4.6", R.string.settings_preset_hint_xai)', "xAI default"),
    ('CustomPreset("Gemini", "https://generativelanguage.googleapis.com/v1beta/openai", "", R.string.settings_preset_hint_gemini)',
     'CustomPreset("Gemini", "https://generativelanguage.googleapis.com/v1beta/openai", "gemini-3.8-flash", R.string.settings_preset_hint_gemini)', "Gemini default"),
    ('CustomPreset("Together", "https://api.together.xyz/v1", "", R.string.settings_preset_hint_together)',
     'CustomPreset("Together", "https://api.together.xyz/v1", "openai/gpt-oss-20b", R.string.settings_preset_hint_together)', "Together default"),
    ('CustomPreset("DeepSeek", "https://api.deepseek.com/v1", "deepseek-chat", R.string.settings_preset_hint_deepseek)',
     'CustomPreset("DeepSeek", "https://api.deepseek.com/v1", "deepseek-v4-flash", R.string.settings_preset_hint_deepseek)', "DeepSeek default"),
    ('CustomPreset("Mistral", "https://api.mistral.ai/v1", "", R.string.settings_preset_hint_mistral)',
     'CustomPreset("Mistral", "https://api.mistral.ai/v1", "mistral-small-latest", R.string.settings_preset_hint_mistral)', "Mistral default"),
):
    s = replace_once(s, old, new, label)

# Curated provider catalogs can be opened without a key. With a key, the VM
# merges them with the provider's live /models response.
s = replace_once(
    s,
    '            enabled = state.customBaseUrl.isNotBlank() && state.customApiKey.isNotBlank(),',
    '            enabled = state.customBaseUrl.isNotBlank(),',
    "model list button",
)
p.write_text(s)


# ---------------------------------------------------------------------------
# 3) Model picker: merge a small verified catalog with live /models and filter
#    obvious non-agent endpoints (audio, embeddings, image/video, moderation,
#    Groq Compound). Compatibility button remains the final truth test.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsViewModel.kt")
s = p.read_text()

start = '    /** Fetches model list from the custom connection\'s base URL and shows the picker dialog. */\n    fun loadCustomModels() {'
end = '    fun hideCustomModelPickerDialog() {'
replacement = '''    private fun curatedAgentModels(provider: String): List<String> = when (provider.trim().lowercase(Locale.ROOT)) {
        "openai" -> listOf("gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol")
        "groq" -> listOf(
            "openai/gpt-oss-20b", "openai/gpt-oss-120b",
            "qwen/qwen3.6-27b", "qwen/qwen3.8-27b",
            "minimaxai/minimax-m2.7", "llama-3.3-70b-versatile", "llama-3.1-8b-instant",
        )
        "xai / grok" -> listOf("grok-4.6", "grok-4.20", "grok-4.20-non-reasoning")
        "gemini" -> listOf("gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.1-pro", "gemini-3.1-flash-lite")
        "together" -> listOf(
            "openai/gpt-oss-20b", "openai/gpt-oss-120b",
            "moonshotai/Kimi-K2.5", "Qwen/Qwen3.5-9B", "zai-org/GLM-5.1",
        )
        "deepseek" -> listOf("deepseek-v4-flash", "deepseek-v4-pro")
        "mistral" -> listOf(
            "mistral-small-latest", "mistral-medium-latest", "mistral-large-latest",
            "ministral-8b-latest", "ministral-14b-latest",
        )
        else -> emptyList()
    }

    private fun isLikelyAgentModel(provider: String, modelId: String): Boolean {
        val id = modelId.trim()
        if (id.isBlank()) return false
        val lower = id.lowercase(Locale.ROOT)
        val blocked = listOf(
            "whisper", "transcrib", "tts", "embedding", "embed-", "moderation",
            "safeguard", "llama-guard", "rerank", "image", "video", "speech", "realtime",
        )
        if (blocked.any { lower.contains(it) }) return false
        if (provider.equals("Groq", ignoreCase = true) && lower.startsWith("groq/compound")) return false
        if (provider.startsWith("xAI", ignoreCase = true)) {
            return lower.startsWith("grok-") && !lower.contains("imagine") && !lower.contains("voice")
        }
        if (provider.equals("Gemini", ignoreCase = true)) {
            return lower.startsWith("gemini-") && !lower.contains("live")
        }
        return true
    }

    /**
     * Shows verified agent models immediately, then merges the authenticated /models result.
     * The compatibility tool-call test is deliberately still required: model catalogs change,
     * and a model being a chat model does not prove its exact BYDMate tool-call behaviour.
     */
    fun loadCustomModels() {
        val state = _uiState.value
        val baseUrl = state.customBaseUrl
        val apiKey = state.customApiKey
        val provider = state.customName
        if (baseUrl.isBlank()) return
        val curated = curatedAgentModels(provider)
        _uiState.update { it.copy(
            customModelsLoading = apiKey.isNotBlank(),
            customModelsError = null,
            customModelList = curated,
            showCustomModelPicker = true,
        ) }
        if (apiKey.isBlank()) return
        viewModelScope.launch {
            val result = openRouterClient.fetchModelsFromUrl(baseUrl, apiKey)
            result.fold(
                onSuccess = { models ->
                    val filtered = models.filter { isLikelyAgentModel(provider, it) }
                    val merged = (curated + filtered).distinct()
                    _uiState.update { it.copy(customModelList = merged, customModelsLoading = false) }
                },
                onFailure = { t ->
                    _uiState.update {
                        it.copy(
                            customModelsError = if (curated.isNotEmpty())
                                appContext.getString(R.string.settings_agent_models_using_catalog)
                            else networkErrorMessage(t),
                            customModelsLoading = false,
                        )
                    }
                },
            )
        }
    }

'''
s = replace_between(s, start, end, replacement, "custom model picker")

# A green compatibility test now also makes that exact slot the primary voice-agent
# connection. This closes the Build71 mismatch where the test used Groq/custom but
# VoiceController could continue using the old OpenRouter primary selection.
start = '    fun testAgentCompatibility(connId: String) {'
end = '    /** Re-read actual model files and persisted provisioning state. */'
replacement = '''    fun testAgentCompatibility(connId: String) {
        if (_uiState.value.connTestRunning != null) return
        _uiState.update { it.copy(connTestRunning = connId) }
        viewModelScope.launch {
            val conn = runCatching { llmConnectionResolver.get(connId) }.getOrNull()
            var compatible = false
            val text = if (conn == null) {
                appContext.getString(R.string.settings_agent_compat_not_configured)
            } else {
                val messages = JSONArray().put(
                    JSONObject().put("role", "user")
                        .put("content", "Вызови функцию readiness_check без дополнительного текста")
                )
                val tools = JSONArray().put(
                    JSONObject()
                        .put("type", "function")
                        .put("function", JSONObject()
                            .put("name", "readiness_check")
                            .put("description", "Проверка поддержки tool calls")
                            .put("parameters", JSONObject()
                                .put("type", "object")
                                .put("properties", JSONObject())
                                .put("additionalProperties", false)))
                )
                val result = openRouterClient.chatRaw(conn.baseUrl, conn.apiKey, conn.model, messages, tools)
                result.fold(
                    onSuccess = { msg ->
                        val calls = msg.optJSONArray("tool_calls")
                        if (calls != null && calls.length() > 0) {
                            compatible = true
                            appContext.getString(R.string.settings_agent_compat_ok_primary)
                        } else {
                            appContext.getString(R.string.settings_agent_compat_no_tools)
                        }
                    },
                    onFailure = { networkErrorMessage(it) },
                )
            }
            if (compatible && conn != null) {
                settingsRepository.setString(SettingsRepository.KEY_AGENT_PRIMARY_CONN, conn.id)
                _uiState.update { it.copy(primaryConn = conn.id) }
                Log.i("SettingsViewModel", "Build72 agent primary=${conn.id} provider=${conn.label} model=${conn.model}")
            }
            _uiState.update { it.copy(
                connTestRunning = null,
                connTestResults = it.connTestResults + (connId to text),
            ) }
        }
    }

'''
s = replace_between(s, start, end, replacement, "agent compatibility primary binding")
p.write_text(s)


# ---------------------------------------------------------------------------
# 4) Runtime diagnostics: distinguish files-on-disk from usable ASR, and log
#    the exact LLM route used by the real voice turn. No API keys are logged.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/voice/ContinuousAsr.kt")
s = p.read_text()
s = replace_once(
    s,
    'interface ContinuousAsr {\n    fun isReady(): Boolean\n',
    'interface ContinuousAsr {\n    fun isReady(): Boolean\n    /** Model/VAD files exist even if the native-load safety guard currently blocks runtime use. */\n    fun filesReady(): Boolean = isReady()\n',
    "ContinuousAsr filesReady",
)
p.write_text(s)

p = Path("app/src/main/kotlin/com/bydmate/app/voice/GigaAmAsrEngine.kt")
s = p.read_text()
s = replace_once(
    s,
    '    override fun isReady(): Boolean = modelManager.isReady() && loadGuard?.isTripped() != true\n',
    '    override fun isReady(): Boolean = modelManager.isReady() && loadGuard?.isTripped() != true\n\n'
    '    override fun filesReady(): Boolean = modelManager.isReady()\n',
    "GigaAM filesReady",
)
p.write_text(s)

p = Path("app/src/main/kotlin/com/bydmate/app/voice/VoiceController.kt")
s = p.read_text()
s = replace_once(
    s,
    '    fun onPttPressed() {\n        if (!gate.isEnabled()) return\n',
    '    fun onPttPressed() {\n'
    '        if (!gate.isEnabled()) return\n'
    '        Log.i(TAG, "BUILD72_PTT asrReady=${continuousAsr.isReady()} filesReady=${continuousAsr.filesReady()} lang=${currentLang()} ttsReady=${ttsEngine.isReady()}")\n',
    "PTT runtime log",
)
# If files are present but runtime is blocked, do not lie that the model is missing.
s = replace_once(
    s,
    '            val langBlocked = continuousAsr.isReady() && currentLang() != VoiceLang.RU\n            val msg = context.getString(\n                if (langBlocked) R.string.voice_error_lang_not_ru\n                else R.string.voice_error_model_missing\n            )\n',
    '            val langBlocked = continuousAsr.isReady() && currentLang() != VoiceLang.RU\n'
    '            val runtimeBlocked = continuousAsr.filesReady() && !continuousAsr.isReady()\n'
    '            val msg = context.getString(\n'
    '                when {\n'
    '                    langBlocked -> R.string.voice_error_lang_not_ru\n'
    '                    runtimeBlocked -> R.string.voice_error_model_runtime_blocked\n'
    '                    else -> R.string.voice_error_model_missing\n'
    '                }\n'
    '            )\n',
    "ASR truthful error",
)
p.write_text(s)

p = Path("app/src/main/kotlin/com/bydmate/app/agent/LlmAgentBackend.kt")
s = p.read_text()
s = replace_once(
    s,
    '        val primary = connections.primary()\n            ?: return Result.failure(LlmError("Агент не настроен: заполните адрес, API-ключ и модель в Настройки, Интеграции"))\n',
    '        val primary = connections.primary()\n'
    '            ?: return Result.failure(LlmError("Агент не настроен: заполните адрес, API-ключ и модель в Настройки, Интеграции"))\n'
    '        Log.i(TAG, "BUILD72_AGENT_ROUTE conn=${primary.id} provider=${primary.label} model=${primary.model} base=${primary.baseUrl}")\n',
    "agent runtime route log",
)
p.write_text(s)

# ---------------------------------------------------------------------------
# 5) Small user-visible strings.
# ---------------------------------------------------------------------------
for values_dir, vals in {
    "values": {
        "settings_agent_models_using_catalog": "Не удалось обновить список через API. Показаны проверенные модели провайдера.",
        "settings_agent_compat_ok_primary": "Совместимо с BYDMate Agent · выбрано для голосового агента",
        "voice_error_model_runtime_blocked": "Голосовая модель установлена, но движок распознавания заблокирован после ошибки загрузки. Проверьте состояние GigaAM.",
    },
    "values-en": {
        "settings_agent_models_using_catalog": "Could not refresh the API model list. Showing verified provider models.",
        "settings_agent_compat_ok_primary": "Compatible with BYDMate Agent · selected for the voice agent",
        "voice_error_model_runtime_blocked": "The voice model is installed, but the recognition engine is blocked after a load failure. Check GigaAM status.",
    },
}.items():
    p = Path(f"app/src/main/res/{values_dir}/strings.xml")
    if not p.exists():
        continue
    s = p.read_text()
    additions = "\n".join(f'    <string name="{k}">{v}</string>' for k, v in vals.items()) + "\n"
    s = replace_once(s, "</resources>", additions + "</resources>", f"{values_dir} Build72 strings")
    p.write_text(s)

print("Build72 fixes applied")
