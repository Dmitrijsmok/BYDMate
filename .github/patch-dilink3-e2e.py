from pathlib import Path

p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()

needle = '''    var systemAsrPartial by remember { mutableStateOf("") }\n\n    val systemRecognizer = remember(systemAsrAvailable) {'''
replacement = '''    var systemAsrPartial by remember { mutableStateOf("") }\n\n    // End-to-end DiLink3 path: System SpeechRecognizer -> production BYDMate agent -> production TTS.\n    val e2eBridge = remember { DiLink3E2EBridge(context.applicationContext) }\n    var e2eStatus by remember { mutableStateOf("idle") }\n    var e2eTranscript by remember { mutableStateOf("") }\n    var e2eAnswer by remember { mutableStateOf("") }\n    var e2eError by remember { mutableStateOf("") }\n    var e2eSpoken by remember { mutableStateOf(false) }\n\n    val systemRecognizer = remember(systemAsrAvailable) {'''
if needle not in s:
    raise SystemExit('E2E state insertion point not found')
s = s.replace(needle, replacement, 1)

needle = '''            override fun onError(error: Int) {\n                systemAsrRunning = false\n                systemAsrError = "$error / ${speechErrorName(error)}"\n                systemAsrStatus = "ERROR"\n            }'''
replacement = '''            override fun onError(error: Int) {\n                systemAsrRunning = false\n                systemAsrError = "$error / ${speechErrorName(error)}"\n                systemAsrStatus = "ERROR"\n                e2eStatus = "ASR ERROR"\n                e2eError = systemAsrError\n            }'''
if needle not in s:
    raise SystemExit('onError insertion point not found')
s = s.replace(needle, replacement, 1)

needle = '''            override fun onResults(results: Bundle?) {\n                systemAsrRunning = false\n                val heard = results\n                    ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)\n                    ?.joinToString(" | ")\n                    .orEmpty()\n                systemAsrHeard = heard\n                systemAsrStatus = if (heard.isBlank()) "finished - no text" else "decoded"\n            }'''
replacement = '''            override fun onResults(results: Bundle?) {\n                systemAsrRunning = false\n                val alternatives = results\n                    ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)\n                    .orEmpty()\n                val transcript = alternatives.firstOrNull().orEmpty().trim()\n                systemAsrHeard = alternatives.joinToString(" | ")\n                systemAsrStatus = if (transcript.isBlank()) "finished - no text" else "decoded"\n\n                if (transcript.isBlank()) {\n                    e2eStatus = "NO SPEECH"\n                    e2eError = "SpeechRecognizer returned no final text"\n                    return\n                }\n\n                e2eTranscript = transcript\n                e2eAnswer = ""\n                e2eError = ""\n                e2eSpoken = false\n                e2eStatus = "asking BYDMate AI..."\n                scope.launch {\n                    try {\n                        val result = e2eBridge.askAndSpeak(transcript)\n                        if (result.error != null) {\n                            e2eStatus = "AGENT ERROR"\n                            e2eError = result.error\n                        } else {\n                            e2eAnswer = result.answer.orEmpty()\n                            e2eSpoken = result.spoken\n                            e2eStatus = if (result.spoken) "ANSWERED + SPEAKING" else "ANSWERED (TTS not started)"\n                        }\n                    } catch (t: Throwable) {\n                        e2eStatus = "E2E ERROR"\n                        e2eError = "${t::class.java.simpleName}: ${t.message}"\n                    }\n                }\n            }'''
if needle not in s:
    raise SystemExit('onResults insertion point not found')
s = s.replace(needle, replacement, 1)

needle = '''                Text("STEP 2A - Android System SpeechRecognizer", style = MaterialTheme.typography.titleSmall)\n                Text(\n                    "Alternative engine test. It bypasses the GigaAM model and uses the speech recognition service installed in DiLink. If this decodes speech while GigaAM does not, the microphone path is good and the problem is GigaAM/model download or decoding.",\n                    style = MaterialTheme.typography.bodySmall,\n                )'''
replacement = '''                Text("STEP 2A - END TO END: System ASR -> BYDMate AI -> TTS", style = MaterialTheme.typography.titleSmall)\n                Text(\n                    "Press the button, ask a normal question, then stop speaking. DiLink's System SpeechRecognizer supplies the text, BYDMate sends it through the production AI agent, and the existing TTS voice speaks the final answer.",\n                    style = MaterialTheme.typography.bodySmall,\n                )'''
if needle not in s:
    raise SystemExit('STEP 2A text insertion point not found')
s = s.replace(needle, replacement, 1)

needle = '''                        } else {\n                            systemAsrHeard = ""\n                            systemAsrPartial = ""\n                            systemAsrError = ""\n                            systemAsrStatus = "starting..."\n                            val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {'''
replacement = '''                        } else {\n                            systemAsrHeard = ""\n                            systemAsrPartial = ""\n                            systemAsrError = ""\n                            systemAsrStatus = "starting..."\n                            e2eStatus = "LISTENING"\n                            e2eTranscript = ""\n                            e2eAnswer = ""\n                            e2eError = ""\n                            e2eSpoken = false\n                            val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {'''
if needle not in s:
    raise SystemExit('start reset insertion point not found')
s = s.replace(needle, replacement, 1)

needle = '''                ) {\n                    Text(if (systemAsrRunning) "STOP SYSTEM ASR" else "TEST ANDROID SYSTEM ASR")\n                }\n                DebugRow("System ASR status", systemAsrStatus)\n                DebugRow("System ASR partial", systemAsrPartial.ifBlank { "<none>" })\n                DebugRow("System ASR HEARD", systemAsrHeard.ifBlank { "<nothing decoded>" })\n                DebugRow("System ASR ERROR", systemAsrError.ifBlank { "none" })'''
replacement = '''                ) {\n                    Text(if (systemAsrRunning) "STOP LISTENING" else "TALK TO BYDMATE - END TO END")\n                }\n                DebugRow("E2E status", e2eStatus)\n                DebugRow("YOU SAID", e2eTranscript.ifBlank { systemAsrPartial.ifBlank { "<waiting>" } })\n                DebugRow("BYDMATE ANSWER", e2eAnswer.ifBlank { "<waiting>" })\n                DebugRow("TTS spoken", yesNo(e2eSpoken))\n                DebugRow("E2E ERROR", e2eError.ifBlank { "none" })\n                DebugRow("System ASR status", systemAsrStatus)\n                DebugRow("System ASR alternatives", systemAsrHeard.ifBlank { "<nothing decoded>" })'''
if needle not in s:
    raise SystemExit('E2E result UI insertion point not found')
s = s.replace(needle, replacement, 1)

needle = '''                Text("STEP 2B - VoiceController / RAW GigaAM", style = MaterialTheme.typography.titleSmall)'''
replacement = '''                Text(\n                    "This end-to-end button intentionally bypasses GigaAM because the vehicle System ASR has already decoded real Russian speech successfully. GigaAM diagnostics remain below for comparison.",\n                    style = MaterialTheme.typography.bodySmall,\n                )\n\n                Text("STEP 2B - Legacy VoiceController / RAW GigaAM", style = MaterialTheme.typography.titleSmall)'''
if needle not in s:
    raise SystemExit('STEP 2B insertion point not found')
s = s.replace(needle, replacement, 1)

p.write_text(s)
print('Applied DiLink3 E2E System ASR -> Agent -> TTS patch')
