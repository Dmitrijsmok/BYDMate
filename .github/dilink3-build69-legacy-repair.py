from pathlib import Path

# Build69: repair persistent system state that old DiLink3 diagnostics could leave behind.
# The old Build45 test could temporarily disable com.byd.vrassistant with `pm disable-user` and
# relied on an app-private snapshot to restore it. If the diagnostic APK was removed before that
# restore completed, Android kept the package disabled while the snapshot disappeared with the APK.
#
# Production must be uninstall-safe: it never needs the stock assistant package disabled. We only
# consume key 327 while BYDMate is selected, so the stock package should always remain enabled.
#
# This patch is deliberately idempotent because a successful verified run commits the repair into
# the production branch before the field APK is assembled. A verification-only rerun must therefore
# accept an already-repaired production tree instead of trying to patch the same anchors twice.

# ---------------------------------------------------------------------------
# 1) HelperDaemon: allow a narrow recovery-only `pm enable` for com.byd.vrassistant.
#    Deliberately DO NOT allow disabling this package through the production helper.
#    Also remove the stale .dilink3diag Accessibility component whenever production A11y is enabled.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/helper/HelperDaemon.kt')
s = p.read_text()

vr_marker = 'pkg == "com.byd.vrassistant" && hidden == 0'
if vr_marker not in s:
    old_tail = '''                        primaryOk && engineOk
                    } else false
                    reply?.writeInt(if (ok) 0 else -1); reply?.writeInt(0)
'''
    new_tail = '''                        primaryOk && engineOk
                    } else if (pkg == "com.byd.vrassistant" && hidden == 0) {
                        // Legacy DiLink3 diagnostic recovery only. Build45 could leave this package
                        // disabled if its APK was removed before AUTO-RESTORE. Production may only
                        // re-enable it; disabling vrassistant through this privileged helper remains
                        // impossible by construction.
                        shExec("pm enable --user 0 \\\"\\$1\\\"", pkg).code == 0
                    } else false
                    reply?.writeInt(if (ok) 0 else -1); reply?.writeInt(0)
'''
    if old_tail not in s:
        raise SystemExit('Build69 HelperDaemon setAppHidden tail anchor not found')
    s = s.replace(old_tail, new_tail, 1)

legacy_a11y_component = (
    'com.bydmate.app.dilink3diag/com.bydmate.app.cluster.SteeringWheelKeyService'
)
if legacy_a11y_component not in s:
    old_others = '''    val others = current.split(':').filter { it.isNotEmpty() && canonicalComponent(it) != target }
'''
    new_others = '''    // Old Build42-66 diagnostics used a side-by-side package. Remove that exact legacy
    // component as part of production self-heal so reinstalling an old diagnostic APK later cannot
    // silently re-bind a second key filter. Every unrelated Accessibility service is preserved.
    val legacyDiagTarget = canonicalComponent(
        "com.bydmate.app.dilink3diag/com.bydmate.app.cluster.SteeringWheelKeyService"
    )
    val others = current.split(':').filter {
        it.isNotEmpty() && canonicalComponent(it) != target && canonicalComponent(it) != legacyDiagTarget
    }
'''
    if old_others not in s:
        raise SystemExit('Build69 HelperDaemon accessibility filter anchor not found')
    s = s.replace(old_others, new_others, 1)

p.write_text(s)

# ---------------------------------------------------------------------------
# 2) TrackingService: one-time DiLink3 migration after the helper is available.
#    - re-enable the stock vrassistant package that Build45 may have left disabled;
#    - restore the older autovoice family as well (legacy BYDMate package-disable feature);
#    - re-assert production Accessibility once, which also removes the stale .dilink3diag entry.
#    This is repair/migration, not the runtime takeover mechanism.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/service/TrackingService.kt')
s = p.read_text()

migration_marker = 'legacy_diag_stock_assistant_restored_v1'
if migration_marker not in s:
    anchor = '''                    val legacyPref = settingsRepository.getString(
                        SettingsRepository.KEY_DISABLE_NATIVE_ASSISTANT, "")
'''
    insert = '''                    // One-time migration for persistent system state left by pre-production
                    // DiLink3 diagnostics. App uninstall clears app data but does NOT reliably undo
                    // shell/secure-settings mutations such as pm disable-user. Production never
                    // disables the stock assistant package; key ownership is event-level only.
                    if (android.os.Build.VERSION.SDK_INT <= 29) {
                        val migrationPrefs = getSharedPreferences("dilink3_migrations", Context.MODE_PRIVATE)
                        if (!migrationPrefs.getBoolean("legacy_diag_stock_assistant_restored_v1", false)) {
                            val a11yRepaired = runCatching { helperClient.enableAccessibilityService() }
                                .getOrDefault(false)
                            val vrRestored = runCatching {
                                helperClient.setAppHidden("com.byd.vrassistant", false)
                            }.getOrDefault(false)
                            val autoVoiceRestored = runCatching {
                                helperClient.setAppHidden("com.byd.autovoice", false)
                            }.getOrDefault(false)
                            val stockRestored = vrRestored || autoVoiceRestored
                            if (a11yRepaired && stockRestored) {
                                migrationPrefs.edit()
                                    .putBoolean("legacy_diag_stock_assistant_restored_v1", true)
                                    .apply()
                                Log.i(
                                    TAG,
                                    "DiLink3 legacy state repaired: a11y=$a11yRepaired vr=$vrRestored autovoice=$autoVoiceRestored"
                                )
                            } else {
                                Log.w(
                                    TAG,
                                    "DiLink3 legacy state repair incomplete: a11y=$a11yRepaired vr=$vrRestored autovoice=$autoVoiceRestored; will retry"
                                )
                            }
                        }
                    }

'''
    if anchor not in s:
        raise SystemExit('Build69 TrackingService legacy restore anchor not found')
    s = s.replace(anchor, insert + anchor, 1)

p.write_text(s)

print('Build69 legacy DiLink3 repair present and verified idempotently')
