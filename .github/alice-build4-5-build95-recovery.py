#!/usr/bin/env python3
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Alice4.5 anchor missing: {label}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# 1) Identity: same Alice4 package, monotonic version for in-place updates when
#    signed with the same stable key.
# ---------------------------------------------------------------------------
p = Path("app/build.gradle.kts")
s = p.read_text()
s = once(s, "versionCode = 64005", "versionCode = 64006", "versionCode")
s = once(
    s,
    'versionName = "3.15.2-alice4.4-silent-recovery"',
    'versionName = "3.15.2-alice4.5-build95-recovery"',
    "versionName",
)
p.write_text(s)


# ---------------------------------------------------------------------------
# 2) Helper daemon: Alice4.2 started targeting com.byd.vrassistant, but the
#    daemon endpoint still only allowed the old com.byd.autovoice family. Keep
#    the endpoint narrowly allow-listed; add ONLY the actual DiLink3 package.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/helper/HelperDaemon.kt")
s = p.read_text()
old = '''                if (pkg != "com.byd.autovoice") {
                    reply.writeInt(0)
                    return true
                }
                val command = if (hidden) {
                    "pm disable-user --user 0 \\"$1\\""
                } else {
                    "pm enable \\"$1\\""
                }
                val packages = listOf(
                    "com.byd.autovoice",
                    "com.byd.autovoice.engine",
                    "com.byd.autovoice.tts",
                )
'''
new = '''                val command = if (hidden) {
                    "pm disable-user --user 0 \\"$1\\""
                } else {
                    "pm enable \\"$1\\""
                }
                if (pkg == "com.byd.vrassistant") {
                    if (!packageExists(pkg)) {
                        reply.writeInt(0)
                        return true
                    }
                    val r = shExec(command, pkg)
                    reply.writeInt(if (r.code == 0) 1 else 0)
                    return true
                }
                if (pkg != "com.byd.autovoice") {
                    reply.writeInt(0)
                    return true
                }
                val packages = listOf(
                    "com.byd.autovoice",
                    "com.byd.autovoice.engine",
                    "com.byd.autovoice.tts",
                )
'''
s = once(s, old, new, "vrassistant helper allowlist")
p.write_text(s)


# ---------------------------------------------------------------------------
# 3) Absolutely no Alice/Yandex boot prewarm. The 4.4 service-only wake is not
#    silent on the field Yandex build. Accessibility recovery remains untouched.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/service/TrackingService.kt")
s = p.read_text()
old = '''        serviceScope.launch {
            val voicePrefs = getSharedPreferences("voice", Context.MODE_PRIVATE)
            if (!voicePrefs.getBoolean("alice_native_takeover", false)) return@launch
            val bootPrefs = getSharedPreferences(BootReceiver.PREFS_NAME, Context.MODE_PRIVATE)
            val action = bootPrefs.getString(BootReceiver.KEY_LAST_BOOT_ACTION, "").orEmpty()
            val bootTs = bootPrefs.getLong(BootReceiver.KEY_LAST_BOOT_TS, 0L)
            val realBoot = action == Intent.ACTION_BOOT_COMPLETED ||
                action == "android.intent.action.QUICKBOOT_POWERON"
            val recent = bootTs > 0L && System.currentTimeMillis() - bootTs in 0L..60_000L
            val marker = voicePrefs.getLong("alice4_4_last_silent_prewarm_boot_ts", 0L)
            if (!realBoot || !recent || marker == bootTs) return@launch
            voicePrefs.edit().putLong("alice4_4_last_silent_prewarm_boot_ts", bootTs).apply()
            delay(5_000L)
            runCatching {
                val wake = Intent().setComponent(
                    ComponentName(
                        "com.yandex.browser",
                        "com.yandex.browser.speech.alice.wakeup.AliceRealmeWakeupService",
                    )
                )
                startService(wake)
                Log.i(TAG, "ALICE4_4_SILENT_PREWARM requested=true")
            }.onFailure {
                Log.w(TAG, "ALICE4_4_SILENT_PREWARM failed=${it.javaClass.simpleName}:${it.message}")
            }
        }
'''
new = '''        // Alice4.5: field test proved even the Yandex wakeup service is visible/audible.
        // Do not touch Yandex at boot. Only recover our Accessibility filter silently.
        Log.i(TAG, "ALICE4_5_BOOT_PREWARM_DISABLED")
'''
s = once(s, old, new, "disable Yandex boot prewarm")
p.write_text(s)


# ---------------------------------------------------------------------------
# 4) Steering/Alice state machine.
#    Field 4.4 sequence was deterministic after a cold boot:
#      cold mic #1 -> cold mic #2 -> exact Alice #1 -> exact Alice #2/listening.
#    Automate that sequence from ONE physical 304 press, but retain the fast
#    one-click exact path when Alice is already warm.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt")
s = p.read_text()

