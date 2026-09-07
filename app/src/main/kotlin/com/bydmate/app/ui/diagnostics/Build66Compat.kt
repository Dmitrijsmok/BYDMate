package com.bydmate.app.ui.diagnostics

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.VisualTransformation

/**
 * Build66 diagnostic-branch compatibility shims.
 *
 * The accumulated DiLink3 patch chain places the compact Build66 wizard above some older
 * locally-scoped helper declarations. Keep this file deliberately tiny: it only exposes the
 * UI helpers needed by that top-level wizard. It does not change the production voice/agent path.
 */
@Composable
internal fun DebugRow(label: String, value: String) {
    androidx.compose.material3.Text(
        text = "$label: $value",
        style = androidx.compose.material3.MaterialTheme.typography.bodySmall,
    )
}

@Composable
internal fun OutlinedTextField(
    value: String,
    onValueChange: (String) -> Unit,
    label: @Composable (() -> Unit)? = null,
    supportingText: @Composable (() -> Unit)? = null,
    singleLine: Boolean = false,
    visualTransformation: VisualTransformation = VisualTransformation.None,
    modifier: Modifier = Modifier,
) {
    androidx.compose.material3.OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        label = label,
        supportingText = supportingText,
        singleLine = singleLine,
        visualTransformation = visualTransformation,
        modifier = modifier,
    )
}

internal fun PasswordVisualTransformation(): VisualTransformation =
    androidx.compose.ui.text.input.PasswordVisualTransformation()

// The Build66 volume button calls the bridge's real TTS test, which returns a concrete error if
// the engine is unavailable. These only avoid depending on older locally-scoped panel flags.
internal const val ttsEnabled: Boolean = true
internal const val ttsReady: Boolean = true
