package com.bydmate.app.voice

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Lightweight process-local diagnostics for DiLink3 voice bring-up. */
object DiLink3VoiceDiagnostics {
    private val _lastEvent = MutableStateFlow("Idle")
    val lastEvent: StateFlow<String> = _lastEvent.asStateFlow()

    private val _micSource = MutableStateFlow("not opened")
    val micSource: StateFlow<String> = _micSource.asStateFlow()

    private val _pcmFrames = MutableStateFlow(0L)
    val pcmFrames: StateFlow<Long> = _pcmFrames.asStateFlow()

    private val _pcmSamples = MutableStateFlow(0L)
    val pcmSamples: StateFlow<Long> = _pcmSamples.asStateFlow()

    private val _speechStarts = MutableStateFlow(0L)
    val speechStarts: StateFlow<Long> = _speechStarts.asStateFlow()

    private val _heard = MutableStateFlow("")
    val heard: StateFlow<String> = _heard.asStateFlow()

    private val _lastError = MutableStateFlow("")
    val lastError: StateFlow<String> = _lastError.asStateFlow()

    private val _recording = MutableStateFlow(false)
    val recording: StateFlow<Boolean> = _recording.asStateFlow()

    fun resetForSession() {
        _lastEvent.value = "PTT pressed"
        _micSource.value = "opening..."
        _pcmFrames.value = 0
        _pcmSamples.value = 0
        _speechStarts.value = 0
        _heard.value = ""
        _lastError.value = ""
        _recording.value = false
    }

    fun event(text: String) { _lastEvent.value = text }
    fun micOpened(source: Int) {
        _micSource.value = "$source (${sourceName(source)})"
        _recording.value = true
        _lastEvent.value = "AudioRecord started"
    }
    fun micFailed(reason: String) {
        _micSource.value = "FAILED"
        _recording.value = false
        error(reason)
    }
    fun frame(samples: Int) {
        _pcmFrames.value += 1
        _pcmSamples.value += samples
    }
    fun speechStart() {
        _speechStarts.value += 1
        _lastEvent.value = "SpeechStart"
    }
    fun transcript(text: String) {
        _heard.value = text
        _lastEvent.value = "Utterance decoded"
    }
    fun error(text: String) {
        _lastError.value = text
        _lastEvent.value = "ERROR"
    }
    fun stopped() {
        _recording.value = false
        _lastEvent.value = "Session stopped"
    }

    private fun sourceName(source: Int): String = when (source) {
        6 -> "VOICE_RECOGNITION"
        7 -> "VOICE_COMMUNICATION"
        1 -> "MIC"
        9 -> "UNPROCESSED"
        0 -> "DEFAULT"
        else -> "UNKNOWN"
    }
}
