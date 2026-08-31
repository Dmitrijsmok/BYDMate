from pathlib import Path

# Build45 is applied after build44. It adds persistent transaction snapshots,
# reversible shell-side mutations and automatic rollback helpers.

# 1) Extend the allow-listed ADB client with reversible mutations only.
p = Path('app/src/main/kotlin/com/bydmate/app/data/autoservice/AdbOnDeviceClient.kt')
s = p.read_text()
if 'suspend fun execDiagnosticMutation(id: String, value: String? = null): String?' not in s:
    s = s.replace(
        '    suspend fun execDiagnostic(id: String): String?\n',
        '    suspend fun execDiagnostic(id: String): String?\n'
        '    /** Executes one allow-listed reversible diagnostic mutation. */\n'
        '    suspend fun execDiagnosticMutation(id: String, value: String? = null): String?\n'
    )

# Add one read-only state probe to the existing diagnostic command map.
needle = '            "resolve_voice" -> "cmd package resolve-activity --brief -a android.intent.action.VOICE_COMMAND 2>&1; cmd package resolve-activity --brief -a android.intent.action.ASSIST 2>&1; cmd package resolve-activity --brief -a android.speech.action.RECOGNIZE_SPEECH 2>&1"\n'
if '"vr_disabled_state"' not in s:
    replacement = needle + '            "vr_disabled_state" -> "if pm list packages -d 2>/dev/null | grep -qx \'package:com.byd.vrassistant\'; then echo disabled=true; else echo disabled=false; fi"\n'
    if needle not in s:
        raise SystemExit('build44 diagnostic command insertion point not found')
    s = s.replace(needle, replacement, 1)

marker = '    override suspend fun grantUsageStatsAppop(packageName: String): Boolean = withContext(Dispatchers.IO) {'
if 'override suspend fun execDiagnosticMutation(id: String, value: String?): String?' not in s:
    impl = r'''    override suspend fun execDiagnosticMutation(id: String, value: String?): String? = withContext(Dispatchers.IO) {
        // Mutations are intentionally tiny and hardcoded. There is no arbitrary-shell API.
        // Setting payloads are restricted to the character set used by Android component lists.
        val safeComponentList = Regex("[A-Za-z0-9_./:$-]*")
        val cmd = when (id) {
            "set_a11y_services" -> {
                val v = value ?: "null"
                require(v == "null" || safeComponentList.matches(v)) { "Unsafe accessibility component list" }
                if (v == "null")
                    "settings delete secure enabled_accessibility_services; echo rc=$?"
                else
                    "settings put secure enabled_accessibility_services $v; echo rc=$?"
            }
            "set_a11y_enabled" -> {
                val v = value ?: "null"
                require(v == "null" || v == "0" || v == "1") { "Unsafe accessibility_enabled value" }
                if (v == "null")
                    "settings delete secure accessibility_enabled; echo rc=$?"
                else
                    "settings put secure accessibility_enabled $v; echo rc=$?"
            }
            "disable_vr_package" -> "pm disable-user --user 0 com.byd.vrassistant 2>&1; echo rc=$?"
            "enable_vr_package" -> "pm enable --user 0 com.byd.vrassistant 2>&1; echo rc=$?"
            else -> throw IllegalArgumentException("Unknown diagnostic mutation id: $id")
        }
        val p = protocol ?: run {
            val r = connect()
            if (r.isFailure) return@withContext null
            protocol ?: return@withContext null
        }
        try {
            kotlinx.coroutines.runInterruptible { p.exec(cmd) }
        } catch (e: Exception) {
            Log.w(TAG, "execDiagnosticMutation($id) failed: ${e.message}")
            null
        }
    }

'''
    if marker not in s:
        raise SystemExit('mutation implementation insertion marker not found')
    s = s.replace(marker, impl + marker, 1)
p.write_text(s)

# 2) Add transaction snapshot/restore controls to the Test Lab.
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()

