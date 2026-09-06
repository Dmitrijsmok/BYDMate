#!/usr/bin/env python3
from pathlib import Path

# Build64 field diagnostics after Build63 proved:
# - physical 304 DOES enter BYDMate on the first press;
# - mic/PCM/GigaAM/resolver all run;
# - the agent request returns AgentResult.Error;
# - the continuous session remains listening, so a later second press merely stops it.
#
# Build64 adds an in-app PTT button that enters the same VoiceController path, detailed
# first-press timing/source/audio diagnostics, clears stale heard/assistant cards at app UI
# creation, and closes the capture session after one routed utterance WITHOUT cancelling
# the completed route. This makes every subsequent physical press a fresh start.

# ---------------------------------------------------------------------------
# VoiceController
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/voice/VoiceController.kt')
s = p.read_text()

field_anchor = '    @Volatile private var build63EarlyReturnReason: String? = null\n'
if field_anchor not in s:
    raise SystemExit('Build64: Build63 state anchor not found')
fields = '''    @Volatile private var build64PttSeq: Int = 0
    @Volatile private var build64PttAtMs: Long = 0L
    @Volatile private var build64PttSource: String = "unknown"
    @Volatile private var build64PcmSeen: Boolean = false
    @Volatile private var build64SpeechSeen: Boolean = false
    @Volatile private var build64UtteranceSeen: Boolean = false
'''
s = s.replace(field_anchor, field_anchor + fields, 1)

# Public source-aware seam used by BOTH steering-wheel and debug-screen PTT.
method_anchor = '    fun sessionActive(): Boolean = listening.value || busy.get()\n'
if method_anchor not in s:
    raise SystemExit('Build64: sessionActive anchor not found')
method = r'''

    /** Build64: one source-aware entry point for physical and on-screen PTT comparison. */
    fun build64PttFrom(source: String) {
        val seq = synchronized(this) { build64PttSeq += 1; build64PttSeq }
        val now = System.currentTimeMillis()
        build64PttAtMs = now
        build64PttSource = source
        build64PcmSeen = false
        build64SpeechSeen = false
        build64UtteranceSeen = false
        val am = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        val music = runCatching { am.getStreamVolume(AudioManager.STREAM_MUSIC) }.getOrDefault(-1)
        val musicMax = runCatching { am.getStreamMaxVolume(AudioManager.STREAM_MUSIC) }.getOrDefault(-1)
        val call = runCatching { am.getStreamVolume(AudioManager.STREAM_VOICE_CALL) }.getOrDefault(-1)
        val callMax = runCatching { am.getStreamMaxVolume(AudioManager.STREAM_VOICE_CALL) }.getOrDefault(-1)
        DiLink3DebugLog.log(
            context,
            "BUILD64_PTT_DISPATCH",
            "seq=$seq source=$source listening=${_listening.value} busy=${busy.get()} gate=${gate.isEnabled()} " +
                "asrReady=${continuousAsr.isReady()} ttsEnabled=${gate.ttsEnabled()} " +
                "music=$music/$musicMax voiceCall=$call/$callMax mode=${am.mode} micMute=${am.isMicrophoneMute}"
        )
        onPttPressed()
        DiLink3DebugLog.log(
            context,
            "BUILD64_PTT_RETURN",
            "seq=$seq source=$source listening=${_listening.value} busy=${busy.get()} state=${_state.value::class.java.simpleName}"
        )
        scope.launch {
            delay(1_500L)
            if (build64PttSeq == seq) {
                DiLink3DebugLog.log(
                    context,
                    "BUILD64_FIRST_PRESS_1500MS",
                    "seq=$seq source=$source pcmSeen=$build64PcmSeen speechSeen=$build64SpeechSeen utteranceSeen=$build64UtteranceSeen " +
                        "listening=${_listening.value} busy=${busy.get()} sessionJobActive=${sessionJob?.isActive == true}"
                )
            }
            delay(4_000L)
            if (build64PttSeq == seq && !build64UtteranceSeen) {
                DiLink3DebugLog.log(
                    context,
                    "BUILD64_FIRST_PRESS_5500MS",
                    "seq=$seq source=$source pcmSeen=$build64PcmSeen speechSeen=$build64SpeechSeen utteranceSeen=$build64UtteranceSeen " +
                        "listening=${_listening.value} busy=${busy.get()} sessionJobActive=${sessionJob?.isActive == true}"
                )
            }
        }
    }
'''
s = s.replace(method_anchor, method_anchor + method, 1)

