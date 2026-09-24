# BYDMate Alice Integration Recovery Status

Last updated: 2026-09-24

This document is the persistent recovery baseline for the Alice/BYDMate integration in this fork.
Read it before starting any new branch, rebase, or APK build.

## Executive status

Build 64023 is CI-green but NOT a field-stable baseline. The 2026-09-24 ATTO 3 / DiLink 3 logs established several facts that future work must preserve exactly:

- **Local physical ducking works in the car.** At 06:55:12.824 the field log records `AudioCapture: duckMusic: 6 -> 1`. This is now the field-proven Local listening mechanism. Do not remove it or replace it with audio-focus-only ducking.
- Local TTS was generated but effectively inaudible while the shared MUSIC route remained at index 1. The log shows `SherpaTtsEngine enqueue` followed by successful `synth done`, so the failure is output audibility, not a missing TTS call.
- Local TTS synthesis itself is also slow for long sentences on this head unit: 67 characters took about 5.7 s (06:55:24.237 -> 06:55:29.960), and 71 characters took about 4.8 s (06:56:03.893 -> 06:56:08.724).
- The active `ttsEngine.warmUp()`, streaming queue, OpenRouter minimal-reasoning settings and latency provider sorting are still present. The 64023 regression is therefore not explained by losing those switches.
- A logged outside-temperature phrase `которая на улице` unnecessarily fell through to OpenRouter. It must be answered from the live snapshot locally.
- A logged generic navigation request first failed as app `навигатор`, then failed as `Яндекс Карты`, and only the third LLM tool call finally opened the selected Google Maps navigator. The launch succeeded, but the conversational result was misleading. Generic `навигатор/навигация` must resolve directly to the selected default navigator and bypass the LLM.
- Alice ducking remains unresolved after the 64023 field test. It is intentionally out of scope for 64024 so the field-proven Local duck/TTS recovery can be validated in isolation; keep the existing Alice audio path unchanged until a separate hardware test proves a replacement.
- **Product decision 2026-09-24:** BYDMate navigation through the Alice bridge is disabled for now. Local BYDMate navigation remains supported. Alice must not enqueue route/search/show, navigator-app, or cluster-navigation actions until a separately field-proven Alice navigation path exists.

### 64024 recovery contract

The next field build uses a two-level Local audio policy:

- Local listening: physical `STREAM_MUSIC = 1` (field proven).
- Local TTS: while the same duck still owns the original restore target, temporarily raise the shared MUSIC route to at most index 4 so the assistant is audible.
- Next Local `SpeechStart`: reassert index 1 without creating another duck owner.
- Session teardown: restore the original saved media level exactly once.
- Alice audio ducking is intentionally unchanged in 64024 and remains a separate field-recovery item.

This is intentionally a minimal adaptation of the proven physical duck. It does not change the saved restore target and does not reintroduce media pause/play.

## Vehicle / runtime target

Field-test vehicle:

- BYD ATTO 3
- DiLink 3.0
- Android 10 / SDK 29
- Locale: Russian

Current package target:

- `com.bydmate.app`

Stable Alice signing certificate SHA-256:

`B8:39:BC:11:CF:AD:61:EC:6A:89:DE:10:DC:0E:5E:B7:4C:BA:25:C5:7D:A1:16:AD:E3:0B:F4:A8:9D:70:C0:54`

Never commit the keystore or passwords. New APKs that must install over the current Alice build must use the same stable certificate.

---

# Field-confirmed working baselines

## 1. Navigation: Alice Build 5.3

Field confirmation date: 2026-09-17.

User-confirmed behavior:

- Local BYDMate command equivalent to "открой навигацию" opened Waze.
- Alice command "Алиса, открой навигацию" also opened Waze.
- User explicitly confirmed that navigation opened successfully for both assistant paths.

Historical identity:

- Alice Build 5.3
- upstream base: BYDMate 3.16.0
- versionCode: 64014
- versionName: `3.16.0-alice5.3-upstream-rebase`

