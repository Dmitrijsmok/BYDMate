#!/usr/bin/env python3
from pathlib import Path

VERSION_CODE = "60029"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Build79 anchor missing: {label}")
    return text.replace(old, new, 1)


# 1) Field identity: monotonic update over Build78.
p = Path("app/build.gradle.kts")
s = p.read_text()
s = replace_once(s, "        versionCode = 60028", f"        versionCode = {VERSION_CODE}", "versionCode")
s = replace_once(
    s,
    '            versionNameSuffix = "-dilink3-production-build78"',
    '            versionNameSuffix = "-dilink3-production-build79"',
    "versionNameSuffix",
)
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = replace_once(
    s,
    'android:label="BYDMate DiLink3 Build78"',
    'android:label="BYDMate DiLink3 Build79"',
    "manifest label",
)
p.write_text(s)


# 2) Retire Marusya completely from the selectable catalog/UI.
#    IMPORTANT: there is no Marusya-specific model archive to delete. It was only Supertonic sid=0
#    and shared modelDirId=supertonic-ru with Mark/Sofia, so deleting that directory would break them.
p = Path("app/src/main/kotlin/com/bydmate/app/voice/TtsVoiceCatalog.kt")
s = p.read_text()
marusya_block = '''        TtsVoice(
            id = "marusya", labelRes = R.string.settings_tts_voice_marusya, url = SUPERTONIC_URL,
            gender = TtsGender.FEMALE, engine = TtsVoiceEngine.SUPERTONIC,
            modelDirId = "supertonic-ru", speakerId = 0, sizeMb = 145,
        ),
'''
if marusya_block not in s:
    raise SystemExit("Build79 anchor missing: Marusya catalog block")
s = s.replace(marusya_block, "", 1)
p.write_text(s)

for values_dir in ("values", "values-en"):
    p = Path(f"app/src/main/res/{values_dir}/strings.xml")
    if p.exists():
        lines = p.read_text().splitlines(keepends=True)
        cleaned = [line for line in lines if 'name="settings_tts_voice_marusya"' not in line]
        p.write_text("".join(cleaned))

# Persistently migrate an installed Build77/78 selection of Marusya back to Dmitri.
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsViewModel.kt")
s = p.read_text()
old = '''            val ttsVoice = TtsVoiceCatalog.byId(
                appContext.getSharedPreferences("voice", Context.MODE_PRIVATE)
                    .getString("tts_voice", TtsModelManager.DEFAULT_VOICE_ID) ?: TtsModelManager.DEFAULT_VOICE_ID,
            ).id
'''
new = '''            val ttsPrefsForMigration = appContext.getSharedPreferences("voice", Context.MODE_PRIVATE)
            val rawTtsVoice = ttsPrefsForMigration
                .getString("tts_voice", TtsModelManager.DEFAULT_VOICE_ID) ?: TtsModelManager.DEFAULT_VOICE_ID
            val ttsVoice = TtsVoiceCatalog.byId(rawTtsVoice).id
            if (rawTtsVoice == "marusya") {
                ttsPrefsForMigration.edit().putString("tts_voice", ttsVoice).apply()
            }
'''
s = replace_once(s, old, new, "Marusya pref migration")
p.write_text(s)


# 3) Expand Build78 diagnostics: ASR/VAD/decode, agent rounds/tools, actual AudioTrack route.
p = Path("app/src/main/kotlin/com/bydmate/app/voice/SherpaTtsEngine.kt")
s = p.read_text()
s = replace_once(
    s,
    '''    @Volatile var asrAtMs: Long = 0L
    @Volatile var agentStartAtMs: Long = 0L
''',
    '''    @Volatile var asrAtMs: Long = 0L
    @Volatile var asrSpeechStartAtMs: Long = 0L
    @Volatile var asrSpeechEndAtMs: Long = 0L
    @Volatile var asrVadReadyAtMs: Long = 0L
    @Volatile var asrDecodeStartAtMs: Long = 0L
    @Volatile var asrDecodeEndAtMs: Long = 0L
    @Volatile var agentStartAtMs: Long = 0L
''',
    "ASR detail fields",
)
s = replace_once(
    s,
    '''    @Volatile var agentFinishedAtMs: Long = 0L

    @Volatile var ttsRequestAtMs: Long = 0L
''',
    '''    @Volatile var agentFinishedAtMs: Long = 0L
    @Volatile var agentRoundCount: Int = 0
    @Volatile var agentToolCount: Int = 0
    @Volatile var agentFirstToolName: String = ""
    @Volatile var agentFirstToolStartAtMs: Long = 0L
    @Volatile var agentFirstToolEndAtMs: Long = 0L

    @Volatile var ttsRequestAtMs: Long = 0L
''',
    "agent detail fields",
)
s = replace_once(
    s,
    '''    @Volatile var ttsError: String = ""

    @Synchronized
''',
    '''    @Volatile var ttsError: String = ""
    // Persists across turns while the same AudioTrack is reused. Blank means no track created yet.
    @Volatile var audioRoute: String = ""

    @Synchronized
''',
    "audio route field",
)
s = replace_once(
    s,
    '''        asrAtMs = 0L
        agentStartAtMs = 0L
''',
    '''        asrAtMs = 0L
        asrSpeechStartAtMs = 0L
        asrSpeechEndAtMs = 0L
        asrVadReadyAtMs = 0L
        asrDecodeStartAtMs = 0L
        asrDecodeEndAtMs = 0L
        agentStartAtMs = 0L
''',
    "ASR detail reset",
)
s = replace_once(
    s,
    '''        agentFirstSentenceAtMs = 0L
        agentFinishedAtMs = 0L
        clearTts()
''',
    '''        agentFirstSentenceAtMs = 0L
        agentFinishedAtMs = 0L
        agentRoundCount = 0
        agentToolCount = 0
        agentFirstToolName = ""
        agentFirstToolStartAtMs = 0L
        agentFirstToolEndAtMs = 0L
        clearTts()
''',
    "agent detail reset",
)

