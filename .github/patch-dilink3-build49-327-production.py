from pathlib import Path

# Build49: turn the confirmed Build48 result into the real DiLink3 behavior.
# Field result: consuming keyCode 327 (scanCode 294) alone suppresses the stock
# BYD assistant. keyCode 304 must remain untouched so BYDMate can use/assign it.

# 1) Replace the temporary Build48 gates with an unconditional production blocker for 327.
p = Path('app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt')
s = p.read_text()
old = '''        // Build48 diagnostic gate. Physical mic press on this DiLink3 emits both
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
new = '''        // Build49 production DiLink3 blocker. One physical microphone press emits
        // 304/scanCode=290 plus 327/scanCode=294. Build48 field testing proved that
        // swallowing 327 alone prevents com.byd.vrassistant from opening. 304 is
        // deliberately NOT consumed here: it continues into BYDMate's normal voice /
        // automation routing and can be assigned by the user.
        if (event.keyCode == 327) {
            DiLink3DebugLog.log(
                applicationContext,
                "BUILD49_STOCK_ASSISTANT_327_BLOCKED",
                "action=${event.action} scanCode=${event.scanCode} deviceId=${event.deviceId} source=${event.source} isDown=$isDown"
            )
            return true
        }
'''
if old not in s:
    raise SystemExit('build49 Build48 diagnostic gate anchor not found')
s = s.replace(old, new, 1)

# Add an explicit connection marker to the diagnostic log so field logs prove the
# filter is actually live after boot/wake, not merely present in secure settings.
anchor = '        Log.d(TAG, "connected; filtering steering-wheel keys")\n'
if 'BUILD49_A11Y_CONNECTED' not in s:
    replacement = anchor + '''        DiLink3DebugLog.log(\n            applicationContext,\n            "BUILD49_A11Y_CONNECTED",\n            "stockAssistant327Block=true"\n        )\n'''
    if anchor not in s:
        raise SystemExit('build49 service-connected log anchor not found')
    s = s.replace(anchor, replacement, 1)
p.write_text(s)

# 2) This APK uses applicationIdSuffix=.dilink3diag. Build42 already retargets these
# constants in the normal patch chain, so this step must be idempotent.
p = Path('app/src/main/kotlin/com/bydmate/app/helper/HelperBinderProtocol.kt')
s = p.read_text()
old_pkg = '    const val APP_PACKAGE = "com.bydmate.app"\n'
new_pkg = '    const val APP_PACKAGE = "com.bydmate.app.dilink3diag"\n'
if old_pkg in s:
    s = s.replace(old_pkg, new_pkg, 1)
elif new_pkg not in s:
    raise SystemExit('build49 APP_PACKAGE diagnostic value not found')
old_component = '''    const val ACCESSIBILITY_SERVICE_COMPONENT =
        "com.bydmate.app/com.bydmate.app.cluster.SteeringWheelKeyService"
'''
new_component = '''    const val ACCESSIBILITY_SERVICE_COMPONENT =
        "com.bydmate.app.dilink3diag/com.bydmate.app.cluster.SteeringWheelKeyService"
'''
if old_component in s:
    s = s.replace(old_component, new_component, 1)
elif new_component not in s:
    raise SystemExit('build49 accessibility diagnostic component not found')
p.write_text(s)

# 3) Keep the key-filter service alive even when projection/voice/knob/HUD features are
# otherwise off. Build49's stock-assistant suppression itself is now a reason to keep A11Y
# bound. Existing GrantSelfHeal handles startup and every SCREEN_ON / USER_PRESENT wake.
p = Path('app/src/main/kotlin/com/bydmate/app/service/TrackingService.kt')
s = p.read_text()
old_gate = '''        if (!mirrorEnabled && !voiceEnabled && !knobEnabled && !hudController.requiresA11y()) return
        starGrant.ensure(reason)
'''
new_gate = '''        // Build49: the permanent keyCode-327 stock-assistant blocker also depends on
        // SteeringWheelKeyService, so this diagnostic APK keeps the service bound even
        // when projection/voice/knob/HUD are all disabled.
        starGrant.ensure("build49_327_blocker:$reason")
'''
if old_gate not in s:
    raise SystemExit('build49 TrackingService a11y gate anchor not found')
s = s.replace(old_gate, new_gate, 1)
p.write_text(s)

# 4) Retire the mutation lab UI. Keep only blocker status + log export so there are no
# obsolete disable/force-stop/restore buttons that can accidentally undo the live filter.
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()
card_start = s.find('    Card(modifier = modifier.fillMaxWidth()) {')
if card_start < 0:
    raise SystemExit('build49 Card start not found')
new_ui = r'''    Card(modifier = modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(10.dp).verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text("DiLink3 STOCK ASSISTANT BLOCKER #49", style = MaterialTheme.typography.titleLarge)
            Text("Рабочая реализация: keyCode 327 блокируется постоянно. keyCode 304 не блокируется и остаётся доступен BYDMate.")
            Text(status, style = MaterialTheme.typography.bodyMedium)

            Button(
                onClick = {
                    val connected = SteeringWheelKeyService.isConnected
                    status = if (connected) {
                        "Блокировка активна: AccessibilityService подключён"
                    } else {
                        "AccessibilityService пока не подключён — TrackingService повторит привязку на старте/пробуждении"
                    }
                    log("BUILD49_STATUS", "steeringConnected=$connected stockAssistant327Block=true")
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("ПРОВЕРИТЬ СТАТУС БЛОКИРОВКИ")
            }

            Button(
                onClick = {
                    DiLink3DebugLog.log(context, "BUILD49_LOG_SHARE_PRESSED", "path=${context.filesDir.absolutePath}/dilink3-voice-debug.log")
                    val opened = DiLink3DebugLog.shareToTelegram(context)
                    status = if (opened) "Окно отправки лога открыто" else "Не удалось открыть отправку лога"
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("ОТПРАВИТЬ ДИАГНОСТИЧЕСКИЙ ЛОГ")
            }

            Text("Проверка: обычное нажатие микрофона не должно открывать BYD Assistant. 304 при этом продолжает идти в обычную маршрутизацию BYDMate.", style = MaterialTheme.typography.bodySmall)
        }
    }
}
'''
s = s[:card_start] + new_ui
p.write_text(s)

print('build49 production 327 blocker installed')
