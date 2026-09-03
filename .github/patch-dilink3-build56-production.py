from pathlib import Path

# Build56 production follow-up to the successful Build55 field test.
# - Keep the confirmed unconditional keyCode 327 blocker.
# - Route the physical DiLink3 mic 304/scanCode 290 into BYDMate's existing voice/PTT path.
# - Replace the multi-step A11Y lab controls with one ACTIVATE BLOCKER action using the
#   exact ADB/Secure-Settings repair path that succeeded in the vehicle on Build55.
# - Keep status + clean/share log diagnostics.

# 1) Physical mic 304 -> existing BYDMate voice action when voice is enabled.
p = Path('app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt')
s = p.read_text()
old = '''        val voicePrefs = applicationContext.getSharedPreferences("voice", Context.MODE_PRIVATE)
        val voiceEnabled = voicePrefs.getBoolean("voice_enabled", false)
        val voiceKey = voicePrefs.getInt("voice_keycode", DEFAULT_VOICE_KEYCODE)
        when (voiceDecision(event.keyCode, isDown, voiceEnabled, voiceKey)) {
'''
new = '''        val voicePrefs = applicationContext.getSharedPreferences("voice", Context.MODE_PRIVATE)
        val voiceEnabled = voicePrefs.getBoolean("voice_enabled", false)
        val voiceKey = voicePrefs.getInt("voice_keycode", DEFAULT_VOICE_KEYCODE)

        // Build56 DiLink3 microphone mapping. The physical microphone button emits
        // 304/scanCode=290 plus 327/scanCode=294. Build49 consumes 327 above to suppress
        // the stock BYD assistant. Feed the matching physical 304 into BYDMate's normal
        // configured voice/PTT route instead of requiring the generic default keyCode 320.
        // Do not bind deviceId because it can change across vehicle boots.
        val build56PhysicalMic304 = event.keyCode == 304 && event.scanCode == 290 && event.source == 257
        val build56VoiceEventKey = if (build56PhysicalMic304) voiceKey else event.keyCode
        if (build56PhysicalMic304) {
            DiLink3DebugLog.log(
                applicationContext,
                "BUILD56_MIC_304_ROUTED_TO_BYDMATE",
                "action=${event.action} isDown=$isDown voiceEnabled=$voiceEnabled configuredVoiceKey=$voiceKey scanCode=${event.scanCode} source=${event.source}"
            )
        }
        when (voiceDecision(build56VoiceEventKey, isDown, voiceEnabled, voiceKey)) {
'''
if old not in s:
    raise SystemExit('Build56 voice routing anchor not found')
s = s.replace(old, new, 1)
p.write_text(s)

# 2) Simplify the Build55 recovery panel to one user-facing activation path.
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()

card_anchor = '    Card(modifier = modifier.fillMaxWidth()) {'
if card_anchor not in s:
    raise SystemExit('Build56 panel Card anchor not found')

if 'fun build56ActivateBlocker()' not in s:
    function = r'''    fun build56ActivateBlocker() {
        scope.launch {
            val component = "${context.packageName}/com.bydmate.app.cluster.SteeringWheelKeyService"
            val beforeServices = secure("enabled_accessibility_services")
            val alreadyEnabled = beforeServices.split(':').any { it == component }
            val alreadyConnected = SteeringWheelKeyService.isConnected
            log(
                "BUILD56_ACTIVATE_BLOCKER_PRESSED",
                "component=$component enabledBefore=$alreadyEnabled connectedBefore=$alreadyConnected servicesBefore=$beforeServices"
            )

            if (alreadyEnabled && alreadyConnected && secure("accessibility_enabled") == "1") {
                status = "БЛОКИРОВКА АКТИВНА ✓"
                log("BUILD56_ACTIVATE_BLOCKER_RESULT", "success=true path=already_active connected=true")
                build55RefreshAccessibilityStatus()
                return@launch
            }

            status = "ACTIVATE BLOCKER: подключаю ADB и восстанавливаю Accessibility..."
            val connectedAdb = runCatching {
                adb.connect()
                adb.isConnected()
            }.getOrDefault(false)
            if (!connectedAdb) {
                status = "НЕ УДАЛОСЬ АКТИВИРОВАТЬ: ADB не подключён. Повторите после разрешения USB debugging."
                log("BUILD56_ACTIVATE_BLOCKER_RESULT", "success=false reason=adb_not_connected")
                return@launch
            }

            val settings = runCatching { adb.execDiagnostic("settings_voice") }.getOrNull()
            val originalRaw = parseSetting(settings, "enabled_accessibility_services")
            val original = if (originalRaw == "null" || originalRaw.isBlank()) emptyList()
                else originalRaw.split(':').filter { it.isNotBlank() }
            val withoutOurs = original.filter { it != component }
            val withOurs = (withoutOurs + component).distinct()

            // Proven Build55 field-repair sequence: remove our exact component, re-add it,
            // then assert accessibility_enabled=1. Preserve every other service entry.
            val r0 = runCatching {
                adb.execDiagnosticMutation("set_a11y_services", if (withoutOurs.isEmpty()) "null" else withoutOurs.joinToString(":"))
            }.getOrNull()
            delay(350)
            val r1 = runCatching {
                adb.execDiagnosticMutation("set_a11y_services", withOurs.joinToString(":"))
            }.getOrNull()
            val r2 = runCatching { adb.execDiagnosticMutation("set_a11y_enabled", "1") }.getOrNull()
            delay(1800)

            val servicesAfter = secure("enabled_accessibility_services")
            val presentAfter = servicesAfter.split(':').any { it == component }
            val connectedAfter = SteeringWheelKeyService.isConnected
            val frameworkAfter = secure("accessibility_enabled") == "1"
            val success = r0 != null && r1 != null && r2 != null && presentAfter && frameworkAfter && connectedAfter
            log(
                "BUILD56_ACTIVATE_BLOCKER_RESULT",
                "success=$success adbConnected=$connectedAdb presentAfter=$presentAfter accessibilityEnabled=$frameworkAfter connectedAfter=$connectedAfter remove=${r0?.replace('\n','|')} add=${r1?.replace('\n','|')} enable=${r2?.replace('\n','|')} servicesAfter=$servicesAfter"
            )
            build55RefreshAccessibilityStatus()
            if (!success) {
                status = "БЛОКИРОВКА НЕ АКТИВНА ✗ Нажмите ACTIVATE BLOCKER ещё раз и отправьте лог."
            }
        }
    }

'''
    s = s.replace(card_anchor, function + card_anchor, 1)

