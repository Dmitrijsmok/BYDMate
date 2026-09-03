from pathlib import Path

# Build55: recover the permanent steering-wheel blocker after an uninstall cleared
# Android's Accessibility authorization. Build49 intentionally removed the old lab UI;
# the underlying helper/ADB recovery functions are still present in the patched panel.
# This patch exposes a compact, safe recovery UI again and makes status truthful.

p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()

card_anchor = '    Card(modifier = modifier.fillMaxWidth()) {'
if card_anchor not in s:
    raise SystemExit('Build55 panel Card anchor not found')

if 'fun build55RefreshAccessibilityStatus()' not in s:
    functions = r'''    fun build55RefreshAccessibilityStatus() {
        val component = "${context.packageName}/com.bydmate.app.cluster.SteeringWheelKeyService"
        val services = secure("enabled_accessibility_services")
        val enabledInSettings = services.split(':').any { it == component }
        val frameworkEnabled = secure("accessibility_enabled") == "1"
        val connected = SteeringWheelKeyService.isConnected
        val blockerActive = enabledInSettings && frameworkEnabled && connected
        status = if (blockerActive) {
            "БЛОКИРОВКА АКТИВНА ✓  A11Y подключён"
        } else {
            "БЛОКИРОВКА НЕ АКТИВНА ✗  secure=$enabledInSettings framework=$frameworkEnabled connected=$connected"
        }
        log(
            "BUILD55_ACCESSIBILITY_STATUS",
            "component=$component enabledInSecureSettings=$enabledInSettings accessibilityEnabled=$frameworkEnabled steeringConnected=$connected blockerActive=$blockerActive services=$services"
        )
    }

    fun build55RecoverAccessibility() {
        scope.launch {
            val component = "${context.packageName}/com.bydmate.app.cluster.SteeringWheelKeyService"
            log("BUILD55_ACCESSIBILITY_ENABLE_PRESSED", "component=$component connectedBefore=${SteeringWheelKeyService.isConnected}")
            status = "A11Y: пробую существующий helper без нового ADB-разрешения..."

            // First try the already-running shell helper. This path does NOT start a new
            // ADB authentication flow, so it can recover A11Y even when the car's USB-debug
            // consent dialog is currently impossible to approve.
            val existingVersion = runCatching { helper.daemonVersion() }.getOrNull()
            val directEnabled = if (existingVersion != null) {
                runCatching { helper.enableAccessibilityService() }.getOrDefault(false)
            } else false
            log("BUILD55_HELPER_DIRECT_RESULT", "daemonVersion=$existingVersion enableResult=$directEnabled")
            delay(1200)
            if (SteeringWheelKeyService.isConnected) {
                log("BUILD55_ACCESSIBILITY_ENABLE_RESULT", "success=true path=existing_helper connected=true")
                build55RefreshAccessibilityStatus()
                return@launch
            }

            // If no usable daemon survived the reinstall/update, use the normal bootstrap.
            // This may require one-time ADB authorization; the dedicated ADB button below
            // makes that state visible instead of silently failing.
            status = "A11Y: существующий helper не помог, запускаю recovery..."
            val ensured = runCatching { bootstrap.ensureRunning() }.getOrDefault(false)
            val helperEnabled = if (ensured) {
                runCatching { helper.enableAccessibilityService() }.getOrDefault(false)
            } else false
            delay(1600)
            val connected = SteeringWheelKeyService.isConnected
            val services = secure("enabled_accessibility_services")
            val enabledInSettings = services.split(':').any { it == component }
            log(
                "BUILD55_ACCESSIBILITY_ENABLE_RESULT",
                "success=${connected && enabledInSettings} path=bootstrap ensured=$ensured helperEnabled=$helperEnabled enabledInSecureSettings=$enabledInSettings connected=$connected services=$services failure=${bootstrap.lastSpawnFailure()}"
            )
            build55RefreshAccessibilityStatus()
            if (!connected) {
                status = if (!ensured) {
                    "A11Y НЕ ПОДНЯТ: helper/ADB не готов. Нажмите «ADB: АВТОРИЗОВАТЬ», затем повторите ENABLE."
                } else {
                    "A11Y записан, но сервис не подключился. Нажмите «FORCE REPAIR A11Y»."
                }
            }
        }
    }

    fun build55AuthorizeAdb() {
        scope.launch {
            status = "ADB: запускаю авторизацию..."
            log("BUILD55_ADB_AUTH_PRESSED", "connectedBefore=${runCatching { adb.isConnected() }.getOrDefault(false)}")
            // Reset only the transport socket, NOT the persisted RSA key. Keeping the key is
            // essential so a previously approved car does not ask again after every app launch.
            runCatching { adb.shutdown() }
            val result = runCatching { adb.connect() }
            val connected = runCatching { adb.isConnected() }.getOrDefault(false)
            log("BUILD55_ADB_AUTH_RESULT", "success=${result.isSuccess && connected} connected=$connected error=${result.exceptionOrNull()?.message}")
            status = if (connected) {
                "ADB АВТОРИЗОВАН ✓ Теперь нажмите ENABLE ACCESSIBILITY"
            } else {
                "ADB не авторизован. Если системный диалог пишет, что он перекрыт другим окном, уберите плавающие окна/HUD и нажмите эту кнопку снова."
            }
        }
    }

    fun build55ForceRepairAccessibilityViaAdb() {
        scope.launch {
            val component = "${context.packageName}/com.bydmate.app.cluster.SteeringWheelKeyService"
            status = "FORCE REPAIR: проверяю ADB..."
            log("BUILD55_ACCESSIBILITY_REPAIR_PRESSED", "component=$component")
            val connectedAdb = runCatching {
                adb.connect()
                adb.isConnected()
            }.getOrDefault(false)
            if (!connectedAdb) {
                status = "FORCE REPAIR: ADB не авторизован"
                log("BUILD55_ACCESSIBILITY_REPAIR_RESULT", "success=false reason=adb_not_connected")
                return@launch
            }

            val settings = runCatching { adb.execDiagnostic("settings_voice") }.getOrNull()
            val originalRaw = parseSetting(settings, "enabled_accessibility_services")
            val original = if (originalRaw == "null" || originalRaw.isBlank()) emptyList()
                else originalRaw.split(':').filter { it.isNotBlank() }
            val withoutOurs = original.filter { it != component }
            val withOurs = (withoutOurs + component).distinct()

            // Remove then re-add our exact component to force Android to rebind a service that
            // is present in secure settings but stuck disconnected. Other enabled services are
            // preserved byte-for-byte as list entries.
            val r0 = runCatching {
                adb.execDiagnosticMutation("set_a11y_services", if (withoutOurs.isEmpty()) "null" else withoutOurs.joinToString(":"))
            }.getOrNull()
            delay(350)
            val r1 = runCatching {
                adb.execDiagnosticMutation("set_a11y_services", withOurs.joinToString(":"))
            }.getOrNull()
            val r2 = runCatching { adb.execDiagnosticMutation("set_a11y_enabled", "1") }.getOrNull()
            delay(1800)

            val serviceConnected = SteeringWheelKeyService.isConnected
            val servicesAfter = secure("enabled_accessibility_services")
            val presentAfter = servicesAfter.split(':').any { it == component }
            val ok = r0 != null && r1 != null && r2 != null && presentAfter
            log(
                "BUILD55_ACCESSIBILITY_REPAIR_RESULT",
                "success=$ok serviceConnected=$serviceConnected presentAfter=$presentAfter remove=${r0?.replace('\n','|')} add=${r1?.replace('\n','|')} enable=${r2?.replace('\n','|')} servicesAfter=$servicesAfter"
            )
            build55RefreshAccessibilityStatus()
            if (!serviceConnected) status = "A11Y записан в Secure Settings, но сервис ещё не connected - отправьте лог"
        }
    }

    fun build55ClearDiagnosticLog() {
        DiLink3DebugLog.clear(context)
        log("BUILD55_LOG_CLEARED", "versionCode=60004")
        status = "Диагностический лог очищен"
    }

'''
    s = s.replace(card_anchor, functions + card_anchor, 1)

