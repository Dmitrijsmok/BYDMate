#!/usr/bin/env python3
from pathlib import Path
import re

# Clean production finalizer for v3.14.3. No diagnostic UI/logging is added here.

# --- 304/327 pure decision layer -------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyDecision.kt')
s = p.read_text(encoding='utf-8')
anchor = 'const val DILINK3_STOCK_ASSISTANT_KEYCODE = 327\n\n'
if anchor not in s:
    raise SystemExit('DiLink3 keycode anchor missing')
if 'fun diLink3TakeoverSupported(' not in s:
    s = s.replace(anchor, anchor + '''/**
 * The field-validated 304/327 takeover belongs to the Android 10 DiLink 3/4 generation.
 * Newer DiLink generations keep the upstream learnable steering-key path.
 */
fun diLink3TakeoverSupported(sdkInt: Int): Boolean = sdkInt <= 29

''', 1)
old = '''    if (!takeoverEnabled) return DiLink3AssistantDecision.PASS_THROUGH
    if (keyCode == DILINK3_STOCK_ASSISTANT_KEYCODE) return DiLink3AssistantDecision.CONSUME
    if (keyCode != DILINK3_MIC_KEYCODE || !voiceEnabled) return DiLink3AssistantDecision.PASS_THROUGH
'''
new = '''    if (!takeoverEnabled || !voiceEnabled) return DiLink3AssistantDecision.PASS_THROUGH
    if (keyCode == DILINK3_STOCK_ASSISTANT_KEYCODE) return DiLink3AssistantDecision.CONSUME
    if (keyCode != DILINK3_MIC_KEYCODE) return DiLink3AssistantDecision.PASS_THROUGH
'''
if old not in s:
    raise SystemExit('DiLink3 decision body anchor missing')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

# --- Steering service -------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt')
s = p.read_text(encoding='utf-8')
pref_pattern = re.compile(
    r'        val diLink3Takeover = voicePrefs\.getBoolean\(\s*'
    r'SettingsRepository\.KEY_DILINK3_STEERING_ASSISTANT,\s*false\s*\)'
)
pref_new = '''        val diLink3Platform = diLink3TakeoverSupported(android.os.Build.VERSION.SDK_INT)
        val diLink3Takeover = diLink3Platform &&
            voicePrefs.getBoolean(SettingsRepository.KEY_DILINK3_STEERING_ASSISTANT, false)'''
s, n = pref_pattern.subn(pref_new, s, count=1)
if n != 1:
    raise SystemExit(f'Steering takeover preference replacement count={n}')

trigger_pattern = re.compile(
    r'(DiLink3AssistantDecision\.TRIGGER_VOICE -> \{\s*)'
    r'entryPoint\(\)\.voiceController\(\)\.onPttPressed\(\)'
)
s, n = trigger_pattern.subn(r'\1entryPoint().voiceController().onSteeringPttPressed()', s, count=1)
if n != 1:
    raise SystemExit(f'DiLink3 steering trigger replacement count={n}')

generic = '''        when (voiceDecision(event.keyCode, isDown, voiceEnabled, voiceKey)) {
            VoiceKeyDecision.TRIGGER -> {
                entryPoint().voiceController().onPttPressed()
                return true
            }
            // Swallow the matching key's UP edge too — otherwise it falls through to the
            // native BYD assistant, which owns the same hardware keycode (Finding 2).
            VoiceKeyDecision.CONSUME -> return true
            VoiceKeyDecision.IGNORE -> {}
        }
'''
if generic not in s:
    raise SystemExit('Generic voice-decision block missing')
wrapped = '''        if (!diLink3Platform) {
            when (voiceDecision(event.keyCode, isDown, voiceEnabled, voiceKey)) {
                VoiceKeyDecision.TRIGGER -> {
                    entryPoint().voiceController().onPttPressed()
                    return true
                }
                VoiceKeyDecision.CONSUME -> return true
                VoiceKeyDecision.IGNORE -> {}
            }
        }
'''
s = s.replace(generic, wrapped, 1)
p.write_text(s, encoding='utf-8')

# --- VoiceController: steering one-shot only -------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/voice/VoiceController.kt')
s = p.read_text(encoding='utf-8')
field_anchor = '    private val stopRequested = AtomicBoolean(false)\n'
if field_anchor not in s:
    raise SystemExit('VoiceController stopRequested anchor missing')
if 'steeringOneShotRequested' not in s:
    s = s.replace(field_anchor, field_anchor + '    private val steeringOneShotRequested = AtomicBoolean(false)\n', 1)

ptt_anchor = '    fun onPttPressed() {\n'
if ptt_anchor not in s:
    raise SystemExit('VoiceController PTT anchor missing')
if 'fun onSteeringPttPressed()' not in s:
    steering_method = '''    /** DiLink3 physical steering microphone: one command per press. */
    fun onSteeringPttPressed() {
        if (!_listening.value) steeringOneShotRequested.set(true)
        onPttPressed()
        if (!_listening.value) steeringOneShotRequested.set(false)
    }

'''
    s = s.replace(ptt_anchor, steering_method + ptt_anchor, 1)

