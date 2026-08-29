from pathlib import Path

p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()

# AIHubMix patch inserts its own state between e2eSpoken and systemRecognizer, so anchor the
# logging state directly before systemRecognizer instead of depending on the previous layout.
needle = '''    val systemRecognizer = remember(systemAsrAvailable) {'''
replacement = '''    var logShareStatus by remember { mutableStateOf("ready") }\n\n    LaunchedEffect(Unit) {\n        DiLink3DebugLog.clear(context)\n        DiLink3DebugLog.log(context, "DEBUG_SESSION_START", "systemAsrAvailable=$systemAsrAvailable")\n        e2eBridge.warmUpTts()\n    }\n\n    val systemRecognizer = remember(systemAsrAvailable) {'''
if needle not in s:
    raise SystemExit('logging state insertion point not found')
s = s.replace(needle, replacement, 1)

repls = [
('''            override fun onReadyForSpeech(params: Bundle?) {\n                systemAsrRunning = true\n                systemAsrStatus = "ready - speak now"\n            }''', '''            override fun onReadyForSpeech(params: Bundle?) {\n                systemAsrRunning = true\n                systemAsrStatus = "ready - speak now"\n                DiLink3DebugLog.log(context, "ASR_READY")\n            }'''),
('''            override fun onBeginningOfSpeech() {\n                systemAsrStatus = "speech detected"\n            }''', '''            override fun onBeginningOfSpeech() {\n                systemAsrStatus = "speech detected"\n                DiLink3DebugLog.log(context, "ASR_SPEECH_BEGIN")\n            }'''),
('''            override fun onEndOfSpeech() {\n                systemAsrStatus = "decoding..."\n            }''', '''            override fun onEndOfSpeech() {\n                systemAsrStatus = "decoding..."\n                DiLink3DebugLog.log(context, "ASR_SPEECH_END")\n            }'''),
('''                e2eStatus = "ASR ERROR"\n                e2eError = systemAsrError\n            }''', '''                e2eStatus = "ASR ERROR"\n                e2eError = systemAsrError\n                DiLink3DebugLog.log(context, "ASR_ERROR", systemAsrError)\n            }'''),
('''                e2eTranscript = transcript\n                e2eAnswer = ""''', '''                DiLink3DebugLog.log(context, "ASR_FINAL", "text=$transcript alternatives=${alternatives.size}")\n                e2eTranscript = transcript\n                e2eAnswer = ""'''),
('''                            e2eStatus = "LISTENING"\n                            e2eTranscript = ""''', '''                            e2eStatus = "LISTENING"\n                            DiLink3DebugLog.log(context, "E2E_BUTTON_PRESSED", "start listening")\n                            e2eTranscript = ""'''),
]
for old, new in repls:
    if old not in s:
        raise SystemExit('logging insertion point not found: ' + old[:50])
    s = s.replace(old, new, 1)

needle = '''                DebugRow("System ASR status", systemAsrStatus)\n                DebugRow("System ASR alternatives", systemAsrHeard.ifBlank { "<nothing decoded>" })'''
replacement = '''                DebugRow("System ASR status", systemAsrStatus)\n                DebugRow("System ASR alternatives", systemAsrHeard.ifBlank { "<nothing decoded>" })\n\n                Button(\n                    onClick = {\n                        DiLink3DebugLog.log(context, "LOG_SHARE_PRESSED")\n                        logShareStatus = if (DiLink3DebugLog.shareToTelegram(context)) "opened Telegram/share" else "share failed"\n                    },\n                    modifier = Modifier.fillMaxWidth(),\n                ) {\n                    Text("SEND DEBUG LOG TO TELEGRAM")\n                }\n                DebugRow("Log share", logShareStatus)\n                Button(\n                    onClick = {\n                        DiLink3DebugLog.clear(context)\n                        DiLink3DebugLog.log(context, "LOG_CLEARED")\n                        logShareStatus = "cleared"\n                    },\n                    modifier = Modifier.fillMaxWidth(),\n                ) {\n                    Text("CLEAR DEBUG LOG")\n                }'''
if needle not in s:
    raise SystemExit('Telegram button insertion point not found')
s = s.replace(needle, replacement, 1)

p.write_text(s)
print('Applied DiLink3 timing log + Telegram share patch')
