from pathlib import Path

# Build58 field follow-up:
# - GigaAM is a Russian ASR model, so recognition/routing must stay RU regardless of UI locale.
# - make the DiLink3 debug panel collapse to a tiny DBG overlay and shrink the actual
#   WindowManager window, so the collapsed diagnostic overlay cannot cover/block other apps.
# - keep Build57 GigaAM resume/reliability, Build56 304 routing and Build49 327 blocker unchanged.

# ---------------------------------------------------------------------------
# 1) VoiceController: decouple the Russian GigaAM recognition language from UI language.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/voice/VoiceController.kt')
s = p.read_text()

lang_anchor = '''    fun currentLang(): VoiceLang =
        gate.preferredLang()
            ?: if ((localePreferences.getLanguage() ?: "ru") == "en") VoiceLang.EN else VoiceLang.RU
'''
if lang_anchor not in s:
    raise SystemExit('Build58 currentLang anchor not found')
if 'fun gigaAmRecognitionLang()' not in s:
    s = s.replace(
        lang_anchor,
        lang_anchor + '''
    // GigaAM v3 bundled/downloaded by BYDMate is the Russian Nemo-CTC model. UI language is
    // presentation only and must never disable PTT or switch the NLU parser away from Russian.
    private fun gigaAmRecognitionLang(): VoiceLang = VoiceLang.RU
''',
        1,
    )

old_ready = '        if (continuousAsr.isReady() && currentLang() == VoiceLang.RU) {\n            startContinuousSession()\n'
new_ready = '''        if (continuousAsr.isReady()) {
            Log.i(TAG, "BUILD58_GIGAAM_FORCED_RU uiLang=${currentLang()} recognitionLang=${gigaAmRecognitionLang()}")
            startContinuousSession()
'''
if old_ready not in s:
    raise SystemExit('Build58 PTT language gate anchor not found')
s = s.replace(old_ready, new_ready, 1)

old_error = '''            // Two distinct causes share this branch (#87): the GigaAM model genuinely
            // missing vs. a non-RU voice language (GigaAM is Russian-only) — the old
            // single "model not loaded" text sent EN-locale users chasing a phantom
            // download problem.
            val langBlocked = continuousAsr.isReady() && currentLang() != VoiceLang.RU
            val msg = context.getString(
                if (langBlocked) R.string.voice_error_lang_not_ru
                else R.string.voice_error_model_missing
            )
'''
new_error = '''            // Build58: UI locale no longer blocks GigaAM. Reaching this branch means the
            // Russian local model/VAD is genuinely not ready.
            val msg = context.getString(R.string.voice_error_model_missing)
'''
if old_error not in s:
    raise SystemExit('Build58 PTT langBlocked block anchor not found')
s = s.replace(old_error, new_error, 1)

old_log = '                "GigaAM ${if (langBlocked) "lang not supported" else "model not ready"} lang=${currentLang()}"\n'
new_log = '                "GigaAM model not ready; uiLang=${currentLang()} recognitionLang=${gigaAmRecognitionLang()}"\n'
if old_log not in s:
    raise SystemExit('Build58 PTT error log anchor not found')
s = s.replace(old_log, new_log, 1)

old_resolve = '        val res = if (followUp) null else resolve(command, currentLang())\n'
new_resolve = '        val res = if (followUp) null else resolve(command, gigaAmRecognitionLang())\n'
if old_resolve not in s:
    raise SystemExit('Build58 GigaAM NLU language anchor not found')
s = s.replace(old_resolve, new_resolve, 1)

# Keep the KDoc truthful for future maintenance.
s = s.replace(
    '''    /** PTT toggle (Wave B): no session running -> start one (continuous GigaAM session when the
     *  model is ready and the language is RU, else the GigaAM model is missing or the language is
     *  non-RU (GigaAM does not support it) -> report the specific cause without starting a
     *  session (#87): "model missing" when GigaAM isn't downloaded, "language not RU" when it
     *  is; a continuous session already listening -> stop it immediately (barge-in stops TTS
     *  too). */''',
    '''    /** PTT toggle (Wave B): no session running -> start the continuous Russian GigaAM
     *  session whenever its model is ready. The application/UI locale is intentionally unrelated
     *  to recognition language. A running session -> stop immediately (barge-in stops TTS too). */''',
    1,
)
p.write_text(s)

# ---------------------------------------------------------------------------
# 2) Settings: make the recognition language explicit to the user.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt')
s = p.read_text()
settings_anchor = '            val gigaAmDownloading = state.gigaAmDownloadProgress >= 0\n'
if settings_anchor not in s:
    raise SystemExit('Build58 GigaAM Settings anchor not found')
if 'Voice recognition: Русский - GigaAM' not in s:
    s = s.replace(
        settings_anchor,
        '''            Text(
                "Voice recognition: Русский - GigaAM",
                color = TextSecondary,
                fontSize = 12.sp,
                modifier = Modifier.padding(vertical = 6.dp),
            )
            val gigaAmDownloading = state.gigaAmDownloadProgress >= 0
''',
        1,
    )
p.write_text(s)

# ---------------------------------------------------------------------------
# 3) DiLink3 debug overlay: consolidate the older two-level Compose collapse into one
# Build58 control and resize the real WindowManager overlay while collapsed.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()

