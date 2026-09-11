#!/usr/bin/env python3
from pathlib import Path


def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit(f"Build88 anchor missing: {label}")
    return text.replace(old, new, 1)

p = Path("app/build.gradle.kts")
s = p.read_text()
s = replace_once(s, "versionCode = 60037", "versionCode = 60038", "versionCode")
s = replace_once(s, 'versionNameSuffix = "-dilink3-production-build87"', 'versionNameSuffix = "-dilink3-production-build88"', "versionName")
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = replace_once(s, 'android:label="BYDMate DiLink3 Build87"', 'android:label="BYDMate DiLink3 Build88"', "label")
p.write_text(s)

p = Path("app/src/main/kotlin/com/bydmate/app/assistantlab/AssistantLab.kt")
s = p.read_text()
s = s.replace("Build87", "Build88")

# On DiLink3 the NOT_FOCUSABLE overlay was visually present but touch events fell through
# to the activity below. Make the lab an explicit touch-modal debug surface while visible.
s = replace_once(
    s,
    '''            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or\n                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,\n''',
    '''            WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or\n                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,\n''',
    "overlay flags",
)

s = replace_once(
    s,
    '''        val outer = LinearLayout(context).apply {\n            orientation = LinearLayout.VERTICAL\n''',
    '''        val outer = LinearLayout(context).apply {\n            orientation = LinearLayout.VERTICAL\n            isClickable = true\n            isFocusable = true\n            isFocusableInTouchMode = true\n            // Consume otherwise-unhandled touches inside the overlay so they can never fall\n            // through to the app underneath on the DiLink3 vendor WindowManager. Child Buttons\n            // still receive their own click events first.\n            setOnTouchListener { _, _ -> true }\n''',
    "touch sink",
)

# Make close/minimize unambiguous and slightly larger for the car screen.
s = replace_once(
    s,
    '''        val close = smallButton(context, "×") { hide() }\n''',
    '''        val close = smallButton(context, "ЗАКРЫТЬ") { hide() }.apply {\n            textSize = 10f\n            layoutParams = LinearLayout.LayoutParams(dp(context, 130), dp(context, 48))\n        }\n''',
    "close button",
)

# Header itself no longer receives a blanket touch listener. Use only the title as drag handle,
# so taps on MINIMIZE/CLOSE can never be stolen by drag gesture handling.
s = replace_once(
    s,
    '''        outer.addView(header)\n        installDrag(header)\n''',
    '''        outer.addView(header)\n        installDrag(title)\n''',
    "drag handle",
)

p.write_text(s)

p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text().replace("Assistant Lab · Build87", "Assistant Lab · Build88")
p.write_text(s)

print("Build88 applied: touch-modal Assistant Lab overlay, reliable minimize/close, title-only drag")
