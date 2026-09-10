#!/usr/bin/env python3
from pathlib import Path

VERSION_CODE = "60036"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Build86 anchor missing: {label}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# 1) Monotonic field identity over frozen Build85.
# ---------------------------------------------------------------------------
p = Path("app/build.gradle.kts")
s = p.read_text()
s = replace_once(s, "        versionCode = 60035", f"        versionCode = {VERSION_CODE}", "versionCode")
s = replace_once(
    s,
    '            versionNameSuffix = "-dilink3-production-build85"',
    '            versionNameSuffix = "-dilink3-production-build86"',
    "versionNameSuffix",
)
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = replace_once(
    s,
    'android:label="BYDMate DiLink3 Build85"',
    'android:label="BYDMate DiLink3 Build86"',
    "manifest label",
)
p.write_text(s)


# ---------------------------------------------------------------------------
# 2) Assistant Lab implementation. This is deliberately isolated from the frozen Build85
#    voice pipeline. It only becomes active when the user opens/arms the lab.
# ---------------------------------------------------------------------------
lab = r'''package com.bydmate.app.assistantlab

import android.Manifest
import android.app.AppOpsManager
import android.app.usage.UsageStatsManager
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.view.Gravity
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.view.accessibility.AccessibilityEvent
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.core.content.ContextCompat
import com.bydmate.app.BuildConfig
import com.bydmate.app.cluster.SteeringWheelKeyService
import com.bydmate.app.data.camera.CameraStateMonitor
import java.io.File
import java.text.SimpleDateFormat
import java.util.ArrayDeque
import java.util.Date
import java.util.Locale
import kotlin.concurrent.thread

/**
 * Build86 field laboratory for external voice assistants.
 *
 * It does NOT alter the Build85 BYDMate voice path unless the user explicitly arms a one-shot
 * external-assistant steering test from the floating window. Structured trace survives the
 * external app coming to foreground and is also persisted/copyable after Stop.
 */
object AssistantLabTrace {
    private const val MAX_LINES = 700
    private const val MIC_KEYCODE = 304
    private val lock = Any()
    private val lines = ArrayDeque<String>()
    private val clock = SimpleDateFormat("HH:mm:ss.SSS", Locale.US)

    @Volatile var active: Boolean = false
        private set
    @Volatile private var armedTarget: AssistantTarget? = null
    @Volatile private var consume304UntilUp: Boolean = false
    @Volatile private var lastA11yFingerprint: String = ""
    @Volatile private var lastA11yAt: Long = 0L

    private var logcatProcess: Process? = null
    private var logcatThread: Thread? = null

    fun start(context: Context) {
        stopLogcat()
        synchronized(lock) { lines.clear() }
        active = true
        armedTarget = null
        consume304UntilUp = false
        add("TRACE START Build86")
        snapshotEnvironment(context.applicationContext)
        startLogcat(context.applicationContext)
    }

    fun stop(context: Context) {
        if (!active) return
        armedTarget = null
        consume304UntilUp = false
        add("TRACE STOP")
        active = false
        stopLogcat()
        persist(context.applicationContext)
    }

    fun clear() {
        synchronized(lock) { lines.clear() }
        if (active) add("trace buffer cleared")
    }

    fun snapshot(): String = synchronized(lock) { lines.joinToString("\n") }

    fun add(message: String) {
        if (!active && !message.startsWith("TRACE")) return
        val line = "${clock.format(Date())}  $message"
        synchronized(lock) {
            lines.addLast(line)
            while (lines.size > MAX_LINES) lines.removeFirst()
        }
    }

    fun armSteering(context: Context, target: AssistantTarget) {
        if (!active) start(context)
        armedTarget = target
        consume304UntilUp = false
        add("ARM next steering mic 304 -> ${target.title}")
    }

    /** Called at the very top of SteeringWheelKeyService.onKeyEvent(). */
    fun maybeHandleSteering(context: Context, event: KeyEvent): Boolean {
        if (!active || event.keyCode != MIC_KEYCODE) return false

        if (consume304UntilUp) {
            add("KEY external-route 304 action=${event.action} scan=${event.scanCode} repeat=${event.repeatCount} consumed")
            if (event.action == KeyEvent.ACTION_UP) consume304UntilUp = false
            return true
        }

        val target = armedTarget ?: return false
        if (event.action != KeyEvent.ACTION_DOWN || event.repeatCount != 0) return false

        armedTarget = null
        consume304UntilUp = true
        add("KEY 304 armed hit scan=${event.scanCode}; bypass BYDMate once -> ${target.title}")
        Handler(Looper.getMainLooper()).post {
            AssistantLabLauncher.launch(context.applicationContext, target, preferVoice = true)
        }
        return true
    }

    fun onKeyEvent(event: KeyEvent) {
        if (!active) return
        add("KEY keyCode=${event.keyCode} scan=${event.scanCode} action=${event.action} repeat=${event.repeatCount} source=${event.source}")
    }

    fun onAccessibilityEvent(event: AccessibilityEvent) {
        if (!active) return
        val pkg = event.packageName?.toString().orEmpty()
        val cls = event.className?.toString().orEmpty()
        val fingerprint = "${event.eventType}|$pkg|$cls"
        val now = System.currentTimeMillis()
        // Window/content changes can arrive dozens of times per second. Keep the trace readable
        // while still logging a repeated event again after one second.
        if (fingerprint == lastA11yFingerprint && now - lastA11yAt < 1_000L) return
        lastA11yFingerprint = fingerprint
        lastA11yAt = now
        add("A11Y type=${event.eventType} pkg=${pkg.ifBlank { "?" }} cls=${cls.ifBlank { "?" }}")
    }

    fun snapshotEnvironment(context: Context) {
        val pm = context.packageManager
        add("ENV sdk=${Build.VERSION.SDK_INT} release=${Build.VERSION.RELEASE} model=${Build.MANUFACTURER}/${Build.MODEL}")
        add("ENV bydmate=${BuildConfig.VERSION_NAME} pkg=${context.packageName}")
        add("ENV overlay=${Settings.canDrawOverlays(context)} recordAudio=${hasPermission(context, Manifest.permission.RECORD_AUDIO)} readLogs=${hasPermission(context, Manifest.permission.READ_LOGS)}")
        add("ENV a11yConnected=${SteeringWheelKeyService.isConnected}")
        listOf("assistant", "voice_interaction_service", "voice_recognition_service").forEach { key ->
            val value = runCatching { Settings.Secure.getString(context.contentResolver, key) }.getOrNull()
            add("SECURE $key=${value ?: "<null>"}")
        }
        listOf("com.google.android.gms", "com.android.vending", "com.google.android.googlequicksearchbox").forEach { pkg ->
            add("PKG $pkg=${if (packageInstalled(pm, pkg)) "present" else "missing"}")
        }
        AssistantTarget.entries.forEach { target ->
            val app = AssistantLabLauncher.resolveInstalled(context, target)
            add("TARGET ${target.title}=${app?.let { "${it.label} ${it.packageName} v${it.versionName}" } ?: "not installed"}")
            app?.let { AssistantLabLauncher.dumpPackage(context, it.packageName) }
        }
        logForeground(context, "snapshot")
    }

    fun logForeground(context: Context, reason: String) {
        val now = System.currentTimeMillis()
        val latest = runCatching {
            val usm = context.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
            CameraStateMonitor.latestResumed(usm, now - 15_000L, now + 1L)
        }.getOrNull()
        add("FOREGROUND[$reason]=${latest?.first ?: "unknown"}${latest?.second?.let { "/$it" } ?: ""}")
    }

    private fun hasPermission(context: Context, permission: String): Boolean =
        ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED

    private fun packageInstalled(pm: PackageManager, pkg: String): Boolean =
        runCatching { pm.getPackageInfo(pkg, 0) }.isSuccess

    private fun startLogcat(context: Context) {
        // On a normal Android app READ_LOGS is signature-only, but some DiLink images/helper grants
        // are more permissive. Try a narrow system log stream and record whether it actually works.
        runCatching {
            val process = ProcessBuilder(
                "logcat", "-v", "threadtime", "-T", "1",
                "ActivityTaskManager:I", "ActivityManager:I", "WindowManager:I",
                "VoiceInteractionManagerService:I", "AndroidRuntime:E", "*:S",
            ).redirectErrorStream(true).start()
            logcatProcess = process
            logcatThread = thread(name = "AssistantLab-logcat", isDaemon = true) {
                runCatching {
                    process.inputStream.bufferedReader().use { reader ->
                        while (active) {
                            val line = reader.readLine() ?: break
                            if (line.isNotBlank()) add("LOGCAT $line")
                        }
                    }
                }.onFailure { add("LOGCAT reader error: ${it.javaClass.simpleName}: ${it.message}") }
            }
            add("LOGCAT requested (system task/window/voice/crash tags)")
            Handler(Looper.getMainLooper()).postDelayed({
                if (active && logcatProcess === process) {
                    val exit = runCatching { process.exitValue() }.getOrNull()
                    if (exit != null) add("LOGCAT unavailable/exited code=$exit (structured trace still active)")
                }
            }, 1_200L)
        }.onFailure {
            add("LOGCAT unavailable: ${it.javaClass.simpleName}: ${it.message}; structured trace still active")
        }
    }

    private fun stopLogcat() {
        runCatching { logcatProcess?.destroy() }
        logcatProcess = null
        logcatThread = null
    }

    private fun persist(context: Context) {
        val text = snapshot()
        runCatching { File(context.filesDir, "assistant-lab-last.txt").writeText(text) }
        runCatching {
            context.getExternalFilesDir(null)?.let { dir ->
                File(dir, "assistant-lab-last.txt").writeText(text)
            }
        }
    }
}

enum class AssistantTarget(
    val title: String,
    val packageCandidates: List<String>,
    val labelNeedles: List<String>,
    val officialInstallUrl: String,
) {
    ALICE(
        "Alice",
        listOf("com.yandex.aliceapp"),
        listOf("алиса", "alice"),
        "https://alice.yandex.ru/",
    ),
    CHATGPT(
        "ChatGPT",
        listOf("com.openai.chatgpt"),
        listOf("chatgpt", "openai"),
        "https://chatgpt.com/download",
    ),
}

data class InstalledAssistant(
    val packageName: String,
    val label: String,
    val versionName: String,
)

object AssistantLabLauncher {
    fun resolveInstalled(context: Context, target: AssistantTarget): InstalledAssistant? {
        val pm = context.packageManager
        target.packageCandidates.forEach { pkg ->
            packageInfo(context, pkg)?.let { info ->
                val label = runCatching { pm.getApplicationLabel(info.applicationInfo).toString() }
                    .getOrDefault(target.title)
                return InstalledAssistant(pkg, label, info.versionName ?: "?")
            }
        }

        // Fallback by launcher label: useful if Yandex changes/repackages Alice on this market.
        val launcher = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        return runCatching { pm.queryIntentActivities(launcher, 0) }.getOrDefault(emptyList())
            .firstOrNull { ri ->
                val label = ri.loadLabel(pm)?.toString()?.lowercase(Locale.getDefault()).orEmpty()
                target.labelNeedles.any { label.contains(it) }
            }?.let { ri ->
                val pkg = ri.activityInfo.packageName
                val info = packageInfo(context, pkg)
                InstalledAssistant(pkg, ri.loadLabel(pm)?.toString() ?: target.title, info?.versionName ?: "?")
            }
    }

    fun isInstalled(context: Context, target: AssistantTarget): Boolean = resolveInstalled(context, target) != null

    fun launch(context: Context, target: AssistantTarget, preferVoice: Boolean) {
        if (!AssistantLabTrace.active) AssistantLabTrace.start(context)
        val app = resolveInstalled(context, target)
        if (app == null) {
            AssistantLabTrace.add("LAUNCH ${target.title}: not installed -> official install page")
            openOfficialInstall(context, target)
            return
        }

        AssistantLabTrace.add("LAUNCH target=${target.title} pkg=${app.packageName} label=${app.label} preferVoice=$preferVoice")
        dumpPackage(context, app.packageName)
        val pm = context.packageManager

        val candidates = if (preferVoice) listOf(Intent.ACTION_ASSIST, Intent.ACTION_VOICE_COMMAND) else emptyList()
        for (action in candidates) {
            val intent = Intent(action).setPackage(app.packageName).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            val matches = runCatching { pm.queryIntentActivities(intent, PackageManager.MATCH_DEFAULT_ONLY) }.getOrDefault(emptyList())
            AssistantLabTrace.add("PROBE action=$action pkg=${app.packageName} matches=${matches.size} ${matches.take(4).joinToString { it.activityInfo.name }}")
            val chosen = matches.firstOrNull { it.activityInfo.exported } ?: continue
            intent.component = android.content.ComponentName(chosen.activityInfo.packageName, chosen.activityInfo.name)
            if (start(context, intent, "voice:$action")) {
                scheduleForegroundChecks(context, target)
                return
            }
        }

        val launcher = pm.getLaunchIntentForPackage(app.packageName)?.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        AssistantLabTrace.add("PROBE launcher=${launcher?.component ?: "null"}")
        if (launcher != null && start(context, launcher, "launcher")) {
            scheduleForegroundChecks(context, target)
            return
        }
        AssistantLabTrace.add("LAUNCH ${target.title}: no working exported voice/launcher activity")
    }

    fun openOfficialInstall(context: Context, target: AssistantTarget) {
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(target.officialInstallUrl)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        start(context, intent, "official-install:${target.officialInstallUrl}")
    }

    fun dumpPackage(context: Context, pkg: String) {
        val pm = context.packageManager
        val info = runCatching {
            @Suppress("DEPRECATION")
            pm.getPackageInfo(pkg, PackageManager.GET_ACTIVITIES or PackageManager.GET_SERVICES or PackageManager.GET_PERMISSIONS)
        }.getOrElse {
            AssistantLabTrace.add("PKG-DUMP $pkg failed ${it.javaClass.simpleName}: ${it.message}")
            return
        }
        AssistantLabTrace.add("PKG-DUMP $pkg version=${info.versionName} activities=${info.activities?.size ?: 0} services=${info.services?.size ?: 0}")
        info.activities.orEmpty().filter { it.exported }.take(16).forEach {
            AssistantLabTrace.add("  activity exported=${it.name} perm=${it.permission ?: "-"}")
        }
        info.services.orEmpty().filter { it.exported || it.name.contains("voice", true) || it.name.contains("assist", true) }.take(16).forEach {
            AssistantLabTrace.add("  service exported=${it.exported} name=${it.name} perm=${it.permission ?: "-"}")
        }
    }

    private fun packageInfo(context: Context, pkg: String) = runCatching {
        @Suppress("DEPRECATION")
        context.packageManager.getPackageInfo(pkg, 0)
    }.getOrNull()

    private fun start(context: Context, intent: Intent, reason: String): Boolean = try {
        AssistantLabTrace.add("START[$reason] action=${intent.action} component=${intent.component} data=${intent.data}")
        context.startActivity(intent)
        AssistantLabTrace.add("START[$reason] returned OK")
        true
    } catch (t: Throwable) {
        AssistantLabTrace.add("START[$reason] FAILED ${t.javaClass.simpleName}: ${t.message}")
        false
    }

    private fun scheduleForegroundChecks(context: Context, target: AssistantTarget) {
        val h = Handler(Looper.getMainLooper())
        listOf(700L, 2_000L, 5_000L, 10_000L).forEach { delay ->
            h.postDelayed({
                if (AssistantLabTrace.active) AssistantLabTrace.logForeground(context, "${target.title}+${delay}ms")
            }, delay)
        }
    }
}

/** Floating, draggable Assistant Lab window that stays over Alice/ChatGPT. */
object AssistantLabOverlay {
    private var wm: WindowManager? = null
    private var root: LinearLayout? = null
    private var params: WindowManager.LayoutParams? = null
    private var expandedContent: LinearLayout? = null
    private var logView: TextView? = null
    private var statusView: TextView? = null
    private var aliceButton: Button? = null
    private var gptButton: Button? = null
    private var minimized = false
    private val handler = Handler(Looper.getMainLooper())
    private var appContext: Context? = null

    private val refreshRunnable = object : Runnable {
        override fun run() {
            refresh()
            if (root != null) handler.postDelayed(this, 700L)
        }
    }

    fun show(context: Context) {
        val ctx = context.applicationContext
        appContext = ctx
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(ctx)) {
            AssistantLabTrace.add("OVERLAY permission missing; opening settings")
            runCatching {
                ctx.startActivity(
                    Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:${ctx.packageName}"))
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                )
            }
            Toast.makeText(ctx, "Разреши BYDMate отображение поверх других окон и открой Assistant Lab ещё раз", Toast.LENGTH_LONG).show()
            return
        }
        if (root != null) {
            refresh()
            return
        }
        buildWindow(ctx)
    }

    fun hide() {
        val view = root ?: return
        runCatching { wm?.removeView(view) }
        root = null
        params = null
        expandedContent = null
        logView = null
        statusView = null
        aliceButton = null
        gptButton = null
        handler.removeCallbacks(refreshRunnable)
    }

    private fun buildWindow(context: Context) {
        val manager = context.getSystemService(Context.WINDOW_SERVICE) as WindowManager
        wm = manager
        val p = WindowManager.LayoutParams(
            dp(context, 900),
            dp(context, 690),
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
            else @Suppress("DEPRECATION") WindowManager.LayoutParams.TYPE_PHONE,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            android.graphics.PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = dp(context, 40)
            y = dp(context, 70)
        }
        params = p

        val outer = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(context, 12), dp(context, 10), dp(context, 12), dp(context, 10))
            background = GradientDrawable().apply {
                setColor(Color.argb(242, 10, 24, 38))
                cornerRadius = dp(context, 14).toFloat()
                setStroke(dp(context, 1), Color.rgb(54, 215, 157))
            }
        }
        root = outer

        val header = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        val title = TextView(context).apply {
            text = "Assistant Lab · Build86"
            setTextColor(Color.WHITE)
            textSize = 17f
            typeface = Typeface.DEFAULT_BOLD
        }
        header.addView(title, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        val min = smallButton(context, "—") { toggleSize(context) }
        val close = smallButton(context, "×") { hide() }
        header.addView(min)
        header.addView(close)
        outer.addView(header)
        installDrag(header)

        val content = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, dp(context, 8), 0, 0)
        }
        expandedContent = content

        val status = TextView(context).apply {
            setTextColor(Color.rgb(190, 205, 215))
            textSize = 13f
        }
        statusView = status
        content.addView(status)

        content.addView(buttonRow(context,
            actionButton(context, "START TRACE") {
                AssistantLabTrace.start(context)
                refresh()
            },
            actionButton(context, "STOP + SAVE") {
                AssistantLabTrace.stop(context)
                refresh()
            },
            actionButton(context, "COPY LOG") { copyLog(context) },
            actionButton(context, "CLEAR") { AssistantLabTrace.clear(); refresh() },
        ))

        val alice = actionButton(context, "Alice") { launchOrInstall(context, AssistantTarget.ALICE) }
        val gpt = actionButton(context, "ChatGPT") { launchOrInstall(context, AssistantTarget.CHATGPT) }
        aliceButton = alice
        gptButton = gpt
        content.addView(buttonRow(context, alice, gpt))

        content.addView(buttonRow(context,
            actionButton(context, "РУЛЬ → ALICE (1 раз)") {
                if (!AssistantLabLauncher.isInstalled(context, AssistantTarget.ALICE)) {
                    AssistantLabLauncher.openOfficialInstall(context, AssistantTarget.ALICE)
                } else {
                    AssistantLabTrace.armSteering(context, AssistantTarget.ALICE)
                    Toast.makeText(context, "Следующее нажатие микрофона пойдёт в Alice", Toast.LENGTH_SHORT).show()
                }
                refresh()
            },
            actionButton(context, "РУЛЬ → GPT (1 раз)") {
                if (!AssistantLabLauncher.isInstalled(context, AssistantTarget.CHATGPT)) {
                    AssistantLabLauncher.openOfficialInstall(context, AssistantTarget.CHATGPT)
                } else {
                    AssistantLabTrace.armSteering(context, AssistantTarget.CHATGPT)
                    Toast.makeText(context, "Следующее нажатие микрофона пойдёт в ChatGPT", Toast.LENGTH_SHORT).show()
                }
                refresh()
            },
        ))

        val scroll = ScrollView(context)
        val log = TextView(context).apply {
            setTextColor(Color.rgb(215, 231, 239))
            textSize = 11f
            typeface = Typeface.MONOSPACE
            setTextIsSelectable(true)
            setPadding(dp(context, 4), dp(context, 8), dp(context, 4), dp(context, 8))
        }
        logView = log
        scroll.addView(log)
        content.addView(scroll, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
        outer.addView(content, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))

        try {
            manager.addView(outer, p)
            handler.post(refreshRunnable)
        } catch (t: Throwable) {
            root = null
            Toast.makeText(context, "Assistant Lab overlay: ${t.message}", Toast.LENGTH_LONG).show()
        }
    }

    private fun launchOrInstall(context: Context, target: AssistantTarget) {
        if (!AssistantLabTrace.active) AssistantLabTrace.start(context)
        if (AssistantLabLauncher.isInstalled(context, target)) {
            AssistantLabLauncher.launch(context, target, preferVoice = true)
        } else {
            AssistantLabTrace.add("UI install requested for ${target.title}")
            AssistantLabLauncher.openOfficialInstall(context, target)
        }
        refresh()
    }

    private fun refresh() {
        val context = appContext ?: return
        val alice = AssistantLabLauncher.resolveInstalled(context, AssistantTarget.ALICE)
        val gpt = AssistantLabLauncher.resolveInstalled(context, AssistantTarget.CHATGPT)
        statusView?.text = buildString {
            append(if (AssistantLabTrace.active) "● TRACE ON" else "○ TRACE OFF")
            append("   A11Y=").append(SteeringWheelKeyService.isConnected)
            append("   overlay=").append(Settings.canDrawOverlays(context))
            append("\nAlice: ").append(alice?.let { "${it.label} · ${it.packageName} · ${it.versionName}" } ?: "НЕ УСТАНОВЛЕНА")
            append("\nChatGPT: ").append(gpt?.let { "${it.label} · ${it.packageName} · ${it.versionName}" } ?: "НЕ УСТАНОВЛЕН")
            append("\nКнопки РУЛЬ→… перенаправляют только ОДНО следующее нажатие 304; обычный Build85 маршрут не меняется.")
        }
        aliceButton?.text = if (alice == null) "УСТАНОВИТЬ ALICE" else "ТЕСТ ALICE"
        gptButton?.text = if (gpt == null) "УСТАНОВИТЬ CHATGPT" else "ТЕСТ CHATGPT"
        val text = AssistantLabTrace.snapshot()
        if (logView?.text?.toString() != text) {
            logView?.text = text
        }
    }

    private fun copyLog(context: Context) {
        val text = AssistantLabTrace.snapshot()
        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newPlainText("BYDMate Assistant Lab", text))
        Toast.makeText(context, "Лог скопирован", Toast.LENGTH_SHORT).show()
    }

    private fun toggleSize(context: Context) {
        minimized = !minimized
        expandedContent?.visibility = if (minimized) View.GONE else View.VISIBLE
        val p = params ?: return
        p.width = dp(context, if (minimized) 430 else 900)
        p.height = if (minimized) WindowManager.LayoutParams.WRAP_CONTENT else dp(context, 690)
        root?.let { runCatching { wm?.updateViewLayout(it, p) } }
    }

    private fun installDrag(view: View) {
        var downX = 0f
        var downY = 0f
        var startX = 0
        var startY = 0
        view.setOnTouchListener { _, e ->
            val p = params ?: return@setOnTouchListener false
            when (e.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    downX = e.rawX; downY = e.rawY; startX = p.x; startY = p.y; true
                }
                MotionEvent.ACTION_MOVE -> {
                    p.x = startX + (e.rawX - downX).toInt()
                    p.y = startY + (e.rawY - downY).toInt()
                    root?.let { runCatching { wm?.updateViewLayout(it, p) } }
                    true
                }
                else -> false
            }
        }
    }

    private fun buttonRow(context: Context, vararg buttons: Button): LinearLayout =
        LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            buttons.forEach { b -> addView(b, LinearLayout.LayoutParams(0, dp(context, 52), 1f).apply { setMargins(dp(context, 3), dp(context, 4), dp(context, 3), dp(context, 4)) }) }
        }

    private fun actionButton(context: Context, label: String, action: () -> Unit): Button =
        Button(context).apply {
            text = label
            textSize = 11f
            isAllCaps = false
            setOnClickListener { action() }
        }

    private fun smallButton(context: Context, label: String, action: () -> Unit): Button =
        Button(context).apply {
            text = label
            textSize = 18f
            minWidth = 0
            minimumWidth = 0
            setPadding(0, 0, 0, 0)
            setOnClickListener { action() }
            layoutParams = LinearLayout.LayoutParams(dp(context, 60), dp(context, 44))
        }

    private fun dp(context: Context, value: Int): Int =
        (value * context.resources.displayMetrics.density).toInt().coerceAtLeast(1)
}
'''

