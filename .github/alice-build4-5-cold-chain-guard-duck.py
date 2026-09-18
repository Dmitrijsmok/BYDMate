#!/usr/bin/env python3
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Alice4.5 anchor missing: {label}")
    return text.replace(old, new, 1)

# ---------------------------------------------------------------------------
# 1) Identity: same package, monotonic versionCode. Signing is handled separately
#    with the permanent Alice4 key so 4.5 installs over 4.4.
# ---------------------------------------------------------------------------
p = Path("app/build.gradle.kts")
s = p.read_text()
s = once(s, "versionCode = 64005", "versionCode = 64006", "versionCode")
s = once(
    s,
    'versionName = "3.15.2-alice4.4-silent-recovery"',
    'versionName = "3.15.2-alice4.5-cold-chain"',
    "versionName",
)
p.write_text(s)

# ---------------------------------------------------------------------------
# 2) Fix the real DiLink3 native assistant package hole.
#    4.2 started calling setAppHidden(com.byd.vrassistant), but the privileged
#    daemon only allowed com.byd.autovoice, so every vrassistant request was
#    rejected and diagnostics kept showing ENABLED. Allow ONLY this exact second
#    known package, using the same reversible pm disable-user / pm enable pair.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/helper/HelperDaemon.kt")
s = p.read_text()
old = '''                    val ok = if (pkg == "com.byd.autovoice" && hidden in 0..1) {
'''
new = '''                    val ok = if (pkg == "com.byd.vrassistant" && hidden in 0..1) {
                        val cmd = if (hidden == 1) "pm disable-user --user 0" else "pm enable"
                        shExec("$cmd \\\"\\$1\\\"", pkg).code == 0
                    } else if (pkg == "com.byd.autovoice" && hidden in 0..1) {
'''
s = once(s, old, new, "vrassistant daemon allowlist")
p.write_text(s)

# Re-apply vrassistant state as soon as the helper becomes available during the
# install/update A11Y recovery. This closes the race where the old startup sync ran
# before the daemon was alive.
p = Path("app/src/main/kotlin/com/bydmate/app/service/TrackingService.kt")
s = p.read_text()
old = '''                if (helperReady) {
                    val reasserted = runCatching { helperClient.enableAccessibilityService() }.getOrDefault(false)
'''
new = '''                if (helperReady) {
                    if (voicePrefs.getBoolean("alice_native_takeover", false)) {
                        val vrBlocked = runCatching {
                            helperClient.setAppHidden("com.byd.vrassistant", true)
                        }.getOrDefault(false)
                        Log.i(TAG, "ALICE4_5_VRASSISTANT_BLOCK startup=$vrBlocked")
                    }
                    val reasserted = runCatching { helperClient.enableAccessibilityService() }.getOrDefault(false)
'''
s = once(s, old, new, "startup vrassistant reassert")
p.write_text(s)

# ---------------------------------------------------------------------------
# 3) External Alice media duck.
#    Local BYDMate voice already has a crash-safe duck stack. Add a milder target
#    for Yandex Alice so music becomes background instead of competing with speech,
#    while keeping enough STREAM_MUSIC level in case Yandex renders speech there.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/voice/AudioCapture.kt")
s = p.read_text()
s = once(
    s,
    "        internal const val DUCK_VOLUME_INDEX = 1\n",
    "        internal const val DUCK_VOLUME_INDEX = 1\n        internal const val EXTERNAL_ASSISTANT_DUCK_VOLUME_INDEX = 4\n",
    "external duck constant",
)
anchor = '''    /** Restore the media volume captured by duckMusic(), or the explicit mid-session override. No-op if nothing was ducked. */
'''
method = '''    /** Milder duck for an external assistant (Yandex Alice). Uses the same nested,
     * crash-safe restore bookkeeping as local voice capture, but does not nearly mute
     * STREAM_MUSIC because Alice itself may render on that stream on some firmware. */
    internal fun duckMusicForExternalAssistant(): Int? = synchronized(duckLock) {
        if (!audioManager.isMusicActive) return null
        val saved = audioManager.getStreamVolume(AudioManager.STREAM_MUSIC)
        val target = EXTERNAL_ASSISTANT_DUCK_VOLUME_INDEX
        if (saved <= target) return null
        val applied = runCatching {
            audioManager.setStreamVolume(AudioManager.STREAM_MUSIC, target, 0)
        }.isSuccess
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
field_anchor = '''    @Volatile private var sessionJob: Job? = null
'''
fields = '''    @Volatile private var sessionJob: Job? = null
    private val externalAliceDuckLock = Any()
    @Volatile private var externalAliceDuckSaved: Int? = null
    private val externalAliceDuckGeneration = AtomicInteger(0)
