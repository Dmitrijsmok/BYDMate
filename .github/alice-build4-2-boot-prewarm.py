#!/usr/bin/env python3
from pathlib import Path

p = Path('app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt')
s = p.read_text()
state_anchor = '    private var aliceCandidateDumped = false\n'
if state_anchor not in s:
    raise SystemExit('Alice4.2 prewarm state anchor missing')
s = s.replace(state_anchor, state_anchor + '    private var aliceBootPrewarm = false\n', 1)

# A real steering press always wins over any startup prewarm still in progress.
s = s.replace(
    '                Log.i(TAG, "DILINK3_304_TRIGGER")\n                launchYandexAliceOrApkPure()\n',
    '                Log.i(TAG, "DILINK3_304_TRIGGER")\n                aliceBootPrewarm = false\n                launchYandexAliceOrApkPure()\n',
    1,
)

# Return to the launcher after boot prewarm has opened/clicked Alice, matching the old Build93/94 behavior.
old = '''        if (clicked && terminal) {
            aliceClickPending = false
            aliceClickGeneration++ // invalidates any timer already queued for this attempt
        }
        return clicked
'''
new = '''        if (clicked && terminal) {
            aliceClickPending = false
            aliceClickGeneration++ // invalidates any timer already queued for this attempt
            if (aliceBootPrewarm) {
                aliceBootPrewarm = false
                aliceHandler.postDelayed({
                    runCatching {
                        val home = Intent(Intent.ACTION_MAIN).apply {
                            addCategory(Intent.CATEGORY_HOME)
                            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_NO_ANIMATION)
                        }
                        startActivity(home)
                        Log.i(TAG, "ALICE4_2_BOOT_PREWARM_COMPLETE returnedHome=true")
                    }.onFailure {
                        Log.w(TAG, "ALICE4_2_BOOT_PREWARM_HOME_FAILED ${it.message}")
                    }
                }, 1200L)
            }
        }
        return clicked
'''
if old not in s:
    raise SystemExit('Alice4.2 prewarm terminal anchor missing')
s = s.replace(old, new, 1)

# Clear prewarm mode if the Yandex handoff is cancelled.
old = '''        aliceColdEntryClicked = false
        aliceCandidateDumped = false
        aliceClickGeneration++
'''
new = '''        aliceColdEntryClicked = false
        aliceCandidateDumped = false
        aliceBootPrewarm = false
        aliceClickGeneration++
'''
if old not in s:
    raise SystemExit('Alice4.2 prewarm cancel anchor missing')
s = s.replace(old, new, 1)

entry_anchor = '''    private fun entryPoint(): ClusterEntryPoint =
'''
helper = '''    private fun startBootAlicePrewarm() {
        val voicePrefs = applicationContext.getSharedPreferences("voice", Context.MODE_PRIVATE)
        if (!voicePrefs.getBoolean("alice_native_takeover", false)) return
        if (packageManager.getLaunchIntentForPackage(YANDEX_BROWSER_PACKAGE) == null) return
        val micGranted = packageManager.checkPermission(
            android.Manifest.permission.RECORD_AUDIO,
            YANDEX_BROWSER_PACKAGE,
        ) == android.content.pm.PackageManager.PERMISSION_GRANTED
        if (!micGranted) return
        aliceBootPrewarm = true
        Log.i(TAG, "ALICE4_2_BOOT_PREWARM_START")
        launchYandexAliceOrApkPure()
    }

'''
if entry_anchor not in s:
    raise SystemExit('Alice4.2 prewarm helper anchor missing')
s = s.replace(entry_anchor, helper + entry_anchor, 1)

companion_anchor = '''        @Volatile
        var isConnected: Boolean = false
            private set
'''
companion_new = companion_anchor + '''
        fun requestBootAlicePrewarm(): Boolean {
            val service = instance ?: return false
            service.aliceHandler.post { service.startBootAlicePrewarm() }
            return true
        }
'''
if companion_anchor not in s:
    raise SystemExit('Alice4.2 prewarm companion anchor missing')
s = s.replace(companion_anchor, companion_new, 1)
p.write_text(s)

p = Path('app/src/main/kotlin/com/bydmate/app/service/TrackingService.kt')
s = p.read_text()
anchor = '        serviceScope.launch { ensureStarServiceRunning("startup") }\n'
extra = anchor + '''        serviceScope.launch {
            val voicePrefs = getSharedPreferences("voice", Context.MODE_PRIVATE)
            if (!voicePrefs.getBoolean("alice_native_takeover", false)) return@launch
            val bootPrefs = getSharedPreferences(BootReceiver.PREFS_NAME, Context.MODE_PRIVATE)
            val action = bootPrefs.getString(BootReceiver.KEY_LAST_BOOT_ACTION, "").orEmpty()
            val bootTs = bootPrefs.getLong(BootReceiver.KEY_LAST_BOOT_TS, 0L)
            val realBoot = action == Intent.ACTION_BOOT_COMPLETED ||
                action == "android.intent.action.QUICKBOOT_POWERON"
            val recent = bootTs > 0L && System.currentTimeMillis() - bootTs in 0L..60_000L
            val marker = voicePrefs.getLong("alice4_2_last_prewarm_boot_ts", 0L)
            if (!realBoot || !recent || marker == bootTs) return@launch
            voicePrefs.edit().putLong("alice4_2_last_prewarm_boot_ts", bootTs).apply()
            delay(5_000L)
            repeat(5) { attempt ->
                if (com.bydmate.app.cluster.SteeringWheelKeyService.requestBootAlicePrewarm()) {
                    Log.i(TAG, "Alice4.2 boot prewarm requested attempt=${attempt + 1}")
                    return@launch
                }
                delay(1_500L)
            }
            Log.w(TAG, "Alice4.2 boot prewarm skipped: accessibility not bound")
        }
'''
if anchor not in s:
    raise SystemExit('Alice4.2 TrackingService startup anchor missing')
s = s.replace(anchor, extra, 1)
p.write_text(s)
print('Alice4.2 boot-only Alice prewarm applied')