Historical workflow:

- `.github/workflows/alice-build5-3.yml`

Important invariant in that workflow:

- it explicitly verifies `app.waze.open` in `AliceAppCommandDispatcher.kt`.

The navigation behavior from Build 5.3 is the field-proven reference.

Use its semantic/app-dispatch behavior as the specification. Do not blindly copy its old applicationId or old upstream tree.

---

## 2. Music ducking: Alice 4.8 behavior carried into 5.3

Field confirmation date: 2026-09-18.

User initially suspected that ducking was missing, then tested with loud music and confirmed that the music really became quieter while speaking/listening to the assistant.

The proven implementation is the manual external-Alice duck restored in Alice 4.8 and preserved through 5.3.

Historical patch:

- `.github/alice-build4-8-fix.py`

Key invariant:

- `BUILD8_MANUAL_DUCK_ENABLED target=4`

Underlying implementation originated in 4.5:

- Local BYDMate has its own physical STREAM_MUSIC duck/restore behavior.
- External Alice uses a milder physical STREAM_MUSIC target because Alice may render speech on the same effective stream.
- External Alice target: volume index 4.
- Original volume is saved before ducking and restored at lifecycle exit.
- Repeated activation must NOT stack physical volume reductions.
- A safety timeout prevents media being left permanently ducked.
- Leaving Yandex, accessibility unbind and accessibility destroy restore the original media volume.

Historical implementation references:

- `.github/alice-build4-5-cold-chain-guard-duck.py`
- `.github/alice-build4-8-fix.py`
- `.github/alice-build4-9-runner.py`
- `.github/alice-build5-3-runner.py`

Build 5.3 explicitly checked that the 4.8 duck survived the rebase:

`grep -R 'BUILD8_MANUAL_DUCK_ENABLED target=4' ...`

This is the authoritative behavior for external-Alice ducking.

---

## 3. Build 95: TTS responsiveness / issue #222 reference

Build 95 is important for TTS responsiveness, not for final music ducking.

Historical identity:

- Alice 4.7 Build95 recovery
- versionCode: 64008
- versionName contains `alice4.7-build95-recovery`

User-confirmed property:

- the TTS agent accepted information and responded quickly enough that issue #222 was considered solved in this build line.

Do NOT use Build 95 as the music ducking reference.

The user explicitly reported that music was not being ducked there. Alice 4.8 was created to restore the working manual duck.

Therefore the recovery references are:

- Build 5.3 = navigation/app bridge
- Build 4.8 -> 5.3 = music ducking
- Build 95 = TTS warm-path / issue #222 responsiveness

---

# Fast Local Agent / issue #222 baseline

This section is mandatory context for any future rebase. The local agent became fast because several latency fixes worked together. Do not reduce this history to "Build95 was fast".

## Field confirmation

User confirmation date: 2026-09-20.

The user explicitly confirmed that in the Build95 line the issue #222 behavior was fixed: after invoking the local TTS agent, it accepted the spoken information and started answering without the long extra pause that existed before.

Build95 is therefore the field-proven responsiveness reference.

Historical identity:

- Alice 4.7 Build95 recovery
- versionCode: 64008
- versionName contains `alice4.7-build95-recovery`

## The important implementation detail: warm TTS while the LLM is thinking

The key regression guard later preserved in `VoiceController.agentFallback()` is:

`if (gate.ttsEnabled()) runCatching { ttsEngine.warmUp() }`

This call must happen before / in parallel with the external LLM request, not after the final text has already arrived.

Why it matters:

- `SherpaTtsEngine.warmUp()` creates/warms the local TTS engine on its own worker.
- The LLM network request is already consuming time.
- Running TTS warm-up during that network wait hides the local model-load latency behind the LLM latency.
- Therefore the first spoken sentence no longer pays a separate cold TTS startup penalty after the model has answered.

