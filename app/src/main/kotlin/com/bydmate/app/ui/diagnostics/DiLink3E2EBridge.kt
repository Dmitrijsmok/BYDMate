package com.bydmate.app.ui.diagnostics

import android.content.Context
import com.bydmate.app.agent.AgentOrchestrator
import com.bydmate.app.agent.AgentResult
import com.bydmate.app.data.repository.SettingsRepository
import com.bydmate.app.voice.TtsEngine
import dagger.hilt.EntryPoint
import dagger.hilt.InstallIn
import dagger.hilt.android.EntryPointAccessors
import dagger.hilt.components.SingletonComponent

/**
 * Small diagnostic bridge for DiLink 3 end-to-end testing:
 * Android System SpeechRecognizer -> BYDMate agent -> existing TTS engine.
 *
 * Also exposes a minimal AIHubMix setup path for the DiLink 3 diagnostic build. AIHubMix is
 * OpenAI-compatible at https://aihubmix.com/v1, so it uses BYDMate's existing custom LLM slot.
 */
class DiLink3E2EBridge(context: Context) {
    @EntryPoint
    @InstallIn(SingletonComponent::class)
    interface Dependencies {
        fun agentOrchestrator(): AgentOrchestrator
        fun ttsEngine(): TtsEngine
        fun settingsRepository(): SettingsRepository
    }

    private val deps: Dependencies = EntryPointAccessors.fromApplication(
        context.applicationContext,
        Dependencies::class.java,
    )

    data class Result(
        val answer: String? = null,
        val error: String? = null,
        val spoken: Boolean = false,
    )

    data class AihubmixConfig(
        val apiKey: String,
        val model: String,
        val enabled: Boolean,
    )

    suspend fun loadAihubmixConfig(): AihubmixConfig {
        val repo = deps.settingsRepository()
        return AihubmixConfig(
            apiKey = repo.getString(SettingsRepository.KEY_CUSTOM_API_KEY, ""),
            model = repo.getString(SettingsRepository.KEY_CUSTOM_MODEL, DEFAULT_AIHUBMIX_MODEL)
                .ifBlank { DEFAULT_AIHUBMIX_MODEL },
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
    }

    suspend fun askAndSpeak(transcript: String): Result {
        val text = transcript.trim()
        if (text.isEmpty()) return Result(error = "SpeechRecognizer returned empty text")

        return when (val result = deps.agentOrchestrator().ask(text)) {
            is AgentResult.Answer -> {
                val spoken = runCatching { deps.ttsEngine().speak(result.text) }.getOrDefault(false)
                Result(answer = result.text, spoken = spoken)
            }
            is AgentResult.Error -> Result(error = result.message)
            AgentResult.Disabled -> Result(
                error = "BYDMate agent is disabled or not configured. Save an AIHubMix key in this debug panel first.",
            )
        }
    }

    companion object {
        const val AIHUBMIX_BASE_URL = "https://aihubmix.com/v1"
        const val DEFAULT_AIHUBMIX_MODEL = "gpt-5.5-free"
    }
}