anchor = '    fun runAdbTest(id: String, label: String) {'
if 'fun restoreAdbTransaction(reason: String = "manual")' not in s:
    fn = r'''    fun parseSetting(output: String?, key: String): String {
        return output?.lineSequence()
            ?.firstOrNull { it.startsWith("$key=") }
            ?.substringAfter('=')
            ?.trim()
            ?.ifEmpty { "null" }
            ?: "null"
    }

    suspend fun ensureAdbTransactionSnapshot(): Boolean {
        val connected = runCatching { adb.connect(); adb.isConnected() }.getOrDefault(false)
        if (!connected) {
            log("LAB_ADB_TX_SNAPSHOT", "success=false reason=not_connected")
            return false
        }
        if (diagPrefs.getBoolean("adb_tx_snapshot_valid", false)) {
            log("LAB_ADB_TX_SNAPSHOT", "success=true reused=true")
            return true
        }
        val settings = runCatching { adb.execDiagnostic("settings_voice") }.getOrNull()
        val vr = runCatching { adb.execDiagnostic("vr_disabled_state") }.getOrNull()
        if (settings == null || vr == null) {
            log("LAB_ADB_TX_SNAPSHOT", "success=false reason=read_failed settings=${settings != null} vr=${vr != null}")
            return false
        }
        val a11yServices = parseSetting(settings, "enabled_accessibility_services")
        val a11yEnabled = parseSetting(settings, "accessibility_enabled")
        val vrDisabled = vr.contains("disabled=true")
        diagPrefs.edit()
            .putBoolean("adb_tx_snapshot_valid", true)
            .putString("adb_tx_a11y_services", a11yServices)
            .putString("adb_tx_a11y_enabled", a11yEnabled)
            .putBoolean("adb_tx_vr_disabled", vrDisabled)
            .putLong("adb_tx_saved_at", System.currentTimeMillis())
            .apply()
        log("LAB_ADB_TX_SNAPSHOT", "success=true reused=false a11yEnabled=$a11yEnabled a11yServices=$a11yServices vrDisabled=$vrDisabled")
        return true
    }

    fun restoreAdbTransaction(reason: String = "manual") {
        scope.launch {
            if (!diagPrefs.getBoolean("adb_tx_snapshot_valid", false)) {
                status = "ADB restore: сохранённого состояния нет"
                log("LAB_ADB_TX_RESTORE", "reason=$reason success=true nothing_to_restore=true")
                return@launch
            }
            status = "ADB: восстанавливаю исходное состояние..."
            val connected = runCatching { adb.connect(); adb.isConnected() }.getOrDefault(false)
            if (!connected) {
                status = "ADB restore: ADB недоступен — snapshot сохранён"
                log("LAB_ADB_TX_RESTORE", "reason=$reason success=false not_connected=true")
                return@launch
            }
            val originalServices = diagPrefs.getString("adb_tx_a11y_services", "null") ?: "null"
            val originalEnabled = diagPrefs.getString("adb_tx_a11y_enabled", "null") ?: "null"
            val originalVrDisabled = diagPrefs.getBoolean("adb_tx_vr_disabled", false)

            val r1 = runCatching { adb.execDiagnosticMutation("set_a11y_services", originalServices) }.getOrNull()
            val r2 = runCatching { adb.execDiagnosticMutation("set_a11y_enabled", originalEnabled) }.getOrNull()
            val r3 = runCatching {
                adb.execDiagnosticMutation(if (originalVrDisabled) "disable_vr_package" else "enable_vr_package")
            }.getOrNull()
            val ok = r1 != null && r2 != null && r3 != null
            log("LAB_ADB_TX_RESTORE_ITEM", "setting=enabled_accessibility_services original=$originalServices result=${r1?.replace('\n', '|')}")
            log("LAB_ADB_TX_RESTORE_ITEM", "setting=accessibility_enabled original=$originalEnabled result=${r2?.replace('\n', '|')}")
            log("LAB_ADB_TX_RESTORE_ITEM", "package=com.byd.vrassistant originalDisabled=$originalVrDisabled result=${r3?.replace('\n', '|')}")
            if (ok) {
                diagPrefs.edit().putBoolean("adb_tx_snapshot_valid", false).apply()
                status = "RESTORED ✓ Исходное состояние возвращено"
            } else {
                status = "RESTORE НЕПОЛНЫЙ — snapshot сохранён, нажмите ещё раз"
            }
            log("LAB_ADB_TX_RESTORE", "reason=$reason success=$ok")
        }
    }

    fun runTransactionalA11y304() {
        scope.launch {
            status = "TX A11Y: сохраняю исходное состояние..."
            if (!ensureAdbTransactionSnapshot()) {
                status = "TX A11Y: не удалось сохранить snapshot"
                return@launch
            }
            val original = diagPrefs.getString("adb_tx_a11y_services", "null") ?: "null"
            val diagComponent = "${context.packageName}/com.bydmate.app.cluster.SteeringWheelKeyService"
            val list = if (original == "null" || original.isBlank()) mutableListOf<String>()
                else original.split(':').filter { it.isNotBlank() }.toMutableList()
            if (!list.contains(diagComponent)) list.add(diagComponent)
            val testServices = list.joinToString(":")
            log("LAB_ADB_TX_APPLY", "test=a11y304 ORIGINAL=$original TEST=$testServices")
            val r1 = runCatching { adb.execDiagnosticMutation("set_a11y_services", testServices) }.getOrNull()
            val r2 = runCatching { adb.execDiagnosticMutation("set_a11y_enabled", "1") }.getOrNull()
            log("LAB_ADB_TX_APPLY_RESULT", "test=a11y304 services=${r1?.replace('\n', '|')} enabled=${r2?.replace('\n', '|')}")
            if (r1 == null || r2 == null) {
                status = "TX A11Y: изменение не удалось; восстанавливаю"
                restoreAdbTransaction("a11y_apply_failed")
                return@launch
            }
            SteeringWheelKeyService.clearDiagKey()
            status = "TX A11Y ACTIVE: нажмите 304 несколько раз. Авто-restore через 15 сек"
            log("LAB_ADB_TX_WINDOW_START", "test=a11y304 durationMs=15000 component=$diagComponent")
            val started = android.os.SystemClock.elapsedRealtime()
            var lastAt = 0L
            while (android.os.SystemClock.elapsedRealtime() - started < 15000L) {
                val at = SteeringWheelKeyService.lastDiagKeyAtMs
                if (at > lastAt) {
                    lastAt = at
                    log("LAB_ADB_TX_304", "keyCode=${SteeringWheelKeyService.lastDiagKeyCode} action=${SteeringWheelKeyService.lastDiagKeyAction} connected=${SteeringWheelKeyService.isConnected} elapsed=${android.os.SystemClock.elapsedRealtime() - started}")
                }
                delay(75)
            }
            log("LAB_ADB_TX_WINDOW_END", "test=a11y304 connected=${SteeringWheelKeyService.isConnected} lastKey=${SteeringWheelKeyService.lastDiagKeyCode}")
            restoreAdbTransaction("a11y304_complete")
        }
    }

    fun runTransactionalDisableVr304() {
        scope.launch {
            status = "TX VR: сохраняю исходное состояние..."
            if (!ensureAdbTransactionSnapshot()) {
                status = "TX VR: не удалось сохранить snapshot"
                return@launch
            }
            val originalDisabled = diagPrefs.getBoolean("adb_tx_vr_disabled", false)
            log("LAB_ADB_TX_APPLY", "test=disable_vr304 ORIGINAL_DISABLED=$originalDisabled TEST_DISABLED=true")
            val out = runCatching { adb.execDiagnosticMutation("disable_vr_package") }.getOrNull()
            log("LAB_ADB_TX_APPLY_RESULT", "test=disable_vr304 result=${out?.replace('\n', '|')}")
            if (out == null) {
                status = "TX VR: disable не удался; восстанавливаю"
                restoreAdbTransaction("vr_disable_failed")
                return@launch
            }
            status = "TX VR ACTIVE: нажмите физическую 304. Авто-restore через 12 сек"
            log("LAB_ADB_TX_WINDOW_START", "test=disable_vr304 durationMs=12000")
            delay(12000)
            val activity = runCatching { adb.execDiagnostic("activity_top") }.getOrNull()
            activity?.take(6000)?.lineSequence()?.forEachIndexed { i, line ->
                if (line.isNotBlank()) log("LAB_ADB_TX_POST", "test=disable_vr304 line=$i $line")
            }
            log("LAB_ADB_TX_WINDOW_END", "test=disable_vr304")
            restoreAdbTransaction("disable_vr304_complete")
        }
    }

'''
    if anchor not in s:
        raise SystemExit('build44 ADB function anchor not found')
    s = s.replace(anchor, fn + anchor, 1)