# Record which AudioTrack route actually survived initialization on THIS car.
old = '''        val result = createTrackWithFallback(
            primary = { newTrack(bydVoiceAttributes(), format, bufLen).takeIfInitialized() },
            fallback = { viaFallback = true; newTrack(accessibilityAttributes(), format, bufLen) },
        )
        if (result.state != AudioTrack.STATE_INITIALIZED) {
'''
new = '''        val result = createTrackWithFallback(
            primary = { newTrack(bydVoiceAttributes(), format, bufLen).takeIfInitialized() },
            fallback = { viaFallback = true; newTrack(accessibilityAttributes(), format, bufLen) },
        )
        VoiceTimingDiagnostics.audioRoute = if (viaFallback) "ACCESSIBILITY" else "BTTS${BYD_STREAM_BTTS}"
        if (result.state != AudioTrack.STATE_INITIALIZED) {
'''
s = replace_once(s, old, new, "AudioTrack route diagnostic")
p.write_text(s)


# 4) Instrument GigaAM itself, so PTT->ASR can be split into speech/VAD/decode instead of guessing.
p = Path("app/src/main/kotlin/com/bydmate/app/voice/GigaAmAsrEngine.kt")
s = p.read_text()
old = '''                if (vad.isSpeechDetected()) {
                    if (!speaking) {
                        speaking = true
                        silentMs = 0L
                        emit(ContinuousAsrEvent.SpeechStart)
                    }
                } else {
                    silentMs += (shorts.size * 1000L) / SAMPLE_RATE
                    emit(ContinuousAsrEvent.SilenceTick(silentMs))
                }
                while (!vad.empty()) {
                    val segment = vad.front()
                    vad.pop()
                    speaking = false
                    val text = recognizer.decode(segment)
                    if (text.isNotBlank()) emit(ContinuousAsrEvent.Utterance(text))
                }
'''
new = '''                if (vad.isSpeechDetected()) {
                    if (!speaking) {
                        speaking = true
                        silentMs = 0L
                        if (VoiceTimingDiagnostics.asrSpeechStartAtMs == 0L) {
                            VoiceTimingDiagnostics.asrSpeechStartAtMs = System.currentTimeMillis()
                        }
                        emit(ContinuousAsrEvent.SpeechStart)
                    }
                } else {
                    if (speaking && VoiceTimingDiagnostics.asrSpeechEndAtMs == 0L) {
                        VoiceTimingDiagnostics.asrSpeechEndAtMs = System.currentTimeMillis()
                    }
                    silentMs += (shorts.size * 1000L) / SAMPLE_RATE
                    emit(ContinuousAsrEvent.SilenceTick(silentMs))
                }
                while (!vad.empty()) {
                    if (VoiceTimingDiagnostics.asrVadReadyAtMs == 0L) {
                        VoiceTimingDiagnostics.asrVadReadyAtMs = System.currentTimeMillis()
                    }
                    val segment = vad.front()
                    vad.pop()
                    speaking = false
                    if (VoiceTimingDiagnostics.asrDecodeStartAtMs == 0L) {
                        VoiceTimingDiagnostics.asrDecodeStartAtMs = System.currentTimeMillis()
                    }
                    val text = recognizer.decode(segment)
                    if (VoiceTimingDiagnostics.asrDecodeEndAtMs == 0L) {
                        VoiceTimingDiagnostics.asrDecodeEndAtMs = System.currentTimeMillis()
                    }
                    if (text.isNotBlank()) emit(ContinuousAsrEvent.Utterance(text))
                }
'''
s = replace_once(s, old, new, "GigaAM VAD/decode timing")
p.write_text(s)


