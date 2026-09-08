#!/usr/bin/env python3
from pathlib import Path

# Build71 is intentionally a narrow field patch on top of the verified Build70 behaviour.
# It keeps the 304/327 routing untouched and changes only settings UI/status handling,
# OpenAI-compatible presets/agent test UX, and GigaAM stale-status recovery.

VERSION_CODE = "60021"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Build71 anchor missing: {label}")
    return text.replace(old, new, 1)

# 1) Update field identity only. Same package/signing path is inherited from Build70 patching.
p = Path("app/build.gradle.kts")
s = p.read_text()
s = replace_once(s, "        versionCode = 60020", f"        versionCode = {VERSION_CODE}", "versionCode")
s = replace_once(
    s,
    '            versionNameSuffix = "-dilink3-production-build70"',
    '            versionNameSuffix = "-dilink3-production-build71"',
    "versionNameSuffix",
)
p.write_text(s)

m = Path("app/src/main/AndroidManifest.xml")
s = m.read_text()
s = replace_once(s, 'android:label="BYDMate DiLink3 Build70"', 'android:label="BYDMate DiLink3 Build71"', "manifest label")
m.write_text(s)

# 2) Add provider presets only; transport already supports any OpenAI-compatible base URL.
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text()
old = '''private val CUSTOM_PRESETS = listOf(
    CustomPreset("Cloudflare", "https://api.cloudflare.com/client/v4/accounts/ACCOUNT_ID/ai/v1",
        "@cf/zai-org/glm-4.7-flash", R.string.settings_preset_hint_cloudflare),
    CustomPreset("Vercel", "https://ai-gateway.vercel.sh/v1",
        "openai/gpt-oss-120b", R.string.settings_preset_hint_vercel),
    CustomPreset("Kimi", "https://api.moonshot.ai/v1", "", R.string.settings_preset_hint_kimi),
    CustomPreset("NanoGPT", "https://nano-gpt.com/api/subscription/v1", "", R.string.settings_preset_hint_nanogpt),
    CustomPreset("DeepSeek", "https://api.deepseek.com/v1", "deepseek-chat", R.string.settings_preset_hint_deepseek),
    CustomPreset("Mistral", "https://api.mistral.ai/v1", "", R.string.settings_preset_hint_mistral),
)
'''
new = '''private val CUSTOM_PRESETS = listOf(
    CustomPreset("OpenAI", "https://api.openai.com/v1", "", R.string.settings_preset_hint_openai),
    CustomPreset("Groq", "https://api.groq.com/openai/v1", "", R.string.settings_preset_hint_groq),
    CustomPreset("xAI / Grok", "https://api.x.ai/v1", "", R.string.settings_preset_hint_xai),
    CustomPreset("Gemini", "https://generativelanguage.googleapis.com/v1beta/openai", "", R.string.settings_preset_hint_gemini),
    CustomPreset("Together", "https://api.together.xyz/v1", "", R.string.settings_preset_hint_together),
    CustomPreset("Cloudflare", "https://api.cloudflare.com/client/v4/accounts/ACCOUNT_ID/ai/v1",
        "@cf/zai-org/glm-4.7-flash", R.string.settings_preset_hint_cloudflare),
    CustomPreset("Vercel", "https://ai-gateway.vercel.sh/v1",
        "openai/gpt-oss-120b", R.string.settings_preset_hint_vercel),
    CustomPreset("Kimi", "https://api.moonshot.ai/v1", "", R.string.settings_preset_hint_kimi),
    CustomPreset("NanoGPT", "https://nano-gpt.com/api/subscription/v1", "", R.string.settings_preset_hint_nanogpt),
    CustomPreset("DeepSeek", "https://api.deepseek.com/v1", "deepseek-chat", R.string.settings_preset_hint_deepseek),
    CustomPreset("Mistral", "https://api.mistral.ai/v1", "", R.string.settings_preset_hint_mistral),
)
'''
s = replace_once(s, old, new, "provider presets")

