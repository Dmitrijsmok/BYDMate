from pathlib import Path

# Build53: make field logs self-proving and impossible to confuse with stale Build47/49 logs.
# The Build52 APK itself no longer contains A11Y_WINDOW_TRACE, but app data survives updates,
# so old lines can remain in dilink3-voice-debug.log and be shared after a successful update.
# Reset the file when the live AccessibilityService connects, then add unique Build53 markers.

p = Path('app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt')
s = p.read_text()

anchor = '        Log.d(TAG, "connected; filtering steering-wheel keys")\n'
insert = anchor + '''        DiLink3DebugLog.clear(applicationContext)\n        DiLink3DebugLog.log(\n            applicationContext,\n            "BUILD53_LOG_RESET",\n            "reason=a11y_service_connected versionCode=60002 staleLogRemoved=true"\n        )\n'''
if anchor not in s:
    raise SystemExit('build53 service-connected anchor not found')
s = s.replace(anchor, insert, 1)

p.write_text(s)

# Update the compact diagnostic panel so the installed APK and shared log identify Build53.
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()
replacements = {
    'DiLink3 STOCK ASSISTANT BLOCKER #50': 'DiLink3 STOCK ASSISTANT BLOCKER #53',
    'log("BUILD50_STATUS", "steeringConnected=$connected stockAssistant327Block=true allKeyTrace=true")':
        'log("BUILD53_STATUS", "steeringConnected=$connected stockAssistant327Block=true allKeyTrace=true versionCode=60002")',
    'DiLink3DebugLog.log(context, "BUILD50_LOG_SHARE_PRESSED",':
        'DiLink3DebugLog.log(context, "BUILD53_LOG_SHARE_PRESSED",',
}
for old, new in replacements.items():
    if old not in s:
        raise SystemExit('build53 panel anchor not found: ' + old)
    s = s.replace(old, new, 1)
p.write_text(s)

print('build53 stale-log reset and provenance markers installed')
