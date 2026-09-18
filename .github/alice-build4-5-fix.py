#!/usr/bin/env python3
from pathlib import Path
import re


def once(text, old, new, label):
    if old not in text:
        raise SystemExit(f"Alice4.5b anchor missing: {label}")
    return text.replace(old, new, 1)

# Identity
p = Path("app/build.gradle.kts")
s = p.read_text()
s = once(s, "versionCode = 64005", "versionCode = 64006", "versionCode")
s = once(s, 'versionName = "3.15.2-alice4.4-silent-recovery"',
         'versionName = "3.15.2-alice4.5-cold-chain"', "versionName")
p.write_text(s)

# Real BYD assistant allowlist: exact second known package, reversible only.
p = Path("app/src/main/kotlin/com/bydmate/app/helper/HelperDaemon.kt")
s = p.read_text()
s = once(s,
'''                    val ok = if (pkg == "com.byd.autovoice" && hidden in 0..1) {
''',
'''                    val ok = if (pkg == "com.byd.vrassistant" && hidden in 0..1) {
                        val cmd = if (hidden == 1) "pm disable-user --user 0" else "pm enable"
                        shExec("$cmd \\\"\\$1\\\"", pkg).code == 0
                    } else if (pkg == "com.byd.autovoice" && hidden in 0..1) {
''', "vrassistant allowlist")
p.write_text(s)

# Reassert vrassistant as soon as helper exists after install/update.
p = Path("app/src/main/kotlin/com/bydmate/app/service/TrackingService.kt")
s = p.read_text()
s = once(s,
'''                if (helperReady) {
                    val reasserted = runCatching { helperClient.enableAccessibilityService() }.getOrDefault(false)
''',
'''                if (helperReady) {
                    if (voicePrefs.getBoolean("alice_native_takeover", false)) {
                        val vrBlocked = runCatching {
                            helperClient.setAppHidden("com.byd.vrassistant", true)
                        }.getOrDefault(false)
                        Log.i(TAG, "ALICE4_5_VRASSISTANT_BLOCK startup=$vrBlocked")
                    }
                    val reasserted = runCatching { helperClient.enableAccessibilityService() }.getOrDefault(false)
''', "vrassistant startup reassert")
p.write_text(s)

# Milder external-Alice music duck, using existing crash-safe stack.
p = Path("app/src/main/kotlin/com/bydmate/app/voice/AudioCapture.kt")
s = p.read_text()
s = once(s, "        internal const val DUCK_VOLUME_INDEX = 1\n",
         "        internal const val DUCK_VOLUME_INDEX = 1\n        internal const val EXTERNAL_ASSISTANT_DUCK_VOLUME_INDEX = 4\n",
         "duck constant")
anchor = '''    /** Restore the media volume captured by duckMusic(), or the explicit mid-session override. No-op if nothing was ducked. */
'''
method = '''    internal fun duckMusicForExternalAssistant(): Int? = synchronized(duckLock) {
        if (!audioManager.isMusicActive) return null
        val saved = audioManager.getStreamVolume(AudioManager.STREAM_MUSIC)
        val target = EXTERNAL_ASSISTANT_DUCK_VOLUME_INDEX
        if (saved <= target) return null
        val applied = runCatching { audioManager.setStreamVolume(AudioManager.STREAM_MUSIC, target, 0) }.isSuccess
        if (!applied) return null
        duckDepth++
        pendingRestore = saved
        prefs.edit().putInt(KEY_PRE_DUCK_VOLUME, saved).apply()
        Log.i(TAG, "duckExternalAlice: $saved -> $target")
        saved
    }

'''
s = once(s, anchor, method + anchor, "external duck method")
p.write_text(s)

p = Path("app/src/main/kotlin/com/bydmate/app/voice/VoiceController.kt")
s = p.read_text()
s = once(s, '''    @Volatile private var sessionJob: Job? = null
''', '''    @Volatile private var sessionJob: Job? = null
    private val externalAliceDuckLock = Any()
    @Volatile private var externalAliceDuckSaved: Int? = null
    private val externalAliceDuckGeneration = AtomicInteger(0)
''', "duck fields")
anchor = '''    fun sessionActive(): Boolean = listening.value || busy.get()
'''
methods = anchor + '''
    fun beginExternalAliceDuck() {
        val saved = synchronized(externalAliceDuckLock) {
            externalAliceDuckSaved ?: runCatching { audioCapture.duckMusicForExternalAssistant() }
                .getOrNull()?.also { externalAliceDuckSaved = it }
        }
        val generation = externalAliceDuckGeneration.incrementAndGet()
        Log.i(TAG, "ALICE_EXTERNAL_DUCK begin saved=$saved generation=$generation")
        scope.launch {
            delay(60_000L)
            if (externalAliceDuckGeneration.get() == generation) endExternalAliceDuck("safety_timeout")
        }
    }

    fun endExternalAliceDuck(reason: String) {
        val saved = synchronized(externalAliceDuckLock) {
            val value = externalAliceDuckSaved
            externalAliceDuckSaved = null
            value
        }
        externalAliceDuckGeneration.incrementAndGet()
        if (saved != null) runCatching { audioCapture.restoreMusic(saved) }
        Log.i(TAG, "ALICE_EXTERNAL_DUCK end reason=$reason restored=${saved != null}")
    }

'''
s = once(s, anchor, methods, "duck controller methods")
p.write_text(s)

