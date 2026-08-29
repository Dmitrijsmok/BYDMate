from pathlib import Path

# Maximum microphone/steering-wheel diagnostics for DiLink3.
# Goals:
# 1) passive observation must NOT consume the native BYD mic action;
# 2) log the complete KeyEvent + originating InputDevice;
# 3) record the app lifecycle/intent path and accessibility window launched by the press;
# 4) provide a separate, reversible consume test after the key has been identified.

# ---------------------------------------------------------------------------
# SteeringWheelKeyService: raw Accessibility key stream + native-action trace.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt')
s = p.read_text()

needle = 'import com.bydmate.app.service.TrackingService\n'
repl = 'import com.bydmate.app.service.TrackingService\nimport com.bydmate.app.ui.diagnostics.DiLink3DebugLog\n'
if needle not in s:
    raise SystemExit('service import insertion point not found')
s = s.replace(needle, repl, 1)

needle = '        Log.d(TAG, "connected; filtering steering-wheel keys")\n'
repl = '''        Log.d(TAG, "connected; filtering steering-wheel keys")\n        DiLink3DebugLog.log(\n            applicationContext,\n            "STEERING_A11Y_CONNECTED",\n            "flags=${serviceInfo?.flags} eventTypes=${serviceInfo?.eventTypes} feedbackType=${serviceInfo?.feedbackType}"\n        )\n'''
if needle not in s:
    raise SystemExit('service connected insertion point not found')
s = s.replace(needle, repl, 1)

needle = '''    override fun onKeyEvent(event: KeyEvent): Boolean {\n        val isDown = event.action == KeyEvent.ACTION_DOWN\n'''
repl = '''    override fun onKeyEvent(event: KeyEvent): Boolean {\n        val isDown = event.action == KeyEvent.ACTION_DOWN\n        val diagPrefs = applicationContext.getSharedPreferences("dilink3_diag", Context.MODE_PRIVATE)\n        val micLoggerArmed = diagPrefs.getBoolean("mic_button_logger_armed", false)\n        if (micLoggerArmed) {\n            val device = runCatching { event.device }.getOrNull()\n            val deviceText = if (device == null) {\n                "device=<null>"\n            } else {\n                "deviceName=${device.name} descriptor=${device.descriptor} vendorId=${device.vendorId} productId=${device.productId} keyboardType=${device.keyboardType} deviceSources=${device.sources}"\n            }\n            DiLink3DebugLog.log(\n                applicationContext,\n                "STEERING_KEY_RAW",\n                "action=${event.action} actionName=${if (isDown) "DOWN" else if (event.action == KeyEvent.ACTION_UP) "UP" else "OTHER"} " +\n                    "keyCode=${event.keyCode} keyName=${KeyEvent.keyCodeToString(event.keyCode)} scanCode=${event.scanCode} " +\n                    "repeat=${event.repeatCount} deviceId=${event.deviceId} source=${event.source} sourceHex=0x${event.source.toString(16)} " +\n                    "flags=${event.flags} flagsHex=0x${event.flags.toString(16)} metaState=${event.metaState} " +\n                    "downTime=${event.downTime} eventTime=${event.eventTime} longPress=${event.isLongPress} canceled=${event.isCanceled} tracking=${event.isTracking} " +\n                    "$deviceText event=${event}"\n            )\n        }\n'''
if needle not in s:
    raise SystemExit('onKeyEvent insertion point not found')
s = s.replace(needle, repl, 1)

