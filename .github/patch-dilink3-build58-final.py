from pathlib import Path
import re

# Build58 final patch: Russian GigaAM independent of UI locale + compact debug overlay.

# 1) Force GigaAM recognition/NLU to Russian, regardless of app locale.
p = Path('app/src/main/kotlin/com/bydmate/app/voice/VoiceController.kt')
s = p.read_text()
lang_anchor = '''    fun currentLang(): VoiceLang =
        gate.preferredLang()
            ?: if ((localePreferences.getLanguage() ?: "ru") == "en") VoiceLang.EN else VoiceLang.RU
'''
if lang_anchor not in s:
    raise SystemExit('Build58 currentLang anchor not found')
s = s.replace(lang_anchor, lang_anchor + '''
    // GigaAM v3 used here is the Russian Nemo-CTC model. UI locale is presentation only.
    private fun gigaAmRecognitionLang(): VoiceLang = VoiceLang.RU
''', 1)

old = '        if (continuousAsr.isReady() && currentLang() == VoiceLang.RU) {\n            startContinuousSession()\n'
new = '''        if (continuousAsr.isReady()) {
            Log.i(TAG, "BUILD58_GIGAAM_FORCED_RU uiLang=${currentLang()} recognitionLang=${gigaAmRecognitionLang()}")
            startContinuousSession()
'''
if old not in s:
    raise SystemExit('Build58 PTT language gate anchor not found')
s = s.replace(old, new, 1)

old = '''            // Two distinct causes share this branch (#87): the GigaAM model genuinely
            // missing vs. a non-RU voice language (GigaAM is Russian-only) — the old
            // single "model not loaded" text sent EN-locale users chasing a phantom
            // download problem.
            val langBlocked = continuousAsr.isReady() && currentLang() != VoiceLang.RU
            val msg = context.getString(
                if (langBlocked) R.string.voice_error_lang_not_ru
                else R.string.voice_error_model_missing
            )
'''
new = '''            // Build58: UI locale never blocks GigaAM; this branch means model/VAD is not ready.
            val msg = context.getString(R.string.voice_error_model_missing)
'''
if old not in s:
    raise SystemExit('Build58 PTT error branch anchor not found')
s = s.replace(old, new, 1)

old = '                "GigaAM ${if (langBlocked) "lang not supported" else "model not ready"} lang=${currentLang()}"\n'
new = '                "GigaAM model not ready; uiLang=${currentLang()} recognitionLang=${gigaAmRecognitionLang()}"\n'
if old not in s:
    raise SystemExit('Build58 PTT log anchor not found')
s = s.replace(old, new, 1)

old = '        val res = if (followUp) null else resolve(command, currentLang())\n'
new = '        val res = if (followUp) null else resolve(command, gigaAmRecognitionLang())\n'
if old not in s:
    raise SystemExit('Build58 NLU language anchor not found')
s = s.replace(old, new, 1)
p.write_text(s)

# 2) Show recognition language explicitly in Settings.
p = Path('app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt')
s = p.read_text()
anchor = '            val gigaAmDownloading = state.gigaAmDownloadProgress >= 0\n'
if anchor not in s:
    raise SystemExit('Build58 settings GigaAM anchor not found')
s = s.replace(anchor, '''            Text(
                "Voice recognition: Русский - GigaAM",
                color = TextSecondary,
                fontSize = 12.sp,
                modifier = Modifier.padding(vertical = 6.dp),
            )
            val gigaAmDownloading = state.gigaAmDownloadProgress >= 0
''', 1)
p.write_text(s)

# 3) Replace Build57's outer collapse with one Build58 collapse and reuse the wizard close state.
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()
if 'import android.view.WindowManager\n' not in s:
    s = s.replace('import android.view.InputDevice\n', 'import android.view.InputDevice\nimport android.view.WindowManager\n', 1)
if 'import androidx.compose.ui.platform.LocalView\n' not in s:
    s = s.replace('import androidx.compose.ui.platform.LocalContext\n', 'import androidx.compose.ui.platform.LocalContext\nimport androidx.compose.ui.platform.LocalView\n', 1)

# Remove Build57 outer collapsed block regardless of header text inserted into its Card.
pat = re.compile(
    r'    var build57PanelExpanded by remember \{ mutableStateOf\(true\) \}\n'
    r'    if \(!build57PanelExpanded\) \{.*?\n        return\n    \}\n',
    re.S,
)
s, n = pat.subn('', s, count=1)
if n != 1:
    raise SystemExit(f'Build58 could not remove Build57 collapse block: matches={n}')

scope_anchor = '    val scope = rememberCoroutineScope()\n'
if scope_anchor not in s:
    raise SystemExit('Build58 panel scope anchor not found')
insert = '''    val scope = rememberCoroutineScope()
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
s = s.replace(scope_anchor, insert, 1)

old_decl = '    var expanded by remember { mutableStateOf(false) }\n'
if old_decl not in s:
    raise SystemExit('Build58 wizard expanded declaration not found')
s = s.replace(old_decl, '', 1)
s = s.replace('expanded =', 'build58PanelExpanded =')
s = s.replace('if (!expanded) {', 'if (!build58PanelExpanded) {')
s = s.replace('Text("DiLink3 диагностика · шаг $step/5"', 'Text("DiLink3 Build58 · диагностика · шаг $step/5"', 1)
p.write_text(s)

print('Build58 final patch installed')