# 5) Agent transport: preserve FIRST HTTP request and FIRST streamed content delta across tool rounds.
p = Path("app/src/main/kotlin/com/bydmate/app/agent/LlmAgentBackend.kt")
s = p.read_text()
s = replace_once(
    s,
    '''                    VoiceTimingDiagnostics.agentFirstDeltaAtMs = nowMs()
''',
    '''                    if (VoiceTimingDiagnostics.agentFirstDeltaAtMs == 0L) {
                        VoiceTimingDiagnostics.agentFirstDeltaAtMs = nowMs()
                    }
''',
    "first content delta only",
)
s = replace_once(
    s,
    '''        VoiceTimingDiagnostics.agentHttpStartAtMs = startedAt
''',
    '''        if (VoiceTimingDiagnostics.agentHttpStartAtMs == 0L) {
            VoiceTimingDiagnostics.agentHttpStartAtMs = startedAt
        }
''',
    "first HTTP round only",
)
p.write_text(s)

p = Path("app/src/main/kotlin/com/bydmate/app/agent/AgentOrchestrator.kt")
s = p.read_text()
s = replace_once(
    s,
    '''import com.bydmate.app.voice.AgentPersonaPrompt
''',
    '''import com.bydmate.app.voice.AgentPersonaPrompt
import com.bydmate.app.voice.VoiceTimingDiagnostics
''',
    "VoiceTimingDiagnostics import",
)
s = replace_once(
    s,
    '''        repeat(MAX_ITERATIONS) {
            // Fresh chunker per LLM turn: a tool round's unterminated tail is discarded when
''',
    '''        repeat(MAX_ITERATIONS) {
            VoiceTimingDiagnostics.agentRoundCount += 1
            // Fresh chunker per LLM turn: a tool round's unterminated tail is discarded when
''',
    "agent round counter",
)
s = replace_once(
    s,
    '''                callCounts[key] = seen + 1
                val res = tools.execute(call, allowAutomationTools)
                // ok = the tool JSON has no "error" key; unparseable output counts as ok
''',
    '''                callCounts[key] = seen + 1
                VoiceTimingDiagnostics.agentToolCount += 1
                val firstTimedTool = VoiceTimingDiagnostics.agentFirstToolStartAtMs == 0L
                if (firstTimedTool) {
                    VoiceTimingDiagnostics.agentFirstToolName = call.name
                    VoiceTimingDiagnostics.agentFirstToolStartAtMs = System.currentTimeMillis()
                }
                val res = tools.execute(call, allowAutomationTools)
                if (firstTimedTool) {
                    VoiceTimingDiagnostics.agentFirstToolEndAtMs = System.currentTimeMillis()
                }
                // ok = the tool JSON has no "error" key; unparseable output counts as ok
''',
    "agent tool timing",
)
p.write_text(s)


# 6) Human-readable Build79 panel: deeper speed breakdown + live read-only audio stream probe.
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text()
old = '''            val _diagTick = diagRefresh // explicit read keeps the polling recomposition dependency

            HorizontalDivider(color = TextMuted, modifier = Modifier.padding(vertical = 6.dp))
'''
new = '''            val _diagTick = diagRefresh // explicit read keeps the polling recomposition dependency
            val diagContext = LocalContext.current
            val diagAudio = diagContext.getSystemService(Context.AUDIO_SERVICE) as? android.media.AudioManager
            fun streamState(id: Int): String = if (diagAudio == null) "—" else runCatching {
                val cur = diagAudio.getStreamVolume(id)
                val max = diagAudio.getStreamMaxVolume(id)
                val muted = runCatching { diagAudio.isStreamMute(id) }.getOrDefault(false)
                "$cur/$max" + if (muted) " mute" else ""
            }.getOrElse { "n/a" }
            fun runtimeAudioConst(className: String, fieldName: String): String = runCatching {
                Class.forName(className).getField(fieldName).getInt(null).toString()
            }.getOrElse { "—" }

            HorizontalDivider(color = TextMuted, modifier = Modifier.padding(vertical = 6.dp))
'''
s = replace_once(s, old, new, "audio diagnostic helpers")

