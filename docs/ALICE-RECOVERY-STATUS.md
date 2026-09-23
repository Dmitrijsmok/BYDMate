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