# One-press cold Yandex/Alice state machine.
p = Path("app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt")
s = p.read_text()
s = once(s, '''    private var aliceColdEntryClicked = false
    private var aliceCandidateDumped = false
''', '''    private var aliceColdEntryClicked = false
    private var aliceCandidateDumped = false
    private var aliceColdClickCount = 0
    private var aliceLastColdClickElapsed = 0L
    private var aliceExactAfterColdClickCount = 0
    private var aliceLastExactClickElapsed = 0L
    private var aliceSessionListening = false
''', "cold state")

# All arm/cancel resets that already reset these two fields also reset counters.
s = s.replace('''        aliceColdEntryClicked = false
        aliceCandidateDumped = false
''', '''        aliceColdEntryClicked = false
        aliceCandidateDumped = false
        aliceColdClickCount = 0
        aliceLastColdClickElapsed = 0L
        aliceExactAfterColdClickCount = 0
        aliceLastExactClickElapsed = 0L
''')

# Warm probe happens before armAliceClick(), so reset at launcher entry too.
s = once(s, '''    private fun launchYandexAliceOrApkPure() {
        val browserLaunchIntent = packageManager.getLaunchIntentForPackage(YANDEX_BROWSER_PACKAGE)
''', '''    private fun launchYandexAliceOrApkPure() {
        aliceColdEntryClicked = false
        aliceCandidateDumped = false
        aliceColdClickCount = 0
        aliceLastColdClickElapsed = 0L
        aliceExactAfterColdClickCount = 0
        aliceLastExactClickElapsed = 0L
        aliceSessionListening = false
        val browserLaunchIntent = packageManager.getLaunchIntentForPackage(YANDEX_BROWSER_PACKAGE)
''', "launcher reset")
s = once(s, "        private const val ALICE_MAX_CLICK_ATTEMPTS = 36\n",
         "        private const val ALICE_MAX_CLICK_ATTEMPTS = 90\n", "retry budget")

# First exact click after cold path primes Alice; second exact click is terminal.
s = once(s, '''            for (node in exact) {
                if (clickAliceCandidate(node, "exact_alice", source, terminal = true)) {
                    Log.i(TAG, "ALICE4_1_LISTENING_CLICK exact=true coldFirst=$aliceColdEntryClicked")
                    return true
                }
            }
''', '''            for (node in exact) {
                val now = android.os.SystemClock.elapsedRealtime()
                val coldChain = aliceColdClickCount > 0
                val firstColdExact = coldChain && aliceExactAfterColdClickCount == 0
                if (coldChain && aliceExactAfterColdClickCount > 0 && now - aliceLastExactClickElapsed < 800L) continue
                val terminal = !firstColdExact
                if (clickAliceCandidate(node, "exact_alice", source, terminal = terminal)) {
                    if (coldChain) {
                        aliceExactAfterColdClickCount++
                        aliceLastExactClickElapsed = now
                    }
                    if (terminal) {
                        aliceSessionListening = true
                        Log.i(TAG, "ALICE4_5_LISTENING_READY cold=$coldChain exactClicks=$aliceExactAfterColdClickCount")
                        return true
                    }
                    Log.i(TAG, "ALICE4_5_COLD_EXACT_PRIME click=$aliceExactAfterColdClickCount continuing=true")
                    return false
                }
            }
''', "cold exact two-click")

