#!/usr/bin/env python3
from pathlib import Path

VERSION_CODE = "60031"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Build81 anchor missing: {label}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# 1) Monotonic field identity over Build80.
# ---------------------------------------------------------------------------
p = Path("app/build.gradle.kts")
s = p.read_text()
s = replace_once(s, "        versionCode = 60030", f"        versionCode = {VERSION_CODE}", "versionCode")
s = replace_once(
    s,
    '            versionNameSuffix = "-dilink3-production-build80"',
    '            versionNameSuffix = "-dilink3-production-build81"',
    "versionNameSuffix",
)
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = replace_once(
    s,
    'android:label="BYDMate DiLink3 Build80"',
    'android:label="BYDMate DiLink3 Build81"',
    "manifest label",
)
p.write_text(s)


# ---------------------------------------------------------------------------
# 2) Build71 displayed "restart required" whenever A11Y was merely disconnected.
#    That is not a reboot condition. Trigger the existing helper recovery and show a
#    truthful transient recovery status instead.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text()
old = '''            val restartRequired = state.voiceEnabled && !build70A11y
            Text(
                if (state.voiceEnabled) {
                    if (build70A11y) stringResource(R.string.settings_dilink3_assistant_status_blocked)
                    else stringResource(R.string.settings_dilink3_assistant_status_waiting)
                } else stringResource(R.string.settings_dilink3_assistant_status_factory),
                color = TextMuted,
                fontSize = 11.sp,
                modifier = Modifier.padding(top = 4.dp),
            )
            if (restartRequired) {
                Text(
                    stringResource(R.string.settings_dilink3_restart_required),
                    color = AccentOrange,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.padding(bottom = 4.dp),
                )
            }
            Text(
                stringResource(R.string.settings_dilink3_debug_codes, build70Age304, build70Age327),
                color = TextMuted,
                fontSize = 10.sp,
                modifier = Modifier.padding(bottom = 6.dp),
            )
'''
new = '''            val steeringRepairNeeded = state.voiceEnabled && !build70A11y
            LaunchedEffect(state.voiceEnabled, build70A11y) {
                if (steeringRepairNeeded) viewModel.ensureDiLink3SteeringTakeover()
            }
            Text(
                if (state.voiceEnabled) {
                    if (build70A11y) stringResource(R.string.settings_dilink3_assistant_status_blocked)
                    else stringResource(R.string.settings_dilink3_assistant_status_recovering)
                } else stringResource(R.string.settings_dilink3_assistant_status_factory),
                color = TextMuted,
                fontSize = 11.sp,
                modifier = Modifier.padding(top = 4.dp),
            )
            if (steeringRepairNeeded) {
                Text(
                    stringResource(R.string.settings_dilink3_recovery_hint),
                    color = AccentOrange,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.padding(bottom = 4.dp),
                )
            }
            Text(
                stringResource(R.string.settings_dilink3_debug_codes, build70Age304, build70Age327),
                color = TextMuted,
                fontSize = 10.sp,
                modifier = Modifier.padding(bottom = 6.dp),
            )
'''
s = replace_once(s, old, new, "replace false reboot warning with auto-recovery")
p.write_text(s)