This behavior first appeared in the fast Build84/85 path and was inherited by Build95.

Historical measured behavior around Build85:

- first model content approximately 1.8 s
- first phrase approximately 1.9 s

The important point is not the exact millisecond number. The key property is that there was almost no second "cold TTS" delay after model text became available.

## Known regression

A later refactor removed the active `ttsEngine.warmUp()` call from `VoiceController.agentFallback()` even though `SherpaTtsEngine.warmUp()` itself still existed.

That created a deceptive state:

- the warm-up implementation was still present in the codebase,
- but the real agent path no longer invoked it at the right time,
- so the first answer after idle again paid cold TTS initialization cost.

This exact regression must be checked after every rebase.

A source snapshot where the correct regression guard is visible:

- commit `29d1e95afc2c2f72d6a7e8034fbf9f8a826e1340`

The relevant comment in that source explicitly identifies it as the regression guard from the fast Build84/85 path.

## Start TTS from streamed sentences, not from the final full answer

The fast path also used the TTS speech queue:

- `ttsEngine.startQueue()`
- stream sentences from `agentOrchestrator.ask(...)`
- `queue.enqueue(sentence)`
- `queue.finish()`

The assistant therefore begins synthesizing/speaking the first complete streamed sentence while the remaining answer is still arriving.

Do NOT regress to:

1. wait for the entire LLM answer,
2. then synthesize the complete response,
3. then start playback.

That pattern was observed to create multi-second TTS latency even when OpenRouter itself was reasonably fast.

## Keep deterministic commands out of the LLM

A second major contributor to perceived speed is the local routing split.

Commands that can be resolved locally must stay local:

- vehicle controls
- navigation/app launches with deterministic mapping
- direct local vehicle-state answers where the snapshot contains the answer

These should follow:

`ASR -> local NLU/resolver -> local action -> short local acknowledgement`

and must NOT become:

`ASR -> OpenRouter -> tool selection -> local action -> generated answer`

For a command such as a known vehicle control, the local path should remain effectively "command -> action -> Готово" and bypass OpenRouter entirely.

This is separate from the TTS warm-up fix. Both are required for the fast local-agent experience.

## Network/agent optimizations that were kept alongside the warm path

The fast line also retained latency-oriented LLM transport behavior:

- low/minimal reasoning effort for this automotive agent path
- latency-oriented model sorting where supported
- streaming responses
- prompt cache
- limited retry/fallback behavior
- one reusable / singleton OkHttp client instead of rebuilding the network stack per request

These optimizations help, but they are NOT a substitute for the TTS warm-up call.

A previous cold profile showed very large first-request latency after idle, improving over successive requests. The warm path was specifically designed so that the local TTS side did not add another cold-start delay on top of that network behavior.

## Important architectural rule

Alice and Local BYDMate are different voice paths.

The fast-local-agent fix belongs to the Local BYDMate agent path.

Do not remove or bypass Local TTS warm-up merely because Alice is now available as another assistant.

A rebase that makes Alice work but removes `ttsEngine.warmUp()` from Local `agentFallback()` is a regression.

## Required regression checks after every rebase

Before a new build is accepted:

1. Search `VoiceController.agentFallback()` and verify active `ttsEngine.warmUp()` before the LLM wait.
2. Verify the call is not inside a path that only runs after the LLM response has completed.
3. Verify `ttsEngine.startQueue()` still starts a sentence queue when TTS is enabled.
4. Verify streamed sentences are enqueued as they arrive.
5. Verify deterministic local commands do not unnecessarily call the external LLM.
6. Verify `SherpaTtsEngine.warmUp()` still performs real engine preparation and has not become a no-op.
7. Vehicle-test a genuine agent question after cold start / idle.
8. After the model's first text arrives, speech should begin without an additional obvious TTS wake-up pause.
9. Compare subjectively against the Build95 behavior if uncertain.

## Recovery priority

