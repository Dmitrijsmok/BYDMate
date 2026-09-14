#!/usr/bin/env python3
from pathlib import Path

p = Path("app/src/main/kotlin/com/bydmate/app/helper/HelperDaemon.kt")
s = p.read_text()
old = '''                    val ok = if (pkg == "com.byd.autovoice" && hidden in 0..1) {
                        // `pm disable-user --user 0` force-stops the package and disables its
                        // components so the framework stops routing the steering voice button to it.
                        // `pm hide` left the already-running system assistant alive — the wheel
                        // button still woke it. The competitor uses disable-user and suppresses the
                        // assistant 100%; reversed with `pm enable`.
                        val cmd = if (hidden == 1) "pm disable-user --user 0" else "pm enable"
                        // The native assistant ships as a package FAMILY on Leopard 3: the launcher
                        // (com.byd.autovoice), the wake/recognition engine (.engine) that actually
                        // services the wheel mic button, and TTS output (.tts). Disabling only the
                        // launcher leaves the wheel button live, so we disable the whole family.
                        // Siblings are hardcoded literals, never caller input. Success is gated on
                        // BOTH the launcher and the wake engine; TTS is output-only and best-effort.
                        val primaryOk = shExec("$cmd \\"\\$1\\"", pkg).code == 0
                        val engineOk = shExec("$cmd \\"\\$1\\"", "com.byd.autovoice.engine").code == 0
                        shExec("$cmd \\"\\$1\\"", "com.byd.autovoice.tts")
                        primaryOk && engineOk
                    } else false
'''
new = '''                    val ok = when {
                        pkg == "com.byd.vrassistant" && hidden in 0..1 -> {
                            // DiLink3 field firmware uses this single package instead of the
                            // older com.byd.autovoice family. Keep the daemon endpoint narrowly
                            // allow-listed: this is the ONLY additional caller-selectable package.
                            val cmd = if (hidden == 1) "pm disable-user --user 0" else "pm enable"
                            shExec("$cmd \\"\\$1\\"", pkg).code == 0
                        }
                        pkg == "com.byd.autovoice" && hidden in 0..1 -> {
                            // `pm disable-user --user 0` force-stops the package and disables its
                            // components so the framework stops routing the steering voice button to it.
                            // `pm hide` left the already-running system assistant alive — the wheel
                            // button still woke it. The competitor uses disable-user and suppresses the
                            // assistant 100%; reversed with `pm enable`.
                            val cmd = if (hidden == 1) "pm disable-user --user 0" else "pm enable"
                            // The native assistant ships as a package FAMILY on other BYD firmware.
                            val primaryOk = shExec("$cmd \\"\\$1\\"", pkg).code == 0
                            val engineOk = shExec("$cmd \\"\\$1\\"", "com.byd.autovoice.engine").code == 0
                            shExec("$cmd \\"\\$1\\"", "com.byd.autovoice.tts")
                            primaryOk && engineOk
                        }
                        else -> false
                    }
'''
if old not in s:
    raise SystemExit("Alice4.5 vrassistant helper anchor missing")
p.write_text(s.replace(old, new, 1))
print("Alice4.5 helper: com.byd.vrassistant can now be disabled/re-enabled")
