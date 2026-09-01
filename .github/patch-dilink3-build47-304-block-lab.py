from pathlib import Path

# Build47: minimal 304 BLOCK LAB. Keep only unresolved tests and log export.

# 1) Add a temporary diagnostic hard-consume gate for physical keyCode 304.
p = Path('app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt')
s = p.read_text()
if 'import com.bydmate.app.ui.diagnostics.DiLink3DebugLog' not in s:
    s = s.replace('import com.bydmate.app.service.TrackingService\n', 'import com.bydmate.app.service.TrackingService\nimport com.bydmate.app.ui.diagnostics.DiLink3DebugLog\n')
needle = '        val isDown = event.action == KeyEvent.ACTION_DOWN\n'
if 'BUILD47_A11Y_304_CONSUMED' not in s:
    gate = '''        val isDown = event.action == KeyEvent.ACTION_DOWN
        // Build47 diagnostic gate: when explicitly armed from the test lab, swallow BOTH
        // DOWN and UP of keyCode 304 before normal BYDMate routing. The flag is temporary,
        // stored only in this diagnostic APK, and the test lab clears it automatically.
        val build47Diag = applicationContext.getSharedPreferences("dilink3_diag", Context.MODE_PRIVATE)
        if (event.keyCode == 304 && build47Diag.getBoolean("build47_block_304", false)) {
            DiLink3DebugLog.log(
                applicationContext,
                "BUILD47_A11Y_304_CONSUMED",
                "action=${event.action} scanCode=${event.scanCode} deviceId=${event.deviceId} source=${event.source} isDown=$isDown"
            )
            return true
        }
'''
    if needle not in s:
        raise SystemExit('build47 SteeringWheelKeyService onKeyEvent anchor not found')
    s = s.replace(needle, gate, 1)
p.write_text(s)

# 2) Add one allow-listed passive probe for the BYD voice package family.
p = Path('app/src/main/kotlin/com/bydmate/app/data/autoservice/AdbOnDeviceClient.kt')
s = p.read_text()
anchor = '            "force_stop_vr" -> "am force-stop com.byd.vrassistant; echo force_stop_rc=$?; sleep 1; ps -A 2>/dev/null | grep -F com.byd.vrassistant || true"\n'
if '"voice_family_probe"' not in s:
    probe = '''            "voice_family_probe" -> "echo ===PACKAGES===; pm list packages -f 2>/dev/null | grep -Ei 'byd.*(voice|vr|assistant|speech|tts)|(voice|vr|assistant|speech|tts).*byd' | head -n 160; echo ===PROCESSES===; ps -A 2>/dev/null | grep -Ei 'byd.*(voice|vr|assistant|speech|tts)|(voice|vr|assistant|speech|tts).*byd' | head -n 160; echo ===SERVICES===; dumpsys activity services 2>/dev/null | grep -Ei 'byd.*(voice|vr|assistant|speech|tts)|(voice|vr|assistant|speech|tts).*byd' | head -n 240; echo ===VR_PACKAGE===; dumpsys package com.byd.vrassistant 2>/dev/null | grep -Ei 'Package \\[|Activity|Service|Receiver|enabled=|processName|permission|intent' | head -n 260"\n'''
    if anchor not in s:
        raise SystemExit('build47 ADB probe insertion anchor not found')
    s = s.replace(anchor, probe + anchor, 1)
p.write_text(s)