# Trace the exact voice decision and the handoff to VoiceController.
needle = '''        when (voiceDecision(event.keyCode, isDown, voiceEnabled, voiceKey)) {\n            VoiceKeyDecision.TRIGGER -> {\n                entryPoint().voiceController().onPttPressed()\n                return true\n            }'''
repl = '''        val voiceKeyDecision = voiceDecision(event.keyCode, isDown, voiceEnabled, voiceKey)\n        if (micLoggerArmed) {\n            DiLink3DebugLog.log(\n                applicationContext,\n                "STEERING_VOICE_DECISION",\n                "eventKey=${event.keyCode} configuredVoiceKey=$voiceKey voiceEnabled=$voiceEnabled isDown=$isDown decision=$voiceKeyDecision"\n            )\n        }\n        when (voiceKeyDecision) {\n            VoiceKeyDecision.TRIGGER -> {\n                if (micLoggerArmed) {\n                    DiLink3DebugLog.log(\n                        applicationContext,\n                        "VOICE_CONTROLLER_PTT_CALL",\n                        "source=SteeringWheelKeyService keyCode=${event.keyCode} keyName=${KeyEvent.keyCodeToString(event.keyCode)}"\n                    )\n                }\n                entryPoint().voiceController().onPttPressed()\n                return true\n            }'''
if needle not in s:
    raise SystemExit('voice decision insertion point not found')
s = s.replace(needle, repl, 1)

needle = '''        // Voice check: runs after learn-mode, before star decision. Returns true only when voice is\n'''
repl = '''        // Separate reversible diagnostic block. Passive logging above NEVER consumes the key.\n        // Enable this only after the observed keyCode is known. DOWN and UP are both swallowed.\n        val blockNativeVoice = diagPrefs.getBoolean("mic_button_block_native", false)\n        val blockKeyCode = diagPrefs.getInt("mic_button_block_keycode", DEFAULT_VOICE_KEYCODE)\n        if (blockNativeVoice && event.keyCode == blockKeyCode) {\n            DiLink3DebugLog.log(\n                applicationContext,\n                "MIC_BUTTON_BLOCKED",\n                "keyCode=${event.keyCode} keyName=${KeyEvent.keyCodeToString(event.keyCode)} action=${event.action} scanCode=${event.scanCode} deviceId=${event.deviceId} source=${event.source}"\n            )\n            return true\n        }\n\n        // Voice check: runs after learn-mode, before star decision. Returns true only when voice is\n'''
if needle not in s:
    raise SystemExit('voice block insertion point not found')
s = s.replace(needle, repl, 1)

needle = '''    override fun onAccessibilityEvent(event: AccessibilityEvent?) {\n        NavA11yFeed.onEvent(this, event)\n    }'''
repl = '''    override fun onAccessibilityEvent(event: AccessibilityEvent?) {\n        if (event != null) {\n            val diagPrefs = applicationContext.getSharedPreferences("dilink3_diag", Context.MODE_PRIVATE)\n            if (diagPrefs.getBoolean("mic_button_logger_armed", false) &&\n                (event.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED ||\n                 event.eventType == AccessibilityEvent.TYPE_WINDOWS_CHANGED ||\n                 event.eventType == AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED)) {\n                val text = runCatching { event.text?.joinToString(" | ") }.getOrNull()\n                DiLink3DebugLog.log(\n                    applicationContext,\n                    "A11Y_WINDOW_TRACE",\n                    "type=${event.eventType} package=${event.packageName} class=${event.className} windowId=${event.windowId} " +\n                        "action=${event.action} contentChangeTypes=${event.contentChangeTypes} contentDescription=${event.contentDescription} text=$text"\n                )\n            }\n        }\n        NavA11yFeed.onEvent(this, event)\n    }'''
if needle not in s:
    raise SystemExit('a11y event insertion point not found')
s = s.replace(needle, repl, 1)
p.write_text(s)

# ---------------------------------------------------------------------------
# MainActivity: catch any KeyEvent/Intent path that reaches the app itself.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/MainActivity.kt')
s = p.read_text()

for needle, repl in [
    ('import android.content.Context\n', 'import android.content.Context\nimport android.content.Intent\n'),
    ('import android.util.Log\n', 'import android.util.Log\nimport android.view.KeyEvent\n'),
    ('import com.bydmate.app.ui.components.LocalConsumptionThresholds\n', 'import com.bydmate.app.ui.components.LocalConsumptionThresholds\nimport com.bydmate.app.ui.diagnostics.DiLink3DebugLog\n'),
]:
    if needle not in s:
        raise SystemExit('MainActivity import insertion point not found: ' + needle)
    s = s.replace(needle, repl, 1)

