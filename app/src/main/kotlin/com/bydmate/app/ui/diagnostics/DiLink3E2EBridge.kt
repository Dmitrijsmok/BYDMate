package com.bydmate.app.ui.diagnostics

import android.content.Context
import com.bydmate.app.agent.AgentOrchestrator
import com.bydmate.app.agent.AgentResult
import com.bydmate.app.voice.TtsEngine
import dagger.hilt.EntryPoint
import dagger.hilt.InstallIn
import dagger.hilt.android.EntryPointAccessors
import dagger.hilt.components.SingletonComponent

/**
 * Small diagnostic bridge for DiLink 3 end-to-end testing:
 * Android System SpeechRecognizer -> BYDMate agent -> existing TTS engine.
 *
 * This intentionally reuses the production AgentOrchestrator and TtsEngine so the test proves
 * the same API/provider configuration and spoken-answer path used by BYDMate itself.
 */
class DiLink3E2EBridge(context: Context) {
    @EntryPoint
    @InstallIn(SingletonComponent::class)
    interface Dependencies {
        fun agentOrchestrator(): AgentOrchestrator
        fun ttsEngine(): TtsEngine
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
                error = "BYDMate agent is disabled or not configured. Enable AI Assistant and configure provider/API key in Integrations.",
            )
        }
    }
}