# Replace the compact Build50 UI text/status with Build55-specific truthful status.
s = s.replace('DiLink3 STOCK ASSISTANT BLOCKER #50', 'DiLink3 STOCK ASSISTANT BLOCKER #55', 1)
s = s.replace(
    'Text("Рабочая реализация: keyCode 327 блокируется постоянно. keyCode 304 не блокируется и остаётся доступен BYDMate.")',
    'Text("keyCode 327 блокируется только когда наш AccessibilityService реально подключён. 304 остаётся доступен BYDMate.")',
    1,
)

old_status_button = r'''            Button(
                onClick = {
                    val connected = SteeringWheelKeyService.isConnected
                    status = if (connected) {
                        "Блокировка активна: AccessibilityService подключён"
                    } else {
                        "AccessibilityService пока не подключён — TrackingService повторит привязку на старте/пробуждении"
                    }
                    log("BUILD50_STATUS", "steeringConnected=$connected stockAssistant327Block=true allKeyTrace=true")
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("ПРОВЕРИТЬ СТАТУС БЛОКИРОВКИ")
            }
'''
new_controls = r'''            Button(onClick = { build55RefreshAccessibilityStatus() }, modifier = Modifier.fillMaxWidth()) {
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
if old_status_button not in s:
    raise SystemExit('Build55 Build50 status button anchor not found')
s = s.replace(old_status_button, new_controls, 1)

s = s.replace(
    'DiLink3DebugLog.log(context, "BUILD50_LOG_SHARE_PRESSED", "path=${context.filesDir.absolutePath}/dilink3-voice-debug.log")',
    'DiLink3DebugLog.log(context, "BUILD55_LOG_SHARE_PRESSED", "path=${context.filesDir.absolutePath}/dilink3-voice-debug.log")',
    1,
)
s = s.replace(
    'Text("ОТПРАВИТЬ ДИАГНОСТИЧЕСКИЙ ЛОГ")',
    'Text("6. ОТПРАВИТЬ ДИАГНОСТИЧЕСКИЙ ЛОГ")',
    1,
)
s = s.replace(
    'Text("Проверка: обычное нажатие микрофона не должно открывать BYD Assistant. 304 при этом продолжает идти в обычную маршрутизацию BYDMate.", style = MaterialTheme.typography.bodySmall)',
    'Text("После ENABLE статус обязан показать blockerActive=true. Затем нажмите физическую кнопку микрофона: в логе ожидаются BUILD50_KEY_EVENT и BUILD49_STOCK_ASSISTANT_327_BLOCKED.", style = MaterialTheme.typography.bodySmall)',
    1,
)

p.write_text(s)
print('Build55 accessibility recovery controls installed')
