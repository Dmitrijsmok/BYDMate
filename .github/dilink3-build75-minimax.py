#!/usr/bin/env python3
from pathlib import Path

VERSION_CODE = "60025"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Build75 anchor missing: {label}")
    return text.replace(old, new, 1)


# 1) Field identity: monotonic update over Build74.
p = Path("app/build.gradle.kts")
s = p.read_text()
s = replace_once(s, "        versionCode = 60024", f"        versionCode = {VERSION_CODE}", "versionCode")
s = replace_once(
    s,
    '            versionNameSuffix = "-dilink3-production-build74"',
    '            versionNameSuffix = "-dilink3-production-build75"',
    "versionNameSuffix",
)
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = replace_once(
    s,
    'android:label="BYDMate DiLink3 Build74"',
    'android:label="BYDMate DiLink3 Build75"',
    "manifest label",
)
p.write_text(s)


# 2) Keep only providers worth field-testing. Groq and xAI/Grok are removed from
#    the visible production presets after failed field tests. MiniMax is added via
#    its official OpenAI-compatible endpoint.
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text()
old = '''private val CUSTOM_PRESETS = listOf(
    CustomPreset("AIHubMix", "https://aihubmix.com/v1", "gpt-5.5-free", R.string.settings_preset_hint_aihubmix),
    CustomPreset("OpenAI", "https://api.openai.com/v1", "gpt-5.6-luna", R.string.settings_preset_hint_openai),
    CustomPreset("Groq", "https://api.groq.com/openai/v1", "openai/gpt-oss-20b", R.string.settings_preset_hint_groq),
    CustomPreset("xAI / Grok", "https://api.x.ai/v1", "grok-4.6", R.string.settings_preset_hint_xai),
    CustomPreset("Gemini", "https://generativelanguage.googleapis.com/v1beta/openai", "gemini-3.8-flash", R.string.settings_preset_hint_gemini),
)
'''
new = '''private val CUSTOM_PRESETS = listOf(
    CustomPreset("AIHubMix", "https://aihubmix.com/v1", "gpt-5.5-free", R.string.settings_preset_hint_aihubmix),
    CustomPreset("OpenAI", "https://api.openai.com/v1", "gpt-5.6-luna", R.string.settings_preset_hint_openai),
    CustomPreset("Gemini", "https://generativelanguage.googleapis.com/v1beta/openai", "gemini-3.8-flash", R.string.settings_preset_hint_gemini),
    CustomPreset("MiniMax", "https://api.minimax.io/v1", "MiniMax-M2.7-highspeed", R.string.settings_preset_hint_minimax),
)
'''
s = replace_once(s, old, new, "provider presets")
p.write_text(s)


# 3) Curated model picker: remove Groq/xAI presets and add MiniMax standard + highspeed.
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsViewModel.kt")
s = p.read_text()
old = '''    private fun curatedAgentModels(provider: String): List<String> = when (provider.trim().lowercase(Locale.ROOT)) {
        "aihubmix" -> listOf("gpt-5.5-free", "gpt-5.6-luna")
        "openai" -> listOf("gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol")
        "groq" -> listOf(
            "openai/gpt-oss-20b", "openai/gpt-oss-120b",
            "qwen/qwen3.6-27b", "qwen/qwen3.8-27b",
            "minimaxai/minimax-m2.7", "llama-3.3-70b-versatile", "llama-3.1-8b-instant",
        )
        "xai / grok" -> listOf("grok-4.6", "grok-4.20", "grok-4.20-non-reasoning")
        "gemini" -> listOf("gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.1-pro", "gemini-3.1-flash-lite")
        "together" -> listOf(
            "openai/gpt-oss-20b", "openai/gpt-oss-120b",
            "moonshotai/Kimi-K2.5", "Qwen/Qwen3.5-9B", "zai-org/GLM-5.1",
        )
        "deepseek" -> listOf("deepseek-v4-flash", "deepseek-v4-pro")
        "mistral" -> listOf(
            "mistral-small-latest", "mistral-medium-latest", "mistral-large-latest",
            "ministral-8b-latest", "ministral-14b-latest",
        )
        else -> emptyList()
    }
'''
new = '''    private fun curatedAgentModels(provider: String): List<String> = when (provider.trim().lowercase(Locale.ROOT)) {
        "aihubmix" -> listOf("gpt-5.5-free", "gpt-5.6-luna")
        "openai" -> listOf("gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol")
        "gemini" -> listOf("gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.1-pro", "gemini-3.1-flash-lite")
        "minimax" -> listOf("MiniMax-M2.7-highspeed", "MiniMax-M2.7", "MiniMax-M2.5-highspeed", "MiniMax-M2.5")
        else -> emptyList()
    }
'''
s = replace_once(s, old, new, "curated provider models")
p.write_text(s)


# 4) One small hint. No wizard or extra diagnostic screen.
for values_dir, text in (
    ("values", "OpenAI-compatible API MiniMax. Для минимальной задержки начните с MiniMax-M2.7-highspeed."),
    ("values-en", "MiniMax OpenAI-compatible API. Start with MiniMax-M2.7-highspeed for the lowest latency."),
):
    p = Path(f"app/src/main/res/{values_dir}/strings.xml")
    if not p.exists():
        continue
    s = p.read_text()
    if 'name="settings_preset_hint_minimax"' not in s:
        s = replace_once(
            s,
            "</resources>",
            f'    <string name="settings_preset_hint_minimax">{text}</string>\n</resources>',
            f"MiniMax hint {values_dir}",
        )
    p.write_text(s)

print("Build75 applied: remove Groq/xAI presets + add MiniMax OpenAI-compatible preset")