# ---------------------------------------------------------------------------
# 3) Immediate steering/A11Y repair from Settings.
#    HelperDaemon.enableAccessibilityService() already does the safe remove+re-add of only
#    our component. If Android 10 still leaves the component in mBindingServices, use the
#    existing daemon force-stop recovery, rate-limited so it cannot loop.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsViewModel.kt")
s = p.read_text()
anchor = '''    fun setDiLink3SteeringAssistant(enabled: Boolean) {
'''
method = '''    @Volatile
    private var build81SteeringRepairRunning = false

    /**
     * DiLink3 microphone takeover is an Accessibility key filter, not a boot-time BYD package
     * mutation. Recover it in-place after APK upgrades / framework unbinds; no head-unit reboot.
     */
    fun ensureDiLink3SteeringTakeover() {
        if (!_uiState.value.voiceEnabled) return
        if (com.bydmate.app.cluster.SteeringWheelKeyService.isConnected) return
        if (build81SteeringRepairRunning) return
        build81SteeringRepairRunning = true
        viewModelScope.launch {
            try {
                val helperReady = runCatching { helperBootstrap.ensureRunning() }.getOrDefault(false)
                if (!helperReady) {
                    Log.e(TAG, "Build81 steering repair: helper daemon unavailable")
                    return@launch
                }

                val reasserted = runCatching { helperClient.enableAccessibilityService() }.getOrDefault(false)
                Log.i(TAG, "Build81 steering repair: a11y reasserted=$reasserted")
                kotlinx.coroutines.delay(1800L)
                if (com.bydmate.app.cluster.SteeringWheelKeyService.isConnected) {
                    Log.i(TAG, "Build81 steering repair: connected after reassert")
                    return@launch
                }

                // Android 10 can retain an already-listed service in mBindingServices after an
                // app-process death/update. The daemon recovery clears that state by force-stopping
                // only BYDMate, then re-enabling this exact component and restarting TrackingService.
                val services = android.provider.Settings.Secure.getString(
                    appContext.contentResolver, "enabled_accessibility_services"
                ).orEmpty()
                val listed = services.contains(appContext.packageName)
                if (listed && android.os.Build.VERSION.SDK_INT <= 29) {
                    val prefs = appContext.getSharedPreferences(
                        "build81_a11y_recovery", Context.MODE_PRIVATE
                    )
                    val now = android.os.SystemClock.elapsedRealtime()
                    val last = prefs.getLong("last_recover_elapsed", 0L)
                    if (last == 0L || now < last || now - last >= 10 * 60 * 1000L) {
                        prefs.edit().putLong("last_recover_elapsed", now).apply()
                        Log.w(TAG, "Build81 steering repair: listed but unbound; invoking Android10 recovery")
                        // The app process is expected to die during this Binder call. A false return
                        // is normal because the caller disappears before the daemon can reply.
                        runCatching { helperClient.recoverAccessibilityService() }
                    }
                }
            } finally {
                build81SteeringRepairRunning = false
            }
        }
    }

'''
s = replace_once(s, anchor, method + anchor, "Build81 steering repair method")
p.write_text(s)


# ---------------------------------------------------------------------------
# 4) Keep checking the steering filter after startup. Existing startup/wake recovery can lose
#    the race with Android 10 after an APK update; a lightweight 30 s watchdog gives it another
#    chance. ensureStarServiceRunning() is internally gated and does nothing when no feature needs it.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/service/TrackingService.kt")
s = p.read_text()
old = '''        serviceScope.launch { ensureStarServiceRunning("startup") }
        serviceScope.launch { notificationListenerGrant.ensure("startup") }
'''
new = '''        serviceScope.launch { ensureStarServiceRunning("startup") }
        serviceScope.launch {
            while (true) {
                kotlinx.coroutines.delay(30_000L)
                ensureStarServiceRunning("build81-watchdog")
            }
        }
        serviceScope.launch { notificationListenerGrant.ensure("startup") }
'''
s = replace_once(s, old, new, "periodic steering a11y watchdog")
p.write_text(s)


# ---------------------------------------------------------------------------
# 5) Short truthful UI strings. The old restart string can stay for historical resources but
#    Build81 no longer references it from the voice takeover card.
# ---------------------------------------------------------------------------
for values_dir, vals in {
    "values": {
        "settings_dilink3_assistant_status_recovering": "Штатный BYD Assistant: восстанавливаю блокировку",
        "settings_dilink3_recovery_hint": "Перехват кнопки восстанавливается автоматически — перезагрузка ДиЛинка не требуется",
    },
    "values-en": {
        "settings_dilink3_assistant_status_recovering": "Factory BYD Assistant: restoring blocker",
        "settings_dilink3_recovery_hint": "Button interception is recovering automatically — no DiLink reboot is required",
    },
}.items():
    p = Path(f"app/src/main/res/{values_dir}/strings.xml")
    if not p.exists():
        continue
    s = p.read_text()
    additions = "\n".join(f'    <string name="{k}">{v}</string>' for k, v in vals.items()) + "\n"
    s = replace_once(s, "</resources>", additions + "</resources>", f"{values_dir} Build81 strings")
    p.write_text(s)

print("Build81 applied: DiLink3 steering takeover self-recovers; reboot warning removed")
