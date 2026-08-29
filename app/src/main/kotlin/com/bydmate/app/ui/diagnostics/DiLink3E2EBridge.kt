package com.bydmate.app.ui.diagnostics

import android.content.Context
import android.os.SystemClock
import com.bydmate.app.agent.AgentOrchestrator
import com.bydmate.app.agent.AgentResult
import com.bydmate.app.data.repository.SettingsRepository
import com.bydmate.app.voice.TtsEngine
import dagger.hilt.EntryPoint
import dagger.hilt.InstallIn
import dagger.hilt.android.EntryPointAccessors
import dagger.hilt.components.SingletonComponent

class DiLink3E2EBridge(context: Context) {
    @EntryPoint
    @InstallIn(SingletonComponent::class)
    interface Dependencies {
        fun agentOrchestrator(): AgentOrchestrator
        fun ttsEngine(): TtsEngine
        fun settingsRepository(): SettingsRepository
    }

    private val appContext = context.applicationContext
    private val deps: Dependencies = EntryPointAccessors.fromApplication(appContext, Dependencies::class.java)

    data class Result(
        val answer: String? = null,
        val error: String? = null,
        val spoken: Boolean = false,
    )

    data class AihubmixConfig(val apiKey: String, val model: String, val enabled: Boolean)

    suspend fun loadAihubmixConfig(): AihubmixConfig {
        val repo = deps.settingsRepository()
        return AihubmixConfig(
            apiKey = repo.getString(SettingsRepository.KEY_CUSTOM_API_KEY, ""),
            model = repo.getString(SettingsRepository.KEY_CUSTOM_MODEL, DEFAULT_AIHUBMIX_MODEL).ifBlank { DEFAULT_AIHUBMIX_MODEL },
            enabled = repo.getString(SettingsRepository.KEY_AGENT_PRIMARY_CONN, "") == "custom" &&
                repo.getString(SettingsRepository.KEY_AGENT_ENABLED, "false").toBoolean(),
        )
    }

    suspend fun saveAihubmixConfig(apiKey: String, model: String) {
        val key = apiKey.trim()
        require(key.isNotBlank()) { "AIHubMix API key is empty" }
        val chosenModel = model.trim().ifBlank { DEFAULT_AIHUBMIX_MODEL }
        deps.settingsRepository().setStrings(
            mapOf(
                SettingsRepository.KEY_CUSTOM_NAME to "AIHubMix",
                SettingsRepository.KEY_CUSTOM_BASE_URL to AIHUBMIX_BASE_URL,
                SettingsRepository.KEY_CUSTOM_API_KEY to key,
                SettingsRepository.KEY_CUSTOM_MODEL to chosenModel,
                SettingsRepository.KEY_CUSTOM_EXTRA_JSON to "",
                SettingsRepository.KEY_AGENT_PRIMARY_CONN to "custom",
                SettingsRepository.KEY_AGENT_ENABLED to "true",
            )
        )
        DiLink3DebugLog.log(appContext, "AIHUBMIX_CONFIG_SAVED", "model=$chosenModel")
    }

    fun warmUpTts() {
        val started = SystemClock.elapsedRealtime()
        DiLink3DebugLog.log(appContext, "TTS_WARMUP_START")
        runCatching { deps.ttsEngine().warmUp() }
            .onSuccess { DiLink3DebugLog.log(appContext, "TTS_WARMUP_DISPATCHED", "dt=${SystemClock.elapsedRealtime() - started}ms") }
            .onFailure { DiLink3DebugLog.log(appContext, "TTS_WARMUP_ERROR", "${it::class.java.simpleName}: ${it.message}") }
    }

    suspend fun askAndSpeak(transcript: String): Result {
        val text = transcript.trim()
        if (text.isEmpty()) return Result(error = "SpeechRecognizer returned empty text")

        val t0 = SystemClock.elapsedRealtime()
        DiLink3DebugLog.log(appContext, "E2E_ASK_START", "text=$text")
        return when (val result = deps.agentOrchestrator().ask(text)) {
            is AgentResult.Answer -> {
                val aiMs = SystemClock.elapsedRealtime() - t0
                DiLink3DebugLog.log(appContext, "E2E_AI_ANSWER_READY", "dt=${aiMs}ms chars=${result.text.length} text=${result.text}")
                val speakStart = SystemClock.elapsedRealtime()
                val spoken = runCatching { deps.ttsEngine().speakOffline(result.text) }
                    .onFailure { DiLink3DebugLog.log(appContext, "E2E_TTS_CALL_ERROR", "${it::class.java.simpleName}: ${it.message}") }
                    .getOrDefault(false)
                DiLink3DebugLog.log(
                    appContext,
                    "E2E_TTS_ENQUEUED",
                    "accepted=$spoken call=${SystemClock.elapsedRealtime() - speakStart}ms ai=${aiMs}ms speaking=${deps.ttsEngine().speaking.value} audible=${deps.ttsEngine().audible()}",
                )
                Result(answer = result.text, spoken = spoken)
            }
            is AgentResult.Error -> {
                DiLink3DebugLog.log(appContext, "E2E_AGENT_ERROR", "dt=${SystemClock.elapsedRealtime() - t0}ms ${result.message}")
                Result(error = result.message)
            }
            AgentResult.Disabled -> {
                val msg = "BYDMate agent is disabled or not configured. Save an AIHubMix key in this debug panel first."
                DiLink3DebugLog.log(appContext, "E2E_AGENT_DISABLED")
                Result(error = msg)
            }
        }
    }

    companion object {
        const val AIHUBMIX_BASE_URL = "https://aihubmix.com/v1"
        const val DEFAULT_AIHUBMIX_MODEL = "gpt-5.5-free"
    }
}
