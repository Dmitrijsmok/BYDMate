from pathlib import Path
import re

# Build57 combines the field-test follow-ups in one build:
# - GigaAM download survives leaving the Activity by running on TrackingService.
# - persistent .part files + HTTP Range resume across process/service restarts.
# - explicit download/extract/validate/VAD stages and a persistent debug log.
# - Accessibility blocker self-heal + removal of the stale legacy BYDMate service.
# - restore a real CLOSE/re-open control to the DiLink3 diagnostic panel.
# - keep Build49 327 blocker + Build56 physical 304 routing unchanged.

# ---------------------------------------------------------------------------
# 1) Replace GigaAM manager with a resumable, stage-aware implementation.
# ---------------------------------------------------------------------------
manager = r'''package com.bydmate.app.voice

import android.content.Context
import android.util.Log
import kotlin.coroutines.coroutineContext
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.apache.commons.compress.archivers.tar.TarArchiveInputStream
import org.apache.commons.compress.compressors.bzip2.BZip2CompressorInputStream
import java.io.BufferedInputStream
import java.io.File
import java.io.FileOutputStream

class GigaAmModelManager(
    private val context: Context,
    private val http: OkHttpClient,
) {
    data class StatusSnapshot(
        val stage: String,
        val progress: Int,
        val active: Boolean,
        val failed: Boolean,
        val detail: String,
    )

    private val prefs = context.getSharedPreferences("gigaam_build57", Context.MODE_PRIVATE)
    private fun baseDir() = File(context.filesDir, "asr/gigaam-v3-ru")
    private fun stagingDir() = File(context.filesDir, "asr/.staging-gigaam-v3-ru")
    private fun legacyDir() = File(context.filesDir, "asr/gigaam-v2-ru")
    private fun legacyStagingDir() = File(context.filesDir, "asr/.staging-gigaam-v2-ru")
    private fun vadFile() = File(context.filesDir, "asr/silero_vad.onnx")
    private fun downloadDir() = File(context.filesDir, "asr/.downloads")
    private fun archivePart() = File(downloadDir(), "gigaam-v3-ru.tar.bz2.part")
    private fun vadPart() = File(downloadDir(), "silero_vad.onnx.part")
    private fun debugFile() = File(context.filesDir, "gigaam-download-debug.log")

    fun modelPath(): String = File(baseDir(), "model.int8.onnx").absolutePath
    fun tokensPath(): String = File(baseDir(), "tokens.txt").absolutePath
    fun vadPath(): String = vadFile().absolutePath

    private fun isModelComplete(dir: File): Boolean =
        File(dir, "model.int8.onnx").let { it.isFile && it.length() > 0 } &&
            File(dir, "tokens.txt").let { it.isFile && it.length() > 0 }
    private fun isVadComplete(): Boolean = vadFile().let { it.isFile && it.length() > 0 }
    fun isReady(): Boolean = isModelComplete(baseDir()) && isVadComplete()

    internal val diskMutex = Mutex()

    fun statusSnapshot(): StatusSnapshot = StatusSnapshot(
        stage = prefs.getString("stage", if (isReady()) "READY" else "IDLE") ?: "IDLE",
        progress = prefs.getInt("progress", if (isReady()) 100 else -1),
        active = prefs.getBoolean("active", false),
        failed = prefs.getBoolean("failed", false),
        detail = prefs.getString("detail", "") ?: "",
    )

    private fun setState(stage: String, progress: Int, active: Boolean, failed: Boolean, detail: String = "") {
        prefs.edit()
            .putString("stage", stage)
            .putInt("progress", progress)
            .putBoolean("active", active)
            .putBoolean("failed", failed)
            .putString("detail", detail.take(500))
            .apply()
        debug("BUILD57_GIGAAM_STAGE | stage=$stage progress=$progress active=$active failed=$failed detail=$detail")
    }

    private fun debug(message: String) {
        Log.i("GigaAmModelManager", message)
        runCatching {
            debugFile().appendText("${System.currentTimeMillis()} | $message\n")
            if (debugFile().length() > 2_000_000L) {
                val tail = debugFile().readText().takeLast(1_000_000)
                debugFile().writeText(tail)
            }
        }
    }

    suspend fun delete() {
        diskMutex.withLock {
            baseDir().deleteRecursively()
            stagingDir().deleteRecursively()
            legacyDir().deleteRecursively()
            legacyStagingDir().deleteRecursively()
            vadFile().delete()
            downloadDir().deleteRecursively()
        }
        prefs.edit().clear().apply()
        setState("IDLE", -1, active = false, failed = false, detail = "model deleted")
    }

    suspend fun download(onProgress: (Int) -> Unit): Result<Unit> = withContext(Dispatchers.IO) {
        runCatching {
            downloadDir().mkdirs()
            val freeBefore = context.filesDir.usableSpace
            setState("DOWNLOADING_MODEL", 0, active = true, failed = false,
                detail = "resumeBytes=${archivePart().length()} freeBytes=$freeBefore")

            downloadToFileResume(MODEL_URL, archivePart()) { pct, bytes, total ->
                val overall = (pct * 75) / 100
                setState("DOWNLOADING_MODEL", overall, true, false, "bytes=$bytes total=$total")
                onProgress(overall)
            }
            coroutineContext.ensureActive()

            setState("EXTRACTING_MODEL", 76, true, false,
                "archiveBytes=${archivePart().length()} freeBytes=${context.filesDir.usableSpace}")
            diskMutex.withLock {
                coroutineContext.ensureActive()
                val staging = stagingDir()
                val target = baseDir()
                staging.deleteRecursively()
                staging.mkdirs()
                try {
                    untarFlatten(archivePart(), staging) { pct, bytes ->
                        val overall = 76 + (pct * 17) / 100
                        setState("EXTRACTING_MODEL", overall, true, false, "modelBytes=$bytes")
                        onProgress(overall)
                    }
                    coroutineContext.ensureActive()
                    setState("VALIDATING_MODEL", 94, true, false,
                        "modelBytes=${File(staging, "model.int8.onnx").length()} tokensBytes=${File(staging, "tokens.txt").length()}")
                    check(isModelComplete(staging)) { "unpack produced incomplete model dir" }
                    target.deleteRecursively()
                    check(staging.renameTo(target)) { "failed to publish staged model" }
                    legacyDir().deleteRecursively()
                    legacyStagingDir().deleteRecursively()
                } catch (t: Throwable) {
                    staging.deleteRecursively()
                    throw t
                }
            }
            coroutineContext.ensureActive()

            setState("DOWNLOADING_VAD", 95, true, false, "resumeBytes=${vadPart().length()}")
            downloadToFileResume(VAD_URL, vadPart()) { pct, bytes, total ->
                val overall = 95 + (pct * 4) / 100
                setState("DOWNLOADING_VAD", overall, true, false, "bytes=$bytes total=$total")
                onProgress(overall)
            }
            coroutineContext.ensureActive()
            diskMutex.withLock {
                coroutineContext.ensureActive()
                check(vadPart().length() > 0) { "downloaded VAD file is empty" }
                vadFile().delete()
                check(vadPart().renameTo(vadFile())) { "failed to publish VAD file" }
            }

            check(isReady()) { "GigaAM publish finished but readiness check failed" }
            archivePart().delete()
            vadPart().delete()
            setState("READY", 100, active = false, failed = false,
                detail = "modelBytes=${File(baseDir(), "model.int8.onnx").length()} vadBytes=${vadFile().length()}")
            onProgress(100)
        }.onFailure { t ->
            if (t is CancellationException) {
                debug("BUILD57_GIGAAM_CANCELLED | stage=${statusSnapshot().stage} detail=${t.message}")
                throw t
            }
            setState("FAILED", statusSnapshot().progress.coerceAtLeast(0), active = false, failed = true,
                detail = "${t::class.java.simpleName}:${t.message}")
        }
    }

    private suspend fun downloadToFileResume(
        url: String,
        dest: File,
        onProgress: (Int, Long, Long) -> Unit,
    ) {
        dest.parentFile?.mkdirs()
        var existing = if (dest.isFile) dest.length() else 0L
        val requestBuilder = Request.Builder().url(url)
        if (existing > 0L) requestBuilder.header("Range", "bytes=$existing-")
        http.newCall(requestBuilder.build()).execute().use { resp ->
            if (existing > 0L && resp.code == 416) {
                debug("BUILD57_GIGAAM_RANGE_416 | url=$url existing=$existing; restarting")
                dest.delete(); existing = 0L
                return downloadToFileResume(url, dest, onProgress)
            }
            if (!resp.isSuccessful) error("HTTP ${resp.code}")
            val body = resp.body ?: error("empty response body")
            val append = existing > 0L && resp.code == 206
            if (existing > 0L && !append) {
                debug("BUILD57_GIGAAM_RANGE_IGNORED | code=${resp.code} existing=$existing; restarting file")
                dest.delete(); existing = 0L
            }
            val remaining = body.contentLength()
            val total = if (remaining > 0L) existing + remaining else -1L
            var read = existing
            debug("BUILD57_GIGAAM_HTTP | code=${resp.code} append=$append existing=$existing remaining=$remaining total=$total url=$url")
            body.byteStream().use { input ->
                FileOutputStream(dest, append).use { out ->
                    val buf = ByteArray(64 * 1024)
                    var lastReported = -1
                    while (true) {
                        coroutineContext.ensureActive()
                        val n = input.read(buf)
                        if (n < 0) break
                        out.write(buf, 0, n)
                        read += n
                        if (total > 0L) {
                            val pct = ((read * 100) / total).toInt().coerceIn(0, 100)
                            if (pct != lastReported) {
                                lastReported = pct
                                onProgress(pct, read, total)
                            }
                        }
                    }
                    out.fd.sync()
                }
            }
            debug("BUILD57_GIGAAM_FILE_COMPLETE | bytes=${dest.length()} url=$url")
        }
    }

    internal suspend fun untarFlatten(
        archive: File,
        target: File,
        onModelProgress: (Int, Long) -> Unit,
    ) {
        val canonicalTarget = target.canonicalFile
        BZip2CompressorInputStream(BufferedInputStream(archive.inputStream())).use { bz ->
            TarArchiveInputStream(bz).use { tar ->
                var entry = tar.nextEntry
                while (entry != null) {
                    coroutineContext.ensureActive()
                    val rel = entry.name.substringAfter('/')
                    if (rel.isNotBlank()) {
                        val outFile = File(target, rel)
                        val canonicalOut = outFile.canonicalFile
                        if (canonicalOut.path == canonicalTarget.path || canonicalOut.path.startsWith(canonicalTarget.path + File.separator)) {
                            if (entry.isDirectory) {
                                outFile.mkdirs()
                            } else {
                                outFile.parentFile?.mkdirs()
                                val expected = entry.size.coerceAtLeast(1L)
                                var written = 0L
                                var lastPct = -1
                                outFile.outputStream().use { out ->
                                    val buf = ByteArray(64 * 1024)
                                    while (true) {
                                        coroutineContext.ensureActive()
                                        val n = tar.read(buf)
                                        if (n < 0) break
                                        out.write(buf, 0, n)
                                        written += n
                                        if (outFile.name == "model.int8.onnx") {
                                            val pct = ((written * 100) / expected).toInt().coerceIn(0, 100)
                                            if (pct != lastPct) {
                                                lastPct = pct
                                                onModelProgress(pct, written)
                                            }
                                        }
                                    }
                                    out.fd.sync()
                                }
                                debug("BUILD57_GIGAAM_UNPACK_FILE | name=${outFile.name} bytes=$written expected=$expected")
                            }
                        }
                    }
                    entry = tar.nextEntry
                }
            }
        }
    }

    companion object {
        const val MODEL_URL =
            "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/" +
                "sherpa-onnx-nemo-ctc-giga-am-v3-russian-2025-12-16.tar.bz2"
        const val VAD_URL =
            "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx"
        const val MODEL_SIZE_LABEL = "226 МБ"
    }
}
'''
Path('app/src/main/kotlin/com/bydmate/app/voice/GigaAmModelManager.kt').write_text(manager)

