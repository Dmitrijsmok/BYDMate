package com.bydmate.app.voice

import android.content.Context
import android.os.SystemClock
import android.util.Log
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

/** Downloads and unpacks a TTS voice archive, selected by [TtsVoice.modelDirId]
 *  (several voices can share one archive/dir -- see [TtsVoiceEngine.VITS_MULTI]).
 *  Archive layout: one top-level dir with model .onnx + tokens.txt, plus either
 *  espeak-ng-data/ (PIPER) or stress.tsv (VITS_MULTI), under
 *  filesDir/tts/<modelDirId>. Same shape as GigaAmModelManager for the ASR
 *  models. */
class TtsModelManager(
    private val context: Context,
    private val http: OkHttpClient,
) {
    private fun baseDir(modelDirId: String) = File(context.filesDir, "tts/$modelDirId")

    private fun stagingDir(modelDirId: String) = File(context.filesDir, "tts/.staging-$modelDirId")

    private fun stressStagingDir(modelDirId: String) = File(context.filesDir, "tts/.staging-$modelDirId-stress")

    fun modelDirPath(modelDirId: String): String = baseDir(modelDirId).absolutePath

    /** The archive's .onnx filename is not hardcoded — find the single model file.
     *  AppleDouble sidecar files (._*.onnx) are skipped; they crash sherpa-onnx. */
    fun onnxFile(modelDirId: String): File? =
        baseDir(modelDirId).listFiles()?.firstOrNull { it.isFile && it.name.endsWith(".onnx") && !it.name.startsWith("._") }

    private fun hasRealOnnx(dir: File): Boolean =
        dir.listFiles()?.any { it.isFile && it.name.endsWith(".onnx") && !it.name.startsWith("._") } == true

    /** PIPER archives need espeak-ng-data/ for phonemization; the VITS_MULTI
     *  archive carries its own stress.tsv instead and ships no espeak data.
     *  Supertonic ships a fixed 7-file layout and NO tokens.txt. */
    private fun isComplete(dir: File, engine: TtsVoiceEngine): Boolean = when (engine) {
        TtsVoiceEngine.PIPER ->
            hasRealOnnx(dir) && File(dir, "tokens.txt").isFile && File(dir, "espeak-ng-data").isDirectory
        TtsVoiceEngine.VITS_MULTI ->
            hasRealOnnx(dir) && File(dir, "tokens.txt").isFile && File(dir, "stress.tsv").isFile
        TtsVoiceEngine.SUPERTONIC -> SUPERTONIC_FILES.all { File(dir, it).isFile }
    }

    fun isReady(voice: TtsVoice): Boolean = isComplete(baseDir(voice.modelDirId), voice.engine)

    /** Serializes all disk mutations of the model dir: a delete can never
     *  interleave with download's commit (unpack) section, so a cancelled
     *  download cannot recreate a dir the user just deleted. */
    internal val diskMutex = Mutex()

    suspend fun delete(modelDirId: String) {
        diskMutex.withLock {
            baseDir(modelDirId).deleteRecursively()
            stagingDir(modelDirId).deleteRecursively()
        }
    }

    /**
     * Downloads a voice archive with verbose diagnostics intended for old DiLink 3 units.
     * Progress behaviour remains compatible with the existing UI, while logcat now shows
     * request URL, redirect target, HTTP status, declared size, transferred bytes, elapsed
     * time, unpack stage and the full exception when anything fails.
     */
    suspend fun download(voice: TtsVoice, onProgress: (Int) -> Unit): Result<Unit> =
        withContext(Dispatchers.IO) {
            val startedAt = SystemClock.elapsedRealtime()
            var stage = "prepare"
            var transferred = 0L
            var declaredLength = -1L
            var finalUrl = voice.url

            Log.i(TAG, "download start voice=${voice.id} modelDir=${voice.modelDirId} engine=${voice.engine} url=${voice.url}")

            runCatching {
                val tmp = File(context.cacheDir, "tts-${voice.modelDirId}.tar.bz2")
                try {
                    stage = "http"
                    val request = Request.Builder()
                        .url(voice.url)
                        .header("User-Agent", "BYDMate-DiLink3-Diagnostic")
                        .build()

                    http.newCall(request).execute().use { resp ->
                        finalUrl = resp.request.url.toString()
                        declaredLength = resp.body?.contentLength() ?: -1L
                        Log.i(
                            TAG,
                            "download response voice=${voice.id} code=${resp.code} protocol=${resp.protocol} " +
                                "redirected=${finalUrl != voice.url} finalUrl=$finalUrl contentLength=$declaredLength " +
                                "contentType=${resp.body?.contentType()}"
                        )
                        if (!resp.isSuccessful) {
                            error("HTTP ${resp.code} ${resp.message}; finalUrl=$finalUrl")
                        }

                        val body = resp.body ?: error("empty response body; finalUrl=$finalUrl")
                        stage = "transfer"
                        var lastLoggedBytes = 0L
                        var lastLoggedAt = startedAt

                        body.byteStream().use { input ->
                            tmp.outputStream().buffered().use { out ->
                                val buf = ByteArray(64 * 1024)
                                while (true) {
                                    ensureActive()
                                    val n = input.read(buf)
                                    if (n < 0) break
                                    out.write(buf, 0, n)
                                    transferred += n

                                    if (declaredLength > 0) {
                                        onProgress(((transferred * 100L) / declaredLength).coerceIn(0L, 100L).toInt())
                                    }

                                    val now = SystemClock.elapsedRealtime()
                                    if (transferred - lastLoggedBytes >= LOG_EVERY_BYTES || now - lastLoggedAt >= LOG_EVERY_MS) {
                                        Log.i(
                                            TAG,
                                            "download progress voice=${voice.id} bytes=$transferred total=$declaredLength " +
                                                "pct=${if (declaredLength > 0) (transferred * 100L / declaredLength) else -1} " +
                                                "elapsedMs=${now - startedAt}"
                                        )
                                        lastLoggedBytes = transferred
                                        lastLoggedAt = now
                                    }
                                }
                                out.flush()
                            }
                        }

                        if (declaredLength > 0 && transferred != declaredLength) {
                            error("truncated download: received=$transferred expected=$declaredLength; finalUrl=$finalUrl")
                        }
                    }

                    Log.i(
                        TAG,
                        "download transfer complete voice=${voice.id} bytes=$transferred fileBytes=${tmp.length()} " +
                            "elapsedMs=${SystemClock.elapsedRealtime() - startedAt}"
                    )

                    stage = "unpack"
                    diskMutex.withLock {
                        ensureActive()
                        val staging = stagingDir(voice.modelDirId)
                        val target = baseDir(voice.modelDirId)
                        staging.deleteRecursively()
                        staging.mkdirs()
                        try {
                            untarFlatten(tmp, staging)
                            check(isComplete(staging, voice.engine)) { "unpack produced incomplete model dir" }
                            target.deleteRecursively()
                            check(staging.renameTo(target)) { "failed to publish staged model" }
                        } catch (t: Throwable) {
                            staging.deleteRecursively()
                            throw t
                        }
                    }

                    stage = "verify"
                    check(isReady(voice)) { "installed model is not ready after publish" }
                    ensureActive()
                    Log.i(
                        TAG,
                        "download success voice=${voice.id} modelDir=${voice.modelDirId} bytes=$transferred " +
                            "elapsedMs=${SystemClock.elapsedRealtime() - startedAt}"
                    )
                } finally {
                    tmp.delete()
                }
            }.onFailure {
                if (it is CancellationException) throw it
                Log.e(
                    TAG,
                    "download failed voice=${voice.id} stage=$stage bytes=$transferred total=$declaredLength " +
                        "finalUrl=$finalUrl elapsedMs=${SystemClock.elapsedRealtime() - startedAt}: " +
                        "${it.javaClass.simpleName}: ${it.message}",
                    it
                )
            }
        }

    /** Supertonic archives (k2-fsa upstream) ship no stress dictionary; fetches our
     *  stress.tsv release asset into the voice dir so UPPERCASE stress marking works.
     *  Fail-soft: any error just leaves marking disabled. Returns true when the dict
     *  is present (already or downloaded just now). */
    suspend fun ensureStressDict(voice: TtsVoice): Boolean =
        withContext(Dispatchers.IO) {
            if (voice.engine != TtsVoiceEngine.SUPERTONIC) return@withContext true
            val targetDir = baseDir(voice.modelDirId)
            val targetFile = File(targetDir, STRESS_DICT_FILE)
            if (targetFile.isFile) return@withContext true
            if (!targetDir.isDirectory) return@withContext false

            val tmp = File(context.cacheDir, "tts-${voice.modelDirId}-stress-${System.nanoTime()}.tar.bz2")
            runCatching {
                try {
                    http.newCall(Request.Builder().url(STRESS_DICT_URL).build()).execute().use { resp ->
                        if (!resp.isSuccessful) error("HTTP ${resp.code}")
                        val body = resp.body ?: error("empty response body")
                        body.byteStream().use { input ->
                            tmp.outputStream().use { out ->
                                val buf = ByteArray(64 * 1024)
                                while (true) {
                                    ensureActive()
                                    val n = input.read(buf); if (n < 0) break
                                    out.write(buf, 0, n)
                                }
                            }
                        }
                    }
                    diskMutex.withLock {
                        ensureActive()
                        if (!targetDir.isDirectory) return@withLock false
                        if (targetFile.isFile) return@withLock true
                        val staging = stressStagingDir(voice.modelDirId)
                        staging.deleteRecursively()
                        staging.mkdirs()
                        try {
                            untarFlatten(tmp, staging)
                            val staged = File(staging, STRESS_DICT_FILE)
                            check(staged.isFile && staged.length() >= STRESS_DICT_MIN_BYTES) {
                                "stress dictionary implausibly small (${staged.length()} bytes)"
                            }
                            check(staged.renameTo(targetFile)) { "failed to publish stress dictionary" }
                            true
                        } finally {
                            staging.deleteRecursively()
                        }
                    }
                } finally {
                    tmp.delete()
                }
            }.onFailure {
                if (it is CancellationException) throw it
                Log.w(TAG, "failed to ensure stress dictionary for ${voice.modelDirId}", it)
            }.getOrDefault(false)
        }

    /** Archive has a single top-level folder; flatten it into [target].
     *  Tar Slip guard mirrors VoiceModelManager.unzipFlatten's Zip Slip guard. */
    internal fun untarFlatten(archive: File, target: File) {
        val canonicalTarget = target.canonicalFile
        BZip2CompressorInputStream(BufferedInputStream(archive.inputStream())).use { bz ->
            TarArchiveInputStream(bz).use { tar ->
                var entry = tar.nextEntry
                while (entry != null) {
                    val rel = entry.name.substringAfter('/')
                    if (isJunkPath(rel)) { entry = tar.nextEntry; continue }
                    if (rel.isNotBlank()) {
                        val outFile = File(target, rel)
                        val canonicalOut = outFile.canonicalFile
                        if (canonicalOut.path != canonicalTarget.path &&
                            !canonicalOut.path.startsWith(canonicalTarget.path + File.separator)) {
                            entry = tar.nextEntry; continue
                        }
                        if (entry.isDirectory) outFile.mkdirs()
                        else { outFile.parentFile?.mkdirs(); outFile.outputStream().use { tar.copyTo(it) } }
                    }
                    entry = tar.nextEntry
                }
            }
        }
    }

    companion object {
        private const val TAG = "TtsModelManager"
        private const val LOG_EVERY_BYTES = 1L * 1024L * 1024L
        private const val LOG_EVERY_MS = 2_000L
        const val DEFAULT_VOICE_ID = "dmitri"
        internal const val STRESS_DICT_URL = "https://github.com/AndyShaman/BYDMate/releases/download/tts-voices-v1/stress-ru.tar.bz2"
        internal const val STRESS_DICT_FILE = "stress.tsv"
        internal const val STRESS_DICT_MIN_BYTES = 1_000_000L

        internal val SUPERTONIC_FILES = listOf(
            "duration_predictor.int8.onnx", "text_encoder.int8.onnx", "vector_estimator.int8.onnx",
            "vocoder.int8.onnx", "tts.json", "unicode_indexer.bin", "voice.bin",
        )

        internal fun isJunkPath(path: String): Boolean =
            path.split('/').any { it.startsWith("._") || it == ".DS_Store" || it == "__MACOSX" }
    }
}