When porting the proven behavior to a new upstream base, preserve these pieces as a unit:

- Build95 / Build84-85 TTS warm-up timing
- streamed sentence queue
- deterministic local routing
- reusable low-latency LLM transport

Do not "simplify" the voice path by removing one of these before field validation.

---

# Historical patch chain worth preserving

The old patch/workflow chain is preserved under `.github/`.

Relevant files:

- `alice-build4-5-cold-chain-guard-duck.py`
- `alice-build4-7-fix.py`
- `alice-build4-8-fix.py`
- `alice-build4-8-runner.py`
- `alice-build4-9-stable.py`
- `alice-build4-9-runner.py`
- `alice-build5-0-command-bridge.py`
- `alice-build5-1-app-bridge.py`
- `alice-build5-2-upstream.py`
- `alice-build5-3-base-compat.py`
- `alice-build5-3-final.py`
- `alice-build5-3-runner.py`
- `alice-build5-4-sunroof-percent.py`
- `alice-build5-4-window-percent.py`
- `alice-build5-4-tiktok.py`

A historical commit that still contains this patch/workflow material is:

- `433c75f49aba8613a51ca35f1b44b885612f405c`

Important: treat this commit as an archive of the historical build definitions. Do not assume it is the exact unpacked final APK source tree.

---

# Current broken experimental branch

Branch:

- `rebase/alice-v3.17.5`

Final tested build commit:

- `4b3a4e0da8adf2eb5f8b8573456bb6318d1abf2d`

Build:

- versionName: 3.17.5
- versionCode: 64023

CI:

- unit tests: PASS
- Android Lint: PASS
- detekt: PASS
- full debug APK assembly: PASS

Field result:

- FAIL for navigation detection/opening
- FAIL for music ducking lifecycle

This is a critical reminder: CI green does not prove DiLink behavior.

## 64023 navigation failure

Observed in the vehicle:

- Waze is installed.
- Waze is selected.
- Assistant says Waze is not installed.

The exact device-side cause has NOT yet been proven.

Do not paper over this with more package heuristics before comparing the 5.3 dispatch path against actual DiLink package discovery.

## 64023 audio failure

Observed in the vehicle:

- Music is not reliably ducked into the background.
- Repeated assistant activation makes volume start from/approach zero.
- The assistant becomes effectively inaudible.

This means the 64023 duck ownership/restore lifecycle is wrong even though tests passed.

Do not use that implementation as the next audio baseline.

---

# Navigation requirements

Navigation is a separate concept from generic application launching.

Required behavior:

1. Settings show detected installed navigator apps.
2. User can choose the default navigator.
3. User can optionally enter an exact package name for a non-standard APK.
4. Generic route commands such as "построй маршрут" use the selected default navigator.
5. Explicit "открой Google Maps" opens Google Maps specifically and must NOT redirect to default Waze.
6. Explicit "открой Waze" opens Waze specifically.
7. Local BYDMate owns navigation in the current product configuration.
8. Alice navigation is disabled until a separately field-proven route is approved.
9. ReVanced/MicroG and other alternative packages may be supported by discovery/manual package configuration.

Important UX rule:

Google Maps is NOT an unrelated feature/button. It belongs inside the navigation selection/system.

---

# Audio requirements

Required DiLink 3 behavior:

1. Local BYDMate starts listening -> background music immediately becomes clearly quieter.
2. Music stays quieter while Local is processing and answering.
3. Alice starts listening -> background music immediately becomes clearly quieter.
4. Music stays quieter while Alice is listening/answering.
5. Music is not paused as the normal ducking mechanism.
6. Repeated activation must NOT reduce the volume again and again.
7. Original media volume is restored exactly once at lifecycle end.
8. Starting music after the assistant session opened must still lead to correct ducking.
9. Crash/unbind/destroy recovery must not leave media stuck at the duck target.
10. Assistant TTS remains clearly audible.

