package com.bydmate.app.voice

import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlin.math.sqrt

/**
 * Low-level DiLink3 microphone probe used only by the diagnostic UI.
 * It bypasses VoiceController and GigaAM and tests Android AudioRecord sources one by one.
 */
object DiLink3AudioSourceProbe {
    private const val TAG = "DiLink3MicProbe"
    private const val SAMPLE_RATE = 16_000
    private const val READ_SAMPLES = 1_600

    data class Result(
        val source: Int,
        val name: String,
        val init: String,
        val start: String,
        val read: String,
        val samples: Int,
        val peak: Int,
        val rms: Int,
        val error: String = "",
    ) {
        fun summary(): String = buildString {
            append(name)
            append(": init=").append(init)
            append(" start=").append(start)
            append(" read=").append(read)
            if (samples > 0) append(" n=").append(samples).append(" peak=").append(peak).append(" rms=").append(rms)
            if (error.isNotBlank()) append(" err=").append(error)
        }
    }

    private val sources = listOf(
        MediaRecorder.AudioSource.VOICE_RECOGNITION to "VOICE_RECOGNITION(6)",
        MediaRecorder.AudioSource.VOICE_COMMUNICATION to "VOICE_COMMUNICATION(7)",
        MediaRecorder.AudioSource.MIC to "MIC(1)",
        MediaRecorder.AudioSource.UNPROCESSED to "UNPROCESSED(9)",
        MediaRecorder.AudioSource.DEFAULT to "DEFAULT(0)",
    )

    suspend fun run(): List<Result> = withContext(Dispatchers.IO) {
        val minBuf = AudioRecord.getMinBufferSize(
            SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        )
        val bufferBytes = minBuf.coerceAtLeast(SAMPLE_RATE * 2)

        sources.map { (source, name) -> probeOne(source, name, bufferBytes) }
    }

    private fun probeOne(source: Int, name: String, bufferBytes: Int): Result {
        var record: AudioRecord? = null
        try {
            record = AudioRecord(
                source,
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                bufferBytes,
            )
            if (record.state != AudioRecord.STATE_INITIALIZED) {
                return Result(source, name, "FAIL", "-", "-", 0, 0, 0, "state=${record.state}")
                    .also { Log.w(TAG, it.summary()) }
            }

            try {
                record.startRecording()
            } catch (t: Throwable) {
                return Result(source, name, "OK", "FAIL", "-", 0, 0, 0, shortError(t))
                    .also { Log.w(TAG, it.summary()) }
            }

            if (record.recordingState != AudioRecord.RECORDSTATE_RECORDING) {
                return Result(source, name, "OK", "FAIL", "-", 0, 0, 0, "recordingState=${record.recordingState}")
                    .also { Log.w(TAG, it.summary()) }
            }

            val buf = ShortArray(READ_SAMPLES)
            val n = record.read(buf, 0, buf.size)
            if (n <= 0) {
                return Result(source, name, "OK", "OK", "FAIL($n)", n, 0, 0, "AudioRecord.read=$n")
                    .also { Log.w(TAG, it.summary()) }
            }

            var peak = 0
            var sumSquares = 0.0
            for (i in 0 until n) {
                val v = kotlin.math.abs(buf[i].toInt())
                if (v > peak) peak = v
                sumSquares += v.toDouble() * v.toDouble()
            }
            val rms = sqrt(sumSquares / n).toInt()
            return Result(source, name, "OK", "OK", "OK", n, peak, rms)
                .also { Log.i(TAG, it.summary()) }
        } catch (t: Throwable) {
            return Result(source, name, "FAIL", "-", "-", 0, 0, 0, shortError(t))
                .also { Log.w(TAG, it.summary(), t) }
        } finally {
            runCatching { record?.stop() }
            runCatching { record?.release() }
        }
    }

    private fun shortError(t: Throwable): String = "${t::class.java.simpleName}: ${t.message ?: "no message"}"
}