# Change custom-connection test button to agent-compatibility semantics, but only after all fields are configured.
old = '''                buttonLabel = if (state.connTestRunning == "custom")
                    stringResource(R.string.settings_conn_check_running)
                else
                    stringResource(R.string.settings_conn_check_button),
                onClick = { viewModel.testConnection("custom") },
                enabled = state.customConfigured && state.connTestRunning == null,
'''
new = '''                buttonLabel = if (state.connTestRunning == "custom")
                    stringResource(R.string.settings_agent_compat_running)
                else
                    stringResource(R.string.settings_agent_compat_button),
                onClick = { viewModel.testAgentCompatibility("custom") },
                enabled = state.customConfigured && state.connTestRunning == null,
'''
s = replace_once(s, old, new, "custom agent compatibility button")

# Keep voice section focused on selecting an already configured model; no API entry fields are moved there.
# Replace the Build70 steering debug line with human-readable status inside the assistant toggle card.
old = '''            Text(
                "Build70 debug: helper=bydmate_h70 | A11y=${if (build70A11y) "CONNECTED" else "OFF"} | 304=$build70Age304 | 327 BLOCKED=$build70Age327",
                color = TextMuted,
                fontSize = 11.sp,
                modifier = Modifier.padding(vertical = 6.dp),
            )
'''
new = '''            val restartRequired = state.voiceEnabled && !build70A11y
            Text(
                if (state.voiceEnabled) {
                    if (build70A11y) stringResource(R.string.settings_dilink3_assistant_status_blocked)
                    else stringResource(R.string.settings_dilink3_assistant_status_waiting)
                } else stringResource(R.string.settings_dilink3_assistant_status_factory),
                color = TextMuted,
                fontSize = 11.sp,
                modifier = Modifier.padding(top = 4.dp),
            )
            if (restartRequired) {
                Text(
                    stringResource(R.string.settings_dilink3_restart_required),
                    color = AccentOrange,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.padding(bottom = 4.dp),
                )
            }
            Text(
                stringResource(R.string.settings_dilink3_debug_codes, build70Age304, build70Age327),
                color = TextMuted,
                fontSize = 10.sp,
                modifier = Modifier.padding(bottom = 6.dp),
            )
'''
s = replace_once(s, old, new, "human steering status")

# GigaAM: add a small manual re-check action only, no new state machine.
old = '''            if (gigaAmDownloading) {
                Text(
                    "GigaAM debug: ${state.gigaAmDownloadPhase} · ${state.gigaAmDownloadProgress}%",
                    color = TextSecondary, fontSize = 12.sp,
                    modifier = Modifier.padding(vertical = 8.dp),
                )
'''
new = '''            if (gigaAmDownloading) {
                Text(
                    "GigaAM: ${state.gigaAmDownloadPhase} · ${state.gigaAmDownloadProgress}%",
                    color = TextSecondary, fontSize = 12.sp,
                    modifier = Modifier.padding(top = 8.dp),
                )
                TextButton(onClick = { viewModel.refreshGigaAmStatus() }) {
                    Text(stringResource(R.string.settings_gigaam_recheck_status))
                }
'''
s = replace_once(s, old, new, "GigaAM recheck UI")
p.write_text(s)