Do not rely only on `AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK`.

Field testing already showed that DiLink/Yandex Music does not reliably honor it.

The field-proven external-Alice duck target is 4 from the 4.8 implementation.

For Local, preserve physical duck/restore while also preserving the Build95 fast TTS/warm path so issue #222 does not return.

---

# PTT / assistant routing requirements

Desired interaction:

- single PTT press -> Local BYDMate
- double PTT press -> Alice
- double press must not allow Local and Alice to own the microphone simultaneously
- native BYD assistant remains disabled when takeover requires it

Any PTT timing change must be vehicle-tested because DiLink may emit non-obvious key sequences.

---

# Later functionality that should not be lost

When rebuilding from the proven baselines, preserve later valid functionality where compatible with the current upstream architecture:

- Alice bridge and worker communication
- dynamic window percentages
- sunroof percentages
- TikTok launcher
- dynamic/alternative launcher support
- Google Maps / Yandex Maps / 2GIS / Waze navigation
- temperature diagnostics
- TTS warm-up / issue #222 fix
- stable signing identity

Port semantics, not obsolete scaffolding.

---

# Recommended recovery strategy

Do NOT keep patching 64023 navigation/audio.

Start a clean recovery branch from the desired current upstream base and port the proven behaviors independently.

Suggested branch:

`recovery/alice-nav-audio-proven-baseline`

## Phase A - navigation

Use Build 5.3 as the behavioral specification.

1. Trace the complete 5.3 path for:
   - Local "open navigation"
   - Alice `app.waze.open`
   - actual package launch
2. Reimplement that path on current upstream with the smallest adaptation.
3. Add default navigator + detected list + optional manual package without changing explicit app semantics.
4. Vehicle-test navigation before changing audio.

## Phase B - audio

Use 4.8/5.3 manual duck as the behavioral specification.

1. Restore the exact idempotent external-Alice duck lifecycle.
2. Preserve crash-safe restore bookkeeping.
3. Preserve the Build95 fast TTS warm path.
4. Do not invent another owner/depth system unless field logs prove it is required.
5. Vehicle-test with loud Yandex Music.

## Phase C - later features

Only after field success, retain/port later features such as percentages, launcher discovery and diagnostics.

Do not combine another major upstream rebase and a new audio/navigation architecture into one untested step.

---

# Minimum field test before declaring a build stable

With Yandex Music playing loudly:

## Local

1. Single PTT -> Local.
2. Music becomes clearly quieter immediately.
3. Local recognizes speech.
4. Local answer remains audible.
5. Ending session restores exactly the original music volume.

Repeat the Local cycle several times.

The volume must return to the same original level every time and must never walk down toward zero.

## Alice

1. Double PTT -> Alice.
2. Local must not answer simultaneously.
3. Music becomes clearly quieter.
4. Alice stays audible.
5. Leaving Alice restores the exact original volume.

## Navigation

With Waze selected as default:

- "открой навигацию" -> Waze
- Alice navigation command -> no BYDMate navigation action is dispatched
- "открой Google Maps" -> Google Maps even though Waze is default
- "открой Waze" -> Waze even if another navigator is default
- "построй маршрут ..." -> selected default navigator

Manual package override must work for a non-standard navigator APK.

Only after these pass in the actual car should a build become the new stable baseline.

---

# Branching rule for all future work

Before starting a new Alice recovery/rebase branch:

1. Read this document.
2. Keep this document in the branch.
3. Treat the three proven baselines separately:
   - Build 5.3 navigation
   - Build 4.8/5.3 ducking
   - Build95 TTS responsiveness
4. Do not call behavior fixed based only on CI.
5. Add exact field results, build number and commit here when a new stable point is confirmed.

The next recovery branch should start from the desired current upstream revision and port, in order:

1. Build 5.3 navigation semantics
2. Build 4.8/5.3 duck lifecycle
3. Build95 TTS warm path