# ---------------------------------------------------------------------------
# 2) Settings ViewModel: hand GigaAM work to the already-foreground TrackingService
# and poll persistent manager state instead of owning the coroutine in viewModelScope.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsViewModel.kt')
s = p.read_text()
s = s.replace(
    '    val gigaAmDownloadProgress: Int = -1,   // -1 = idle, 0..100 = downloading\n    val gigaAmDownloadFailed: Boolean = false,',
    '    val gigaAmDownloadProgress: Int = -1,   // -1 = idle, 0..100 = downloading\n    val gigaAmDownloadFailed: Boolean = false,\n    val gigaAmStage: String = "IDLE",\n    val gigaAmDetail: String = "",',
    1,
)
s = s.replace(
    '        loadSettings()\n        observeLogRecorder()\n',
    '        loadSettings()\n        observeLogRecorder()\n        observeBuild57GigaAmStatus()\n',
    1,
)
pattern = re.compile(r'''    private var gigaAmDownloadJob: Job\? = null\n\n    fun downloadGigaAmModel\(\) \{.*?\n    \}\n\n    fun deleteGigaAmModel\(\) \{.*?\n    \}\n''', re.S)
replacement = r'''    fun downloadGigaAmModel() {
        val intent = Intent(appContext, TrackingService::class.java)
            .setAction(TrackingService.ACTION_GIGAAM_DOWNLOAD)
        ContextCompat.startForegroundService(appContext, intent)
    }

    fun deleteGigaAmModel() {
        val intent = Intent(appContext, TrackingService::class.java)
            .setAction(TrackingService.ACTION_GIGAAM_DELETE)
        ContextCompat.startForegroundService(appContext, intent)
    }

    private fun observeBuild57GigaAmStatus() {
        viewModelScope.launch {
            while (isActive) {
                val snap = gigaAmModelManager.statusSnapshot()
                _uiState.update {
                    it.copy(
                        gigaAmDownloadProgress = if (snap.active) snap.progress.coerceAtLeast(0) else -1,
                        gigaAmModelReady = gigaAmModelManager.isReady(),
                        gigaAmDownloadFailed = snap.failed,
                        gigaAmStage = snap.stage,
                        gigaAmDetail = snap.detail,
                    )
                }
                delay(750)
            }
        }
    }
'''
s, n = pattern.subn(replacement, s, count=1)
if n != 1:
    raise SystemExit('Build57 could not replace SettingsViewModel GigaAM job block')