# Add visible transactional controls before the build44 passive ADB section.
ui_anchor = '            Button(onClick = { runAdbPassivePack() }, modifier = Modifier.fillMaxWidth()) { Text("8. ADB: ВСЕ ПАССИВНЫЕ ПРОВЕРКИ") }'
if 'SAFE ADB TRANSACTIONS' not in s:
    ui = r'''            Text("SAFE ADB TRANSACTIONS", style = MaterialTheme.typography.titleMedium)
            Text("Перед любым постоянным изменением сохраняется ORIGINAL. После теста выполняется AUTO-RESTORE. Snapshot хранится в приложении даже после перезапуска.")
            Button(onClick = { restoreAdbTransaction("manual_button") }, modifier = Modifier.fillMaxWidth()) { Text("RESTORE EVERYTHING — ВОССТАНОВИТЬ ВСЁ") }
            Button(onClick = { runTransactionalA11y304() }, modifier = Modifier.fillMaxWidth()) { Text("TX1. ВРЕМЕННО A11Y → 304 → AUTO-RESTORE") }
            Button(onClick = { runTransactionalDisableVr304() }, modifier = Modifier.fillMaxWidth()) { Text("TX2. ВРЕМЕННО DISABLE VR → 304 → AUTO-RESTORE") }

'''
    if ui_anchor not in s:
        raise SystemExit('build44 passive ADB UI anchor not found')
    s = s.replace(ui_anchor, ui + ui_anchor, 1)