# 3) Agent compatibility: use an actual function/tool call instead of plain text response.
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsViewModel.kt")
s = p.read_text()
anchor = '''    fun testConnection(connId: String) {
        if (_uiState.value.connTestRunning != null) return
'''
insert = '''    fun testAgentCompatibility(connId: String) {
        if (_uiState.value.connTestRunning != null) return
        _uiState.update { it.copy(connTestRunning = connId) }
        viewModelScope.launch {
            val conn = runCatching { llmConnectionResolver.get(connId) }.getOrNull()
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
                            appContext.getString(R.string.settings_agent_compat_ok)
                        } else {
                            appContext.getString(R.string.settings_agent_compat_no_tools)
                        }
                    },
                    onFailure = { networkErrorMessage(it) },
                )
            }
            _uiState.update { it.copy(
                connTestRunning = null,
                connTestResults = it.connTestResults + (connId to text),
            ) }
        }
    }

    /** Re-read actual GigaAM files and persisted provisioning state. A completed model always wins
     *  over a stale 93/99% UI marker after process/system restarts. */
    fun refreshGigaAmStatus() {
        val status = gigaAmModelManager.statusSnapshot()
        val ready = gigaAmModelManager.isReady()
        _uiState.update { it.copy(
            gigaAmModelReady = ready,
            gigaAmDownloadProgress = if (ready) 100 else status.progress,
            gigaAmDownloadFailed = if (ready) false else status.failed,
            gigaAmDownloadPhase = if (ready) "ready" else status.phase,
        ) }
    }

'''
s = replace_once(s, anchor, insert + anchor, "agent compatibility method")
p.write_text(s)

# 4) Strings: use the app's existing resource mechanism; small EN translations are cheap and safe.
for values_dir, vals in {
    "values": {
        "settings_preset_hint_openai": "OpenAI API",
        "settings_preset_hint_groq": "Groq OpenAI-compatible API",
        "settings_preset_hint_xai": "xAI Grok API",
        "settings_preset_hint_gemini": "Google Gemini OpenAI-compatible API",
        "settings_preset_hint_together": "Together AI OpenAI-compatible API",
        "settings_agent_compat_button": "Проверить агента",
        "settings_agent_compat_running": "Проверка…",
        "settings_agent_compat_not_configured": "Сначала заполните подключение и модель",
        "settings_agent_compat_ok": "Совместимо с BYDMate Agent",
        "settings_agent_compat_no_tools": "API отвечает, но модель не вернула tool call",
        "settings_dilink3_assistant_status_blocked": "Штатный BYD Assistant: заблокирован",
        "settings_dilink3_assistant_status_waiting": "Штатный BYD Assistant: ожидает активации",
        "settings_dilink3_assistant_status_factory": "Штатный BYD Assistant: активен",
        "settings_dilink3_restart_required": "Требуется перезапуск системы",
        "settings_dilink3_debug_codes": "Микрофон BYDMate: %1$s · штатный ассистент: %2$s",
        "settings_gigaam_recheck_status": "Проверить состояние",
    },
    "values-en": {
        "settings_preset_hint_openai": "OpenAI API",
        "settings_preset_hint_groq": "Groq OpenAI-compatible API",
        "settings_preset_hint_xai": "xAI Grok API",
        "settings_preset_hint_gemini": "Google Gemini OpenAI-compatible API",
        "settings_preset_hint_together": "Together AI OpenAI-compatible API",
        "settings_agent_compat_button": "Check agent",
        "settings_agent_compat_running": "Checking…",
        "settings_agent_compat_not_configured": "Configure the connection and model first",
        "settings_agent_compat_ok": "Compatible with BYDMate Agent",
        "settings_agent_compat_no_tools": "API responds, but the model did not return a tool call",
        "settings_dilink3_assistant_status_blocked": "Factory BYD Assistant: blocked",
        "settings_dilink3_assistant_status_waiting": "Factory BYD Assistant: waiting for activation",
        "settings_dilink3_assistant_status_factory": "Factory BYD Assistant: active",
        "settings_dilink3_restart_required": "System restart required",
        "settings_dilink3_debug_codes": "BYDMate microphone: %1$s · factory assistant: %2$s",
        "settings_gigaam_recheck_status": "Check status",
    },
}.items():
    p = Path(f"app/src/main/res/{values_dir}/strings.xml")
    if not p.exists():
        continue
    s = p.read_text()
    marker = "</resources>"
    additions = "\n".join(f'    <string name="{k}">{v}</string>' for k, v in vals.items()) + "\n"
    s = replace_once(s, marker, additions + marker, f"{values_dir} Build71 strings")
    p.write_text(s)

print("Build71 minimal fixes applied")
