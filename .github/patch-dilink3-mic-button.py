from pathlib import Path

# Patch steering-wheel accessibility service: log raw key data, observe assistant window launch,
# and optionally swallow the known BYD voice key (320) without invoking legacy GigaAM.
p = Path('app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt')
s = p.read_text()

needle = 'import com.bydmate.app.service.TrackingService\n'
repl = 'import com.bydmate.app.service.TrackingService\nimport com.bydmate.app.ui.diagnostics.DiLink3DebugLog\n'
if needle not in s:
    raise SystemExit('service import insertion point not found')
s = s.replace(needle, repl, 1)

needle = '        Log.d(TAG, "connected; filtering steering-wheel keys")\n'
repl = '''        Log.d(TAG, "connected; filtering steering-wheel keys")\n        DiLink3DebugLog.log(applicationContext, "STEERING_A11Y_CONNECTED", "filterKeyEvents=true")\n'''
s = s.replace(needle, repl, 1)

needle = '''    override fun onKeyEvent(event: KeyEvent): Boolean {\n        val isDown = event.action == KeyEvent.ACTION_DOWN\n'''
repl = '''    override fun onKeyEvent(event: KeyEvent): Boolean {\n        val isDown = event.action == KeyEvent.ACTION_DOWN\n        val diagPrefs = applicationContext.getSharedPreferences("dilink3_diag", Context.MODE_PRIVATE)\n        val micLoggerArmed = diagPrefs.getBoolean("mic_button_logger_armed", false)\n        if (micLoggerArmed) {\n            DiLink3DebugLog.log(\n                applicationContext,\n                "STEERING_KEY",\n                "action=${event.action} keyCode=${event.keyCode} scanCode=${event.scanCode} repeat=${event.repeatCount} deviceId=${event.deviceId} source=${event.source} flags=${event.flags}"\n            )\n        }\n'''
if needle not in s:
    raise SystemExit('onKeyEvent insertion point not found')
s = s.replace(needle, repl, 1)

needle = '''        // Voice check: runs after learn-mode, before star decision. Returns true only when voice is\n'''
repl = '''        // Diagnostic-only reversible test: swallow the known BYD voice key before the stock\n        // assistant sees either DOWN or UP. This proves whether Accessibility interception is enough\n        // on this DiLink build. It does NOT launch legacy VoiceController/GigaAM.\n        val blockNativeVoice = diagPrefs.getBoolean("mic_button_block_native", false)\n        if (blockNativeVoice && event.keyCode == DEFAULT_VOICE_KEYCODE) {\n            DiLink3DebugLog.log(applicationContext, "MIC_BUTTON_BLOCKED", "keyCode=${event.keyCode} action=${event.action}")\n            return true\n        }\n\n        // Voice check: runs after learn-mode, before star decision. Returns true only when voice is\n'''
if needle not in s:
    raise SystemExit('voice block insertion point not found')
s = s.replace(needle, repl, 1)

needle = '''    override fun onAccessibilityEvent(event: AccessibilityEvent?) {\n        NavA11yFeed.onEvent(this, event)\n    }'''
repl = '''    override fun onAccessibilityEvent(event: AccessibilityEvent?) {\n        if (event != null) {\n            val diagPrefs = applicationContext.getSharedPreferences("dilink3_diag", Context.MODE_PRIVATE)\n            if (diagPrefs.getBoolean("mic_button_logger_armed", false) &&\n                (event.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED ||\n                 event.eventType == AccessibilityEvent.TYPE_WINDOWS_CHANGED)) {\n                DiLink3DebugLog.log(\n                    applicationContext,\n                    "A11Y_WINDOW",\n                    "type=${event.eventType} package=${event.packageName} class=${event.className}"\n                )\n            }\n        }\n        NavA11yFeed.onEvent(this, event)\n    }'''
if needle not in s:
    raise SystemExit('a11y event insertion point not found')
s = s.replace(needle, repl, 1)
p.write_text(s)

# Patch diagnostic panel after E2E + AIHubMix + logging patches.
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
repl = '''    var logShareStatus by remember { mutableStateOf("ready") }\n    val diagPrefs = remember { context.getSharedPreferences("dilink3_diag", Context.MODE_PRIVATE) }\n    var micLoggerArmed by remember { mutableStateOf(diagPrefs.getBoolean("mic_button_logger_armed", false)) }\n    var blockNativeVoice by remember { mutableStateOf(diagPrefs.getBoolean("mic_button_block_native", false)) }\n    val capturedSteeringKey by SteeringWheelKeyService.capturedKey.collectAsState()\n    val ttsServices = remember {\n        runCatching {\n            context.packageManager\n                .queryIntentServices(Intent(TextToSpeech.Engine.INTENT_ACTION_TTS_SERVICE), 0)\n                .mapNotNull { it.serviceInfo?.packageName }\n                .distinct()\n        }.getOrDefault(emptyList())\n    }\n'''
if needle not in s:
    raise SystemExit('diag state insertion point not found')
