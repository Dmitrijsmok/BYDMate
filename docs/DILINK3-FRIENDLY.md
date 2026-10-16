# DiLink3 Friendly (noncommercial BYDMate-derived edition)

Based on closed, unmerged upstream PR #261, commit `7cd2028a0eb24d15ee9686092013c5db66fe03ee`, in the user's fork. The original BYDMate authorship and PolyForm Noncommercial 1.0.0 LICENSE are retained without alterations.

- Branch: `dilink3-friendly/main` in `Dmitrijsmok/BYDMate`. The fork's previous `main` is not replaced.
- Android applicationId `com.bydmate.dilink3.app`; Kotlin namespace stays `com.bydmate.app` to preserve all compiled component classes.
- Independent version `1.0.0` / versionCode `100001`; release APK `DiLink3Friendly-v1.0.0.apk`.
- OTA GitHub Releases feed: `https://api.github.com/repos/Dmitrijsmok/BYDMate/releases/latest`. Only the `DiLink3Friendly-v<version>.apk` asset from this fork is accepted. Without a first release GitHub returns 404, interpreted as no update.
- Own helper process, binder service, action, lock file, and log file to prevent collisions with the original application's helper.
- A privately backed-up release keystore is required. Configure local gitignored `keystore.properties`. Never commit signing keys or passwords, and use the same certificate for every future update.
- Before first release, run `./gradlew :app:testDebugUnitTest :app:assembleDebug :app:lintDebug :app:detekt`, then build a signed APK; check package name and signer with `apksigner`, publish tag `v1.0.0` and APK asset named precisely `DiLink3Friendly-v1.0.0.apk`.
- Android 10 uses user-confirmed system package installation; OTA cannot silently install without privileged permissions.
- A different app ID does not automatically migrate BYDMate data. Export or back up supported data first.
- Even with distinct packages, never allow both apps to simultaneously own steering-wheel PTT, Accessibility, or the stock BYD assistant state.
- On-car acceptance should include Android 10 boot / QuickBoot, keycodes 304 and 327, Alice single/double press, local agent, native assistant disable/re-enable, daemon recovery, media/navigation stream, and update checks.
- Upstream changes only by intentional, reviewed cherry-picks. Existing in-app original author credit remains.
- Historical docs/scripts may still reference `com.bydmate.app`; inspect before running diagnostic commands on DiLink3 Friendly.

