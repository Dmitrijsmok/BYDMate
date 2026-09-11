#!/usr/bin/env python3
from pathlib import Path

p = Path("app/src/main/kotlin/com/bydmate/app/service/BootReceiver.kt")
s = p.read_text()
anchor = '''        logBootEvent(context, intent.action ?: "unknown")

        if (intent.action == Intent.ACTION_MY_PACKAGE_REPLACED) {
'''
replacement = '''        logBootEvent(context, intent.action ?: "unknown")

        // Build92: on DiLink 3 the accessibility key filter may not be rebound yet after a cold
        // vehicle restart. WorkManager can start too late, leaving a window where keyCode 327
        // reaches the factory BYD Assistant. Start TrackingService immediately on boot/wake so its
        // existing Build81/83 accessibility self-heal runs before the user presses the mic button.
        if (
            intent.action == Intent.ACTION_BOOT_COMPLETED ||
            intent.action == "android.intent.action.QUICKBOOT_POWERON" ||
            intent.action == Intent.ACTION_USER_PRESENT
        ) {
            try {
                TrackingService.start(context)
                updateBootMethod(context, "Build92DirectBootGuard")
                ChainLog.append(context, "Build92 direct TrackingService start OK: ${intent.action}")
                Log.i(TAG, "Build92 boot guard: TrackingService started immediately for 327 blocker")
            } catch (e: Exception) {
                ChainLog.append(context, "Build92 direct boot guard failed: ${e.message}")
                Log.w(TAG, "Build92 direct boot guard failed; WorkManager fallback follows", e)
            }
        }

        if (intent.action == Intent.ACTION_MY_PACKAGE_REPLACED) {
'''
if anchor not in s:
    raise SystemExit("Build92 startup blocker anchor missing")
s = s.replace(anchor, replacement, 1)
p.write_text(s)
print("Build92 startup blocker applied")
