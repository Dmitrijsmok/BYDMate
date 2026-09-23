# BYDMate Alice Integration Recovery Status

Last updated: 2026-09-23

This document is the persistent recovery baseline for the Alice/BYDMate integration in this fork.
Read it before starting any new branch, rebase, or APK build.

## Executive status

The experimental branch `rebase/alice-v3.17.5` and build 64023 are NOT a field-proven baseline.

Build 64023 passed CI but failed in the actual BYD ATTO 3 / DiLink 3 car:

- Waze was selected and installed, but the assistant reported that Waze was not installed.
- Music ducking regressed. Repeated assistant activation drove media volume toward zero and the assistant became inaudible.
- Therefore 64023 must not be used as the behavioral reference for navigation or audio.

Do not keep patching these two areas from 64023. Restore the previously field-confirmed behavior described below.

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

# DiLink 3 native assistant takeover baseline

This section records the field-proven workaround that stopped the stock BYD voice assistant from competing with BYDMate/Alice on DiLink 3.

This must be preserved across rebases. The solution was not a single toggle. It required several defensive layers because DiLink 3 can still surface the native assistant even when one layer appears to be disabled.

## The original failure mode

Early takeover builds attempted to disable the BYD native assistant by calling:

`helperClient.setAppHidden("com.byd.vrassistant", true)`

but the privileged helper daemon only allowed:

`com.byd.autovoice`

As a result:

- BYDMate believed it had requested the disable,
- the privileged daemon rejected the real `com.byd.vrassistant` package,
- diagnostics continued showing the native assistant as ENABLED,
- the stock assistant could still appear and compete for the microphone/UI.

This was the core DiLink 3 package-hole bug.

## Field-proven fix: Alice 4.5

The decisive fix was added in:

- `.github/alice-build4-5-cold-chain-guard-duck.py`

Historical identity:

- Alice 4.5
- versionCode: 64006
- versionName: `3.15.2-alice4.5-cold-chain`

### 1. Privileged helper allowlist must include the real DiLink 3 package

`HelperDaemon.kt` was changed so the exact package:

`com.byd.vrassistant`

is explicitly accepted in addition to:

`com.byd.autovoice`

The operation remains deliberately narrow. Do not expand this into arbitrary package control.

The reversible command pair is:

- disable: `pm disable-user --user 0 <package>`
- enable: `pm enable <package>`

The helper only accepts the known assistant package and a boolean hidden state.

This was the fix that made the earlier `setAppHidden("com.byd.vrassistant", true)` call actually work.

## 2. Keep the old BYD voice package synchronized too

The takeover path must account for both known BYD voice packages:

- `com.byd.autovoice`
- `com.byd.vrassistant`

Historical sync patch:

- `.github/alice-build4-2-vrassistant-sync.py`

When the user enables native-assistant blocking, Settings applies the hidden state to both package families.

The diagnostic package set also included:

- `com.byd.autovoice`
- `com.byd.autovoice.engine`
- `com.byd.autovoice.tts`
- `com.byd.vrassistant`

Do not assume that disabling only `com.byd.autovoice` is sufficient on DiLink 3.

## 3. Persist takeover state separately from the visible voice setting

The working integration mirrored the native-assistant state into the voice preferences:

`alice_native_takeover`

Historical patch:

- `.github/alice-build4-native-mirror.py`

The important behavior is:

- takeover enabled -> `alice_native_takeover = true`
- takeover disabled -> `alice_native_takeover = false`

The hardware-key gate, startup synchronization and Accessibility fallback all read this same persisted flag.

Do not derive takeover state indirectly from a provider selection after every rebase. Preserve a single explicit persisted takeover flag.

## 4. Intercept the DiLink 3 hardware path before the native assistant receives it

Historical master gate:

- `.github/alice-build4-2-master-gate.py`

The working DiLink 3 path intercepted the relevant hardware events inside `SteeringWheelKeyService`.

Historical key handling:

- keyCode `304`: treated as the DiLink 3 microphone/Alice trigger
- keyCode `327`: explicitly consumed while native takeover was enabled

Behavior:

- if `alice_native_takeover == false`, the event is passed through and the stock system remains untouched;
- if takeover is enabled, the native trigger is consumed;
- the BYDMate/Alice route is launched by our service instead of allowing the event to continue to the stock assistant.

Historical log markers:

- `DILINK3_MIC_PASS_THROUGH`
- `DILINK3_327_BLOCKED`
- `DILINK3_304_TRIGGER`
- `DILINK3_304_CONSUMED`

Important: current/newer firmware may report a different steering-wheel keycode. Do not blindly hard-code 304/327 on a new upstream without checking the real diagnostic dump. Preserve the takeover semantics, then map them to the actually observed key events on the target car.

