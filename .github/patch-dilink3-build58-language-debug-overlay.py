from pathlib import Path

# Build58 field follow-up:
# - GigaAM is the Russian ASR model, so recognition/routing stays RU regardless of UI locale.
# - collapse the DiLink3 debug panel to one tiny DBG control and, when it is hosted by a
#   WindowManager overlay, shrink the real overlay window so it cannot cover other apps.
# - preserve Build57 download/resume reliability, Build56 304 routing and Build49 327 blocker.

# ---------------------------------------------------------------------------
# 1) VoiceController: decouple Russian GigaAM recognition from UI language.
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
    // The downloadable GigaAM v3 asset is the Russian Nemo-CTC model. Application locale is
    // presentation only and must not disable PTT or switch GigaAM NLU away from Russian.
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
# 2) Settings: state the recognition language explicitly.
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
# 3) DiLink3 debug panel. Build57 added an outer collapse around the wizard, while the wizard
# already had its own `expanded` state. Consolidate both onto one Build58 state. Re-use the
# wizard's existing close button by retargeting `expanded` -> `build58PanelExpanded`.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()
if 'import android.view.WindowManager\n' not in s:
    s = s.replace('import android.view.InputDevice\n', 'import android.view.InputDevice\nimport android.view.WindowManager\n', 1)
if 'import androidx.compose.ui.platform.LocalView\n' not in s:
    s = s.replace('import androidx.compose.ui.platform.LocalContext\n', 'import androidx.compose.ui.platform.LocalContext\nimport androidx.compose.ui.platform.LocalView\n', 1)

start_anchor = '    val scope = rememberCoroutineScope()\n'
end_anchor = '    val voicePrefs = remember { context.getSharedPreferences("voice", Context.MODE_PRIVATE) }\n'
if start_anchor not in s:
    raise SystemExit('Build58 panel scope anchor not found')
if end_anchor not in s:
    raise SystemExit('Build58 panel voicePrefs anchor not found')
start = s.index(start_anchor)
end = s.index(end_anchor, start)
new_scope = '''    val scope = rememberCoroutineScope()
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
            DiLink3DebugLog.log(context, "BUILD58_DEBUG_WINDOW_RESIZE", "skipped=no_window_layout_params collapsed=$collapsed")
            return
        }
        val isOverlay =
            lp.type == WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY ||
                lp.type == WindowManager.LayoutParams.TYPE_PHONE ||
                lp.type == WindowManager.LayoutParams.TYPE_SYSTEM_ALERT
        if (!isOverlay) {
            // Safety: never resize MainActivity's normal application window.
            DiLink3DebugLog.log(context, "BUILD58_DEBUG_WINDOW_RESIZE", "skipped=not_overlay type=${lp.type} collapsed=$collapsed")
            return
        }
        if (build58OriginalWindow == null) {
            build58OriginalWindow = intArrayOf(lp.width, lp.height, lp.flags)
        }
        val original = build58OriginalWindow ?: return
        if (collapsed) {
            lp.width = (72f * build58Density).toInt().coerceAtLeast(1)
            lp.height = (52f * build58Density).toInt().coerceAtLeast(1)
            lp.flags = original[2] or WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL
        } else {
            lp.width = original[0]
            lp.height = original[1]
            lp.flags = original[2]
        }
        runCatching { build58WindowManager.updateViewLayout(root, lp) }
            .onSuccess {
                DiLink3DebugLog.log(context, "BUILD58_DEBUG_WINDOW_RESIZE", "success=true collapsed=$collapsed width=${lp.width} height=${lp.height} type=${lp.type} flags=${lp.flags}")
            }
            .onFailure {
                DiLink3DebugLog.log(context, "BUILD58_DEBUG_WINDOW_RESIZE", "success=false collapsed=$collapsed error=${it::class.java.simpleName}:${it.message}")
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

'''
s = s[:start] + new_scope + s[end:]

old_decl = '    var expanded by remember { mutableStateOf(false) }\n'
if old_decl not in s:
    raise SystemExit('Build58 wizard expanded declaration not found')
s = s.replace(old_decl, '', 1)
s = s.replace('expanded =', 'build58PanelExpanded =')
s = s.replace('if (!expanded) {', 'if (!build58PanelExpanded) {')
s = s.replace('Text("DiLink3 диагностика · шаг $step/5"', 'Text("DiLink3 Build58 · диагностика · шаг $step/5"', 1)

p.write_text(s)
print('Build58 installed: GigaAM forced-RU recognition + consolidated DBG WindowManager collapse')