p.write_text(s)

# Settings UI: show actual stage/detail, so 99% can never be a silent mystery again.
p = Path('app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt')
s = p.read_text()
anchor = '            if (gigaAmDownloading) {\n'
if anchor not in s:
    raise SystemExit('Build57 GigaAM Settings UI anchor not found')
s = s.replace(anchor, anchor + '''                Text(
                    "GigaAM: ${state.gigaAmStage} ${state.gigaAmDetail}",
                    color = TextSecondary,
                    fontSize = 11.sp,
                    modifier = Modifier.padding(vertical = 4.dp),
                )
''', 1)
p.write_text(s)

# ---------------------------------------------------------------------------
# 3) TrackingService owns the model job. It is already a foreground service, so
# switching apps no longer cancels the download. Sticky restart resumes .part files.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/service/TrackingService.kt')
s = p.read_text()
s = s.replace(
    '    private var pollingJob: Job? = null\n',
    '    private var pollingJob: Job? = null\n    private var build57GigaAmJob: Job? = null\n',
    1,
)
companion_anchor = '        private const val CHANNEL_ID = "bydmate_tracking"\n'
if companion_anchor not in s:
    raise SystemExit('Build57 TrackingService companion anchor not found')
s = s.replace(companion_anchor, companion_anchor + '''        const val ACTION_GIGAAM_DOWNLOAD = "com.bydmate.app.action.GIGAAM_DOWNLOAD"
        const val ACTION_GIGAAM_DELETE = "com.bydmate.app.action.GIGAAM_DELETE"
''', 1)