needle = '''    private fun requestPermissionsIfNeeded() {\n'''
repl = '''    private fun micDiagArmed(): Boolean =\n        applicationContext.getSharedPreferences("dilink3_diag", Context.MODE_PRIVATE)\n            .getBoolean("mic_button_logger_armed", false)\n\n    private fun describeDiagKey(event: KeyEvent): String {\n        val device = runCatching { event.device }.getOrNull()\n        val deviceText = if (device == null) {\n            "device=<null>"\n        } else {\n            "deviceName=${device.name} descriptor=${device.descriptor} vendorId=${device.vendorId} productId=${device.productId} keyboardType=${device.keyboardType} deviceSources=${device.sources}"\n        }\n        return "action=${event.action} keyCode=${event.keyCode} keyName=${KeyEvent.keyCodeToString(event.keyCode)} " +\n            "scanCode=${event.scanCode} repeat=${event.repeatCount} deviceId=${event.deviceId} source=${event.source} sourceHex=0x${event.source.toString(16)} " +\n            "flags=${event.flags} flagsHex=0x${event.flags.toString(16)} metaState=${event.metaState} downTime=${event.downTime} eventTime=${event.eventTime} " +\n            "longPress=${event.isLongPress} canceled=${event.isCanceled} tracking=${event.isTracking} $deviceText event=$event"\n    }\n\n    override fun dispatchKeyEvent(event: KeyEvent): Boolean {\n        if (micDiagArmed()) {\n            DiLink3DebugLog.log(applicationContext, "ACTIVITY_DISPATCH_KEY", describeDiagKey(event))\n        }\n        return super.dispatchKeyEvent(event)\n    }\n\n    override fun onKeyDown(keyCode: Int, event: KeyEvent): Boolean {\n        if (micDiagArmed()) {\n            DiLink3DebugLog.log(applicationContext, "ACTIVITY_KEY_DOWN", describeDiagKey(event))\n        }\n        return super.onKeyDown(keyCode, event)\n    }\n\n    override fun onKeyUp(keyCode: Int, event: KeyEvent): Boolean {\n        if (micDiagArmed()) {\n            DiLink3DebugLog.log(applicationContext, "ACTIVITY_KEY_UP", describeDiagKey(event))\n        }\n        return super.onKeyUp(keyCode, event)\n    }\n\n    override fun onNewIntent(intent: Intent) {\n        super.onNewIntent(intent)\n        if (micDiagArmed()) {\n            val extrasText = runCatching {\n                intent.extras?.keySet()?.joinToString("; ") { key ->\n                    val value = runCatching { intent.extras?.get(key) }.getOrNull()\n                    "$key=$value"\n                }\n            }.getOrNull()\n            DiLink3DebugLog.log(\n                applicationContext,\n                "ACTIVITY_NEW_INTENT",\n                "action=${intent.action} categories=${intent.categories} component=${intent.component} package=${intent.`package`} " +\n                    "data=${intent.dataString} flags=${intent.flags} extras=$extrasText"\n            )\n        }\n    }\n\n    override fun onResume() {\n        super.onResume()\n        if (micDiagArmed()) DiLink3DebugLog.log(applicationContext, "ACTIVITY_RESUME", "hasFocus=$hasWindowFocus")\n    }\n\n    override fun onPause() {\n        if (micDiagArmed()) DiLink3DebugLog.log(applicationContext, "ACTIVITY_PAUSE", "hasFocus=$hasWindowFocus")\n        super.onPause()\n    }\n\n    override fun onWindowFocusChanged(hasFocus: Boolean) {\n        super.onWindowFocusChanged(hasFocus)\n        if (micDiagArmed()) DiLink3DebugLog.log(applicationContext, "ACTIVITY_WINDOW_FOCUS", "hasFocus=$hasFocus")\n    }\n\n    private fun requestPermissionsIfNeeded() {\n'''
if needle not in s:
    raise SystemExit('MainActivity method insertion point not found')