s = s.replace(needle, repl, 1)

needle = '''        DiLink3DebugLog.log(context, "DEBUG_SESSION_START", "systemAsrAvailable=$systemAsrAvailable")\n        e2eBridge.warmUpTts()'''
repl = '''        DiLink3DebugLog.log(context, "DEBUG_SESSION_START", "systemAsrAvailable=$systemAsrAvailable")\n        DiLink3DebugLog.log(context, "ANDROID_TTS_SERVICES", "count=${ttsServices.size} packages=${ttsServices.joinToString()}")\n        e2eBridge.warmUpTts()'''
if needle not in s:
    raise SystemExit('TTS inventory log insertion point not found')
s = s.replace(needle, repl, 1)

needle = '                Text("AI PROVIDER - AIHubMix", style = MaterialTheme.typography.titleSmall)\n'
repl = '''                Text("MIC BUTTON / STOCK BYD ASSISTANT", style = MaterialTheme.typography.titleSmall)\n                DebugRow("Accessibility key filter", if (SteeringWheelKeyService.isConnected) "CONNECTED" else "NOT CONNECTED")\n                DebugRow("Known BYD voice key", DEFAULT_VOICE_KEYCODE.toString())\n                DebugRow("Captured key", capturedSteeringKey?.let { "${it.keyCode} assignable=${it.assignable}" } ?: "<none>")\n                Button(\n                    onClick = {\n                        micLoggerArmed = true\n                        diagPrefs.edit().putBoolean("mic_button_logger_armed", true).apply()\n                        SteeringWheelKeyService.capturedKey.value = null\n                        SteeringWheelKeyService.learnMode = true\n                        DiLink3DebugLog.log(context, "MIC_LOGGER_ARMED", "press physical microphone button now")\n                    },\n                    modifier = Modifier.fillMaxWidth(),\n                ) { Text("ARM + CAPTURE PHYSICAL MIC BUTTON") }\n                Button(\n                    onClick = {\n                        blockNativeVoice = !blockNativeVoice\n                        diagPrefs.edit().putBoolean("mic_button_block_native", blockNativeVoice).apply()\n                        DiLink3DebugLog.log(context, "MIC_NATIVE_BLOCK", "enabled=$blockNativeVoice key=$DEFAULT_VOICE_KEYCODE")\n                    },\n                    modifier = Modifier.fillMaxWidth(),\n                ) { Text(if (blockNativeVoice) "UNBLOCK STOCK BYD ASSISTANT" else "BLOCK STOCK BYD ASSISTANT (KEY 320 TEST)") }\n                Text(\n                    "Capture mode consumes the next steering-wheel key so its native action should not fire. The block test is reversible and only swallows key 320; it does not call legacy GigaAM. Logs include keyCode/scanCode/device/source plus the package/window that appears after the press.",\n                    style = MaterialTheme.typography.bodySmall,\n                )\n\n                Text("ANDROID TTS INVENTORY", style = MaterialTheme.typography.titleSmall)\n                DebugRow("Installed TTS services", if (ttsServices.isEmpty()) "NONE" else ttsServices.joinToString())\n                Text(\n                    "This only detects Android TextToSpeech services actually installed in DiLink. If NONE, we will use a separate modern TTS provider instead of pretending Android System TTS exists.",\n                    style = MaterialTheme.typography.bodySmall,\n                )\n\n                Text("AI PROVIDER - AIHubMix", style = MaterialTheme.typography.titleSmall)\n'''
if needle not in s:
    raise SystemExit('mic diagnostics UI insertion point not found')
s = s.replace(needle, repl, 1)

# Remove obsolete legacy controls requested by the user: START Voice + RAW GigaAM test and counters.
start = s.find('                Text("STEP 2B - Legacy VoiceController / RAW GigaAM"')
end = s.find('                Button(\n                    onClick = { expanded = false }', start)
if start == -1 or end == -1:
    raise SystemExit('legacy GigaAM block boundaries not found')
s = s[:start] + s[end:]

p.write_text(s)
print('Applied DiLink3 mic-button interception + TTS inventory diagnostics; removed legacy Voice/GigaAM controls')
