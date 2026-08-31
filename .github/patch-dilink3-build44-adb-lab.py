from pathlib import Path

# 1) Expose the on-device ADB client through the existing Hilt entry point.
p = Path('app/src/main/kotlin/com/bydmate/app/cluster/ClusterEntryPoint.kt')
s = p.read_text()
if 'import com.bydmate.app.data.autoservice.AdbOnDeviceClient' not in s:
    s = s.replace('package com.bydmate.app.cluster\n\n', 'package com.bydmate.app.cluster\n\nimport com.bydmate.app.data.autoservice.AdbOnDeviceClient\n')
if 'fun adbOnDeviceClient(): AdbOnDeviceClient' not in s:
    s = s.replace('    fun helperBootstrap(): HelperBootstrap\n', '    fun helperBootstrap(): HelperBootstrap\n    fun adbOnDeviceClient(): AdbOnDeviceClient\n')
p.write_text(s)

# 2) Add a deliberately allow-listed rootless diagnostic command surface.
p = Path('app/src/main/kotlin/com/bydmate/app/data/autoservice/AdbOnDeviceClient.kt')
s = p.read_text()
if 'suspend fun execDiagnostic(id: String): String?' not in s:
    s = s.replace(
        '    suspend fun exec(cmd: String): String?\n',
        '    suspend fun exec(cmd: String): String?\n'
        '    /** Executes one hardcoded, rootless diagnostic shell command by id. */\n'
        '    suspend fun execDiagnostic(id: String): String?\n'
    )

marker = '    override suspend fun grantUsageStatsAppop(packageName: String): Boolean = withContext(Dispatchers.IO) {'
if 'override suspend fun execDiagnostic(id: String): String?' not in s:
    impl = '''    override suspend fun execDiagnostic(id: String): String? = withContext(Dispatchers.IO) {
        val cmd = when (id) {
            // Read-only snapshots available to the shell uid on stock Android/DiLink.
            "settings_voice" -> "echo assistant=$(settings get secure assistant); echo voice_interaction_service=$(settings get secure voice_interaction_service); echo voice_recognition_service=$(settings get secure voice_recognition_service); echo enabled_accessibility_services=$(settings get secure enabled_accessibility_services); echo accessibility_enabled=$(settings get secure accessibility_enabled)"
            "vr_package" -> "dumpsys package com.byd.vrassistant 2>/dev/null | head -n 260"
            "autovoice_package" -> "dumpsys package com.byd.autovoice 2>/dev/null | head -n 220"
            "voice_processes" -> "ps -A 2>/dev/null | grep -Ei 'byd|voice|vr|assistant' | head -n 120"
            "activity_top" -> "dumpsys activity activities 2>/dev/null | grep -Ei 'mResumedActivity|topResumedActivity|byd|vrassistant|autovoice' | head -n 160"
            "services_voice" -> "dumpsys activity services 2>/dev/null | grep -Ei 'byd|vrassistant|autovoice|voice' | head -n 200"
            "window_top" -> "dumpsys window windows 2>/dev/null | grep -Ei 'mCurrentFocus|mFocusedApp|byd|vrassistant|autovoice' | head -n 120"
            "appops_vr" -> "appops get com.byd.vrassistant 2>/dev/null | grep -Ei 'RECORD_AUDIO|MICROPHONE|SYSTEM_ALERT_WINDOW|RUN_IN_BACKGROUND|WAKE_LOCK|FOREGROUND' | head -n 100"
            "resolve_voice" -> "cmd package resolve-activity --brief -a android.intent.action.VOICE_COMMAND 2>&1; cmd package resolve-activity --brief -a android.intent.action.ASSIST 2>&1; cmd package resolve-activity --brief -a android.speech.action.RECOGNIZE_SPEECH 2>&1"

            // Active but non-persistent tests. No root required; all run as shell uid.
            "force_stop_vr" -> "am force-stop com.byd.vrassistant; echo force_stop_rc=$?; sleep 1; ps -A 2>/dev/null | grep -F com.byd.vrassistant || true"
            "inject_304" -> "input keyevent 304; echo input_keyevent_rc=$?"
            "start_voice_command" -> "am start -a android.intent.action.VOICE_COMMAND 2>&1 | head -n 80"
            "start_assist" -> "am start -a android.intent.action.ASSIST 2>&1 | head -n 80"
            else -> throw IllegalArgumentException("Unknown diagnostic command id: $id")
        }
        val p = protocol ?: run {
            val r = connect()
            if (r.isFailure) return@withContext null
            protocol ?: return@withContext null
        }
        try {
            kotlinx.coroutines.runInterruptible { p.exec(cmd) }
        } catch (e: Exception) {
            Log.w(TAG, "execDiagnostic($id) failed: ${e.message}")
            null
        }
    }

'''
    if marker not in s:
        raise SystemExit('AdbOnDeviceClient impl insertion marker not found')
    s = s.replace(marker, impl + marker, 1)