# 3) Add focused test functions, then replace the entire old Test Lab UI with a short one.
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()
fn_anchor = '    fun runAdbTest(id: String, label: String) {'
if 'fun runBuild47A11yConsume304' not in s:
    funcs = r'''    fun armBuild47Consume(enabled: Boolean) {
        diagPrefs.edit().putBoolean("build47_block_304", enabled).apply()
        log("BUILD47_BLOCK_FLAG", "enabled=$enabled steeringConnected=${SteeringWheelKeyService.isConnected}")
    }

    fun runBuild47A11yConsume304() {
        scope.launch {
            status = "A11Y BLOCK: сохраняю ORIGINAL..."
            if (!ensureAdbTransactionSnapshot()) {
                status = "A11Y BLOCK: snapshot не создан"
                return@launch
            }
            val original = diagPrefs.getString("adb_tx_a11y_services", "null") ?: "null"
            val diagComponent = "${context.packageName}/com.bydmate.app.cluster.SteeringWheelKeyService"
            val list = if (original == "null" || original.isBlank()) mutableListOf<String>()
                else original.split(':').filter { it.isNotBlank() }.toMutableList()
            if (!list.contains(diagComponent)) list.add(diagComponent)
            val r1 = runCatching { adb.execDiagnosticMutation("set_a11y_services", list.joinToString(":")) }.getOrNull()
            val r2 = runCatching { adb.execDiagnosticMutation("set_a11y_enabled", "1") }.getOrNull()
            log("BUILD47_A11Y_PREP", "services=${r1?.replace('\n','|')} enabled=${r2?.replace('\n','|')} component=$diagComponent")
            repeat(20) {
                if (!SteeringWheelKeyService.isConnected) delay(100)
            }
            armBuild47Consume(true)
            status = "A11Y CONSUME ACTIVE: нажмите физическую кнопку микрофона 3 раза"
            log("BUILD47_TEST_START", "test=a11y_consume_304 durationMs=12000 connected=${SteeringWheelKeyService.isConnected}")
            delay(12000)
            armBuild47Consume(false)
            val top = runCatching { adb.execDiagnostic("activity_top") }.getOrNull()
            top?.take(6000)?.lineSequence()?.forEachIndexed { i, line -> if (line.isNotBlank()) log("BUILD47_POST", "test=a11y_consume_304 line=$i $line") }
            restoreAdbTransaction("build47_a11y_consume_complete")
            log("BUILD47_TEST_END", "test=a11y_consume_304")
            status = "A11Y CONSUME завершён"
        }
    }

    fun runBuild47Combined304() {
        scope.launch {
            status = "COMBINED: сохраняю ORIGINAL..."
            if (!ensureAdbTransactionSnapshot()) {
                status = "COMBINED: snapshot не создан"
                return@launch
            }
            val original = diagPrefs.getString("adb_tx_a11y_services", "null") ?: "null"
            val diagComponent = "${context.packageName}/com.bydmate.app.cluster.SteeringWheelKeyService"
            val list = if (original == "null" || original.isBlank()) mutableListOf<String>()
                else original.split(':').filter { it.isNotBlank() }.toMutableList()
            if (!list.contains(diagComponent)) list.add(diagComponent)
            val a1 = runCatching { adb.execDiagnosticMutation("set_a11y_services", list.joinToString(":")) }.getOrNull()
            val a2 = runCatching { adb.execDiagnosticMutation("set_a11y_enabled", "1") }.getOrNull()
            val vr = runCatching { adb.execDiagnosticMutation("disable_vr_package") }.getOrNull()
            log("BUILD47_COMBINED_PREP", "a11yServices=${a1?.replace('\n','|')} a11yEnabled=${a2?.replace('\n','|')} disableVr=${vr?.replace('\n','|')}")
            repeat(20) {
                if (!SteeringWheelKeyService.isConnected) delay(100)
            }
            armBuild47Consume(true)
            status = "A11Y + DISABLE VR ACTIVE: нажмите физическую кнопку микрофона 3 раза"
            log("BUILD47_TEST_START", "test=a11y_consume_plus_disable_vr durationMs=12000 connected=${SteeringWheelKeyService.isConnected}")
            delay(12000)
            armBuild47Consume(false)
            val top = runCatching { adb.execDiagnostic("activity_top") }.getOrNull()
            top?.take(6000)?.lineSequence()?.forEachIndexed { i, line -> if (line.isNotBlank()) log("BUILD47_POST", "test=a11y_consume_plus_disable_vr line=$i $line") }
            restoreAdbTransaction("build47_combined_complete")
            log("BUILD47_TEST_END", "test=a11y_consume_plus_disable_vr")
            status = "COMBINED завершён"
        }
    }

    fun runBuild47VoiceFamilyProbe() {
        scope.launch {
            status = "Сканирую семейство BYD Voice..."
            val connected = runCatching { adb.connect(); adb.isConnected() }.getOrDefault(false)
            log("BUILD47_FAMILY_PROBE_START", "connected=$connected")
            if (!connected) {
                status = "ADB недоступен для package probe"
                log("BUILD47_FAMILY_PROBE_END", "success=false reason=not_connected")
                return@launch
            }
            val out = runCatching { adb.execDiagnostic("voice_family_probe") }.getOrNull()
            out?.take(24000)?.lineSequence()?.forEachIndexed { i, line -> if (line.isNotBlank()) log("BUILD47_FAMILY", "line=$i $line") }
            log("BUILD47_FAMILY_PROBE_END", "success=${out != null} chars=${out?.length ?: -1}")
            status = "Package-family probe завершён"
        }
    }

'''
    if fn_anchor not in s:
        raise SystemExit('build47 function insertion anchor not found')
    s = s.replace(fn_anchor, funcs + fn_anchor, 1)