# Correlate first PCM with the PTT source/sequence and latency.
pcm_anchor = '''                        if (build59FirstPcm) {
                            build59FirstPcm = false
                            DiLink3DebugLog.log(context, "BUILD59_PCM_FIRST_FRAME", "samples=${it.size}")
                        }
'''
if pcm_anchor not in s:
    raise SystemExit('Build64: Build59 first PCM anchor not found')
pcm_new = pcm_anchor + '''                        if (!build64PcmSeen) {
                            build64PcmSeen = true
                            DiLink3DebugLog.log(
                                context,
                                "BUILD64_PCM_READY",
                                "seq=$build64PttSeq source=$build64PttSource afterPttMs=${System.currentTimeMillis() - build64PttAtMs} samples=${it.size}"
                            )
                        }
'''
s = s.replace(pcm_anchor, pcm_new, 1)

speech_anchor = '                            DiLink3DebugLog.log(context, "BUILD59_GIGAAM_SPEECH_START", "processingUtterance=$processingUtterance")\n'
if speech_anchor not in s:
    raise SystemExit('Build64: speech marker anchor not found')
speech_new = speech_anchor + '''                            build64SpeechSeen = true
                            DiLink3DebugLog.log(
                                context,
                                "BUILD64_SPEECH_READY",
                                "seq=$build64PttSeq source=$build64PttSource afterPttMs=${System.currentTimeMillis() - build64PttAtMs}"
                            )
'''
s = s.replace(speech_anchor, speech_new, 1)

utterance_anchor = '''                            DiLink3DebugLog.log(
                                context,
                                "BUILD59_GIGAAM_UTTERANCE",
                                "decodeMs=$decodeMs processingUtterance=$processingUtterance text=${ev.text}"
                            )
'''
if utterance_anchor not in s:
    raise SystemExit('Build64: utterance marker anchor not found')
utterance_new = utterance_anchor + '''                            build64UtteranceSeen = true
                            DiLink3DebugLog.log(
                                context,
                                "BUILD64_UTTERANCE_READY",
                                "seq=$build64PttSeq source=$build64PttSource afterPttMs=${System.currentTimeMillis() - build64PttAtMs} decodeMs=$decodeMs text=${ev.text}"
                            )
'''
s = s.replace(utterance_anchor, utterance_new, 1)

# Exact agent error text in the exported DiLink log.
agent_error_anchor = '''            is AgentResult.Error -> {
                earcon.fail(); _state.value = VoiceUiState.Blocked(result.message)
'''
if agent_error_anchor not in s:
    raise SystemExit('Build64: AgentResult.Error anchor not found')
agent_error_new = '''            is AgentResult.Error -> {
                DiLink3DebugLog.log(
                    context,
                    "BUILD64_AGENT_ERROR",
                    "message=${result.message} transcript=$transcript source=$build64PttSource seq=$build64PttSeq"
                )
                earcon.fail(); _state.value = VoiceUiState.Blocked(result.message)
'''
s = s.replace(agent_error_anchor, agent_error_new, 1)

# TTS success has not guaranteed audible output in-car. Log logical and physical playback state.
tts_end_anchor = '''        DiLink3DebugLog.log(
            context,
            "BUILD60_TTS_TRACE",
            "stage=$stage phase=end success=$ok error=${result.exceptionOrNull()?.let { it::class.java.simpleName + ":" + it.message }}"
        )
        return ok
'''
if tts_end_anchor not in s:
    raise SystemExit('Build64: Build60 TTS end anchor not found')
tts_end_new = '''        DiLink3DebugLog.log(
            context,
            "BUILD60_TTS_TRACE",
            "stage=$stage phase=end success=$ok error=${result.exceptionOrNull()?.let { it::class.java.simpleName + ":" + it.message }}"
        )
        DiLink3DebugLog.log(
            context,
            "BUILD64_TTS_STATE",
            "stage=$stage success=$ok speaking=${ttsEngine.speaking.value} audible=${runCatching { ttsEngine.audible() }.getOrDefault(false)} " +
                "ttsEnabled=${gate.ttsEnabled()} source=$build64PttSource seq=$build64PttSeq"
        )
        return ok
'''
s = s.replace(tts_end_anchor, tts_end_new, 1)