p.write_text(s)

# 3) Extend Test Lab UI with ADB alternatives. Build43 replaces the whole panel first.
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()
if 'val adb = remember { entry.adbOnDeviceClient() }' not in s:
    s = s.replace('    val bootstrap = remember { entry.helperBootstrap() }\n', '    val bootstrap = remember { entry.helperBootstrap() }\n    val adb = remember { entry.adbOnDeviceClient() }\n')

anchor = '    fun runPassivePack() {'
if 'fun runAdbTest(id: String, label: String)' not in s:
    fn = '''    fun runAdbTest(id: String, label: String) {
        scope.launch {
            status = "ADB: $label..."
            log("LAB_ADB_TEST_START", "id=$id label=$label")
            val connect = runCatching { adb.connect() }.getOrNull()
            val connected = runCatching { adb.isConnected() }.getOrDefault(false)
            log("LAB_ADB_CONNECT", "id=$id result=$connect connected=$connected")
            if (!connected) {
                status = "ADB недоступен: $label"
                log("LAB_ADB_TEST_END", "id=$id success=false reason=not_connected")
                return@launch
            }
            val started = android.os.SystemClock.elapsedRealtime()
            val out = runCatching { adb.execDiagnostic(id) }
                .onFailure { log("LAB_ADB_ERROR", "id=$id ${it::class.java.simpleName}:${it.message}") }
                .getOrNull()
            val dt = android.os.SystemClock.elapsedRealtime() - started
            if (out == null) {
                log("LAB_ADB_RESULT", "id=$id dtMs=$dt output=NULL")
                status = "ADB $label: нет результата"
            } else {
                val clipped = if (out.length > 12000) out.take(12000) + "\\n...[clipped]" else out
                clipped.lineSequence().forEachIndexed { index, line ->
                    if (line.isNotBlank()) log("LAB_ADB_OUT", "id=$id line=$index $line")
                }
                log("LAB_ADB_RESULT", "id=$id dtMs=$dt chars=${out.length} lines=${out.lineSequence().count()}")
                status = "ADB $label: готово (${dt} мс)"
            }
            log("LAB_ADB_TEST_END", "id=$id success=${out != null}")
        }
    }

    fun runAdbPassivePack() {
        scope.launch {
            status = "ADB: полный пассивный пакет..."
            val ids = listOf(
                "settings_voice" to "Secure voice settings",
                "resolve_voice" to "Intent resolve",
                "voice_processes" to "Voice processes",
                "activity_top" to "Activity stack",
                "services_voice" to "Voice services",
                "window_top" to "Window focus",
                "appops_vr" to "VR appops",
                "vr_package" to "vrassistant package",
                "autovoice_package" to "autovoice package",
            )
            val connected = runCatching { adb.connect(); adb.isConnected() }.getOrDefault(false)
            log("LAB_ADB_PACK_START", "connected=$connected count=${ids.size}")
            if (!connected) {
                status = "ADB недоступен"
                log("LAB_ADB_PACK_END", "success=false")
                return@launch
            }
            ids.forEach { (id, label) ->
                val started = android.os.SystemClock.elapsedRealtime()
                val out = runCatching { adb.execDiagnostic(id) }.getOrNull()
                val dt = android.os.SystemClock.elapsedRealtime() - started
                log("LAB_ADB_PACK_ITEM", "id=$id label=$label dtMs=$dt chars=${out?.length ?: -1}")
                out?.take(12000)?.lineSequence()?.forEachIndexed { index, line ->
                    if (line.isNotBlank()) log("LAB_ADB_OUT", "id=$id line=$index $line")
                }
                delay(150)
            }
            log("LAB_ADB_PACK_END", "success=true")
            status = "ADB пассивный пакет завершён"
        }
    }

'''
    if anchor not in s:
        raise SystemExit('Test Lab function insertion anchor not found')
    s = s.replace(anchor, fn + anchor, 1)

