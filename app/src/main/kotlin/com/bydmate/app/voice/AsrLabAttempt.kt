package com.bydmate.app.voice

data class AsrLabResult(
    val timestampMs: Long,
    val preRollMs: Int,
    val transcript: String,
    val error: String?,
    val stagesNs: List<Long?>,
    val segmentStart: Long?,
    val vadSamples: Int?,
    val decodedSamples: Int?,
)

class AsrLabAttempt(
    private var preRollMs: Int,
    private val nanoTime: () -> Long = System::nanoTime,
    private val timestampMs: Long = System.currentTimeMillis(),
) {
    private val pttNs = nanoTime()
    @Volatile private var openingNs: Long? = null
    @Volatile private var readyNs: Long? = null
    @Volatile private var firstPcmNs: Long? = null
    private var vadNs: Long? = null
    private var decodeNs: Long? = null
    private var completedNs: Long? = null
    private var transcript = ""
    private var segmentStart: Long? = null
    private var vadSamples: Int? = null
    private var decodedSamples: Int? = null

    fun opening() { openingNs = nanoTime() }
    fun ready() { readyNs = nanoTime() }
    fun firstPcm() { if (firstPcmNs == null) firstPcmNs = nanoTime() }
    fun speechStart(selectedMs: Int) {
        if (vadNs == null) {
            preRollMs = selectedMs
            vadNs = nanoTime()
        }
    }
    fun decodeStart(start: Long, original: Int, extended: Int) {
        segmentStart = start
        vadSamples = original
        decodedSamples = extended
        decodeNs = nanoTime()
    }
    fun decoded(text: String) {
        transcript = text
        if (completedNs == null) completedNs = nanoTime()
    }
    fun result(error: String? = null) = AsrLabResult(
        timestampMs, preRollMs, transcript, error,
        listOf(pttNs, openingNs, readyNs, firstPcmNs, vadNs, decodeNs, completedNs),
        segmentStart, vadSamples, decodedSamples,
    )
}

internal fun labCsv(results: List<AsrLabResult>, version: String, versionCode: Int, baseline: String): String {
    val header = listOf("timestamp_unix_ms", "version", "version_code", "baseline_sha", "sample_rate", "pre_roll_ms",
        "transcript", "error", "ptt_ns", "record_open_ns", "record_ready_ns", "first_pcm_ns", "vad_start_ns",
        "decode_start_ns", "decode_complete_ns", "ptt_to_open_ms", "open_to_ready_ms", "ready_to_pcm_ms",
        "pcm_to_vad_ms", "vad_to_decode_ms", "decode_ms", "ptt_to_complete_ms", "vad_segment_start_sample",
        "vad_samples", "decoded_samples", "vad_threshold", "vad_min_silence_s", "vad_min_speech_s", "vad_max_speech_s")
    fun cell(value: Any?) = "\"${value?.toString().orEmpty().replace("\"", "\"\"")}\""
    val rows = results.map { result ->
        val stages = result.stagesNs
        val intervals = stages.zipWithNext { a, b -> if (a != null && b != null) (b - a) / 1_000_000.0 else null }
        val total = stages.last()?.let { (it - stages.first()!!) / 1_000_000.0 }
        (listOf(result.timestampMs, version, versionCode, baseline, 16000, result.preRollMs, result.transcript, result.error) +
            stages + intervals + listOf(total, result.segmentStart, result.vadSamples, result.decodedSamples,
                GigaAmAsrEngine.VAD_THRESHOLD, GigaAmAsrEngine.VAD_MIN_SILENCE_SEC,
                GigaAmAsrEngine.VAD_MIN_SPEECH_SEC, GigaAmAsrEngine.VAD_MAX_SPEECH_SEC)).joinToString(",", transform = ::cell)
    }
    return (listOf(header.joinToString(",")) + rows).joinToString("\r\n", postfix = "\r\n")
}