# Replace old long UI. Functions stay compiled for compatibility, but no redundant buttons remain.
card_start = s.find('    Card(modifier = modifier.fillMaxWidth()) {')
if card_start < 0:
    raise SystemExit('build47 Card start not found')
new_ui = r'''    Card(modifier = modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(10.dp).verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text("DiLink3 304 BLOCK LAB #47", style = MaterialTheme.typography.titleLarge)
            Text("Только ещё не подтверждённые тесты. Каждый активный тест автоматически возвращает ORIGINAL.")
            Text(status, style = MaterialTheme.typography.bodyMedium)

            Button(onClick = {
                armBuild47Consume(false)
                restoreAdbTransaction("build47_manual_restore")
            }, modifier = Modifier.fillMaxWidth()) {
                Text("RESTORE EVERYTHING — ВОССТАНОВИТЬ ВСЁ")
            }

            Button(onClick = { runBuild47A11yConsume304() }, modifier = Modifier.fillMaxWidth()) {
                Text("1. A11Y CONSUME 304 — 3 НАЖАТИЯ")
            }
            Text("Проверяет главное: может ли Accessibility поглотить физический 304 до штатного BYD Assistant.", style = MaterialTheme.typography.bodySmall)

            Button(onClick = { runTransactionalDisableVr304() }, modifier = Modifier.fillMaxWidth()) {
                Text("2. DISABLE com.byd.vrassistant → 304")
            }
            Text("Временно disable-user, затем AUTO-RESTORE. Во время окна нажмите микрофон.", style = MaterialTheme.typography.bodySmall)

            Button(onClick = { runBuild47Combined304() }, modifier = Modifier.fillMaxWidth()) {
                Text("3. A11Y CONSUME + DISABLE VR → 304")
            }
            Text("Комбинированный контрольный тест. Нажмите микрофон 3 раза.", style = MaterialTheme.typography.bodySmall)

            Button(onClick = { runBuild47VoiceFamilyProbe() }, modifier = Modifier.fillMaxWidth()) {
                Text("4. BYD VOICE PACKAGE-FAMILY PROBE")
            }
            Text("Ищет отдельный engine/service, который может продолжать владеть кнопкой после отключения vrassistant.", style = MaterialTheme.typography.bodySmall)

            Button(
                onClick = {
                    DiLink3DebugLog.log(context, "BUILD47_LOG_SHARE_PRESSED", "path=${context.filesDir.absolutePath}/dilink3-voice-debug.log")
                    val opened = DiLink3DebugLog.shareToTelegram(context)
                    status = if (opened) "Окно отправки лога открыто" else "Не удалось открыть отправку лога"
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("ОТПРАВИТЬ ДИАГНОСТИЧЕСКИЙ ЛОГ")
            }
            Text("После 1 → 2 → 3 → 4 нажмите эту кнопку один раз.", style = MaterialTheme.typography.bodySmall)
            Text("Файл: ${context.filesDir.absolutePath}/dilink3-voice-debug.log", style = MaterialTheme.typography.bodySmall)
        }
    }
}
'''
s = s[:card_start] + new_ui
p.write_text(s)
print('build47 minimal 304 BLOCK LAB installed')
