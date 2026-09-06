#!/usr/bin/env python3
from pathlib import Path

# Build63: use the Build62 diagnosis to fix the most likely cause and make the
# remaining early-return condition explicit.
#
# Field evidence from Build62:
#   GigaAM -> Utterance works, then Build60 diagnostic TTS says "Я услышал...",
#   then routeUtterance() enters and returns before resolver.
# The base router has exactly one return before resolver: SelfEchoFilter.
# Build60's diagnostic helper noteSpoken()'d "Я услышал: <same transcript>" before
# routing, so Build63 removes that pre-route speech and instruments the guard.
#
# Also fixes Build61/62 cards not updating until another UI event by registering
# a SharedPreferences listener and storing the values as Compose state.

p = Path('app/src/main/kotlin/com/bydmate/app/voice/VoiceController.kt')
s = p.read_text()

# 1) Do NOT speak the recognition echo before the router. It pollutes SelfEchoFilter.
heard_echo = '''                            if (ev.text.isNotBlank()) {
                                build60SpeakTrace("heard_echo", "Я услышал: ${ev.text}")
                            }
'''
if heard_echo not in s:
    raise SystemExit('Build63: pre-route heard_echo block not found')
s = s.replace(
    heard_echo,
    '''                            DiLink3DebugLog.log(
                                context,
                                "BUILD63_PRE_ROUTE_TTS_SKIPPED",
                                "reason=avoid_self_echo_filter text=${ev.text}"
                            )
''',
    1,
)

# 2) Exact early-return diagnosis. This is intentionally placed on the only
# pre-resolver return in the current base routeUtterance implementation.
echo_block = '''        if (transcript == command && echoFilter.isEcho(transcript)) {
            record(VoiceJournalEntry.Route.NONE, transcript, withDecodeMs(transcript, decodeMs),
                VoiceJournalEntry.Outcome.NOT_UNDERSTOOD, "Эхо своей речи",
                "Echo filtered: transcript=\\"$transcript\\"")
            return
        }
'''
if echo_block not in s:
    raise SystemExit('Build63: base echo guard block not found')
echo_new = '''        val build63NamePrefixed = transcript != command
        val build63EchoMatched = if (!build63NamePrefixed) echoFilter.isEcho(transcript) else false
        val build63Now = System.currentTimeMillis()
        val build63SpeakingAgeMs = if (lastSpeakingSeenMs > 0L) build63Now - lastSpeakingSeenMs else -1L
        DiLink3DebugLog.log(
            context,
            "BUILD63_PRE_RESOLVER_GUARD",
            "namePrefixed=$build63NamePrefixed echoMatched=$build63EchoMatched speakingAgeMs=$build63SpeakingAgeMs " +
                "ttsAudible=${runCatching { ttsEngine.audible() }.getOrDefault(false)} transcript=$transcript command=$command"
        )
        if (!build63NamePrefixed && build63EchoMatched) {
            build63EarlyReturnReason = "SELF_ECHO_GUARD"
            DiLink3DebugLog.log(context, "BUILD63_EARLY_RETURN", "reason=SELF_ECHO_GUARD transcript=$transcript")
            record(VoiceJournalEntry.Route.NONE, transcript, withDecodeMs(transcript, decodeMs),
                VoiceJournalEntry.Outcome.NOT_UNDERSTOOD, "Эхо своей речи",
                "Echo filtered: transcript=\\"$transcript\\"")
            return
        }
        DiLink3DebugLog.log(context, "BUILD63_PRE_RESOLVER_PASS", "command=$command")
'''
s = s.replace(echo_block, echo_new, 1)

# 3) Extend Build62 diagnosis with the exact pre-resolver reason.
field_anchor = '    @Volatile private var build62RealAnswerReceived = false\n'
if field_anchor not in s:
    raise SystemExit('Build63: Build62 state anchor not found')
s = s.replace(field_anchor, field_anchor + '    @Volatile private var build63EarlyReturnReason: String? = null\n', 1)

reset_anchor = '        build62RealAnswerReceived = false\n'
if reset_anchor not in s:
    raise SystemExit('Build63: Build62 reset anchor not found')
s = s.replace(reset_anchor, reset_anchor + '        build63EarlyReturnReason = null\n', 1)