ui_anchor = '            Text("Каждый тест пишет LAB_* строки. После серии тестов экспортируйте один общий лог.")'
if 'ADB БЕЗ ROOT' not in s:
    ui = '''            Text("ADB БЕЗ ROOT", style = MaterialTheme.typography.titleMedium)
            Text("Команды выполняются через встроенный on-device ADB от shell uid. Никакого su/root. Активные тесты не меняют настройки постоянно.")
            Button(onClick = { runAdbPassivePack() }, modifier = Modifier.fillMaxWidth()) { Text("8. ADB: ВСЕ ПАССИВНЫЕ ПРОВЕРКИ") }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                Button(onClick = { runAdbTest("settings_voice", "Secure voice settings") }, modifier = Modifier.weight(1f)) { Text("Secure settings") }
                Button(onClick = { runAdbTest("resolve_voice", "Intent resolve") }, modifier = Modifier.weight(1f)) { Text("Resolve intents") }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                Button(onClick = { runAdbTest("activity_top", "Activity stack") }, modifier = Modifier.weight(1f)) { Text("Activity") }
                Button(onClick = { runAdbTest("window_top", "Window focus") }, modifier = Modifier.weight(1f)) { Text("Window") }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                Button(onClick = { runAdbTest("services_voice", "Voice services") }, modifier = Modifier.weight(1f)) { Text("Services") }
                Button(onClick = { runAdbTest("voice_processes", "Voice processes") }, modifier = Modifier.weight(1f)) { Text("Processes") }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                Button(onClick = { runAdbTest("vr_package", "vrassistant package") }, modifier = Modifier.weight(1f)) { Text("VR package") }
                Button(onClick = { runAdbTest("appops_vr", "VR appops") }, modifier = Modifier.weight(1f)) { Text("VR appops") }
            }
            Text("Активные ADB альтернативы", style = MaterialTheme.typography.titleSmall)
            Button(onClick = { runAdbTest("force_stop_vr", "Force-stop BYD Assistant") }, modifier = Modifier.fillMaxWidth()) { Text("9. FORCE-STOP VRASSISTANT → потом 304") }
            Button(onClick = { runAdbTest("inject_304", "ADB input keyevent 304") }, modifier = Modifier.fillMaxWidth()) { Text("10. ADB INPUT KEYEVENT 304") }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                Button(onClick = { runAdbTest("start_voice_command", "ADB VOICE_COMMAND") }, modifier = Modifier.weight(1f)) { Text("VOICE_COMMAND") }
                Button(onClick = { runAdbTest("start_assist", "ADB ASSIST") }, modifier = Modifier.weight(1f)) { Text("ASSIST") }
            }

'''
    if ui_anchor not in s:
        raise SystemExit('Test Lab UI insertion anchor not found')
    s = s.replace(ui_anchor, ui + ui_anchor, 1)

s = s.replace('DiLink3 Voice Test Lab #43', 'DiLink3 Voice Test Lab #44')
p.write_text(s)
