package com.bydmate.app.ui.diagnostics

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioManager
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.bydmate.app.voice.AudioCapture
import com.bydmate.app.voice.ContinuousAsr
import com.bydmate.app.voice.ContinuousAsrEvent
import com.bydmate.app.voice.DiLink3AudioSourceProbe
import com.bydmate.app.voice.TtsModelManager
import com.bydmate.app.voice.TtsVoiceCatalog
import com.bydmate.app.voice.VoiceController
import com.bydmate.app.voice.VoiceUiState
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.launch

/** Visible, self-contained DiLink3 diagnostic panel. */
@Composable
fun DiLink3VoiceDebugPanel(
    voiceController: VoiceController,
    continuousAsr: ContinuousAsr,
    audioCapture: AudioCapture,
    ttsModelManager: TtsModelManager,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val voiceState by voiceController.state.collectAsState()
    val listening by voiceController.listening.collectAsState()
    val scope = rememberCoroutineScope()

    // Start collapsed so the diagnostic UI never blocks normal use after launch/update.
    var expanded by remember { mutableStateOf(false) }

    if (!expanded) {
        Card(modifier = modifier.fillMaxWidth()) {
            Button(
                onClick = { expanded = true },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(8.dp),
            ) {
                Text("OPEN DiLink3 VOICE DEBUG")
            }
        }
        return
    }

    val prefs = remember { context.getSharedPreferences("voice", Context.MODE_PRIVATE) }
    var refresh by remember { mutableLongStateOf(0L) }
    LaunchedEffect(Unit) {
        while (true) {
            kotlinx.coroutines.delay(500)
            refresh++
        }
    }

    val micGranted = ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
    val voiceEnabled = prefs.getBoolean("voice_enabled", false)
    val voiceLang = prefs.getString("voice_lang", "")?.ifBlank { "AUTO" } ?: "AUTO"
    val ttsEnabled = prefs.getBoolean("tts_enabled", false)
    val selectedVoiceId = prefs.getString("tts_voice", TtsModelManager.DEFAULT_VOICE_ID) ?: TtsModelManager.DEFAULT_VOICE_ID
    val selectedVoice = TtsVoiceCatalog.byId(selectedVoiceId)
    val ttsReady = ttsModelManager.isReady(selectedVoice)
    val asrReady = continuousAsr.isReady()

    var rawJob by remember { mutableStateOf<Job?>(null) }
    var rawStatus by remember { mutableStateOf("idle") }
    var rawFrames by remember { mutableLongStateOf(0L) }
    var rawSamples by remember { mutableLongStateOf(0L) }
    var rawSpeechStarts by remember { mutableLongStateOf(0L) }
    var rawHeard by remember { mutableStateOf("") }
    var rawError by remember { mutableStateOf("") }

    var probeRunning by remember { mutableStateOf(false) }
    var probeResults by remember { mutableStateOf<List<DiLink3AudioSourceProbe.Result>>(emptyList()) }
    var probeError by remember { mutableStateOf("") }

    // Alternative ASR path: Android's installed SpeechRecognizer service. This does not use GigaAM.
    val systemAsrAvailable = remember { SpeechRecognizer.isRecognitionAvailable(context) }
    var systemAsrRunning by remember { mutableStateOf(false) }
    var systemAsrStatus by remember { mutableStateOf("idle") }
    var systemAsrHeard by remember { mutableStateOf("") }
    var systemAsrError by remember { mutableStateOf("") }
    var systemAsrPartial by remember { mutableStateOf("") }

    val systemRecognizer = remember(systemAsrAvailable) {
        if (systemAsrAvailable) SpeechRecognizer.createSpeechRecognizer(context) else null
    }

    DisposableEffect(systemRecognizer) {
        onDispose {
            runCatching { systemRecognizer?.cancel() }
            runCatching { systemRecognizer?.destroy() }
        }
    }

    LaunchedEffect(systemRecognizer) {
        systemRecognizer?.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) {
                systemAsrRunning = true
                systemAsrStatus = "ready - speak now"
            }

            override fun onBeginningOfSpeech() {
                systemAsrStatus = "speech detected"
            }

            override fun onRmsChanged(rmsdB: Float) {
                if (systemAsrRunning) systemAsrStatus = "listening rms=${"%.1f".format(rmsdB)}"
            }

            override fun onBufferReceived(buffer: ByteArray?) = Unit

            override fun onEndOfSpeech() {
                systemAsrStatus = "decoding..."
            }

            override fun onError(error: Int) {
                systemAsrRunning = false
                systemAsrError = "$error / ${speechErrorName(error)}"
                systemAsrStatus = "ERROR"
            }

            override fun onResults(results: Bundle?) {
                systemAsrRunning = false
                val heard = results
                    ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    ?.joinToString(" | ")
                    .orEmpty()
                systemAsrHeard = heard
                systemAsrStatus = if (heard.isBlank()) "finished - no text" else "decoded"
            }

            override fun onPartialResults(partialResults: Bundle?) {
                systemAsrPartial = partialResults
                    ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    ?.joinToString(" | ")
                    .orEmpty()
            }

            override fun onEvent(eventType: Int, params: Bundle?) = Unit
        })
    }

    val audioManager = remember { context.getSystemService(Context.AUDIO_SERVICE) as AudioManager }
    val activeRecording = runCatching {
        audioManager.activeRecordingConfigurations
            .joinToString { cfg -> "src=${cfg.audioSource}, session=${cfg.clientAudioSessionId}, rate=${cfg.format.sampleRate}" }
    }.getOrDefault("").ifBlank { "none" }

    val stateText = when (val s = voiceState) {
        VoiceUiState.Idle -> "Idle"
        VoiceUiState.Listening -> "Listening"
        VoiceUiState.Thinking -> "Thinking"
        is VoiceUiState.Done -> "Done: ${s.transcript}"
        is VoiceUiState.Blocked -> "Blocked: ${s.reason}"
        is VoiceUiState.NotUnderstood -> "NotUnderstood: ${s.transcript}"
        is VoiceUiState.AgentAnswer -> "AgentAnswer: ${s.text}"
    }

    Card(modifier = modifier.fillMaxWidth()) {
        // The header is outside the scrolling content so CLOSE is always visible.
        Column(modifier = Modifier.fillMaxWidth()) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(
                    "DiLink3 Voice Debug",
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.weight(1f),
                )
                Button(onClick = { expanded = false }) {
                    Text("CLOSE")
                }
            }

            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp, vertical = 6.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Text(
                    "CLOSE stays pinned above this scrolling area. Re-open with OPEN DiLink3 VOICE DEBUG.",
                    style = MaterialTheme.typography.bodySmall,
                )

                DebugRow("Mic permission", yesNo(micGranted))
                DebugRow("Voice commands", yesNo(voiceEnabled))
                DebugRow("Voice language", voiceLang)
                DebugRow("GigaAM ASR ready", yesNo(asrReady))
                DebugRow("Android System ASR", if (systemAsrAvailable) "AVAILABLE" else "NOT AVAILABLE")
                DebugRow("TTS enabled", yesNo(ttsEnabled))
                DebugRow("TTS voice", "${selectedVoice.id} / ${selectedVoice.engine}")
                DebugRow("TTS model ready", yesNo(ttsReady))
                DebugRow("Controller listening", yesNo(listening))
                DebugRow("Controller state", stateText)
                DebugRow("Android active recording", activeRecording)

                Text("STEP 1 - Android microphone sources", style = MaterialTheme.typography.titleSmall)
                Text(
                    "This test does NOT use GigaAM, OpenRouter, VoiceController or TTS. It opens each Android microphone source, starts recording and reads raw PCM.",
                    style = MaterialTheme.typography.bodySmall,
                )
                Button(
                    enabled = micGranted && !probeRunning && rawJob?.isActive != true && !listening && !systemAsrRunning,
                    onClick = {
                        probeRunning = true
                        probeResults = emptyList()
                        probeError = ""
                        scope.launch {
                            try {
                                probeResults = DiLink3AudioSourceProbe.run()
                            } catch (t: Throwable) {
                                probeError = "${t::class.java.simpleName}: ${t.message}"
                            } finally {
                                probeRunning = false
                            }
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(if (probeRunning) "PROBING..." else "PROBE MIC SOURCES")
                }
                if (probeResults.isEmpty()) {
                    DebugRow("Probe", if (probeRunning) "running..." else "not run yet")
                } else {
                    probeResults.forEach { result ->
                        DebugRow(result.name, result.summary())
                    }
                }
                if (probeError.isNotBlank()) DebugRow("Probe ERROR", probeError)

                Text("STEP 2A - Android System SpeechRecognizer", style = MaterialTheme.typography.titleSmall)
                Text(
                    "Alternative engine test. It bypasses the GigaAM model and uses the speech recognition service installed in DiLink. If this decodes speech while GigaAM does not, the microphone path is good and the problem is GigaAM/model download or decoding.",
                    style = MaterialTheme.typography.bodySmall,
                )
                Button(
                    enabled = micGranted && systemAsrAvailable && !probeRunning && rawJob?.isActive != true && !listening,
                    onClick = {
                        if (systemAsrRunning) {
                            runCatching { systemRecognizer?.cancel() }
                            systemAsrRunning = false
                            systemAsrStatus = "stopped"
                        } else {
                            systemAsrHeard = ""
                            systemAsrPartial = ""
                            systemAsrError = ""
                            systemAsrStatus = "starting..."
                            val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                                putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                                putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 5)
                                when (voiceLang.uppercase()) {
                                    "RU", "RU-RU" -> putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ru-RU")
                                    "EN", "EN-US" -> putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-US")
                                    "LV", "LV-LV" -> putExtra(RecognizerIntent.EXTRA_LANGUAGE, "lv-LV")
                                }
                            }
                            runCatching {
                                systemRecognizer?.startListening(intent)
                                systemAsrRunning = true
                            }.onFailure { t ->
                                systemAsrRunning = false
                                systemAsrStatus = "ERROR"
                                systemAsrError = "${t::class.java.simpleName}: ${t.message}"
                            }
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(if (systemAsrRunning) "STOP SYSTEM ASR" else "TEST ANDROID SYSTEM ASR")
                }
                DebugRow("System ASR status", systemAsrStatus)
                DebugRow("System ASR partial", systemAsrPartial.ifBlank { "<none>" })
                DebugRow("System ASR HEARD", systemAsrHeard.ifBlank { "<nothing decoded>" })
                DebugRow("System ASR ERROR", systemAsrError.ifBlank { "none" })

                Text("STEP 2B - VoiceController / RAW GigaAM", style = MaterialTheme.typography.titleSmall)

                Button(
                    enabled = !probeRunning && !systemAsrRunning,
                    onClick = { voiceController.onPttPressed() },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(if (listening) "STOP Voice" else "START Voice")
                }

                Button(
                    enabled = micGranted && asrReady && !probeRunning && !systemAsrRunning,
                    onClick = {
                        if (rawJob?.isActive == true) {
                            rawJob?.cancel()
                            rawStatus = "stopping..."
                        } else {
                            rawFrames = 0
                            rawSamples = 0
                            rawSpeechStarts = 0
                            rawHeard = ""
                            rawError = ""
                            rawStatus = "starting mic + GigaAM..."
                            rawJob = scope.launch {
                                try {
                                    val pcm = audioCapture.captureSession(maxMs = 20_000)
                                        .onEach { frame ->
                                            rawFrames++
                                            rawSamples += frame.size
                                            rawStatus = "PCM flowing"
                                        }
                                    continuousAsr.transcribe(pcm).collect { ev ->
                                        when (ev) {
                                            ContinuousAsrEvent.SpeechStart -> {
                                                rawSpeechStarts++
                                                rawStatus = "speech detected"
                                            }
                                            is ContinuousAsrEvent.SilenceTick -> {
                                                if (rawSpeechStarts == 0L) rawStatus = "listening / silence ${ev.silentMs}ms"
                                            }
                                            is ContinuousAsrEvent.Utterance -> {
                                                rawHeard = ev.text
                                                rawStatus = "decoded"
                                            }
                                        }
                                    }
                                    rawStatus = "finished"
                                } catch (t: Throwable) {
                                    if (t is CancellationException) {
                                        rawStatus = "stopped"
                                        throw t
                                    }
                                    rawError = "${t::class.java.simpleName}: ${t.message}"
                                    rawStatus = "ERROR"
                                }
                            }
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(if (rawJob?.isActive == true) "STOP RAW" else "RAW GIGAAM ASR TEST")
                }

                Text("RAW ASR TEST (AudioCapture -> GigaAM)", style = MaterialTheme.typography.titleSmall)
                DebugRow("Raw status", rawStatus)
                DebugRow("PCM frames", rawFrames.toString())
                DebugRow("PCM samples", rawSamples.toString())
                DebugRow("SpeechStart count", rawSpeechStarts.toString())
                DebugRow("HEARD", rawHeard.ifBlank { "<nothing decoded>" })
                DebugRow("ERROR", rawError.ifBlank { "none" })

                Text(
                    "Interpretation: mic probe read=OK proves raw PCM access. System ASR HEARD text proves DiLink's installed recognizer can use the mic without GigaAM. If System ASR works but GigaAM stays not ready or fails, focus on the GigaAM model/download source. If System ASR reports unavailable, DiLink has no compatible recognition service installed.",
                    style = MaterialTheme.typography.bodySmall,
                )

                Button(
                    onClick = { expanded = false },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("CLOSE DEBUG")
                }
            }
        }
    }
}

@Composable
private fun DebugRow(label: String, value: String) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .padding(horizontal = 8.dp, vertical = 5.dp)
    ) {
        Text(label, style = MaterialTheme.typography.labelSmall)
        Text(
            value,
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.fillMaxWidth(),
            softWrap = true,
        )
    }
}

private fun yesNo(value: Boolean): String = if (value) "YES" else "NO"

private fun speechErrorName(error: Int): String = when (error) {
    SpeechRecognizer.ERROR_AUDIO -> "AUDIO"
    SpeechRecognizer.ERROR_CLIENT -> "CLIENT"
    SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "INSUFFICIENT_PERMISSIONS"
    SpeechRecognizer.ERROR_NETWORK -> "NETWORK"
    SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "NETWORK_TIMEOUT"
    SpeechRecognizer.ERROR_NO_MATCH -> "NO_MATCH"
    SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "RECOGNIZER_BUSY"
    SpeechRecognizer.ERROR_SERVER -> "SERVER"
    SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "SPEECH_TIMEOUT"
    else -> "UNKNOWN"
}