s = once(
    s,
    "    private var aliceCandidateDumped = false\n",
    "    private var aliceCandidateDumped = false\n"
    "    private var aliceColdClickCount = 0\n"
    "    private var aliceNextColdRetryElapsed = 0L\n"
    "    private var aliceColdSurfacePrimed = false\n"
    "    private var aliceSecondExactNotBeforeElapsed = 0L\n"
    "    private var lastStockAssistantBackElapsed = 0L\n"
    "    private var aliceDuckOriginalVolume: Int? = null\n"
    "    private var aliceDuckGeneration = 0\n",
    "Alice4.5 state fields",
)

# Longer cold budget: this head unit needed ~7 s just to create Chromium's cold
# process, then several more seconds for BroAliceActivity.
s = once(s, "        private const val ALICE_CLICK_RETRY_MS = 180L\n", "        private const val ALICE_CLICK_RETRY_MS = 200L\n", "retry interval")
s = once(s, "        private const val ALICE_MAX_CLICK_ATTEMPTS = 36\n", "        private const val ALICE_MAX_CLICK_ATTEMPTS = 80\n", "retry attempts")

# Reset all cold phases on each new Browser launch/arm.
s = once(
    s,
    '''        aliceColdEntryClicked = false
        aliceCandidateDumped = false
        val generation = ++aliceClickGeneration
''',
    '''        aliceColdEntryClicked = false
        aliceCandidateDumped = false
        aliceColdClickCount = 0
        aliceNextColdRetryElapsed = 0L
        aliceColdSurfacePrimed = false
        aliceSecondExactNotBeforeElapsed = 0L
        val generation = ++aliceClickGeneration
''',
    "arm staged-state reset",
)

# Replace the whole matcher. This intentionally does NOT call the cold control
# in a tight loop: a second cold click is allowed only after a settle delay.
start = s.find("    private fun tryClickAliceNode(source: String): Boolean {")
end = s.find("    private fun dumpYandexVoiceCandidates(", start)
if start < 0 or end < 0:
    raise SystemExit("Alice4.5 tryClickAliceNode anchors missing")