# After one route has completed, close ONLY the capture session. Do not use stopContinuousSession(),
# because that would cancel the route/TTS/agent pipeline. At this point routeUtterance has returned.
route_final_anchor = '''                                    routingJob = null
                                    processingUtterance = false
                                    runCatching { updateListeningOverlay(context.getString(R.string.voice_listening)) }
                                    if (stopRequested.get()) session?.cancel()
'''
if route_final_anchor not in s:
    raise SystemExit('Build64: routing finally anchor not found')
route_final_new = '''                                    routingJob = null
                                    processingUtterance = false
                                    DiLink3DebugLog.log(
                                        context,
                                        "BUILD64_AUTO_SESSION_CLOSE",
                                        "seq=$build64PttSeq source=$build64PttSource reason=one_utterance_route_finished"
                                    )
                                    session?.cancel()
'''
s = s.replace(route_final_anchor, route_final_new, 1)

p.write_text(s)

# ---------------------------------------------------------------------------
# SteeringWheelKeyService: physical and screen triggers now call the same source-aware seam.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt')
s = p.read_text()
old_call = '                entryPoint().voiceController().onPttPressed()\n'
if old_call not in s:
    raise SystemExit('Build64: steering PTT call anchor not found')
new_call = '''                entryPoint().voiceController().build64PttFrom(
                    "steering keyCode=${event.keyCode} scanCode=${event.scanCode} deviceId=${event.deviceId} source=${event.source}"
                )
'''
s = s.replace(old_call, new_call, 1)
p.write_text(s)

# ---------------------------------------------------------------------------
# Diagnostic panel: screen PTT + reset stale cards on app/panel composition.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()

s = s.replace('DiLink3 Build63 ROUTER GUARD FIX', 'DiLink3 Build64 INPUT PARITY DIAG', 1)

# Clear stale cards once when this screen enters composition, before the collapsed early return.
context_anchor = '''    val context = LocalContext.current
    val voiceState by voiceController.state.collectAsState()
'''
if context_anchor not in s:
    raise SystemExit('Build64: panel context anchor not found')
context_new = '''    val context = LocalContext.current
    LaunchedEffect(Unit) {
        context.getSharedPreferences("build61_voice_trace", Context.MODE_PRIVATE)
            .edit()
            .remove("last_heard")
            .remove("last_heard_ms")
            .remove("last_assistant")
            .remove("last_assistant_source")
            .remove("last_assistant_ms")
            .apply()
        DiLink3DebugLog.log(context, "BUILD64_TRACE_FIELDS_RESET", "reason=panel_composition")
    }
    val voiceState by voiceController.state.collectAsState()
'''
s = s.replace(context_anchor, context_new, 1)

# Put the screen trigger immediately below the Build64 title so it is easy to find.
title_anchor = '            Text("DiLink3 Build64 INPUT PARITY DIAG", style = MaterialTheme.typography.titleLarge)\n\n'
if title_anchor not in s:
    raise SystemExit('Build64: Build64 title anchor not found after rename')
controls = '''            Text("DiLink3 Build64 INPUT PARITY DIAG", style = MaterialTheme.typography.titleLarge)

            Button(
                onClick = {
                    DiLink3DebugLog.log(context, "BUILD64_SCREEN_PTT_BUTTON", "action=press")
                    voiceController.build64PttFrom("debug_screen_button")
                },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("ЗАПУСТИТЬ ГОЛОСОВУЮ КОМАНДУ С ЭКРАНА") }

            Text(
                "Эта кнопка запускает тот же VoiceController PTT путь, что и кнопка руля. В логе сравни BUILD64_PTT_DISPATCH source=debug_screen_button и source=steering. После одного распознанного запроса запись автоматически закрывается, поэтому следующее нажатие снова запускает новую команду.",
                style = MaterialTheme.typography.bodySmall,
            )

'''
s = s.replace(title_anchor, controls, 1)

# Replace Build63 explanation with current field finding.
s = s.replace(
    'Build63 убирает диагностическое «Я услышал» перед маршрутизацией, потому что оно могло активировать SelfEchoFilter. Перед resolver теперь отдельно логируется точный echo-guard и любой ранний возврат. Поля «Что услышал» и «Что сказал ассистент» обновляются сразу через listener, без Share/Clear log.',
    'Build64 сравнивает физическую кнопку и кнопку на экране через один и тот же PTT-вход. Первый press трассируется до PCM, SpeechStart и Utterance с задержками. Также логируется точный AgentResult.Error и состояние TTS. Старые карточки очищаются при открытии экрана.',
    1,
)

p.write_text(s)
print('Build64 installed: screen PTT parity + first-press timing + agent/TTS diagnostics + one-shot capture close + stale-card reset')
