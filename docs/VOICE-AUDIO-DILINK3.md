# DiLink 3 voice audio baseline

This file records the field-proven audio behavior for the BYD ATTO 3 / DiLink 3 voice path. Treat it as a regression contract when rebasing voice or Alice integration.

## Field confirmation

Confirmed on 2026-09-24 with BYDMate 3.17.5 build 64023 on:

- BYD ATTO 3
- DiLink 3.0
- Android 10 / SDK 29
- fingerprint: `BYD-AUTO/DiLink3.0/DiLink3.0:10/QKQ1.210910.001/eng.build.20260610.070138:user/release-keys`

The diagnostic log showed:

```text
music_stream: vol=6/39 active=true
06:55:12.824 I/AudioCapture: duckMusic: 6 -> 1
```

The user confirmed in the car that Local BYDMate correctly lowered the music while listening.

## Local BYDMate listening contract

DiLink 3 media does not reliably honor `AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK`. The working path is explicit `STREAM_MUSIC` volume control.

Required behavior:

1. Local listening starts.
2. If music is active and above the duck target, save the exact current media volume.
3. Set `STREAM_MUSIC` to `DUCK_VOLUME_INDEX = 1`.
4. Keep playback alive. Do not send MEDIA_PAUSE / MEDIA_PLAY.
5. Restore the saved user volume when the Local voice session ends.
6. Preserve the persisted pre-duck marker so a process death cannot leave media stuck quiet.

Do not replace this with audio-focus-only ducking unless an on-car test proves equivalent behavior.

## Local reply volume

Build 64023 exposed a second DiLink 3 property: the Local Sherpa TTS fallback is also rendered through the effective MUSIC path.

Keeping `STREAM_MUSIC = 1` during TTS therefore makes the assistant nearly inaudible even though synthesis succeeds.

The build 64024 contract is two-level ducking:

- listening: `DUCK_VOLUME_INDEX = 1`
- Local spoken reply: at most `LOCAL_REPLY_DUCK_VOLUME_INDEX = 4`, but never above the user's pre-duck/explicitly selected media level
- after the reply drains and continuous listening resumes: return to index 1
- when the Local session ends: restore the exact pre-duck user volume

The reply level is still deliberately below the user's original music volume. It is not a general media-volume change and must not overwrite the final restore target.

## Evidence for the 64023 silent-reply regression

The same field log showed that TTS was not disabled or missing:

```text
06:55:24.237 I/SherpaTtsEngine: enqueue: len=67 engineRate=22050
06:55:24.246 I/SherpaTtsEngine: DiLink3 detected: skipping BYD stream 17
06:55:24.295 I/SherpaTtsEngine: track created: rate=22050 state=1 viaFallback=true
06:55:29.960 I/SherpaTtsEngine: synth done (queued): samples=93124 generation ok=true
```

The engine synthesized the reply. The regression was that the shared media path remained at index 1 while playback occurred.

## Alice limitation

Build 64023 did not produce reliable media ducking for Alice.

Alice uses an external Yandex audio path that shares/competes with media differently from Local BYDMate. Physically forcing `STREAM_MUSIC` down can also attenuate Alice itself, while audio-focus-only ducking is ignored by the head unit.

Until a Yandex-specific stream/focus mechanism is proven on the car:

- `beginExternalAssistantAudio()` and `endExternalAssistantAudio()` stay neutral
- do not claim that Alice ducks media
- do not reuse the Local index-1 listening workaround for Alice

## Local agent latency baseline

Voice audio changes must not regress the field-proven fast Local agent path documented in commit `2b4922a7ab9ae235459ae8e5e583d973d39b1c63`.

Required pieces remain:

- `ttsEngine.warmUp()` starts before/in parallel with the external LLM wait
- streamed sentence queue remains enabled
- deterministic vehicle/app/navigation commands stay local
- direct vehicle-state questions use local snapshot answers where unambiguous
- OpenRouter latency-oriented settings remain enabled

## Regression checklist

Before accepting a voice build on DiLink 3:

1. Start music at a normal audible level.
2. Invoke Local BYDMate.
3. Confirm log contains `duckMusic: <saved> -> 1` and music becomes effectively quiet.
4. Ask a Local question that requires speech.
5. Confirm the reply raises only to the Local reply duck level and is audible.
6. Confirm continuous listening returns to index 1 after speech.
7. End the Local session and confirm the exact original media volume returns.
8. Repeat with music initially off. BYDMate must not raise the volume unexpectedly.
9. Change media volume explicitly during a live Local session and verify final restore honors the new user-selected volume.
10. Do not mark Alice ducking as supported unless separately proven on the car.
