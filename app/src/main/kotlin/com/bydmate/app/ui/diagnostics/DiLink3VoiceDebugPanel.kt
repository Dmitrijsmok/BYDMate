package com.bydmate.app.ui.diagnostics

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioManager
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
import com.bydmate.app.voice.TtsModelManager
import com.bydmate.app.voice.TtsVoiceCatalog
import com.bydmate.app.voice.VoiceController
import com.bydmate.app.voice.VoiceUiState
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.launch

/** Visible, self-contained DiLink3 diagnostic panel. It intentionally includes a RAW ASR test
 * that bypasses VoiceController/gates/routing and feeds AudioCapture directly into GigaAM. */
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
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text("DiLink3 Voice Debug", style = MaterialTheme.typography.titleMedium)
            DebugRow("Mic permission", yesNo(micGranted))
            DebugRow("Voice commands", yesNo(voiceEnabled))
            DebugRow("Voice language", voiceLang)
            DebugRow("GigaAM ASR ready", yesNo(asrReady))
            DebugRow("TTS enabled", yesNo(ttsEnabled))
            DebugRow("TTS voice", "${selectedVoice.id} / ${selectedVoice.engine}")
            DebugRow("TTS model ready", yesNo(ttsReady))
            DebugRow("Controller listening", yesNo(listening))
            DebugRow("Controller state", stateText)
            DebugRow("Android active recording", activeRecording)

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { voiceController.onPttPressed() }) {
                    Text(if (listening) "STOP Voice" else "START Voice")
                }
                Button(
                    enabled = micGranted && asrReady,
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
                ) {
                    Text(if (rawJob?.isActive == true) "STOP RAW" else "RAW ASR TEST")
                }
            }

            Text("RAW ASR TEST (bypasses VoiceController)", style = MaterialTheme.typography.titleSmall)
            DebugRow("Raw status", rawStatus)
            DebugRow("PCM frames", rawFrames.toString())
            DebugRow("PCM samples", rawSamples.toString())
            DebugRow("SpeechStart count", rawSpeechStarts.toString())
            DebugRow("HEARD", rawHeard.ifBlank { "<nothing decoded>" })
            DebugRow("ERROR", rawError.ifBlank { "none" })

            Text(
                "Interpretation: frames=0 means microphone/capture path failed. Frames>0 but SpeechStart=0 means VAD sees no speech. SpeechStart>0 but HEARD empty points to GigaAM decode/model. HEARD text proves mic + VAD + ASR all work.",
                style = MaterialTheme.typography.bodySmall,
            )
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
        Text(value, style = MaterialTheme.typography.bodySmall)
    }
}

private fun yesNo(value: Boolean): String = if (value) "YES" else "NO"