p = Path("app/src/main/kotlin/com/bydmate/app/assistantlab/AssistantLab.kt")
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(lab)


# ---------------------------------------------------------------------------
# 3) Hook structured trace into the Accessibility/key service. The one-shot 304 handler runs
#    before the normal Build85 route ONLY when explicitly armed in the lab. 327 remains governed
#    by the existing proven Build70/Build81 blocker.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt")
s = p.read_text()
s = replace_once(
    s,
    "package com.bydmate.app.cluster\n",
    "package com.bydmate.app.cluster\n\nimport com.bydmate.app.assistantlab.AssistantLabTrace\n",
    "AssistantLabTrace import",
)
s = replace_once(
    s,
    "    override fun onAccessibilityEvent(event: AccessibilityEvent?) {\n",
    "    override fun onAccessibilityEvent(event: AccessibilityEvent?) {\n        if (event != null) AssistantLabTrace.onAccessibilityEvent(event)\n",
    "a11y trace hook",
)
s = replace_once(
    s,
    "    override fun onKeyEvent(event: KeyEvent): Boolean {\n",
    "    override fun onKeyEvent(event: KeyEvent): Boolean {\n        AssistantLabTrace.onKeyEvent(event)\n        if (AssistantLabTrace.maybeHandleSteering(applicationContext, event)) return true\n",
    "key trace/one-shot route hook",
)
p.write_text(s)