start_pattern = re.compile(
    r'    private fun startContinuousSession\(\) \{\n'
    r'        if \(!busy\.compareAndSet\(false, true\)\) return\n'
    r'        ensureSupertonicStressDict\(\)\n'
)
start_new = '''    private fun startContinuousSession() {
        if (!busy.compareAndSet(false, true)) return
        val oneShotAfterFirstUtterance = steeringOneShotRequested.getAndSet(false)
        ensureSupertonicStressDict()
'''
s, n = start_pattern.subn(start_new, s, count=1)
if n != 1:
    raise SystemExit(f'VoiceController start replacement count={n}')

finally_pattern = re.compile(
    r'                                    routingJob = null\n'
    r'                                    processingUtterance = false\n'
    r'                                    runCatching \{ updateListeningOverlay\(context\.getString\(R\.string\.voice_listening\)\) \}\n'
    r'                                    if \(stopRequested\.get\(\)\) session\?\.cancel\(\)\n'
)
finally_new = '''                                    routingJob = null
                                    processingUtterance = false
                                    if (oneShotAfterFirstUtterance || stopRequested.get()) {
                                        session?.cancel()
                                    } else {
                                        runCatching { updateListeningOverlay(context.getString(R.string.voice_listening)) }
                                    }
'''
s, n = finally_pattern.subn(finally_new, s, count=1)
if n != 1:
    raise SystemExit(f'VoiceController routing-finally replacement count={n}')
p.write_text(s, encoding='utf-8')

# --- Settings UI ------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt')
s = p.read_text(encoding='utf-8')
ui_pattern = re.compile(
    r'    // DiLink3 steering microphone ownership\. Disabled unless the voice pipeline is ON;\n'
    r'.*?'
    r'    // Contacts permission \(call_contact tool\)\n', re.S
)
ui_new = '''    val diLink3TakeoverAvailable = remember {
        com.bydmate.app.cluster.diLink3TakeoverSupported(android.os.Build.VERSION.SDK_INT)
    }
    if (diLink3TakeoverAvailable) {
        Card(
            shape = RoundedCornerShape(12.dp),
            colors = CardDefaults.cardColors(containerColor = CardSurfaceElevated),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Column(modifier = Modifier.padding(horizontal = 12.dp)) {
                SettingChipRow(
                    title = stringResource(R.string.settings_dilink3_steering_assistant_title),
                    description = stringResource(R.string.settings_dilink3_steering_assistant_desc),
                    options = listOf("BYD Assistant", "BYDMate"),
                    selectedIndex = if (state.dilink3SteeringAssistant) 1 else 0,
                    onSelect = { index -> viewModel.setDiLink3SteeringAssistant(index == 1) },
                    enabled = state.voiceEnabled,
                )
            }
        }
    } else {
        var learningVoiceKey by remember { mutableStateOf(false) }
        Card(
            shape = RoundedCornerShape(12.dp),
            colors = CardDefaults.cardColors(containerColor = CardSurfaceElevated),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Column(modifier = Modifier.padding(horizontal = 12.dp)) {
                val keyLabel = steeringButtonLabel(
                    if (state.voiceKeycode == 0) DEFAULT_VOICE_KEYCODE else state.voiceKeycode
                )
                SettingValueRow(
                    title = stringResource(R.string.settings_voice_button_label),
                    value = stringResource(R.string.settings_voice_button_current, keyLabel),
                    onClick = { learningVoiceKey = true },
                )
            }
        }
        if (learningVoiceKey) {
            LearnButtonDialog(
                onSave = { code ->
                    viewModel.saveVoiceKeycode(code)
                    learningVoiceKey = false
                },
                onDismiss = { learningVoiceKey = false },
            )
        }
    }

    // Contacts permission (call_contact tool)
'''
s, n = ui_pattern.subn(ui_new, s, count=1)
if n != 1:
    raise SystemExit(f'Settings DiLink3 UI replacement count={n}')
p.write_text(s, encoding='utf-8')

# --- Legacy package-disable path: restore-only ------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsViewModel.kt')
s = p.read_text(encoding='utf-8')
setter_pattern = re.compile(
    r'    /\*\*\n'
    r'     \* Toggle the native BYD voice assistant\..*?\n'
    r'    fun setDisableNativeAssistant\(disabled: Boolean\) \{\n'
    r'        _uiState\.update \{ it\.copy\(disableNativeAssistant = disabled\) \}\n'
    r'        viewModelScope\.launch \{\n'
    r'            settingsRepository\.setString\(SettingsRepository\.KEY_DISABLE_NATIVE_ASSISTANT, disabled\.toString\(\)\)\n'
    r'            helperClient\.setAppHidden\("com\.byd\.autovoice", disabled\)\n'
    r'        \}\n'
    r'    \}\n', re.S
)
setter_new = '''    /** Legacy compatibility only: the stock BYD Assistant package must stay enabled. */
    @Deprecated("Use DiLink3 steering takeover")
    fun setDisableNativeAssistant(disabled: Boolean) {
        _uiState.update { it.copy(disableNativeAssistant = false) }
        viewModelScope.launch {
            settingsRepository.setString(SettingsRepository.KEY_DISABLE_NATIVE_ASSISTANT, "false")
            if (helperBootstrap.ensureRunning()) {
                helperClient.setAppHidden("com.byd.autovoice", false)
            }
            if (disabled) Log.i(TAG, "Ignored legacy request to disable stock BYD Assistant")
        }
    }
'''
s, n = setter_pattern.subn(setter_new, s, count=1)
if n != 1:
    raise SystemExit(f'Legacy assistant setter replacement count={n}')