s = s.replace('DiLink3 STOCK ASSISTANT BLOCKER #55', 'DiLink3 STOCK ASSISTANT BLOCKER #56', 1)
s = s.replace(
    'Text("keyCode 327 блокируется только когда наш AccessibilityService реально подключён. 304 остаётся доступен BYDMate.")',
    'Text("327 блокирует штатный BYD Assistant. Физический 304/scanCode 290 направляется в обычный BYDMate voice/PTT маршрут.")',
    1,
)

old_controls = r'''            Button(onClick = { build55RefreshAccessibilityStatus() }, modifier = Modifier.fillMaxWidth()) {
                Text("1. ПРОВЕРИТЬ СТАТУС БЛОКИРОВКИ")
            }

            Button(onClick = { build55RecoverAccessibility() }, modifier = Modifier.fillMaxWidth()) {
                Text("2. ENABLE ACCESSIBILITY / ВКЛЮЧИТЬ БЛОКИРОВКУ")
            }

            Button(onClick = { build55AuthorizeAdb() }, modifier = Modifier.fillMaxWidth()) {
                Text("3. ADB: АВТОРИЗОВАТЬ / ПОВТОРИТЬ ЗАПРОС")
            }

            Button(onClick = { build55ForceRepairAccessibilityViaAdb() }, modifier = Modifier.fillMaxWidth()) {
                Text("4. FORCE REPAIR A11Y (СОХРАНЯЕТ ДРУГИЕ СЕРВИСЫ)")
            }

            Button(onClick = { build55ClearDiagnosticLog() }, modifier = Modifier.fillMaxWidth()) {
                Text("5. ОЧИСТИТЬ ДИАГНОСТИЧЕСКИЙ ЛОГ")
            }
'''
new_controls = r'''            Button(onClick = { build55RefreshAccessibilityStatus() }, modifier = Modifier.fillMaxWidth()) {
                Text("ПРОВЕРИТЬ СТАТУС")
            }

            Button(onClick = { build56ActivateBlocker() }, modifier = Modifier.fillMaxWidth()) {
                Text("ACTIVATE BLOCKER / АКТИВИРОВАТЬ")
            }

            Button(onClick = { build55ClearDiagnosticLog() }, modifier = Modifier.fillMaxWidth()) {
                Text("ОЧИСТИТЬ ЛОГ")
            }
'''
if old_controls not in s:
    raise SystemExit('Build56 Build55 controls anchor not found')
s = s.replace(old_controls, new_controls, 1)

s = s.replace(
    'DiLink3DebugLog.log(context, "BUILD55_LOG_SHARE_PRESSED", "path=${context.filesDir.absolutePath}/dilink3-voice-debug.log")',
    'DiLink3DebugLog.log(context, "BUILD56_LOG_SHARE_PRESSED", "path=${context.filesDir.absolutePath}/dilink3-voice-debug.log")',
    1,
)
s = s.replace('Text("6. ОТПРАВИТЬ ДИАГНОСТИЧЕСКИЙ ЛОГ")', 'Text("ОТПРАВИТЬ ЛОГ")', 1)
s = s.replace(
    'Text("После ENABLE статус обязан показать blockerActive=true. Затем нажмите физическую кнопку микрофона: в логе ожидаются BUILD50_KEY_EVENT и BUILD49_STOCK_ASSISTANT_327_BLOCKED.", style = MaterialTheme.typography.bodySmall)',
    'Text("Accessibility нужен для кнопок руля/voice PTT, steering-key automation, star projection trigger, knob override и Navi HUD reads. Split-screen запускается через helper и сам по себе от Accessibility не зависит.", style = MaterialTheme.typography.bodySmall)',
    1,
)

p.write_text(s)
print('Build56 production blocker activation + physical 304 routing installed')
