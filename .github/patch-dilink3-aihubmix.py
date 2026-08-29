from pathlib import Path

p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()

# Extra UI imports for the small AIHubMix setup card.
needle = 'import androidx.compose.material3.Button\n'
replacement = 'import androidx.compose.material3.Button\nimport androidx.compose.material3.OutlinedTextField\n'
if needle not in s:
    raise SystemExit('AIHubMix import insertion point not found')
s = s.replace(needle, replacement, 1)

needle = 'import androidx.compose.ui.platform.LocalContext\n'
replacement = 'import androidx.compose.ui.platform.LocalContext\nimport androidx.compose.ui.text.input.PasswordVisualTransformation\n'
if needle not in s:
    raise SystemExit('AIHubMix password import insertion point not found')
s = s.replace(needle, replacement, 1)

# State + load the existing custom-slot values, if any.
needle = '''    var e2eSpoken by remember { mutableStateOf(false) }\n\n    val systemRecognizer = remember(systemAsrAvailable) {'''
replacement = '''    var e2eSpoken by remember { mutableStateOf(false) }\n\n    // AIHubMix quick setup for the diagnostic build. The provider is OpenAI-compatible and\n    // maps to BYDMate's production custom-LLM connection slot.\n    var aihubmixApiKey by remember { mutableStateOf("") }\n    var aihubmixModel by remember { mutableStateOf(DiLink3E2EBridge.DEFAULT_AIHUBMIX_MODEL) }\n    var aihubmixStatus by remember { mutableStateOf("not configured") }\n    LaunchedEffect(e2eBridge) {\n        runCatching { e2eBridge.loadAihubmixConfig() }\n            .onSuccess { cfg ->\n                aihubmixApiKey = cfg.apiKey\n                aihubmixModel = cfg.model\n                aihubmixStatus = if (cfg.enabled && cfg.apiKey.isNotBlank()) "READY - primary AI provider" else "enter API key and save"\n            }\n            .onFailure { t -> aihubmixStatus = "load error: ${t.message}" }\n    }\n\n    val systemRecognizer = remember(systemAsrAvailable) {'''
if needle not in s:
    raise SystemExit('AIHubMix state insertion point not found')
s = s.replace(needle, replacement, 1)

# Put provider configuration immediately before the E2E voice test so it is impossible to miss.
needle = '''                Text("STEP 2A - END TO END: System ASR -> BYDMate AI -> TTS", style = MaterialTheme.typography.titleSmall)'''
replacement = '''                Text("AI PROVIDER - AIHubMix", style = MaterialTheme.typography.titleSmall)\n                Text(\n                    "AIHubMix uses the OpenAI-compatible gateway https://aihubmix.com/v1. Paste only your API key; the app fills the provider URL and makes this connection primary. The default gpt-5.5-free model supports streaming and tool calling and can be replaced with any AIHubMix chat model ID.",\n                    style = MaterialTheme.typography.bodySmall,\n                )\n                OutlinedTextField(\n                    value = aihubmixApiKey,\n                    onValueChange = { aihubmixApiKey = it },\n                    label = { Text("AIHubMix API key (sk-...)") },\n                    singleLine = true,\n                    visualTransformation = PasswordVisualTransformation(),\n                    modifier = Modifier.fillMaxWidth(),\n                )\n                OutlinedTextField(\n                    value = aihubmixModel,\n                    onValueChange = { aihubmixModel = it },\n                    label = { Text("AIHubMix model") },\n                    supportingText = { Text("Default: gpt-5.5-free; paid alternative: gpt-5.6-luna") },\n                    singleLine = true,\n                    modifier = Modifier.fillMaxWidth(),\n                )\n                Button(\n                    enabled = aihubmixApiKey.isNotBlank(),\n                    onClick = {\n                        aihubmixStatus = "saving..."\n                        scope.launch {\n                            runCatching { e2eBridge.saveAihubmixConfig(aihubmixApiKey, aihubmixModel) }\n                                .onSuccess {\n                                    aihubmixStatus = "READY - AIHubMix is primary; press TALK TO BYDMATE"\n                                    e2eError = ""\n                                }\n                                .onFailure { t -> aihubmixStatus = "save error: ${t.message}" }\n                        }\n                    },\n                    modifier = Modifier.fillMaxWidth(),\n                ) {\n                    Text("SAVE AIHUBMIX + ENABLE AI AGENT")\n                }\n                DebugRow("AIHubMix", aihubmixStatus)\n                DebugRow("Gateway", DiLink3E2EBridge.AIHUBMIX_BASE_URL)\n\n                Text("STEP 2A - END TO END: System ASR -> BYDMate AI -> TTS", style = MaterialTheme.typography.titleSmall)'''
if needle not in s:
    raise SystemExit('AIHubMix UI insertion point not found (E2E patch must run first)')
s = s.replace(needle, replacement, 1)

p.write_text(s)
print('Applied DiLink3 AIHubMix quick-setup patch')
