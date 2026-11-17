package com.bydmate.app.ui.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.bydmate.app.R
import com.bydmate.app.split.AppSet
import com.bydmate.app.split.AppSetLauncher
import com.bydmate.app.split.AppSetStore
import com.bydmate.app.ui.components.AppLaunchPickerDialog
import com.bydmate.app.ui.theme.AccentGreen
import com.bydmate.app.ui.theme.CardSurfaceElevated
import com.bydmate.app.ui.theme.SocRed
import com.bydmate.app.ui.theme.TextPrimary

/**
 * «Комплекты приложений» section of the Android 10 head units (DiLink 3 / 4), in place of the
 * freeform split, which the firmware does not run: a name that doubles as the voice command, the
 * app for the left half, the app for the right half and «open at start».
 */
@Composable
internal fun AppSetsSection(viewModel: AppSetsViewModel = hiltViewModel()) {
    val sets by viewModel.store.sets.collectAsStateWithLifecycle()
    var adding by remember { mutableStateOf(false) }
    SectionHeader(text = stringResource(R.string.settings_section_app_sets_title))
    Card(
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardSurfaceElevated),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            SettingHint(text = stringResource(R.string.settings_app_sets_howto))
        }
    }
    sets.forEach { set ->
        key(set.id) { AppSetEditor(viewModel, set, isNew = false, onDone = {}) }
    }
    if (adding) {
        AppSetEditor(viewModel, AppSet(viewModel.store.newId(), "", ""), isNew = true, onDone = { adding = false })
    } else if (sets.size < AppSetStore.MAX_SETS) {
        Card(
            shape = RoundedCornerShape(12.dp),
            colors = CardDefaults.cardColors(containerColor = CardSurfaceElevated),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Column(modifier = Modifier.padding(12.dp)) {
                SettingActionRow(
                    title = stringResource(R.string.settings_app_sets_add_title),
                    buttonLabel = stringResource(R.string.settings_app_sets_add),
                    onClick = { adding = true },
                    style = SettingButtonStyle.Primary,
                )
            }
        }
    }
}

private enum class PickerFor { LEFT, RIGHT }

@Composable
private fun AppSetEditor(viewModel: AppSetsViewModel, initial: AppSet, isNew: Boolean, onDone: () -> Unit) {
    val context = LocalContext.current
    var name by remember(initial) { mutableStateOf(initial.name) }
    var left by remember(initial) { mutableStateOf(initial.leftPkg) }
    var right by remember(initial) { mutableStateOf(initial.rightPkg) }
    var autostart by remember(initial) { mutableStateOf(initial.autostart) }
    var picker by remember { mutableStateOf<PickerFor?>(null) }
    var message by remember { mutableStateOf<String?>(null) }
    var messageIsError by remember { mutableStateOf(false) }
    val lastRun by viewModel.lastRun.collectAsStateWithLifecycle()

    fun draft() = AppSet(initial.id, name.trim(), left, right, autostart)

    val errors = mapOf(
        AppSetStore.Check.NoName to stringResource(R.string.settings_app_sets_err_name),
        AppSetStore.Check.NameTooLong to stringResource(R.string.settings_app_sets_err_name_long),
        AppSetStore.Check.NoLeftApp to stringResource(R.string.settings_app_sets_err_left),
        AppSetStore.Check.SameApp to stringResource(R.string.settings_app_sets_err_same),
        AppSetStore.Check.TooMany to stringResource(R.string.settings_app_sets_err_many),
    )
    val inUse = stringResource(R.string.settings_app_sets_err_in_use)
    val saved = stringResource(R.string.settings_app_sets_saved)
    val runFailed = stringResource(R.string.settings_app_sets_run_failed)

    Card(
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardSurfaceElevated),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value = name,
                onValueChange = { name = it.take(AppSetStore.MAX_NAME_CHARS + 1); message = null },
                label = { Text(stringResource(R.string.settings_app_sets_name_label)) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedTextColor = TextPrimary,
                    unfocusedTextColor = TextPrimary,
                    focusedBorderColor = AccentGreen,
                ),
            )
            SettingValueRow(
                title = stringResource(R.string.settings_app_sets_left_title),
                value = left.takeIf { it.isNotBlank() }?.let { resolveAppLabel(context, it) }
                    ?: stringResource(R.string.settings_app_sets_not_chosen),
                onClick = { picker = PickerFor.LEFT },
            )
            SettingDivider()
            SettingValueRow(
                title = stringResource(R.string.settings_app_sets_right_title),
                description = stringResource(R.string.settings_app_sets_right_desc),
                value = right?.let { resolveAppLabel(context, it) }
                    ?: stringResource(R.string.settings_app_sets_right_keep),
                onClick = { picker = PickerFor.RIGHT },
            )
            if (right != null) {
                SettingActionRow(
                    title = stringResource(R.string.settings_app_sets_right_clear_title),
                    buttonLabel = stringResource(R.string.settings_app_sets_right_clear),
                    onClick = { right = null; message = null },
                    style = SettingButtonStyle.Secondary,
                )
            }
            SettingDivider()
            SettingToggleRow(
                title = stringResource(R.string.settings_app_sets_autostart_title),
                description = stringResource(R.string.settings_app_sets_autostart_desc),
                checked = autostart,
                onCheckedChange = { autostart = it; message = null },
                traceId = "app_set_autostart",
            )
            SettingDivider()
            SettingActionRow(
                title = name.trim().ifBlank { stringResource(R.string.settings_app_sets_untitled) },
                buttonLabel = stringResource(R.string.settings_app_sets_save),
                onClick = {
                    val check = viewModel.store.check(draft())
                    when {
                        check == AppSetStore.Check.Ok -> {
                            viewModel.store.upsert(draft())
                            message = saved; messageIsError = false
                            if (isNew) onDone()
                        }
                        check is AppSetStore.Check.NameInUse -> { message = inUse.format(check.owner); messageIsError = true }
                        else -> { message = errors[check]; messageIsError = true }
                    }
                },
                style = SettingButtonStyle.Primary,
                secondButtonLabel = stringResource(R.string.settings_app_sets_run),
                onSecondClick = { viewModel.run(draft()) },
                secondButtonEnabled = left.isNotBlank(),
            )
            if (!isNew) {
                SettingActionRow(
                    title = stringResource(R.string.settings_app_sets_delete_title),
                    buttonLabel = stringResource(R.string.settings_app_sets_delete),
                    onClick = { viewModel.store.remove(initial.id) },
                    style = SettingButtonStyle.Secondary,
                )
            } else {
                SettingActionRow(
                    title = stringResource(R.string.settings_app_sets_cancel_title),
                    buttonLabel = stringResource(R.string.settings_app_sets_cancel),
                    onClick = onDone,
                    style = SettingButtonStyle.Secondary,
                )
            }
            val shown = message ?: runFailed.takeIf { lastRun != null && lastRun != AppSetLauncher.Outcome.OK }
            shown?.let {
                Text(it, color = if (message == null || messageIsError) SocRed else AccentGreen, fontSize = 12.sp)
            }
        }
    }

    picker?.let { role ->
        val other = if (role == PickerFor.LEFT) right else left.takeIf { it.isNotBlank() }
        AppLaunchPickerDialog(
            currentPackage = (if (role == PickerFor.LEFT) left else right).orEmpty(),
            excludedPackages = setOfNotNull(other),
            onDismiss = { picker = null },
            onSelect = { pkg, _ ->
                if (role == PickerFor.LEFT) left = pkg else right = pkg
                message = null
                picker = null
            },
        )
    }
}