# On opening the panel, auto-recover an unfinished transaction from a prior crash/restart.
old = '    LaunchedEffect(Unit) {\n        log("LAB_OPEN", "package=${context.packageName} steeringConnected=${SteeringWheelKeyService.isConnected} systemAsr=${SpeechRecognizer.isRecognitionAvailable(context)}")\n    }'
if 'LAB_ADB_TX_PENDING_ON_OPEN' not in s:
    new = '''    LaunchedEffect(Unit) {\n        log("LAB_OPEN", "package=${context.packageName} steeringConnected=${SteeringWheelKeyService.isConnected} systemAsr=${SpeechRecognizer.isRecognitionAvailable(context)}")\n        if (diagPrefs.getBoolean("adb_tx_snapshot_valid", false)) {\n            log("LAB_ADB_TX_PENDING_ON_OPEN", "savedAt=${diagPrefs.getLong(\"adb_tx_saved_at\", 0L)} autoRestore=true")\n            delay(600)\n            restoreAdbTransaction("auto_on_open")\n        }\n    }'''
    if old not in s:
        raise SystemExit('LaunchedEffect anchor not found')
    s = s.replace(old, new, 1)

s = s.replace('DiLink3 Voice Test Lab #44', 'DiLink3 Voice Test Lab #45')
p.write_text(s)
