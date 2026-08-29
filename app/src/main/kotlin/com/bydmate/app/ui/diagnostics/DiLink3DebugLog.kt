package com.bydmate.app.ui.diagnostics

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import androidx.core.content.FileProvider
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object DiLink3DebugLog {
    private const val DIR = "dilink3-debug"
    private const val FILE = "dilink3-voice-debug.log"
    private const val MAX_BYTES = 512 * 1024L
    private val lock = Any()
    private val stamp = SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS", Locale.US)

    private fun file(context: Context): File {
        val dir = File(context.cacheDir, DIR).apply { mkdirs() }
        return File(dir, FILE)
    }

    fun clear(context: Context) = synchronized(lock) {
        runCatching { file(context).writeText("") }
    }

    fun log(context: Context, event: String, detail: String = "") {
        val line = buildString {
            append(stamp.format(Date()))
            append(" | ")
            append(event)
            if (detail.isNotBlank()) {
                append(" | ")
                append(detail.replace('\n', ' '))
            }
            append('\n')
        }
        synchronized(lock) {
            runCatching {
                val f = file(context)
                if (f.exists() && f.length() > MAX_BYTES) {
                    val bytes = f.readBytes()
                    val keepFrom = (bytes.size / 2).coerceAtLeast(0)
                    f.writeBytes(bytes.copyOfRange(keepFrom, bytes.size))
                }
                f.appendText(line)
            }
        }
    }

    fun shareToTelegram(context: Context): Boolean {
        val f = file(context)
        if (!f.exists() || f.length() == 0L) log(context, "LOG_EXPORT", "log was empty")
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", f)
        val base = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_STREAM, uri)
            putExtra(Intent.EXTRA_TEXT, "BYDMate DiLink3 voice debug log")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        }

        // One tap when Telegram is installed; otherwise fall back to Android's share chooser.
        return try {
            context.startActivity(Intent(base).setPackage("org.telegram.messenger"))
            true
        } catch (_: ActivityNotFoundException) {
            runCatching {
                context.startActivity(Intent.createChooser(base, "Send BYDMate log").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            }.isSuccess
        }
    }
}
