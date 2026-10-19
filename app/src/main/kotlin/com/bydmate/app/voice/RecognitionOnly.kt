package com.bydmate.app.voice

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.firstOrNull
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull

@Suppress("TooGenericExceptionCaught") // Native capture/decoder failures must be reported without entering command routing.
internal suspend fun runRecognitionOnly(
    capture: AudioCapture,
    asr: ContinuousAsr,
    attempt: AsrLabAttempt,
    timeoutMs: Long = 30_000,
): AsrLabResult = withContext(Dispatchers.IO) {
    try {
        if (!asr.isReady()) return@withContext attempt.result("offline model unavailable")
        var completed = false
        val event = withTimeoutOrNull(timeoutMs) {
            if (asr.requiresWarmBeforeListening()) asr.warmUp()
            val pcm = capture.captureSessionObserved(timeoutMs, attempt) { Unit }.map { it.pcm }
            asr.transcribeMeasured(pcm, attempt).firstOrNull { it is ContinuousAsrEvent.Utterance }.also { completed = true }
        } as? ContinuousAsrEvent.Utterance
        if (event == null) attempt.result(if (completed) "capture ended without transcript" else "timeout") else {
            attempt.decoded(event.text)
            attempt.result(if (event.text.isEmpty()) "empty transcript" else null)
        }
    } catch (cancelled: CancellationException) {
        throw cancelled
    } catch (error: Exception) {
        attempt.result("recognition failed: ${error.javaClass.simpleName}")
    }
}