old = '''            Text(
                "PTT → ASR текст: ${sec(msBetween(diag.pttAtMs, diag.asrAtMs))}",
                color = TextMuted, fontSize = 10.sp,
            )
'''
new = '''            Text(
                "ASR всего: PTT → текст ${sec(msBetween(diag.pttAtMs, diag.asrAtMs))}",
                color = TextMuted, fontSize = 10.sp,
            )
            Text(
                "ASR детали: до речи ${sec(msBetween(diag.pttAtMs, diag.asrSpeechStartAtMs))} · " +
                    "речь/VAD ${sec(msBetween(diag.asrSpeechStartAtMs, diag.asrSpeechEndAtMs))} · " +
                    "VAD finalize ${sec(msBetween(diag.asrSpeechEndAtMs, diag.asrVadReadyAtMs))} · " +
                    "GigaAM decode ${sec(msBetween(diag.asrDecodeStartAtMs, diag.asrDecodeEndAtMs))}",
                color = TextMuted, fontSize = 10.sp,
            )
'''
s = replace_once(s, old, new, "ASR detailed panel")

old = '''            Text(
                "API: до 1-го токена ${sec(msBetween(diag.agentHttpStartAtMs, diag.agentFirstDeltaAtMs))} · " +
                    "до 1-й фразы ${sec(msBetween(diag.agentStartAtMs, diag.agentFirstSentenceAtMs))} · " +
                    "весь ответ ${sec(msBetween(diag.agentStartAtMs, diag.agentFinishedAtMs))}",
                color = TextMuted, fontSize = 10.sp,
            )
'''
new = '''            Text(
                "Agent/API: до 1-го content ${sec(msBetween(diag.agentHttpStartAtMs, diag.agentFirstDeltaAtMs))} · " +
                    "до 1-й фразы ${sec(msBetween(diag.agentStartAtMs, diag.agentFirstSentenceAtMs))} · " +
                    "весь ответ ${sec(msBetween(diag.agentStartAtMs, diag.agentFinishedAtMs))}",
                color = TextMuted, fontSize = 10.sp,
            )
            Text(
                "Agent loop: rounds=${diag.agentRoundCount} · tools=${diag.agentToolCount} · " +
                    "1-й tool=${diag.agentFirstToolName.ifBlank { "—" }} ${sec(msBetween(diag.agentFirstToolStartAtMs, diag.agentFirstToolEndAtMs))}",
                color = TextMuted, fontSize = 10.sp,
            )
'''
s = replace_once(s, old, new, "agent detailed panel")

old = '''            Text(
                "TTS data: text=${diag.ttsTextLength} chars · samples=${if (diag.ttsSamples >= 0) diag.ttsSamples else "—"} · " +
                    "rate=${if (diag.ttsSampleRate > 0) diag.ttsSampleRate else "—"}",
                color = TextMuted, fontSize = 10.sp,
            )
'''
new = '''            Text(
                "TTS data: text=${diag.ttsTextLength} chars · samples=${if (diag.ttsSamples >= 0) diag.ttsSamples else "—"} · " +
                    "rate=${if (diag.ttsSampleRate > 0) diag.ttsSampleRate else "—"}",
                color = TextMuted, fontSize = 10.sp,
            )
            val synthMs = msBetween(diag.ttsSynthStartAtMs, diag.ttsSynthEndAtMs)
            val audioDurationMs = if (diag.ttsSamples > 0 && diag.ttsSampleRate > 0)
                diag.ttsSamples * 1000.0 / diag.ttsSampleRate else null
            val rtf = if (synthMs != null && audioDurationMs != null && audioDurationMs > 0.0)
                synthMs / audioDurationMs else null
            Text(
                "TTS скорость: audio=${if (audioDurationMs == null) "—" else java.lang.String.format(java.util.Locale.US, "%.2f с", audioDurationMs / 1000.0)} · " +
                    "RTF=${if (rtf == null) "—" else java.lang.String.format(java.util.Locale.US, "%.2fx", rtf)}",
                color = TextMuted, fontSize = 10.sp,
            )
            Text(
                "Audio route: ${diag.audioRoute.ifBlank { "—" }} · media(3)=${streamState(3)} · s15=${streamState(15)} · s16=${streamState(16)} · s17=${streamState(17)}",
                color = TextMuted, fontSize = 10.sp,
            )
            Text(
                "Framework streams: AudioManager NAVI=${runtimeAudioConst("android.media.AudioManager", "STREAM_NAVI")} " +
                    "BTTS=${runtimeAudioConst("android.media.AudioManager", "STREAM_BTTS")} · " +
                    "AudioSystem NAVI=${runtimeAudioConst("android.media.AudioSystem", "STREAM_NAVI")} " +
                    "BTTS=${runtimeAudioConst("android.media.AudioSystem", "STREAM_BTTS")}",
                color = TextMuted, fontSize = 10.sp,
            )
'''
s = replace_once(s, old, new, "TTS RTF and audio streams panel")
p.write_text(s)

print("Build79 applied: Marusya retired; deep ASR/agent/TTS/audio diagnostics enabled")