start_anchor = '''    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        maybeAttachWidget()
        return START_STICKY
    }
'''
replacement_start = r'''    private fun build57StartGigaAm(reason: String) {
        if (gigaAmModelManager.isReady()) return
        if (build57GigaAmJob?.isActive == true) return
        com.bydmate.app.ui.diagnostics.DiLink3DebugLog.log(
            this, "BUILD57_GIGAAM_SERVICE_START", "reason=$reason stage=${gigaAmModelManager.statusSnapshot().stage}"
        )
        build57GigaAmJob = serviceScope.launch(Dispatchers.IO) {
            try {
                val result = gigaAmModelManager.download { }
                com.bydmate.app.ui.diagnostics.DiLink3DebugLog.log(
                    this@TrackingService, "BUILD57_GIGAAM_SERVICE_RESULT",
                    "success=${result.isSuccess} ready=${gigaAmModelManager.isReady()} stage=${gigaAmModelManager.statusSnapshot().stage}"
                )
                if (result.isSuccess) runCatching { continuousAsr.warmUp() }
            } finally {
                build57GigaAmJob = null
            }
        }
    }

    private fun build57DeleteGigaAm() {
        build57GigaAmJob?.cancel()
        build57GigaAmJob = null
        serviceScope.launch(Dispatchers.IO) {
            gigaAmModelManager.delete()
            com.bydmate.app.ui.diagnostics.DiLink3DebugLog.log(
                this@TrackingService, "BUILD57_GIGAAM_DELETE", "done=true"
            )
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_GIGAAM_DOWNLOAD -> build57StartGigaAm("user")
            ACTION_GIGAAM_DELETE -> build57DeleteGigaAm()
        }
        maybeAttachWidget()
        return START_STICKY
    }
'''
if start_anchor not in s:
    raise SystemExit('Build57 onStartCommand anchor not found')