'''
s = once(s, field_anchor, fields, "external duck fields")
method_anchor = '''    fun sessionActive(): Boolean = listening.value || busy.get()
'''
methods = method_anchor + '''
    /** Duck media for the external Yandex Alice route. Repeated steering presses only
     * refresh the safety timeout; they never nest another physical volume change. */
    fun beginExternalAliceDuck() {
        val saved = synchronized(externalAliceDuckLock) {
            externalAliceDuckSaved ?: runCatching {
                audioCapture.duckMusicForExternalAssistant()
            }.getOrNull()?.also { externalAliceDuckSaved = it }
        }
        val generation = externalAliceDuckGeneration.incrementAndGet()
        Log.i(TAG, "ALICE_EXTERNAL_DUCK begin saved=$saved generation=$generation")
        scope.launch {
            delay(60_000L)
            if (externalAliceDuckGeneration.get() == generation) {
                endExternalAliceDuck("safety_timeout")
            }
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
s = once(s, method_anchor, methods, "external duck controller methods")
p.write_text(s)

# ---------------------------------------------------------------------------
# 4) Turn the observed three human presses into one cold handoff.
#    Field log 4.4 proves:
#      - first cold mic click can report ACTION_CLICK success while the SAME cold
#        button remains visible; retry it after a short debounce.
#      - the first exact alice_input_quarknyx click after a cold path can merely
#        prime/open Alice; click that exact control a second time after it settles.
#    Warm Alice remains one exact click and is not slowed down.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt")
s = p.read_text()
s = once(
    s,
    '''    private var aliceColdEntryClicked = false
    private var aliceCandidateDumped = false
''',
    '''    private var aliceColdEntryClicked = false
    private var aliceCandidateDumped = false
    private var aliceColdClickCount = 0
    private var aliceLastColdClickElapsed = 0L
    private var aliceExactAfterColdClickCount = 0
    private var aliceLastExactClickElapsed = 0L
    private var aliceSessionListening = false
''',
    "cold-chain state fields",
)

# Reset state both on newly armed delayed handoff and cancel paths.
s = s.replace(
    '''        aliceColdEntryClicked = false
        aliceCandidateDumped = false
''',
    '''        aliceColdEntryClicked = false
        aliceCandidateDumped = false
        aliceColdClickCount = 0
        aliceLastColdClickElapsed = 0L
        aliceExactAfterColdClickCount = 0
        aliceLastExactClickElapsed = 0L
''',
)

# Warm-toolbar probing happens before armAliceClick(), so clear per-press chain state
# at launcher entry too; otherwise a previous cold session can make a later warm click
# look like a cold continuation.
s = once(
    s,
    '''    private fun launchYandexAliceOrApkPure() {
        val browserLaunchIntent = packageManager.getLaunchIntentForPackage(YANDEX_BROWSER_PACKAGE)
''',
    '''    private fun launchYandexAliceOrApkPure() {
        aliceColdEntryClicked = false
        aliceCandidateDumped = false
        aliceColdClickCount = 0
        aliceLastColdClickElapsed = 0L
        aliceExactAfterColdClickCount = 0
        aliceLastExactClickElapsed = 0L
        aliceSessionListening = false
        val browserLaunchIntent = packageManager.getLaunchIntentForPackage(YANDEX_BROWSER_PACKAGE)
''',
    "per-press handoff reset",
)

# Give a truly cold Chromium/Alice chain enough time to finish automatically.
s = once(
    s,
    "        private const val ALICE_MAX_CLICK_ATTEMPTS = 36\n",
    "        private const val ALICE_MAX_CLICK_ATTEMPTS = 90\n",
    "cold handoff retry budget",
)

old_exact = '''            for (node in exact) {
                if (clickAliceCandidate(node, "exact_alice", source, terminal = true)) {
                    Log.i(TAG, "ALICE4_1_LISTENING_CLICK exact=true coldFirst=$aliceColdEntryClicked")
                    return true
                }
            }
'''
new_exact = '''            for (node in exact) {
                val now = android.os.SystemClock.elapsedRealtime()
                val coldChain = aliceColdClickCount > 0
                val firstColdExact = coldChain && aliceExactAfterColdClickCount == 0
                if (coldChain && aliceExactAfterColdClickCount > 0 &&
                    now - aliceLastExactClickElapsed < 800L) continue
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
                    Log.i(TAG, "ALICE4_5_COLD_EXACT_PRIME click=$aliceExactAfterColdClickCount; continuing")
                    return false
                }
            }
'''
s = once(s, old_exact, new_exact, "two-stage exact Alice click")

old_cold_exact = '''        if (!aliceColdEntryClicked) {
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
'''
new_cold_exact = '''        if (aliceColdClickCount < 3) {
            for (root in roots) {
                for (coldId in listOf(ALICE_COLD_CURRENT_VIEW_ID, ALICE_COLD_VIEW_ID)) {
                    val nodes = runCatching { root.findAccessibilityNodeInfosByViewId(coldId) }
                        .getOrNull().orEmpty()
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
'''
s = once(s, old_cold_exact, new_cold_exact, "repeat cold exact click")

# Start the external duck immediately with 304 before Browser/Alice launch.
s = once(
    s,
    '''            if (isDown && event.repeatCount == 0) {
                Log.i(TAG, "DILINK3_304_TRIGGER")
                launchYandexAliceOrApkPure()
            }
''',
    '''            if (isDown && event.repeatCount == 0) {
                Log.i(TAG, "DILINK3_304_TRIGGER")
                entryPoint().voiceController().beginExternalAliceDuck()
                launchYandexAliceOrApkPure()
            }
''',
    "duck on 304",
)

# Second safety layer: if vrassistant still manages to surface during a takeover,
# immediately BACK out. Also restore duck after the user actually leaves Yandex,
# but only after Alice reached the terminal listening click so transition events
# during cold startup cannot restore it prematurely.
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
        if (nativeTakeover && eventPkg == "com.byd.vrassistant" &&
            event.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
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
s = once(s, old_event, new_event, "vrassistant window guard and duck restore")

# If A11Y is torn down while ducked, never leave media stuck low.
s = once(
    s,
    '''    override fun onUnbind(intent: Intent?): Boolean {
        cancelAliceClick("a11y_unbind")
''',
    '''    override fun onUnbind(intent: Intent?): Boolean {
        entryPoint().voiceController().endExternalAliceDuck("a11y_unbind")
        cancelAliceClick("a11y_unbind")
''',
    "duck restore on unbind",
)
s = once(
    s,
    '''    override fun onDestroy() {
        cancelAliceClick("a11y_destroy")
''',
    '''    override fun onDestroy() {
        entryPoint().voiceController().endExternalAliceDuck("a11y_destroy")
        cancelAliceClick("a11y_destroy")
''',
    "duck restore on destroy",
)
p.write_text(s)

print("Alice4.5 applied: cold chain retries + vrassistant hard block + external Alice media duck")
