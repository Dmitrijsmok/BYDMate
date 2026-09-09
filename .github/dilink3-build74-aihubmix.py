#!/usr/bin/env python3
from pathlib import Path

VERSION_CODE = "60024"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Build74 anchor missing: {label}")
    return text.replace(old, new, 1)


# 1) Field identity: same package/signer, monotonic update over Build73.
p = Path("app/build.gradle.kts")
s = p.read_text()
s = replace_once(s, "        versionCode = 60023", f"        versionCode = {VERSION_CODE}", "versionCode")
s = replace_once(
    s,
    '            versionNameSuffix = "-dilink3-production-build73"',
    '            versionNameSuffix = "-dilink3-production-build74"',
    "versionNameSuffix",
)
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = replace_once(
    s,
    'android:label="BYDMate DiLink3 Build73"',
    'android:label="BYDMate DiLink3 Build74"',
    "manifest label",
)
p.write_text(s)


# 2) Keep the production Custom card, but remove the long provider-preset clutter.
#    AIHubMix is restored using the exact gateway/default model from the field-proven
#    Build66 wizard. Manual Base URL/name/model fields remain available for any other
#    OpenAI-compatible service, so removing a preset does NOT remove Custom support.
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text()
start = s.find('private val CUSTOM_PRESETS = listOf(\n')
if start < 0:
    raise SystemExit("Build74 anchor missing: CUSTOM_PRESETS start")
end = s.find('\n)\n', start)
if end < 0:
    raise SystemExit("Build74 anchor missing: CUSTOM_PRESETS end")
end += len('\n)\n')
new_presets = '''private val CUSTOM_PRESETS = listOf(
    CustomPreset("AIHubMix", "https://aihubmix.com/v1", "gpt-5.5-free", R.string.settings_preset_hint_aihubmix),
    CustomPreset("OpenAI", "https://api.openai.com/v1", "gpt-5.6-luna", R.string.settings_preset_hint_openai),
    CustomPreset("Groq", "https://api.groq.com/openai/v1", "openai/gpt-oss-20b", R.string.settings_preset_hint_groq),
    CustomPreset("xAI / Grok", "https://api.x.ai/v1", "grok-4.6", R.string.settings_preset_hint_xai),
    CustomPreset("Gemini", "https://generativelanguage.googleapis.com/v1beta/openai", "gemini-3.8-flash", R.string.settings_preset_hint_gemini),
)
'''
s = s[:start] + new_presets + s[end:]
p.write_text(s)


# 3) AIHubMix gets a local curated model list even before /models succeeds.
#    The live provider response is still merged and the Build73 full live-agent
#    compatibility probe remains the final truth test.
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsViewModel.kt")
s = p.read_text()
old = '''    private fun curatedAgentModels(provider: String): List<String> = when (provider.trim().lowercase(Locale.ROOT)) {
        "openai" -> listOf("gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol")
'''
new = '''    private fun curatedAgentModels(provider: String): List<String> = when (provider.trim().lowercase(Locale.ROOT)) {
        "aihubmix" -> listOf("gpt-5.5-free", "gpt-5.6-luna")
        "openai" -> listOf("gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol")
'''
s = replace_once(s, old, new, "AIHubMix curated models")
p.write_text(s)


# 4) Small preset hint only; no wizard/debug screen is reintroduced.
for values_dir, text in (
    ("values", "OpenAI-compatible шлюз AIHubMix. Вставьте API key; Base URL заполнится автоматически."),
    ("values-en", "AIHubMix OpenAI-compatible gateway. Paste the API key; Base URL is filled automatically."),
):
    p = Path(f"app/src/main/res/{values_dir}/strings.xml")
    if not p.exists():
        continue
    s = p.read_text()
    if 'name="settings_preset_hint_aihubmix"' not in s:
        s = replace_once(
            s,
            "</resources>",
            f'    <string name="settings_preset_hint_aihubmix">{text}</string>\n</resources>',
            f"AIHubMix hint {values_dir}",
        )
    p.write_text(s)

print("Build74 applied: compact provider presets + field-proven AIHubMix preset")
