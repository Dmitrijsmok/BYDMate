# v4.0.1 SpeechPreRoll laboratory

This experiment starts at upstream `v4.0.1`, commit
`b47ead7fc9f0741ed2d4b2ff61a785da337f0500` (upstream versionCode 508).
Application code from older fork branches and the rest of PR #261 are not imported.
In particular, this experiment does not add, restore, or alter Alice integration.
Only the fork's identity and permanent signing infrastructure are carried forward
from fork main `1b846609d7003bf9297f9a40b16c6584ebca7de6`.

## Build identity and signing

- Branch: `lab/v4.0.1-speech-preroll`; main is not changed.
- Package: `com.bydmate.dilink3.app`.
- versionCode: `100002`, following fork main's `100001`.
- versionName: `4.0.1-asr-lab.1`.
- APK: `BYDMate-dilink3-v4.0.1-asr-lab.1.apk` (arm64, Android 10+).
- Permanent certificate SHA-256:
  `B839BC11CFAD61EC6A89DE10DC0E5EB74CBA25C57DA116ADE30BF4A89D70C054`.

CI runs signing regression tests, all debug unit tests, Android lint and detekt
before the release job. Existing main signing restrictions remain intact. The lab
exception requires a push by `Dmitrijsmok` (including the rerun actor), in the owner
repository, to exactly the protected lab branch, using this branch's `ci.yml`.
PRs, other branches, workflow dispatch and unprotected lab pushes cannot sign.
The lab branch has the same deletion and non-fast-forward protections as main.

The script verifies private-key access and the pinned certificate before building,
then verifies APK signature, package, version, filename and release manifest flags.
Signing material is removed before staging. Signing-job caches are disabled.
Only the verified APK and `verification.json` are uploaded. The report includes
commit SHA, APK SHA-256, certificate SHA-256 and the build/check outcomes.
No new signing key is generated. Repository configuration or missing secrets must
be fixed by the owner if this path refuses signing; do not bypass the gates.

## Buffer behavior

PCM is mono, 16 kHz. Settings are exactly 0, 100, 200, 300, 400, 600, 800 and
1000 ms, default 0. The preference also applies to normal voice sessions; choose
0 to restore control behavior. A new value is latched at the next VAD speech-start
transition, including within an already running normal session.

Each ASR collection owns its ring and frozen prefix. The ring holds at most
16,000 float samples. At speech detection a snapshot of up to the selected duration
is frozen, so a long utterance cannot overwrite its onset. The snapshot ends at the
end of the frame that triggered detection. Before decoding, sherpa's absolute
`SpeechSegment.start` trims all overlap with the VAD's existing onset padding.
Previously consumed segment audio cannot become the next prefix. The ring plus
snapshot use at most 32,000 floats (128,000 bytes), separate from the existing VAD
and recognizer buffers. The temporary decode array is bounded by the VAD segment
plus at most 16,000 extra samples. No buffer/file work runs on the capture thread.

At 0 ms the original segment array is passed directly to the decoder. VAD values
remain threshold 0.4, silence 0.8 s, minimum speech 0.25 s and maximum speech 15 s.
Existing Android 10 spare-VAD prewarming is preserved. Cancellation/teardown drops
all per-collection buffer state; microphone restart creates a fresh collection.

## Screen and safe testing

Open **Settings → ASR Lab · SpeechPreRoll**. Select a duration, then tap
**PTT: начать один тест**. One phrase is recognized through the existing offline
capture, VAD and decoder, with a 30-second test limit. The exact transcript is
shown without normalization. Stop cancels the attempt. Leaving/backgrounding the
screen also cancels it. The model must already be installed; the lab does not
download models or contact the network.

The recognition-only runner has no command, application-launch, navigation,
automation, LLM or TTS dependencies. It bypasses normal voice routing and network
prewarming. The controller's existing busy reservation guards both paths. A lab
test is refused while normal listening or model warmup is active; physical PTT
does not start another listener during a lab attempt. Normal operation is unchanged
when the lab is inactive, apart from the explicitly selected pre-roll value.
Existing capture ducking and restoration are reused.

The latest 100 attempts are kept in memory until process exit. Clear deletes that
history. CSV export uses Android's document picker and UTF-8; the chosen destination
is the user's responsibility. No raw microphone audio is saved. Export before
restarting the app if results are needed. Transcripts may contain private speech.

## Measurements and their limits

Every attempt records wall-clock Unix milliseconds for human correlation and
monotonic nanoseconds (`System.nanoTime`) for stage timing:

1. Lab PTT button activation, before launching the test coroutine.
2. Capture startup, before buffer sizing, ducking and AudioRecord construction.
3. `startRecording()` returned (software readiness).
4. First successful PCM read, stamped on the capture thread.
5. First VAD speech-start detection on the ASR consumer thread.
6. Decode start and completion on the ASR consumer thread.

CSV includes all absolute stages, adjacent-stage intervals and PTT-to-completion,
selected pre-roll, exact transcript, error/cancellation/timeout, version, baseline,
16 kHz rate, original VAD start/sample count, decoded sample count and VAD tuning.
Missing stages remain empty. The screen shows each available stage relative to PTT.
Capture-thread instrumentation consists only of optional clock reads/primitive field
assignments. Normal capture calls use no timing observer.

The lab button is the PTT measured here, not the steering-wheel hardware edge.
PTT-to-capture includes model warmup when needed. Open-to-ready measures software
startup; ready-to-first-PCM includes the 100 ms capture chunk and device buffering.
`startRecording()` returning does not prove when acoustic capture began. Consumer
VAD/decode timings include scheduling and queued-audio latency. A slow JNI decode
cannot be interrupted mid-call, so stop/timeout may await its return.

These measurements can identify delayed startup and show how much recorded PCM was
added before the VAD segment. They cannot reveal acoustic speech onset, recover
speech spoken before recording, prove a syllable existed in retained PCM, or prove
that the decoder should have recognized it. Without an external reference recording
and alignment, a truncated transcript alone cannot separate VAD loss from decoding
error. No field improvement is claimed by this implementation.

## Field protocol (parked vehicle)

Install the verified APK as an update only if the installed package/certificate
match and installed versionCode is at most 100002. For an existing compatible
installation, use Android's package installer or:

```text
adb install -r BYDMate-dilink3-v4.0.1-asr-lab.1.apk
```

Compare 0, 200, 400, 600 and 800 ms, with at least ten repetitions per setting
and phrase. Keep cabin noise, microphone, speaking volume, PTT-to-speech delay and
model warm/cold conditions consistent. Rotate setting order between blocks to limit
practice/noise bias. Record those conditions separately alongside the exported CSV.

- «Открой навигатор»
- «Включи обогрев»
- «Какая температура на улице»
- «Сколько заряда осталось»

Review the exact transcripts and timing distributions, including failed attempts.
Repeat with deliberate short and long PTT-to-speech pauses to probe startup loss.
Export each block. Do not infer a winning value from a single successful phrase.
Actual measurements must be collected later on the BYD ATTO 3.

## Rollback

Immediately select 0 ms and stop/leave ASR Lab for baseline recognition behavior.
For binary rollback, prefer a permanent-key stable build with versionCode greater
than 100002. Android normally refuses a lower-code release APK as an update;
reinstalling fork main's 100001 requires a supported downgrade procedure or
backup/uninstall/reinstall (which removes app data). Do not uninstall without a
verified backup. This experiment adds no database migration.