new_try = r'''    private fun tryClickAliceNode(source: String): Boolean {
        if (!aliceClickPending) return false
        val roots = yandexBrowserRoots()
        if (roots.isEmpty()) return false
        val now = android.os.SystemClock.elapsedRealtime()

        // Warm path: a ready Alice surface needs exactly one click.
        // Cold path: field logs proved the first exact-Alice click only primes the
        // surface; wait for UI settle, then click the exact control once more.
        for (root in roots) {
            val exact = runCatching {
                root.findAccessibilityNodeInfosByViewId(ALICE_EXACT_VIEW_ID)
            }.getOrNull().orEmpty()
            for (node in exact) {
                if (!aliceColdEntryClicked) {
                    if (clickAliceCandidate(node, "exact_alice_warm", source, terminal = true)) {
                        Log.i(TAG, "ALICE4_5_LISTENING_ACTIVATE cold=false")
                        return true
                    }
                } else if (!aliceColdSurfacePrimed) {
                    if (clickAliceCandidate(node, "exact_alice_stage1", source, terminal = false)) {
                        aliceColdSurfacePrimed = true
                        aliceSecondExactNotBeforeElapsed = now + 1600L
                        val generation = aliceClickGeneration
                        Log.i(TAG, "ALICE4_5_COLD_SURFACE_PRIMED delayMs=1600")
                        aliceHandler.postDelayed({
                            if (aliceClickPending && generation == aliceClickGeneration) {
                                tryClickAliceNode("cold_exact_stage2")
                            }
                        }, 1650L)
                        return false
                    }
                } else if (now >= aliceSecondExactNotBeforeElapsed) {
                    if (clickAliceCandidate(node, "exact_alice_stage2", source, terminal = true)) {
                        Log.i(TAG, "ALICE4_5_LISTENING_ACTIVATE cold=true coldClicks=$aliceColdClickCount")
                        return true
                    }
                }
            }
        }

        // Description fallback follows exactly the same warm/cold staging rule.
        for (root in roots) {
            val queue = ArrayDeque<AccessibilityNodeInfo>()
            queue.add(root)
            var visited = 0
            while (queue.isNotEmpty() && visited < ALICE_NODE_SCAN_LIMIT) {
                val node = queue.removeFirst()
                visited++
                val desc = node.contentDescription?.toString()?.trim()?.lowercase(Locale.ROOT).orEmpty()
                if (desc == "голосовой помощник" || desc == "voice assistant") {
                    if (!aliceColdEntryClicked) {
                        if (clickAliceCandidate(node, "alice_description_warm", source, terminal = true)) {
                            Log.i(TAG, "ALICE4_5_LISTENING_ACTIVATE desc=true cold=false")
                            return true
                        }
                    } else if (!aliceColdSurfacePrimed) {
                        if (clickAliceCandidate(node, "alice_description_stage1", source, terminal = false)) {
                            aliceColdSurfacePrimed = true
                            aliceSecondExactNotBeforeElapsed = now + 1600L
                            val generation = aliceClickGeneration
                            Log.i(TAG, "ALICE4_5_COLD_SURFACE_PRIMED desc=true delayMs=1600")
                            aliceHandler.postDelayed({
                                if (aliceClickPending && generation == aliceClickGeneration) {
                                    tryClickAliceNode("cold_desc_stage2")
                                }
                            }, 1650L)
                            return false
                        }
                    } else if (now >= aliceSecondExactNotBeforeElapsed) {
                        if (clickAliceCandidate(node, "alice_description_stage2", source, terminal = true)) {
                            Log.i(TAG, "ALICE4_5_LISTENING_ACTIVATE desc=true cold=true coldClicks=$aliceColdClickCount")
                            return true
                        }
                    }
                }
                for (i in 0 until node.childCount) {
                    runCatching { node.getChild(i) }.getOrNull()?.let(queue::addLast)
                }
            }
        }

        // Cold Browser entry. On this Yandex/DiLink build the first cold click did
        // not expose alice_input_quarknyx; the second physical press clicked this
        // same control again and only then Alice appeared. Reproduce that one time.
        if (!aliceColdSurfacePrimed && aliceColdClickCount < 2) {
            val coldAllowed = aliceColdClickCount == 0 || now >= aliceNextColdRetryElapsed
            if (coldAllowed) {
                for (root in roots) {
                    for (coldId in listOf(ALICE_COLD_CURRENT_VIEW_ID, ALICE_COLD_VIEW_ID)) {
                        val nodes = runCatching { root.findAccessibilityNodeInfosByViewId(coldId) }
                            .getOrNull().orEmpty()
                        for (node in nodes) {
                            if (clickAliceCandidate(node, "cold_exact_id", source, terminal = false)) {
                                aliceColdClickCount++
                                aliceColdEntryClicked = true
                                aliceNextColdRetryElapsed = android.os.SystemClock.elapsedRealtime() + 1800L
                                Log.i(
                                    TAG,
                                    "ALICE4_5_COLD_ENTRY_CLICK count=$aliceColdClickCount id=${node.viewIdResourceName ?: "-"} desc=${node.contentDescription ?: "-"}"
                                )
                                return false
                            }
                        }
                    }
                }

                // Family/description fallback for Yandex versions that rename the exact ID.
                for (root in roots) {
                    val queue = ArrayDeque<AccessibilityNodeInfo>()
                    queue.add(root)
                    var visited = 0
                    while (queue.isNotEmpty() && visited < ALICE_NODE_SCAN_LIMIT) {
                        val node = queue.removeFirst()
                        visited++
                        val id = node.viewIdResourceName?.lowercase(Locale.ROOT).orEmpty()
                        val desc = node.contentDescription?.toString()?.trim()?.lowercase(Locale.ROOT).orEmpty()
                        val coldId = id == ALICE_COLD_VIEW_ID.lowercase(Locale.ROOT) ||
                            id == ALICE_COLD_CURRENT_VIEW_ID.lowercase(Locale.ROOT) ||
                            id.contains("bro_omnibox_button_microphone") ||
                            id.endsWith("bro_omnibox_button_mic")
                        val coldDesc = desc == "активировать голосовой поиск" ||
                            desc == "голосовой поиск" ||
                            desc == "activate voice search" ||
                            desc == "voice search"
                        if (coldId || coldDesc) {
                            if (clickAliceCandidate(node, "cold_voice_entry", source, terminal = false)) {
                                aliceColdClickCount++
                                aliceColdEntryClicked = true
                                aliceNextColdRetryElapsed = android.os.SystemClock.elapsedRealtime() + 1800L
                                Log.i(TAG, "ALICE4_5_COLD_ENTRY_CLICK count=$aliceColdClickCount fallback=true")
                                return false
                            }
                        }
                        for (i in 0 until node.childCount) {
                            runCatching { node.getChild(i) }.getOrNull()?.let(queue::addLast)
                        }
                    }
                }
            }
        }

        if (!aliceCandidateDumped && aliceClickAttempt >= 3) {
            aliceCandidateDumped = true
            dumpYandexVoiceCandidates(roots, source)
        }

        Log.d(
            TAG,
            "ALICE4_5_ENTRY_WAIT source=$source coldClicks=$aliceColdClickCount " +
                "primed=$aliceColdSurfacePrimed attempt=$aliceClickAttempt"
        )
        return false
    }

'''
s = s[:start] + new_try + s[end:]

