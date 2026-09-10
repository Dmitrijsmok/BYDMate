#!/usr/bin/env python3
from pathlib import Path

VERSION_CODE = "60034"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Build84 anchor missing: {label}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# 1) Monotonic field identity over Build83.
# ---------------------------------------------------------------------------
p = Path("app/build.gradle.kts")
s = p.read_text()
s = replace_once(s, "        versionCode = 60033", f"        versionCode = {VERSION_CODE}", "versionCode")
s = replace_once(
    s,
    '            versionNameSuffix = "-dilink3-production-build83"',
    '            versionNameSuffix = "-dilink3-production-build84"',
    "versionNameSuffix",
)
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = replace_once(
    s,
    'android:label="BYDMate DiLink3 Build83"',
    'android:label="BYDMate DiLink3 Build84"',
    "manifest label",
)
p.write_text(s)


# ---------------------------------------------------------------------------
# 2) Field data: 4 TTS threads made normalized RTF ~26% worse on this DiLink3.
#    Go back to the proven 2-thread setting. Keep the helper so Build83 logging remains intact.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/voice/SherpaTtsEngine.kt")
s = p.read_text()
s = replace_once(
    s,
    '''    private fun sherpaThreadCount(): Int =
        Runtime.getRuntime().availableProcessors().coerceIn(2, 4)
''',
    '''    private fun sherpaThreadCount(): Int = 2
''',
    "restore two TTS threads",
)

# ---------------------------------------------------------------------------
# 3) Safe latency overlap: startQueue() is created BEFORE AgentOrchestrator.ask(), while the
#    network is still waiting for first content. Previously the sherpa model was only created
#    after the first completed sentence arrived. Prewarm it on the existing single TTS worker.
#
#    This is NOT Build82 PCM streaming: no AudioTrack is started and no partial PCM is played.
#    The existing safe full-sentence generation/write path is unchanged. The prewarm job simply
#    hides model-init time behind the Agent API wait; enqueue jobs naturally run after it on the
#    same executor, so there is no concurrent access to OfflineTts.
# ---------------------------------------------------------------------------
old = '''    override fun startQueue(): TtsEngine.SpeechQueue? {
        if (!isReady()) return null
        val myGen = generation.incrementAndGet()
        return QueuedSpeech(myGen)
    }
'''
new = '''    override fun startQueue(): TtsEngine.SpeechQueue? {
        if (!isReady()) return null
        val myGen = generation.incrementAndGet()
        worker.execute {
            if (generation.get() != myGen || tts != null) return@execute
            val warmed = createTts()
            if (warmed != null && generation.get() == myGen) {
                tts = warmed
                Log.i(
                    TAG,
                    "Build84 TTS prewarm ready: voice=${selectedVoice().id} " +
                        "rate=${warmed.sampleRate()} threads=${sherpaThreadCount()}",
                )
            } else {
                runCatching { warmed?.release() }
                Log.w(TAG, "Build84 TTS prewarm skipped/failed: generation=${generation.get()} expected=$myGen")
            }
        }
        return QueuedSpeech(myGen)
    }
'''
s = replace_once(s, old, new, "TTS prewarm during Agent API wait")
p.write_text(s)


# ---------------------------------------------------------------------------
# 4) Make the intended low-latency path explicit in the agent prompt. The app ALREADY streams
#    completed sentences from SSE to TtsEngine.SpeechQueue while the LLM continues generating.
#    Ask the model to put the answer's useful fact in a short first sentence, so the first safe
#    TTS unit is available and synthesizable sooner without unsafe token/PCM streaming.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/agent/AgentOrchestrator.kt")
s = p.read_text()
old = '''            ответ читается вслух: отвечай по-русски, максимум 1-2 коротких предложения,
            без списков и markdown.
'''
new = '''            ответ читается вслух: отвечай по-русски, максимум 1-2 коротких предложения,
            без списков и markdown. Первое предложение начинай сразу с ответа и делай максимально
            коротким и самостоятельным; детали, если нужны, вынеси во второе предложение.
'''
s = replace_once(s, old, new, "short first spoken sentence prompt")
p.write_text(s)

print("Build84 applied: 2-thread sherpa + safe TTS prewarm + short-first-sentence streaming")
