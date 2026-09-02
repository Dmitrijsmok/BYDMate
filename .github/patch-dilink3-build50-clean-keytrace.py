from pathlib import Path

# Build50: clean production diagnostic build.
# - Keep the confirmed Build49 permanent keyCode 327 blocker unchanged.
# - Remove the extremely noisy Accessibility window/content trace.
# - Disable the stale legacy passive-logger preference left by earlier lab builds.
# - Log every KeyEvent that actually reaches SteeringWheelKeyService.onKeyEvent(),
#   before any event is consumed, so a physical mic press can be proven end-to-end.

p = Path('app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt')
s = p.read_text()

# 1) Remove the legacy A11Y_WINDOW_TRACE block entirely. Navigation feed remains intact.
old_a11y = '''    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event != null) {
            val diagPrefs = applicationContext.getSharedPreferences("dilink3_diag", Context.MODE_PRIVATE)
            if (diagPrefs.getBoolean("mic_button_logger_armed", false) &&
                (event.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED ||
                 event.eventType == AccessibilityEvent.TYPE_WINDOWS_CHANGED ||
                 event.eventType == AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED)) {
                val text = runCatching { event.text?.joinToString(" | ") }.getOrNull()
                DiLink3DebugLog.log(
                    applicationContext,
                    "A11Y_WINDOW_TRACE",
                    "type=${event.eventType} package=${event.packageName} class=${event.className} windowId=${event.windowId} " +
                        "action=${event.action} contentChangeTypes=${event.contentChangeTypes} contentDescription=${event.contentDescription} text=$text"
                )
            }
        }
        NavA11yFeed.onEvent(this, event)
    }'''
new_a11y = '''    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        NavA11yFeed.onEvent(this, event)
    }'''
if old_a11y not in s:
    raise SystemExit('build50 A11Y_WINDOW_TRACE block anchor not found')
s = s.replace(old_a11y, new_a11y, 1)

# 2) Clear stale old diagnostic logger state when the service binds. This prevents older
# STEERING_KEY_RAW / Activity trace code from producing duplicate legacy diagnostics.
connected_anchor = '''        DiLink3DebugLog.log(
            applicationContext,
            "BUILD49_A11Y_CONNECTED",
            "stockAssistant327Block=true"
        )
'''
connected_new = connected_anchor + '''        applicationContext.getSharedPreferences("dilink3_diag", Context.MODE_PRIVATE)
            .edit()
            .putBoolean("mic_button_logger_armed", false)
            .apply()
        DiLink3DebugLog.log(
            applicationContext,
            "BUILD50_A11Y_CONNECTED",
            "stockAssistant327Block=true legacyWindowTrace=false allKeyTrace=true"
        )
'''
if connected_anchor not in s:
    raise SystemExit('build50 Build49 connection marker anchor not found')
s = s.replace(connected_anchor, connected_new, 1)

# 3) Trace every KeyEvent that reaches AccessibilityService BEFORE the Build49 327 blocker.
# This is intentionally independent of old SharedPreferences diagnostic flags.
block_anchor = '''        // Build49 production DiLink3 blocker. One physical microphone press emits
'''
key_trace = '''        DiLink3DebugLog.log(
            applicationContext,
            "BUILD50_KEY_EVENT",
            "keyCode=${event.keyCode} keyName=${KeyEvent.keyCodeToString(event.keyCode)} " +
                "action=${event.action} actionName=${if (isDown) "DOWN" else if (event.action == KeyEvent.ACTION_UP) "UP" else "OTHER"} " +
                "scanCode=${event.scanCode} repeat=${event.repeatCount} deviceId=${event.deviceId} " +
                "source=${event.source} sourceHex=0x${event.source.toString(16)} flags=${event.flags} " +
                "metaState=${event.metaState} downTime=${event.downTime} eventTime=${event.eventTime}"
        )

'''
if block_anchor not in s:
    raise SystemExit('build50 Build49 327 blocker anchor not found')
s = s.replace(block_anchor, key_trace + block_anchor, 1)

p.write_text(s)

# 4) Make the diagnostic panel clearly identify Build50 and use Build50 markers.
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()
replacements = {
    'DiLink3 STOCK ASSISTANT BLOCKER #49': 'DiLink3 STOCK ASSISTANT BLOCKER #50',
    'log("BUILD49_STATUS", "steeringConnected=$connected stockAssistant327Block=true")':
        'log("BUILD50_STATUS", "steeringConnected=$connected stockAssistant327Block=true allKeyTrace=true")',
    'DiLink3DebugLog.log(context, "BUILD49_LOG_SHARE_PRESSED",':
        'DiLink3DebugLog.log(context, "BUILD50_LOG_SHARE_PRESSED",',
}
for old, new in replacements.items():
    if old not in s:
        raise SystemExit('build50 panel anchor not found: ' + old)
    s = s.replace(old, new, 1)
p.write_text(s)

print('build50 clean key trace installed')