## 5. Re-assert the disabled state after the privileged helper becomes ready

There was a startup race:

1. application startup synchronization ran,
2. the privileged helper was not ready yet,
3. the disable request could be lost,
4. the native assistant remained enabled.

Alice 4.5 fixed this by re-applying:

`helperClient.setAppHidden("com.byd.vrassistant", true)`

immediately after the helper became available during install/update/Accessibility recovery.

Historical marker:

`ALICE4_5_VRASSISTANT_BLOCK startup=<true|false>`

This startup reassertion is mandatory.

A rebase that only applies the package state once from Settings is vulnerable to the same race.

## 6. Accessibility fallback closes the native assistant if it still surfaces

Package disabling and key interception are the primary controls, but the proven implementation added a second safety layer.

When Accessibility receives a window-state event from:

`com.byd.vrassistant`

while `alice_native_takeover` is enabled, the service immediately performs:

`GLOBAL_ACTION_BACK`

Historical marker:

`ALICE4_5_VRASSISTANT_WINDOW_BLOCKED back=<true|false>`

This is deliberately a fallback, not the primary takeover mechanism.

Why it exists:

- DiLink can race the package-disable/hardware path,
- an already-starting native window may still appear briefly,
- the Accessibility guard prevents it from staying on screen and stealing the interaction.

Do not remove this fallback merely because package state currently looks DISABLED in diagnostics.

## 7. Startup / boot behavior

The working Alice line also included boot-time coordination.

Historical patch:

- `.github/alice-build4-2-boot-prewarm.py`

When `alice_native_takeover` is enabled and Yandex Browser has microphone permission, the app can prewarm the Alice path shortly after a real boot.

This was primarily a cold-start latency optimization, but it also matters for takeover stability because the replacement assistant is ready before the first steering-wheel use.

The prewarm logic:

- only runs when takeover is enabled,
- only runs after a real/recent boot marker,
- waits for Accessibility to be bound,
- opens/primes Alice,
- returns to HOME after prewarm.

Do not confuse boot prewarm with the actual native-assistant block. The block must work even if prewarm is disabled.

## 8. Why one-layer fixes are not enough

The field-proven takeover is intentionally redundant:

1. explicit persisted `alice_native_takeover` state
2. hardware-key interception
3. privileged package disable for both BYD assistant packages
4. helper-ready startup reassertion
5. Accessibility window fallback

Each layer protects against a different DiLink 3 failure mode.

Removing any layer requires a real vehicle test proving it is no longer needed.

## 9. Reversibility is mandatory

The workaround must remain reversible.

When native takeover is turned off:

- hardware events must pass through again,
- `com.byd.autovoice` must be re-enabled,
- `com.byd.vrassistant` must be re-enabled,
- the Accessibility fallback must stop closing BYD assistant windows.

Never leave the stock assistant permanently disabled after the user turns takeover off.

## 10. Regression checklist after every rebase

Before declaring native-assistant takeover preserved:

1. Verify `alice_native_takeover` still exists and is persisted.
2. Verify current DiLink steering-wheel key events with diagnostics.
3. Verify takeover-disabled mode passes native key events through.
4. Verify takeover-enabled mode consumes the native assistant trigger.
5. Verify HelperDaemon explicitly allows `com.byd.vrassistant`.
6. Verify the helper still uses reversible `pm disable-user --user 0` / `pm enable`.
7. Verify both `com.byd.autovoice` and `com.byd.vrassistant` are synchronized.
8. Verify the disable is re-applied after helper startup/recovery.
9. Verify Accessibility closes a `com.byd.vrassistant` window if one still appears.
10. Reboot the head unit and repeat the test.
11. Toggle takeover OFF and verify the stock BYD assistant works again.
12. Toggle takeover ON and verify only the selected BYDMate/Alice path responds.

## 11. Critical historical references

Primary scripts:

- `.github/alice-build4-native-mirror.py`
- `.github/alice-build4-2-master-gate.py`
- `.github/alice-build4-2-vrassistant-sync.py`
- `.github/alice-build4-2-boot-prewarm.py`
- `.github/alice-build4-5-cold-chain-guard-duck.py`

Historical patch archive commit:

- `433c75f49aba8613a51ca35f1b44b885612f405c`

The most important recovery fact is:

**4.2 already tried to disable `com.byd.vrassistant`, but it did not become reliable until 4.5 added that package to the privileged helper allowlist and reasserted the state after helper startup.**

That exact mistake must not be repeated in a future rebase.

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
7. Local BYDMate and Alice use the same semantic navigator/app mapping.
8. ReVanced/MicroG and other alternative packages may be supported by discovery/manual package configuration, but Build 5.3 field-proven dispatch semantics take priority over new abstractions.

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
- Alice "открой навигацию" -> Waze
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
