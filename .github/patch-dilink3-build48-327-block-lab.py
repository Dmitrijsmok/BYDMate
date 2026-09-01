from pathlib import Path

# Build48: focused follow-up from build47 logs.
# New unresolved hypotheses only:
#   1) keyCode 327 is the stock-assistant trigger,
#   2) both 304+327 must be consumed,
#   3) vrassistant must be disabled AND force-stopped before the physical press.

# 1) Upgrade SteeringWheelKeyService diagnostic gate from 304-only to independent 304/327 gates.
p = Path('app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt')
s = p.read_text()
old = '''        // Build47 diagnostic gate: when explicitly armed from the test lab, swallow BOTH
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
new = '''        // Build48 diagnostic gate. Physical mic press on this DiLink3 emits both
        // 304/scanCode=290 and 327/scanCode=294. Tests can swallow either or both.
        val build48Diag = applicationContext.getSharedPreferences("dilink3_diag", Context.MODE_PRIVATE)
        val build48Block304 = build48Diag.getBoolean("build48_block_304", false)
        val build48Block327 = build48Diag.getBoolean("build48_block_327", false)
        if ((event.keyCode == 304 && build48Block304) || (event.keyCode == 327 && build48Block327)) {
            DiLink3DebugLog.log(
                applicationContext,
                "BUILD48_A11Y_KEY_CONSUMED",
                "keyCode=${event.keyCode} action=${event.action} scanCode=${event.scanCode} deviceId=${event.deviceId} source=${event.source} isDown=$isDown block304=$build48Block304 block327=$build48Block327"
            )
            return true
        }
