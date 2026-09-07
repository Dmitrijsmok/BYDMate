package com.bydmate.app.voice

import android.content.Context
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

/** Downloads and unpacks the GigaAM v3 Russian ASR model (sherpa-onnx nemo-ctc archive:
 *  model.int8.onnx + tokens.txt under one top-level dir) plus the standalone silero VAD
 *  .onnx file, into filesDir/asr/. Same staging + atomic-rename shape as TtsModelManager. */
class GigaAmModelManager(
    private val context: Context,
    private val http: OkHttpClient,
) {
    private fun baseDir() = File(context.filesDir, "asr/gigaam-v3-ru")

    private fun stagingDir() = File(context.filesDir, "asr/.staging-gigaam-v3-ru")

    /** v2 model dir left behind by pre-v3.7 installs; swept on the next download/delete. */
    private fun legacyDir() = File(context.filesDir, "asr/gigaam-v2-ru")

    /** v2-era staging dir orphaned by a download killed mid-unpack; swept alongside legacyDir(). */
    private fun legacyStagingDir() = File(context.filesDir, "asr/.staging-gigaam-v2-ru")

    private fun vadFile() = File(context.filesDir, "asr/silero_vad.onnx")

    private fun downloadDir() = File(context.filesDir, "asr/.downloads")
    private fun archivePart() = File(downloadDir(), "gigaam-v3-ru.tar.bz2.part")
    private fun vadPart() = File(downloadDir(), "silero_vad.onnx.part")
    private val provisioningPrefs = context.getSharedPreferences("gigaam_provisioning", Context.MODE_PRIVATE)

    fun modelPath(): String = File(baseDir(), "model.int8.onnx").absolutePath

    fun tokensPath(): String = File(baseDir(), "tokens.txt").absolutePath

    fun vadPath(): String = vadFile().absolutePath

    private fun isModelComplete(dir: File): Boolean =
        File(dir, "model.int8.onnx").let { it.isFile && it.length() > 0 } &&
            File(dir, "tokens.txt").let { it.isFile && it.length() > 0 }

    private fun isVadComplete(): Boolean = vadFile().let { it.isFile && it.length() > 0 }

    fun isReady(): Boolean = isModelComplete(baseDir()) && isVadComplete()

    data class StatusSnapshot(
        val progress: Int,
        val active: Boolean,
        val failed: Boolean,
    )

    fun statusSnapshot(): StatusSnapshot {
        if (isReady()) return StatusSnapshot(progress = 100, active = false, failed = false)
        return StatusSnapshot(
  progress = provisioningPrefs.getInt("progress", -1),
  active = provisioningPrefs.getBoolean("active", false),
  failed = provisioningPrefs.getBoolean("failed", false),
        )
    }

    private fun setProvisioningState(progress: Int, active: Boolean, failed: Boolean) {
        provisioningPrefs.edit()
  .putInt("progress", progress)
  .putBoolean("active", active)
  .putBoolean("failed", failed)
  .apply()
    }

    /** Serializes all disk mutations of the model dir / vad file: a delete can never
     *  interleave with download's commit (unpack / rename) sections, so a cancelled
     *  download cannot recreate files the user just deleted. */
    internal val diskMutex = Mutex()

    suspend fun delete() {
    diskMutex.withLock {
        baseDir().deleteRecursively()
        stagingDir().deleteRecursively()
        legacyDir().deleteRecursively()
        legacyStagingDir().deleteRecursively()
        vadFile().delete()
        downloadDir().deleteRecursively()
    }
    provisioningPrefs.edit().clear().apply()
}

    suspend fun download(onProgress: (Int) -> Unit): Result<Unit> =
    withContext(Dispatchers.IO) {
        if (isReady()) {
  setProvisioningState(100, active = false, failed = false)
  onProgress(100)
  return@withContext Result.success(Unit)
        }

        setProvisioningState(statusSnapshot().progress.coerceAtLeast(0), active = true, failed = false)
        runCatching {
  downloadDir().mkdirs()

  // Keep a completed model while retrying only a failed/missing VAD download.
  if (!isModelComplete(baseDir())) {
      downloadToFileResume(MODEL_URL, archivePart()) { pct ->
          val overall = (pct * 92) / 100
          setProvisioningState(overall, active = true, failed = false)
          onProgress(overall)
      }
      coroutineContext.ensureActive()
      diskMutex.withLock {
          coroutineContext.ensureActive()
          val staging = stagingDir()
          val target = baseDir()
          staging.deleteRecursively()
          staging.mkdirs()
          try {
              untarFlatten(archivePart(), staging)
              coroutineContext.ensureActive()
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
      setProvisioningState(96, active = true, failed = false)
      onProgress(96)
  }

  coroutineContext.ensureActive()
  if (!isVadComplete()) {
      downloadToFileResume(VAD_URL, vadPart()) { pct ->
          val overall = 97 + (pct * 2) / 100
          setProvisioningState(overall, active = true, failed = false)
          onProgress(overall)
      }
      coroutineContext.ensureActive()
      diskMutex.withLock {
          coroutineContext.ensureActive()
          check(vadPart().length() > 0) { "downloaded VAD file is empty" }
          vadFile().delete()
          check(vadPart().renameTo(vadFile())) { "failed to publish VAD file" }
      }
  }

  check(isReady()) { "GigaAM publish finished but readiness check failed" }
  archivePart().delete()
  vadPart().delete()
  setProvisioningState(100, active = false, failed = false)
  onProgress(100)
        }.onFailure { error ->
  if (error is CancellationException) {
      // Deliberately leave active=true: START_STICKY can resume the .part file.
      throw error
  }
  setProvisioningState(statusSnapshot().progress.coerceAtLeast(0), active = false, failed = true)
        }
    }

    private suspend fun downloadToFileResume(url: String, dest: File, onProgress: (Int) -> Unit) {
        dest.parentFile?.mkdirs()
        var existing = if (dest.isFile) dest.length() else 0L
        val request = Request.Builder().url(url).apply {
  if (existing > 0L) header("Range", "bytes=$existing-")
        }.build()

        http.newCall(request).execute().use { response ->
  if (existing > 0L && response.code == 416) {
      val remoteSize = response.header("Content-Range")
          ?.substringAfter("*/", "")
          ?.toLongOrNull()
      if (remoteSize != null && remoteSize == existing) {
          onProgress(100)
          return
      }
      dest.delete()
      return downloadToFileResume(url, dest, onProgress)
  }
  if (!response.isSuccessful) error("HTTP ${response.code}")
  val body = response.body ?: error("empty response body")
  val append = existing > 0L && response.code == 206
  if (existing > 0L && !append) {
      dest.delete()
      existing = 0L
  }
  val remaining = body.contentLength()
  val total = if (remaining > 0L) existing + remaining else -1L
  var read = existing
  body.byteStream().use { input ->
      FileOutputStream(dest, append).use { output ->
          val buffer = ByteArray(64 * 1024)
          var lastProgress = -1
          while (true) {
              coroutineContext.ensureActive()
              val count = input.read(buffer)
              if (count < 0) break
              output.write(buffer, 0, count)
              read += count
              if (total > 0L) {
                  val progress = ((read * 100L) / total).toInt().coerceIn(0, 100)
                  if (progress != lastProgress) {
                      lastProgress = progress
                      onProgress(progress)
                  }
              }
          }
          output.fd.sync()
      }
  }
  check(total <= 0L || dest.length() == total) {
      "incomplete download: ${dest.length()} of $total bytes"
  }
        }
    }

    /** Archive has a single top-level folder; flatten it into [target].
     *  Tar Slip guard mirrors TtsModelManager.untarFlatten. Suspend: the model is a
     *  single ~226 MiB entry and diskMutex is held for the whole unpack, so the
     *  per-entry copy loop must stay cancellable (chunked copy + ensureActive). */
    internal suspend fun untarFlatten(archive: File, target: File) {
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
                        if (canonicalOut.path != canonicalTarget.path &&
                            !canonicalOut.path.startsWith(canonicalTarget.path + File.separator)) {
                            entry = tar.nextEntry; continue
                        }
                        if (entry.isDirectory) outFile.mkdirs()
                        else {
                            outFile.parentFile?.mkdirs()
                            outFile.outputStream().use { out ->
                                val buf = ByteArray(64 * 1024)
                                while (true) {
                                    coroutineContext.ensureActive()
                                    val n = tar.read(buf); if (n < 0) break
                                    out.write(buf, 0, n)
                                }
                                // fsync before the staging dir is rename-published: an
                                // abrupt power-off after the rename must not leave a
                                // "complete" model dir whose data blocks are garbage.
                                out.fd.sync()
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

        /** Percentage of the combined progress spent on the (much larger) model archive;
         *  the remainder covers the small standalone VAD file. */
        private const val MODEL_WEIGHT = 99
    }
}