import_anchor = 'import android.view.InputDevice\n'
if import_anchor not in s:
    raise SystemExit('Build58 panel InputDevice import anchor not found')
if 'import android.view.WindowManager\n' not in s:
    s = s.replace(import_anchor, import_anchor + 'import android.view.WindowManager\n', 1)

local_context_anchor = 'import androidx.compose.ui.platform.LocalContext\n'
if local_context_anchor not in s:
    raise SystemExit('Build58 LocalContext import anchor not found')
if 'import androidx.compose.ui.platform.LocalView\n' not in s:
    s = s.replace(local_context_anchor, local_context_anchor + 'import androidx.compose.ui.platform.LocalView\n', 1)

# Build57 injected its own build57PanelExpanded block immediately after rememberCoroutineScope,
# while the generated wizard already had a separate `expanded` collapsed state. The exact body
# changed as later patches inserted a header into the first Card, so replace the entire region
# up to the stable prefs anchor instead of matching fragile whitespace/body text.
collapse_start_anchor = '    val scope = rememberCoroutineScope()\n'
collapse_end_anchor = '    val prefs = remember { context.getSharedPreferences("voice", Context.MODE_PRIVATE) }\n'
if collapse_start_anchor not in s:
    raise SystemExit('Build58 panel scope anchor not found')
if collapse_end_anchor not in s:
    raise SystemExit('Build58 panel prefs anchor not found')
start = s.index(collapse_start_anchor)
end = s.index(collapse_end_anchor, start)

new_block = '''    val scope = rememberCoroutineScope()
    val build58HostView = LocalView.current
    val build58WindowManager = remember {
        context.getSystemService(Context.WINDOW_SERVICE) as WindowManager
    }
    val build58Density = context.resources.displayMetrics.density
    var build58PanelExpanded by remember { mutableStateOf(false) }
    var build58OriginalWindow by remember { mutableStateOf<IntArray?>(null) }

    @Suppress("DEPRECATION")
    fun build58ResizeDebugWindow(collapsed: Boolean) {
        val root = build58HostView.rootView
        val lp = root.layoutParams as? WindowManager.LayoutParams ?: run {
            DiLink3DebugLog.log(
                context,
                "BUILD58_DEBUG_WINDOW_RESIZE",
                "skipped=no_window_layout_params collapsed=$collapsed"
            )
            return
        }
        val isOverlay =
            lp.type == WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY ||
                lp.type == WindowManager.LayoutParams.TYPE_PHONE ||
                lp.type == WindowManager.LayoutParams.TYPE_SYSTEM_ALERT
        if (!isOverlay) {
            // Safety: never resize MainActivity's TYPE_BASE_APPLICATION decor window.
            DiLink3DebugLog.log(
                context,
                "BUILD58_DEBUG_WINDOW_RESIZE",
                "skipped=not_overlay type=${lp.type} collapsed=$collapsed"
            )
            return
        }
        if (build58OriginalWindow == null) {
            build58OriginalWindow = intArrayOf(lp.width, lp.height, lp.flags)
        }
        val original = build58OriginalWindow ?: return
        if (collapsed) {
            lp.width = (72f * build58Density).toInt().coerceAtLeast(1)
            lp.height = (52f * build58Density).toInt().coerceAtLeast(1)
            lp.flags = original[2] or
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL
        } else {
            lp.width = original[0]
            lp.height = original[1]
            lp.flags = original[2]
        }
        runCatching { build58WindowManager.updateViewLayout(root, lp) }
            .onSuccess {
                DiLink3DebugLog.log(
                    context,
                    "BUILD58_DEBUG_WINDOW_RESIZE",
                    "success=true collapsed=$collapsed width=${lp.width} height=${lp.height} type=${lp.type} flags=${lp.flags}"
                )
            }
            .onFailure {
                DiLink3DebugLog.log(
                    context,
                    "BUILD58_DEBUG_WINDOW_RESIZE",
                    "success=false collapsed=$collapsed error=${it::class.java.simpleName}:${it.message}"
                )
            }
    }

    LaunchedEffect(build58PanelExpanded) {
        build58ResizeDebugWindow(collapsed = !build58PanelExpanded)
    }

    if (!build58PanelExpanded) {
        Card(modifier = modifier.fillMaxWidth()) {
            Button(
                onClick = {
                    build58PanelExpanded = true
                    DiLink3DebugLog.log(context, "BUILD58_DEBUG_PANEL", "action=expand")
                },
                modifier = Modifier.fillMaxWidth().padding(2.dp),
            ) { Text("DBG") }
        }
        return
    }

    Row(
        modifier = modifier.fillMaxWidth().padding(8.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text("DiLink3 Build58", modifier = Modifier.weight(1f))
        Button(onClick = {
            build58PanelExpanded = false
            DiLink3DebugLog.log(context, "BUILD58_DEBUG_PANEL", "action=collapse")
        }) { Text("CLOSE") }
    }

'''
s = s[:start] + new_block + s[end:]
p.write_text(s)
print('Build58 installed: GigaAM forced-RU recognition + real DBG WindowManager collapse')