'''
if old not in s:
    raise SystemExit('build48 build47 gate anchor not found')
s = s.replace(old, new, 1)
p.write_text(s)

# 2) Add a read-only process/service probe around the disable+force-stop experiment.
p = Path('app/src/main/kotlin/com/bydmate/app/data/autoservice/AdbOnDeviceClient.kt')
s = p.read_text()
anchor = '            "voice_family_probe" -> '
idx = s.find(anchor)
if idx < 0:
    raise SystemExit('build48 voice_family_probe anchor not found')
if '"vr_runtime_probe"' not in s:
    line_end = s.find('\n', idx)
    if line_end < 0:
        raise SystemExit('build48 voice_family_probe line end not found')
    probe = '            "vr_runtime_probe" -> "echo ===VR_PROCESS===; ps -A 2>/dev/null | grep -F com.byd.vrassistant || true; echo ===VR_SERVICES===; dumpsys activity services com.byd.vrassistant 2>/dev/null | grep -Ei \'ServiceRecord|processName|app=ProcessRecord|SpeechService|NeuVoiceService|vrassistant\' | head -n 160; echo ===VR_DISABLED===; if pm list packages -d 2>/dev/null | grep -qx \'package:com.byd.vrassistant\'; then echo disabled=true; else echo disabled=false; fi"\n'
    s = s[:line_end + 1] + probe + s[line_end + 1:]
p.write_text(s)

# 3) Add build48 test helpers, then replace build47 UI with the minimal 3-test lab.
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()
fn_anchor = '    fun runAdbTest(id: String, label: String) {'
if 'fun runBuild48Consume327' not in s:
    funcs = r'''    fun armBuild48Consume(block304: Boolean, block327: Boolean) {
        diagPrefs.edit()
            .putBoolean("build48_block_304", block304)
            .putBoolean("build48_block_327", block327)
            .putBoolean("build47_block_304", false)
            .apply()
        log("BUILD48_BLOCK_FLAGS", "block304=$block304 block327=$block327 steeringConnected=${SteeringWheelKeyService.isConnected}")
    }

    suspend fun prepareBuild48A11y(test: String): Boolean {
        if (!ensureAdbTransactionSnapshot()) return false
        val original = diagPrefs.getString("adb_tx_a11y_services", "null") ?: "null"
        val diagComponent = "${context.packageName}/com.bydmate.app.cluster.SteeringWheelKeyService"
        val list = if (original == "null" || original.isBlank()) mutableListOf<String>()
            else original.split(':').filter { it.isNotBlank() }.toMutableList()
        if (!list.contains(diagComponent)) list.add(diagComponent)
        val r1 = runCatching { adb.execDiagnosticMutation("set_a11y_services", list.joinToString(":")) }.getOrNull()
        val r2 = runCatching { adb.execDiagnosticMutation("set_a11y_enabled", "1") }.getOrNull()
        log("BUILD48_A11Y_PREP", "test=$test services=${r1?.replace('\n','|')} enabled=${r2?.replace('\n','|')} component=$diagComponent")
        if (r1 == null || r2 == null) return false
        repeat(20) {
            if (!SteeringWheelKeyService.isConnected) delay(100)
        }
        return true
    }

    fun runBuild48Consume327() {
        scope.launch {
            status = "327 ONLY: сохраняю ORIGINAL..."
            if (!prepareBuild48A11y("consume_327")) {
                status = "327 ONLY: A11Y prep не удался"
                restoreAdbTransaction("build48_327_prep_failed")
                return@launch
            }
            armBuild48Consume(block304 = false, block327 = true)
            status = "327 CONSUME ACTIVE: нажмите физическую кнопку микрофона 3 раза"
            log("BUILD48_TEST_START", "test=consume_327 durationMs=12000 connected=${SteeringWheelKeyService.isConnected}")
            delay(12000)
            armBuild48Consume(false, false)
            val top = runCatching { adb.execDiagnostic("activity_top") }.getOrNull()
            top?.take(6000)?.lineSequence()?.forEachIndexed { i, line -> if (line.isNotBlank()) log("BUILD48_POST", "test=consume_327 line=$i $line") }
            restoreAdbTransaction("build48_327_complete")
            log("BUILD48_TEST_END", "test=consume_327")
            status = "327 ONLY завершён"
        }
    }

    fun runBuild48Consume304And327() {
        scope.launch {
            status = "304+327: сохраняю ORIGINAL..."
            if (!prepareBuild48A11y("consume_304_327")) {
                status = "304+327: A11Y prep не удался"
                restoreAdbTransaction("build48_both_prep_failed")
                return@launch
            }
            armBuild48Consume(block304 = true, block327 = true)
            status = "304+327 CONSUME ACTIVE: нажмите физическую кнопку микрофона 3 раза"
            log("BUILD48_TEST_START", "test=consume_304_327 durationMs=12000 connected=${SteeringWheelKeyService.isConnected}")
            delay(12000)
            armBuild48Consume(false, false)
            val top = runCatching { adb.execDiagnostic("activity_top") }.getOrNull()
            top?.take(6000)?.lineSequence()?.forEachIndexed { i, line -> if (line.isNotBlank()) log("BUILD48_POST", "test=consume_304_327 line=$i $line") }
            restoreAdbTransaction("build48_both_complete")
            log("BUILD48_TEST_END", "test=consume_304_327")
            status = "304+327 завершён"
        }
    }

    fun runBuild48DisableForceStop() {
        scope.launch {
            status = "VR STOP: сохраняю ORIGINAL..."
            if (!ensureAdbTransactionSnapshot()) {
                status = "VR STOP: snapshot не создан"
                return@launch
            }
            val before = runCatching { adb.execDiagnostic("vr_runtime_probe") }.getOrNull()
            before?.take(12000)?.lineSequence()?.forEachIndexed { i, line -> if (line.isNotBlank()) log("BUILD48_VR_RUNTIME", "phase=before line=$i $line") }

            val disabled = runCatching { adb.execDiagnosticMutation("disable_vr_package") }.getOrNull()
            log("BUILD48_VR_DISABLE", "result=${disabled?.replace('\n','|')}")
            if (disabled == null) {
                status = "VR STOP: disable не удался; restore"
                restoreAdbTransaction("build48_disable_failed")
                return@launch
            }

            val afterDisable = runCatching { adb.execDiagnostic("vr_runtime_probe") }.getOrNull()
            afterDisable?.take(12000)?.lineSequence()?.forEachIndexed { i, line -> if (line.isNotBlank()) log("BUILD48_VR_RUNTIME", "phase=after_disable line=$i $line") }

            val stopped = runCatching { adb.execDiagnostic("force_stop_vr") }.getOrNull()
            log("BUILD48_VR_FORCE_STOP", "result=${stopped?.replace('\n','|')}")
            delay(700)
            val afterStop = runCatching { adb.execDiagnostic("vr_runtime_probe") }.getOrNull()
            afterStop?.take(12000)?.lineSequence()?.forEachIndexed { i, line -> if (line.isNotBlank()) log("BUILD48_VR_RUNTIME", "phase=after_force_stop line=$i $line") }

            status = "VR DISABLED + FORCE-STOPPED: нажмите физическую кнопку микрофона 3 раза"
            log("BUILD48_TEST_START", "test=disable_force_stop durationMs=12000")
            delay(12000)

            val afterPress = runCatching { adb.execDiagnostic("vr_runtime_probe") }.getOrNull()
            afterPress?.take(12000)?.lineSequence()?.forEachIndexed { i, line -> if (line.isNotBlank()) log("BUILD48_VR_RUNTIME", "phase=after_press line=$i $line") }
            val top = runCatching { adb.execDiagnostic("activity_top") }.getOrNull()
            top?.take(6000)?.lineSequence()?.forEachIndexed { i, line -> if (line.isNotBlank()) log("BUILD48_POST", "test=disable_force_stop line=$i $line") }

            restoreAdbTransaction("build48_disable_force_stop_complete")
            log("BUILD48_TEST_END", "test=disable_force_stop")
            status = "VR STOP test завершён"
        }
    }