p.write_text(s, encoding='utf-8')

# --- Startup migration: undo old disable=true ------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/service/TrackingService.kt')
s = p.read_text(encoding='utf-8')
legacy_pattern = re.compile(
    r'                if \(ok\) \{\n'
    r'                    val pref = settingsRepository\.getString\(\n'
    r'                        com\.bydmate\.app\.data\.repository\.SettingsRepository\.KEY_DISABLE_NATIVE_ASSISTANT,\n'
    r'                        ""\)\n'
    r'                    if \(pref\.isNotEmpty\(\)\) \{\n'
    r'                        helperClient\.setAppHidden\("com\.byd\.autovoice", pref == "true"\)\n'
    r'                    \}\n'
    r'                \}\n'
)
legacy_new = '''                if (ok) {
                    val legacyPref = settingsRepository.getString(
                        SettingsRepository.KEY_DISABLE_NATIVE_ASSISTANT, "")
                    if (legacyPref == "true") {
                        val restored = helperClient.setAppHidden("com.byd.autovoice", false)
                        if (restored) {
                            settingsRepository.setString(SettingsRepository.KEY_DISABLE_NATIVE_ASSISTANT, "false")
                            Log.i(TAG, "Restored stock BYD Assistant from legacy package-disable setting")
                        } else {
                            Log.w(TAG, "Could not restore stock BYD Assistant from legacy setting")
                        }
                    }
                }
'''
s, n = legacy_pattern.subn(legacy_new, s, count=1)
if n != 1:
    raise SystemExit(f'TrackingService legacy migration replacement count={n}')
p.write_text(s, encoding='utf-8')

# --- Regression tests -------------------------------------------------------------
p = Path('app/src/test/kotlin/com/bydmate/app/cluster/SteeringWheelKeyDecisionTest.kt')
s = p.read_text(encoding='utf-8')
test_anchor = '    @Test fun `dilink3 field keycodes stay pinned to 304 and 327`() {\n'
if test_anchor not in s:
    raise SystemExit('Steering decision test anchor missing')
tests = '''    @Test fun `dilink3 takeover is limited to Android 10 generation`() {
        assertTrue(diLink3TakeoverSupported(29))
        assertFalse(diLink3TakeoverSupported(30))
        assertFalse(diLink3TakeoverSupported(35))
    }

    @Test fun `voice master off restores both DiLink3 physical events`() {
        assertEquals(
            DiLink3AssistantDecision.PASS_THROUGH,
            diLink3AssistantDecision(DILINK3_MIC_KEYCODE, true, true, false),
        )
        assertEquals(
            DiLink3AssistantDecision.PASS_THROUGH,
            diLink3AssistantDecision(DILINK3_STOCK_ASSISTANT_KEYCODE, true, true, false),
        )
    }

'''
s = s.replace(test_anchor, tests + test_anchor, 1)
p.write_text(s, encoding='utf-8')

p = Path('app/src/test/kotlin/com/bydmate/app/voice/VoiceControllerAgentFallbackTest.kt')
s = p.read_text(encoding='utf-8')
test_anchor = '    @Test fun `agent Answer becomes AgentAnswer state, earcon ok, orchestrator called once`() {\n'
if test_anchor not in s:
    raise SystemExit('VoiceController test anchor missing')
test = '''    @Test fun `steering PTT closes after one routed utterance while generic PTT stays continuous`() {
        val agent = mockk<AgentOrchestrator>()
        coEvery { agent.ask(any(), any()) } returns AgentResult.Answer("готово")

        val steeringAsr = FakeContinuousAsr()
        val steering = makeController(agentOrchestrator = agent, continuousAsr = steeringAsr)
        steering.onSteeringPttPressed()
        awaitTrue { steering.listening.value }
        awaitSubscribed(steeringAsr.events)
        steeringAsr.events.tryEmit(ContinuousAsrEvent.Utterance("навигатор"))
        awaitTrue { !steering.listening.value }

        val normalAsr = FakeContinuousAsr()
        val normal = makeController(agentOrchestrator = agent, continuousAsr = normalAsr)
        normal.onPttPressed()
        awaitTrue { normal.listening.value }
        awaitSubscribed(normalAsr.events)
        normalAsr.events.tryEmit(ContinuousAsrEvent.Utterance("навигатор"))
        awaitTrue { normal.routingJobForTest() == null }
        assertEquals(true, normal.listening.value)
        normal.onPttPressed()
        awaitTrue { !normal.listening.value }
    }

'''
s = s.replace(test_anchor, test + test_anchor, 1)
p.write_text(s, encoding='utf-8')