s = s.replace(start_anchor, replacement_start, 1)

# Resume an interrupted install automatically when the foreground service comes back.
resume_anchor = '        ChainLog.append(this, "TrackingService fully started")\n'
if resume_anchor not in s:
    raise SystemExit('Build57 TrackingService fully-started anchor not found')
s = s.replace(resume_anchor, resume_anchor + '''        if (gigaAmModelManager.statusSnapshot().active && !gigaAmModelManager.isReady()) {
            build57StartGigaAm("sticky_resume")
        }
''', 1)

# Accessibility self-heal. Remove stale production-package service, preserve all unrelated
# services, and re-add only this build's component when disconnected or drift is detected.
a11y_func_anchor = '    private fun maybeAttachWidget() {\n'
a11y_func = r'''    private suspend fun build57SelfHealAccessibility(reason: String) {
        val current = "$packageName/com.bydmate.app.cluster.SteeringWheelKeyService"
        val legacy = "com.bydmate.app/com.bydmate.app.cluster.SteeringWheelKeyService"
        val raw = android.provider.Settings.Secure.getString(contentResolver, "enabled_accessibility_services").orEmpty()
        val existing = raw.split(':').filter { it.isNotBlank() }
        val connected = com.bydmate.app.cluster.SteeringWheelKeyService.isConnected
        val needsRepair = !connected || legacy in existing || current !in existing
        if (!needsRepair) {
            com.bydmate.app.ui.diagnostics.DiLink3DebugLog.log(
                this, "BUILD57_A11Y_SELF_HEAL", "reason=$reason action=none connected=true legacy=false"
            )
            return
        }
        val adbOk = runCatching {
            adbOnDeviceClient.connect()
            adbOnDeviceClient.isConnected()
        }.getOrDefault(false)
        if (!adbOk) {
            com.bydmate.app.ui.diagnostics.DiLink3DebugLog.log(
                this, "BUILD57_A11Y_SELF_HEAL", "reason=$reason success=false adb=false connectedBefore=$connected legacyPresent=${legacy in existing}"
            )
            return
        }
        val clean = existing.filter { it != legacy && it != current }.distinct()
        val target = (clean + current).distinct()
        val r0 = runCatching {
            adbOnDeviceClient.execDiagnosticMutation("set_a11y_services", if (clean.isEmpty()) "null" else clean.joinToString(":"))
        }.getOrNull()
        delay(350)
        val r1 = runCatching {
            adbOnDeviceClient.execDiagnosticMutation("set_a11y_services", target.joinToString(":"))
        }.getOrNull()
        val r2 = runCatching { adbOnDeviceClient.execDiagnosticMutation("set_a11y_enabled", "1") }.getOrNull()
        delay(1800)
        val afterRaw = android.provider.Settings.Secure.getString(contentResolver, "enabled_accessibility_services").orEmpty()
        val after = afterRaw.split(':').filter { it.isNotBlank() }
        val connectedAfter = com.bydmate.app.cluster.SteeringWheelKeyService.isConnected
        val success = current in after && legacy !in after && connectedAfter &&
            android.provider.Settings.Secure.getInt(contentResolver, "accessibility_enabled", 0) == 1
        com.bydmate.app.ui.diagnostics.DiLink3DebugLog.log(
            this, "BUILD57_A11Y_SELF_HEAL",
            "reason=$reason success=$success connectedBefore=$connected connectedAfter=$connectedAfter legacyBefore=${legacy in existing} legacyAfter=${legacy in after} remove=${r0?.replace('\n','|')} add=${r1?.replace('\n','|')} enable=${r2?.replace('\n','|')}"
        )
    }

'''
if a11y_func_anchor not in s:
    raise SystemExit('Build57 maybeAttachWidget anchor not found')