# Cold mic ACTION_CLICK can succeed without navigating; retry same exact control after 900 ms, max 3.
s = once(s, '''        if (!aliceColdEntryClicked) {
            for (root in roots) {
                for (coldId in listOf(ALICE_COLD_CURRENT_VIEW_ID, ALICE_COLD_VIEW_ID)) {
                    val nodes = runCatching { root.findAccessibilityNodeInfosByViewId(coldId) }
                        .getOrNull().orEmpty()
                    for (node in nodes) {
                        if (clickAliceCandidate(node, "cold_exact_id", source, terminal = false)) {
                            aliceColdEntryClicked = true
                            Log.i(TAG, "ALICE4_2_COLD_ENTRY_CLICKED id=${node.viewIdResourceName ?: "-"} desc=${node.contentDescription ?: "-"}")
                            return false
                        }
                    }
                }
            }
        }
''', '''        if (aliceColdClickCount < 3) {
            for (root in roots) {
                for (coldId in listOf(ALICE_COLD_CURRENT_VIEW_ID, ALICE_COLD_VIEW_ID)) {
                    val nodes = runCatching { root.findAccessibilityNodeInfosByViewId(coldId) }.getOrNull().orEmpty()
                    for (node in nodes) {
                        val now = android.os.SystemClock.elapsedRealtime()
                        if (aliceColdClickCount > 0 && now - aliceLastColdClickElapsed < 900L) continue
                        if (clickAliceCandidate(node, "cold_exact_id", source, terminal = false)) {
                            aliceColdEntryClicked = true
                            aliceColdClickCount++
                            aliceLastColdClickElapsed = now
                            Log.i(TAG, "ALICE4_5_COLD_ENTRY_CLICK count=$aliceColdClickCount id=${node.viewIdResourceName ?: "-"} desc=${node.contentDescription ?: "-"}")
                            return false
                        }
                    }
                }
            }
        }
''', "cold mic retries")

# Inject duck robustly at the observed 304 log -> launcher pair, regardless of intermediate comments/spacing.
pat = re.compile(r'(Log\.i\(TAG, "DILINK3_304_TRIGGER"\)\s*\n)(\s*)(launchYandexAliceOrApkPure\(\))')
m = pat.search(s)
if not m:
    raise SystemExit("Alice4.5b anchor missing: DILINK3_304_TRIGGER launcher")
indent = m.group(2)
s = s[:m.start()] + m.group(1) + indent + 'entryPoint().voiceController().beginExternalAliceDuck()\n' + indent + m.group(3) + s[m.end():]

# Guard native BYD window and restore media when user leaves Yandex after listening is reached.
old_event = '''    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        NavA11yFeed.onEvent(this, event)

        if (aliceClickPending && event?.packageName?.toString() == YANDEX_BROWSER_PACKAGE) {
            if (!yandexWindowLogged) {
                yandexWindowLogged = true
                Log.i(TAG, "YANDEX_WINDOW_DETECTED eventType=${event.eventType}")
            }
            tryClickAliceNode("event:${event.eventType}")
        }
    }
'''
new_event = '''    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        NavA11yFeed.onEvent(this, event)
        if (event == null) return
        val eventPkg = event.packageName?.toString().orEmpty()
        val nativeTakeover = applicationContext.getSharedPreferences("voice", Context.MODE_PRIVATE)
            .getBoolean("alice_native_takeover", false)
        if (nativeTakeover && eventPkg == "com.byd.vrassistant" && event.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
            val closed = performGlobalAction(GLOBAL_ACTION_BACK)
            Log.w(TAG, "ALICE4_5_VRASSISTANT_WINDOW_BLOCKED back=$closed")
        }
        if (aliceClickPending && eventPkg == YANDEX_BROWSER_PACKAGE) {
            if (!yandexWindowLogged) {
                yandexWindowLogged = true
                Log.i(TAG, "YANDEX_WINDOW_DETECTED eventType=${event.eventType}")
            }
            tryClickAliceNode("event:${event.eventType}")
        }
        if (aliceSessionListening && event.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED &&
            eventPkg.isNotBlank() && eventPkg != YANDEX_BROWSER_PACKAGE && eventPkg != packageName) {
            aliceHandler.postDelayed({
                val activePkg = runCatching { rootInActiveWindow?.packageName?.toString() }.getOrNull()
                if (aliceSessionListening && activePkg != YANDEX_BROWSER_PACKAGE) {
                    aliceSessionListening = false
                    entryPoint().voiceController().endExternalAliceDuck("left_yandex:${activePkg ?: eventPkg}")
                }
            }, 1_200L)
        }
    }
'''
s = once(s, old_event, new_event, "event guard")

s = once(s, '''    override fun onUnbind(intent: Intent?): Boolean {
        cancelAliceClick("a11y_unbind")
''', '''    override fun onUnbind(intent: Intent?): Boolean {
        entryPoint().voiceController().endExternalAliceDuck("a11y_unbind")
        cancelAliceClick("a11y_unbind")
''', "unbind restore")
s = once(s, '''    override fun onDestroy() {
        cancelAliceClick("a11y_destroy")
''', '''    override fun onDestroy() {
        entryPoint().voiceController().endExternalAliceDuck("a11y_destroy")
        cancelAliceClick("a11y_destroy")
''', "destroy restore")
p.write_text(s)

print("Alice4.5b applied: cold one-press chain + vrassistant hard block + media duck")