s = s.replace(needle, repl, 1)
p.write_text(s)

# ---------------------------------------------------------------------------
# Diagnostic panel: passive logger first; capture/consume and blocking are separate.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()

for needle, repl in [
    ('import android.speech.SpeechRecognizer\n', 'import android.speech.SpeechRecognizer\nimport android.speech.tts.TextToSpeech\n'),
    ('import com.bydmate.app.voice.AudioCapture\n', 'import com.bydmate.app.cluster.DEFAULT_VOICE_KEYCODE\nimport com.bydmate.app.cluster.SteeringWheelKeyService\nimport com.bydmate.app.voice.AudioCapture\n'),
]:
    if needle not in s:
        raise SystemExit('panel import insertion point not found: ' + needle)
    s = s.replace(needle, repl, 1)

needle = '    var logShareStatus by remember { mutableStateOf("ready") }\n'
repl = '''    var logShareStatus by remember { mutableStateOf("ready") }\n    val diagPrefs = remember { context.getSharedPreferences("dilink3_diag", Context.MODE_PRIVATE) }\n    var micLoggerArmed by remember { mutableStateOf(diagPrefs.getBoolean("mic_button_logger_armed", false)) }\n    var blockNativeVoice by remember { mutableStateOf(diagPrefs.getBoolean("mic_button_block_native", false)) }\n    var blockKeyCode by remember { mutableStateOf(diagPrefs.getInt("mic_button_block_keycode", DEFAULT_VOICE_KEYCODE)) }\n    val capturedSteeringKey by SteeringWheelKeyService.capturedKey.collectAsState()\n    val ttsServices = remember {\n        runCatching {\n            context.packageManager\n                .queryIntentServices(Intent(TextToSpeech.Engine.INTENT_ACTION_TTS_SERVICE), 0)\n                .mapNotNull { it.serviceInfo?.packageName }\n                .distinct()\n        }.getOrDefault(emptyList())\n    }\n'''
if needle not in s:
    raise SystemExit('diag state insertion point not found')
s = s.replace(needle, repl, 1)

needle = '''        DiLink3DebugLog.log(context, "DEBUG_SESSION_START", "systemAsrAvailable=$systemAsrAvailable")\n        e2eBridge.warmUpTts()'''
repl = '''        DiLink3DebugLog.log(context, "DEBUG_SESSION_START", "systemAsrAvailable=$systemAsrAvailable")\n        DiLink3DebugLog.log(context, "ANDROID_TTS_SERVICES", "count=${ttsServices.size} packages=${ttsServices.joinToString()}")\n        e2eBridge.warmUpTts()'''
if needle not in s:
    raise SystemExit('TTS inventory log insertion point not found')
s = s.replace(needle, repl, 1)