diag_when = '''            val reason = when {
                !build62RouteEntered -> "ROUTE_NEVER_ENTERED"
                build62RouteReturned && !build62ResolveStarted -> "ROUTE_RETURNED_BEFORE_RESOLVER"
'''
if diag_when not in s:
    raise SystemExit('Build63: Build62 diagnosis classifier anchor not found')
s = s.replace(
    diag_when,
    '''            val reason = when {
                build63EarlyReturnReason != null -> build63EarlyReturnReason!!
                !build62RouteEntered -> "ROUTE_NEVER_ENTERED"
                build62RouteReturned && !build62ResolveStarted -> "ROUTE_RETURNED_BEFORE_RESOLVER"
''',
    1,
)

diag_text_anchor = '        "ROUTE_RETURNED_BEFORE_RESOLVER" -> "Диагностика: маршрутизатор завершился до запуска обработчика команды"\n'
if diag_text_anchor not in s:
    raise SystemExit('Build63: diagnosis text anchor not found')
s = s.replace(
    diag_text_anchor,
    diag_text_anchor + '        "SELF_ECHO_GUARD" -> "Диагностика: команда была отброшена защитой от эха собственной речи"\n',
    1,
)

# 4) Make version logging honest. Old Build56 marker was hard-coded and misleading.
s = s.replace(
    'DiLink3DebugLog.log(context, "BUILD56_LOG_CLEARED", "versionCode=60005")',
    'DiLink3DebugLog.log(context, "BUILD56_LOG_CLEARED", "versionCode=${com.bydmate.app.BuildConfig.VERSION_CODE}")',
)

p.write_text(s)

# 5) Reactive cards: SharedPreferences listener updates Compose state immediately.
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()

s = s.replace('DiLink3 Build62 AUTO DIAG', 'DiLink3 Build63 ROUTER GUARD FIX', 1)

old_ui = '''            val build61TracePrefs = remember { context.getSharedPreferences("build61_voice_trace", Context.MODE_PRIVATE) }
            val build61Heard = build61TracePrefs.getString("last_heard", "—") ?: "—"
            val build61Assistant = build61TracePrefs.getString("last_assistant", "—") ?: "—"
            val build61AssistantSource = build61TracePrefs.getString("last_assistant_source", "") ?: ""
'''
if old_ui not in s:
    raise SystemExit('Build63: Build61 trace UI values anchor not found')
new_ui = '''            val build61TracePrefs = remember { context.getSharedPreferences("build61_voice_trace", Context.MODE_PRIVATE) }
            var build61Heard by remember { mutableStateOf(build61TracePrefs.getString("last_heard", "—") ?: "—") }
            var build61Assistant by remember { mutableStateOf(build61TracePrefs.getString("last_assistant", "—") ?: "—") }
            var build61AssistantSource by remember { mutableStateOf(build61TracePrefs.getString("last_assistant_source", "") ?: "") }
            DisposableEffect(build61TracePrefs) {
                val listener = android.content.SharedPreferences.OnSharedPreferenceChangeListener { prefs, key ->
                    when (key) {
                        "last_heard" -> build61Heard = prefs.getString("last_heard", "—") ?: "—"
                        "last_assistant" -> build61Assistant = prefs.getString("last_assistant", "—") ?: "—"
                        "last_assistant_source" -> build61AssistantSource = prefs.getString("last_assistant_source", "") ?: ""
                    }
                }
                build61TracePrefs.registerOnSharedPreferenceChangeListener(listener)
                onDispose { build61TracePrefs.unregisterOnSharedPreferenceChangeListener(listener) }
            }
'''
s = s.replace(old_ui, new_ui, 1)

# Update Build62 explanation to match Build63 behavior.
s = s.replace(
    'Build62 автоматически трассирует каждый этап после распознавания и через 12 секунд без реального ответа сам определяет класс сбоя. Причина записывается в поле ответа как [DIAG] и в лог BUILD62_DIAGNOSIS, а также произносится вслух. Поля «Что услышал» и «Что сказал ассистент» сохранены.',
    'Build63 убирает диагностическое «Я услышал» перед маршрутизацией, потому что оно могло активировать SelfEchoFilter. Перед resolver теперь отдельно логируется точный echo-guard и любой ранний возврат. Поля «Что услышал» и «Что сказал ассистент» обновляются сразу через listener, без Share/Clear log.',
    1,
)

p.write_text(s)
print('Build63 installed: remove pre-route TTS self-echo poisoning + exact early-return guard + reactive trace cards')