'''
    if fn_anchor not in s:
        raise SystemExit('build48 function insertion anchor not found')
    s = s.replace(fn_anchor, funcs + fn_anchor, 1)

card_start = s.find('    Card(modifier = modifier.fillMaxWidth()) {')
if card_start < 0:
    raise SystemExit('build48 Card start not found')
new_ui = r'''    Card(modifier = modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(10.dp).verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text("DiLink3 304/327 BLOCK LAB #48", style = MaterialTheme.typography.titleLarge)
            Text("Build47 уже подтвердил: 304 ловится и consume работает, но BYD Assistant всё равно запускается. Здесь только новые тесты.")
            Text(status, style = MaterialTheme.typography.bodyMedium)

            Button(onClick = {
                armBuild48Consume(false, false)
                restoreAdbTransaction("build48_manual_restore")
            }, modifier = Modifier.fillMaxWidth()) {
                Text("RESTORE EVERYTHING — ВОССТАНОВИТЬ ВСЁ")
            }

            Button(onClick = { runBuild48Consume327() }, modifier = Modifier.fillMaxWidth()) {
                Text("1. A11Y CONSUME 327 — 3 НАЖАТИЯ")
            }
            Text("Поглощает только physical keyCode 327 / scanCode 294. Проверяем, запускает ли штатный BYD Assistant именно 327.", style = MaterialTheme.typography.bodySmall)

            Button(onClick = { runBuild48Consume304And327() }, modifier = Modifier.fillMaxWidth()) {
                Text("2. A11Y CONSUME 304 + 327 — 3 НАЖАТИЯ")
            }
            Text("Поглощает обе пары DOWN/UP одного физического нажатия. Это главный контрольный тест.", style = MaterialTheme.typography.bodySmall)

            Button(onClick = { runBuild48DisableForceStop() }, modifier = Modifier.fillMaxWidth()) {
                Text("3. DISABLE VR + FORCE-STOP → 3 НАЖАТИЯ")
            }
            Text("Снимает runtime-снимки до/после disable, после force-stop и после нажатий; затем AUTO-RESTORE.", style = MaterialTheme.typography.bodySmall)

            Button(
                onClick = {
                    DiLink3DebugLog.log(context, "BUILD48_LOG_SHARE_PRESSED", "path=${context.filesDir.absolutePath}/dilink3-voice-debug.log")
                    val opened = DiLink3DebugLog.shareToTelegram(context)
                    status = if (opened) "Окно отправки лога открыто" else "Не удалось открыть отправку лога"
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("ОТПРАВИТЬ ДИАГНОСТИЧЕСКИЙ ЛОГ")
            }
            Text("Сделайте 1 → 2 → 3 по порядку, затем отправьте лог один раз.", style = MaterialTheme.typography.bodySmall)
            Text("Если что-то ведёт себя необычно — RESTORE EVERYTHING.", style = MaterialTheme.typography.bodySmall)
        }
    }
}
'''
s = s[:card_start] + new_ui
p.write_text(s)
print('build48 focused 327/dual-key/force-stop lab installed')