# Reset staged state when pending handoff is cancelled.
s = once(
    s,
    '''        aliceColdEntryClicked = false
        aliceCandidateDumped = false
        aliceClickGeneration++
''',
    '''        aliceColdEntryClicked = false
        aliceCandidateDumped = false
        aliceColdClickCount = 0
        aliceNextColdRetryElapsed = 0L
        aliceColdSurfacePrimed = false
        aliceSecondExactNotBeforeElapsed = 0L
        aliceClickGeneration++
''',
    "cancel staged-state reset",
)

# Music duck belongs to the external Alice route, not BYDMate's local AudioCapture.
# Keep the very first volume as the restore point; repeated presses only extend the timer.
entry_anchor = "    private fun entryPoint(): ClusterEntryPoint =\n"
duck_helper = r'''    private fun duckMusicForAlice(durationMs: Long = 12_000L) {
        val audio = getSystemService(Context.AUDIO_SERVICE) as android.media.AudioManager
        val current = runCatching {
            audio.getStreamVolume(android.media.AudioManager.STREAM_MUSIC)
        }.getOrDefault(0)
        if (aliceDuckOriginalVolume == null) aliceDuckOriginalVolume = current
        val target = if (current <= 1) current else 1
        if (current > target) {
            runCatching {
                audio.setStreamVolume(android.media.AudioManager.STREAM_MUSIC, target, 0)
            }.onFailure {
                Log.w(TAG, "ALICE4_5_DUCK_FAILED ${it.javaClass.simpleName}:${it.message}")
            }
        }
        val generation = ++aliceDuckGeneration
        Log.i(TAG, "ALICE4_5_DUCK from=$current target=$target restoreMs=$durationMs")
        aliceHandler.postDelayed({
            if (generation != aliceDuckGeneration) return@postDelayed
            val original = aliceDuckOriginalVolume ?: return@postDelayed
            runCatching {
                audio.setStreamVolume(android.media.AudioManager.STREAM_MUSIC, original, 0)
            }.onSuccess {
                Log.i(TAG, "ALICE4_5_DUCK_RESTORE volume=$original")
            }.onFailure {
                Log.w(TAG, "ALICE4_5_DUCK_RESTORE_FAILED ${it.javaClass.simpleName}:${it.message}")
            }
            aliceDuckOriginalVolume = null
        }, durationMs)
    }

'''
if entry_anchor not in s:
    raise SystemExit("Alice4.5 entryPoint anchor missing")
s = s.replace(entry_anchor, duck_helper + entry_anchor, 1)

# Duck only on a real 304 DOWN that is owned by Alice. 327 remains consumed before
# any downstream firmware routing exactly as in 4.4.
s = once(
    s,
    '''            if (isDown && event.repeatCount == 0) {
                Log.i(TAG, "DILINK3_304_TRIGGER")
                aliceBootPrewarm = false
                launchYandexAliceOrApkPure()
            }
''',
    '''            if (isDown && event.repeatCount == 0) {
                Log.i(TAG, "DILINK3_304_TRIGGER")
                aliceBootPrewarm = false
                duckMusicForAlice()
                launchYandexAliceOrApkPure()
            }
''',
    "duck on 304",
)

# Build95 had a second line of defence: if the BYD system app manages to start
# anyway, close its transient window immediately while takeover is ON.
start = s.find("    override fun onAccessibilityEvent(event: AccessibilityEvent?) {")
end = s.find("    override fun onInterrupt()", start)
if start < 0 or end < 0:
    raise SystemExit("Alice4.5 accessibility event anchors missing")
new_event = r'''    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        NavA11yFeed.onEvent(this, event)
        if (event == null) return

        val takeover = applicationContext
            .getSharedPreferences("voice", Context.MODE_PRIVATE)
            .getBoolean("alice_native_takeover", false)
        if (takeover && event.packageName?.toString() == "com.byd.vrassistant") {
            val now = android.os.SystemClock.elapsedRealtime()
            if (now - lastStockAssistantBackElapsed >= 700L) {
                lastStockAssistantBackElapsed = now
                val closed = performGlobalAction(GLOBAL_ACTION_BACK)
                Log.w(
                    TAG,
                    "ALICE4_5_STOCK_ASSISTANT_BACK eventType=${event.eventType} result=$closed"
                )
            }
            return
        }

        if (aliceClickPending && event.packageName?.toString() == YANDEX_BROWSER_PACKAGE) {
            if (!yandexWindowLogged) {
                yandexWindowLogged = true
                Log.i(TAG, "YANDEX_WINDOW_DETECTED eventType=${event.eventType}")
            }
            tryClickAliceNode("event:${event.eventType}")
        }
    }

'''
s = s[:start] + new_event + s[end:]

p.write_text(s)
print("Alice4.5 applied: Build95 stock guard + vrassistant disable + one-press cold handoff + music duck + no boot warmup")
