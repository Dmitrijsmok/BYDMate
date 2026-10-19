package com.bydmate.app.voice

import android.content.Context
import com.bydmate.app.agent.AgentOrchestrator
import com.bydmate.app.data.automation.ActionDispatcher
import com.bydmate.app.data.automation.AutomationEngine
import com.bydmate.app.util.appStringsOver
import io.mockk.Called
import io.mockk.every
import io.mockk.mockk
import io.mockk.verify
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AsrLabSafetyTest {
    private val capture = mockk<AudioCapture>(relaxed = true)
    private val dispatcher = mockk<ActionDispatcher>(relaxed = true)
    private val automation = mockk<AutomationEngine>(relaxed = true)
    private val agent = mockk<AgentOrchestrator>(relaxed = true)
    private val tts = mockk<TtsEngine>(relaxed = true)
    private val models = mockk<TtsModelManager>(relaxed = true)
    private val resolver = mockk<VoiceAutomationResolver>(relaxed = true)
    private val context = mockk<Context>(relaxed = true)
    private val gate = mockk<VoiceGate>(relaxed = true)

    private fun controller(asr: ContinuousAsr): VoiceController {
        every { tts.speaking } returns MutableStateFlow(false)
        every { gate.isEnabled() } returns true
        every { capture.captureSessionObserved(any(), any(), any<(ShortArray) -> Unit>()) } returns
            flowOf(MicFrame(shortArrayOf(1), Unit))
        return VoiceController(capture, dispatcher, mockk(relaxed = true), gate, automation, resolver, agent,
            context, tts, VoiceJournal(), asr, { AgentIdentity("", AgentPersona.NAVIGATOR) },
            models, RuStressMarker { null }, { TtsVoiceCatalog.byId("dmitri") }, appStringsOver(context))
    }

    private fun noDownstreamCalls() {
        verify { listOf(dispatcher, automation, agent, tts, models, resolver) wasNot Called }
    }

    @Test fun `recognition-only returns exact vehicle and application commands without dispatch`() = runBlocking {
        for (text in listOf("Открой навигатор", "Включи обогрев", "  Точный текст!  ")) {
            val asr = object : ContinuousAsr {
                override fun isReady() = true
                override fun transcribe(pcm: Flow<ShortArray>) = flow {
                    pcm.collect { emit(ContinuousAsrEvent.Utterance(text)) }
                }
            }
            val voice = controller(asr)
            assertEquals(text, voice.runAsrLab(AsrLabAttempt(0)).transcript)
            assertFalse(voice.sessionActive())
        }
        noDownstreamCalls()
    }

    @Test fun `cancellation releases ownership and physical PTT cannot start a competing listener`() = runBlocking {
        val started = CompletableDeferred<Unit>()
        val asr = object : ContinuousAsr {
            override fun isReady() = true
            override fun transcribe(pcm: Flow<ShortArray>) = flow<ContinuousAsrEvent> {
                started.complete(Unit)
                awaitCancellation()
            }
        }
        val voice = controller(asr)
        val test = launch { voice.runAsrLab(AsrLabAttempt(400)) }
        withTimeout(5000) { started.await() }
        assertTrue(voice.sessionActive())
        voice.onPttPressed()
        assertEquals("voice session busy", voice.runAsrLab(AsrLabAttempt(0)).error)
        test.cancelAndJoin()
        assertFalse(voice.sessionActive())
        noDownstreamCalls()
    }

    @Test fun `missing model does not download or start the microphone`() = runBlocking {
        val asr = mockk<ContinuousAsr> { every { isReady() } returns false }
        val voice = controller(asr)
        assertEquals("offline model unavailable", voice.runAsrLab(AsrLabAttempt(0)).error)
        verify(exactly = 0) { capture.captureSessionObserved(any(), any(), any<(ShortArray) -> Unit>()) }
        noDownstreamCalls()
    }

    @Test fun `silence times out without downstream calls`() = runBlocking {
        val asr = object : ContinuousAsr {
            override fun isReady() = true
            override fun transcribe(pcm: Flow<ShortArray>) = flow<ContinuousAsrEvent> { awaitCancellation() }
        }
        controller(asr)
        assertEquals("timeout", runRecognitionOnly(capture, asr, AsrLabAttempt(0), timeoutMs = 20).error)
        noDownstreamCalls()
    }

    @Test fun `normal listening keeps microphone ownership when the lab requests a test`() = runBlocking {
        val started = CompletableDeferred<Unit>()
        val asr = object : ContinuousAsr {
            override fun isReady() = true
            override fun transcribe(pcm: Flow<ShortArray>) = flow<ContinuousAsrEvent> {
                started.complete(Unit)
                awaitCancellation()
            }
        }
        val voice = controller(asr)
        voice.onPttPressed()
        withTimeout(5000) { started.await() }
        assertTrue(voice.listening.value)
        assertEquals("voice session busy", voice.runAsrLab(AsrLabAttempt(0)).error)
        verify(exactly = 0) { capture.captureSessionObserved(any(), any(), any<(ShortArray) -> Unit>()) }
        voice.onPttPressed()
        withTimeout(5000) { while (voice.sessionActive()) delay(10) }
    }

    @Test fun `early end is not mislabeled as timeout`() = runBlocking {
        val asr = object : ContinuousAsr {
            override fun isReady() = true
            override fun transcribe(pcm: Flow<ShortArray>) = flowOf<ContinuousAsrEvent>()
        }
        val voice = controller(asr)
        assertEquals("capture ended without transcript", voice.runAsrLab(AsrLabAttempt(0)).error)
        noDownstreamCalls()
    }
}