# ---------------------------------------------------------------------------
# 4) Settings entry. The actual lab is a floating WindowManager overlay so it remains visible
#    while Alice/ChatGPT are foreground and can be minimized/expanded/dragged.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text()
s = replace_once(
    s,
    "import com.bydmate.app.agent.LlmAgentBackend\n",
    "import com.bydmate.app.agent.LlmAgentBackend\nimport com.bydmate.app.assistantlab.AssistantLabOverlay\n",
    "AssistantLabOverlay import",
)
s = replace_once(
    s,
    "    VOICE(R.string.settings_section_voice_agent, Icons.Outlined.Mic),\n",
    "    VOICE(R.string.settings_section_voice_agent, Icons.Outlined.Mic),\n    ASSISTANT_LAB(R.string.settings_section_assistant_lab, Icons.Outlined.Build),\n",
    "settings enum",
)
s = replace_once(
    s,
    "                        SettingsSection.VOICE -> VoiceSettingsContent(state, viewModel, onNavigateToVoiceJournal, onNavigateToAgentChat)\n",
    "                        SettingsSection.VOICE -> VoiceSettingsContent(state, viewModel, onNavigateToVoiceJournal, onNavigateToAgentChat)\n                        SettingsSection.ASSISTANT_LAB -> AssistantLabSection()\n",
    "settings route",
)
anchor = "@Composable\nprivate fun BatterySection(state: SettingsUiState, viewModel: SettingsViewModel) {\n"
section = r'''@Composable
private fun AssistantLabSection() {
    val context = LocalContext.current
    SectionHeader(text = "Assistant Lab · Build86")
    Text(
        text = "Build85 голосовой тракт зафиксирован. Эта лаборатория отдельно проверяет Alice и ChatGPT: установку, exported voice intents, запуск, foreground, Accessibility, системный assistant state и узкий logcat. Плавающее окно остаётся поверх внешнего приложения и сворачивается в компактную панель.",
        color = TextSecondary,
        fontSize = 14.sp,
    )
    Button(onClick = { AssistantLabOverlay.show(context) }) {
        Text("Открыть плавающее debug-окно")
    }
    Text(
        text = "Если BYDMate ещё не разрешено отображение поверх других окон, первая попытка откроет системное разрешение. После разрешения вернись сюда и нажми кнопку ещё раз. Если Alice/ChatGPT отсутствуют, в окне появится кнопка официальной установки. Кнопки «РУЛЬ → …» действуют только на одно следующее нажатие и не меняют обычный маршрут Build85.",
        color = TextMuted,
        fontSize = 12.sp,
    )
}

'''
s = replace_once(s, anchor, section + anchor, "AssistantLabSection")
p.write_text(s)


# ---------------------------------------------------------------------------
# 5) Settings rail label.
# ---------------------------------------------------------------------------
p = Path("app/src/main/res/values/strings.xml")
s = p.read_text()
s = replace_once(
    s,
    '    <string name="settings_section_widget_title">Виджет</string>\n',
    '    <string name="settings_section_widget_title">Виджет</string>\n    <string name="settings_section_assistant_lab">Assistant Lab</string>\n',
    "assistant lab string",
)
p.write_text(s)

print("Build86 applied: frozen Build85 + floating Alice/ChatGPT Assistant Lab")