s = s.replace(a11y_func_anchor, a11y_func + a11y_func_anchor, 1)
startup_anchor = '        serviceScope.launch { ensureStarServiceRunning("startup") }\n'
if startup_anchor not in s:
    raise SystemExit('Build57 startup a11y anchor not found')
s = s.replace(startup_anchor, startup_anchor + '        serviceScope.launch { delay(1500); build57SelfHealAccessibility("startup") }\n', 1)
p.write_text(s)

# ---------------------------------------------------------------------------
# 4) Final generated DiLink3 panel: real close/re-open control and legacy-service cleanup
# in the manual blocker repair path too.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()
s = s.replace(
    '    val scope = rememberCoroutineScope()\n',
    '''    val scope = rememberCoroutineScope()
    var build57PanelExpanded by remember { mutableStateOf(true) }
    if (!build57PanelExpanded) {
        Card(modifier = modifier.fillMaxWidth()) {
            Button(
                onClick = { build57PanelExpanded = true },
                modifier = Modifier.fillMaxWidth().padding(8.dp),
            ) { Text("OPEN DiLink3 VOICE DEBUG") }
        }
        return
    }
''',
    1,
)
card_anchor = '    Card(modifier = modifier.fillMaxWidth()) {\n'
if card_anchor not in s:
    raise SystemExit('Build57 panel Card anchor not found')
s = s.replace(card_anchor, card_anchor + '''        Row(
            modifier = Modifier.fillMaxWidth().padding(8.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text("DiLink3 Build57", modifier = Modifier.weight(1f))
            Button(onClick = { build57PanelExpanded = false }) { Text("CLOSE") }
        }
''', 1)
# Manual repair from Build56 must also remove the stale production-package service.
s = s.replace(
    '            val withoutOurs = original.filter { it != component }\n',
    '            val legacyComponent = "com.bydmate.app/com.bydmate.app.cluster.SteeringWheelKeyService"\n            val withoutOurs = original.filter { it != component && it != legacyComponent }\n',
    1,
)
p.write_text(s)

# Additional field-test marker around physical 304 routing.
p = Path('app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt')
s = p.read_text()
needle = '                "BUILD56_MIC_304_ROUTED_TO_BYDMATE",\n'
if needle not in s:
    raise SystemExit('Build57 Build56 304 marker anchor not found')
s = s.replace(
    '        val voiceKeyDecision = voiceDecision(build56VoiceEventKey, isDown, voiceEnabled, voiceKey)\n',
    '''        if (build56PhysicalMic304) {
            DiLink3DebugLog.log(
                applicationContext,
                "BUILD57_MIC_STATUS",
                "voiceEnabled=$voiceEnabled blockerConnected=${isConnected} configuredVoiceKey=$voiceKey action=${event.action}"
            )
        }
        val voiceKeyDecision = voiceDecision(build56VoiceEventKey, isDown, voiceEnabled, voiceKey)
''',
    1,
)
p.write_text(s)

print('Build57 reliability bundle installed: GigaAM foreground/resume diagnostics, A11y self-heal, panel CLOSE, mic status')