needle = '                Text("AI PROVIDER - AIHubMix", style = MaterialTheme.typography.titleSmall)\n'
repl = '''                Text("MIC BUTTON / MAX TRACE", style = MaterialTheme.typography.titleSmall)\n                DebugRow("Accessibility key filter", if (SteeringWheelKeyService.isConnected) "CONNECTED" else "NOT CONNECTED")\n                DebugRow("Default BYD voice key", DEFAULT_VOICE_KEYCODE.toString())\n                DebugRow("Block key", blockKeyCode.toString())\n                DebugRow("Captured key", capturedSteeringKey?.let { "${it.keyCode} assignable=${it.assignable}" } ?: "<none>")\n                DebugRow("Passive logger", if (micLoggerArmed) "ARMED" else "OFF")\n\n                Button(\n                    onClick = {\n                        micLoggerArmed = true\n                        diagPrefs.edit().putBoolean("mic_button_logger_armed", true).apply()\n                        SteeringWheelKeyService.learnMode = false\n                        DiLink3DebugLog.log(context, "MIC_PASSIVE_LOGGER_ARMED", "native action will NOT be consumed")\n                    },\n                    modifier = Modifier.fillMaxWidth(),\n                ) { Text("ARM PASSIVE MIC LOGGER") }\n                Button(\n                    onClick = {\n                        micLoggerArmed = false\n                        diagPrefs.edit().putBoolean("mic_button_logger_armed", false).apply()\n                        SteeringWheelKeyService.learnMode = false\n                        DiLink3DebugLog.log(context, "MIC_PASSIVE_LOGGER_DISARMED", "logger off")\n                    },\n                    modifier = Modifier.fillMaxWidth(),\n                ) { Text("STOP PASSIVE LOGGER") }\n                Text(\n                    "PASSIVE is the main test: press the physical microphone button once. It logs the raw Accessibility KeyEvent, InputDevice, Activity key/intent path, focus/lifecycle changes and the package/window opened by BYD, without intentionally consuming the button.",\n                    style = MaterialTheme.typography.bodySmall,\n                )\n\n                Button(\n                    onClick = {\n                        micLoggerArmed = true\n                        diagPrefs.edit().putBoolean("mic_button_logger_armed", true).apply()\n                        SteeringWheelKeyService.capturedKey.value = null\n                        SteeringWheelKeyService.learnMode = true\n                        DiLink3DebugLog.log(context, "MIC_CAPTURE_CONSUME_ARMED", "next steering key will be consumed")\n                    },\n                    modifier = Modifier.fillMaxWidth(),\n                ) { Text("CAPTURE + CONSUME NEXT KEY") }\n                Button(\n                    enabled = capturedSteeringKey != null,\n                    onClick = {\n                        capturedSteeringKey?.let { result ->\n                            blockKeyCode = result.keyCode\n                            diagPrefs.edit().putInt("mic_button_block_keycode", result.keyCode).apply()\n                            DiLink3DebugLog.log(context, "MIC_BLOCK_KEY_SELECTED", "keyCode=${result.keyCode}")\n                        }\n                    },\n                    modifier = Modifier.fillMaxWidth(),\n                ) { Text("USE CAPTURED KEY AS BLOCK KEY") }\n                Button(\n                    onClick = {\n                        blockNativeVoice = !blockNativeVoice\n                        diagPrefs.edit().putBoolean("mic_button_block_native", blockNativeVoice).apply()\n                        DiLink3DebugLog.log(context, "MIC_NATIVE_BLOCK", "enabled=$blockNativeVoice key=$blockKeyCode")\n                    },\n                    modifier = Modifier.fillMaxWidth(),\n                ) { Text(if (blockNativeVoice) "UNBLOCK KEY $blockKeyCode" else "BLOCK KEY $blockKeyCode") }\n                Text(\n                    "BLOCK is a separate reversible test. It swallows both DOWN and UP for the selected key inside SteeringWheelKeyService before BYDMate voice handling. Use it only after PASSIVE logging identifies the key.",\n                    style = MaterialTheme.typography.bodySmall,\n                )\n\n                Text("ANDROID TTS INVENTORY", style = MaterialTheme.typography.titleSmall)\n                DebugRow("Installed TTS services", if (ttsServices.isEmpty()) "NONE" else ttsServices.joinToString())\n                Text(\n                    "This detects Android TextToSpeech services actually installed in DiLink.",\n                    style = MaterialTheme.typography.bodySmall,\n                )\n\n                Text("AI PROVIDER - AIHubMix", style = MaterialTheme.typography.titleSmall)\n'''
if needle not in s:
    raise SystemExit('mic diagnostics UI insertion point not found')
s = s.replace(needle, repl, 1)

# Remove obsolete legacy controls requested earlier: START Voice + RAW GigaAM test and counters.
start = s.find('                Text("STEP 2B - Legacy VoiceController / RAW GigaAM"')
end = s.find('                Button(\n                    onClick = { expanded = false }', start)
if start == -1 or end == -1:
    raise SystemExit('legacy GigaAM block boundaries not found')
s = s[:start] + s[end:]

p.write_text(s)
print('Applied maximum passive mic-button trace + reversible dynamic key block + TTS inventory diagnostics')
