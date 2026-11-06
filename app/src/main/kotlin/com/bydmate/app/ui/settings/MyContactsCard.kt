package com.bydmate.app.ui.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.bydmate.app.R
import com.bydmate.app.agent.MyContact
import com.bydmate.app.ui.components.AppAlertDialog
import com.bydmate.app.ui.theme.AccentGreen
import com.bydmate.app.ui.theme.CardBorder
import com.bydmate.app.ui.theme.CardSurfaceElevated
import com.bydmate.app.ui.theme.TextSecondary

@Composable
internal fun MyContactsCard(viewModel: MyContactsViewModel = hiltViewModel()) {
    val contacts by viewModel.contacts.collectAsState()
    // null = closed; -1 = new contact; otherwise the index being edited.
    var editing by remember { mutableStateOf<Int?>(null) }

    Card(
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardSurfaceElevated),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(horizontal = 12.dp)) {
            SettingActionRow(
                title = stringResource(R.string.settings_my_contacts_title),
                description = stringResource(R.string.settings_my_contacts_desc),
                buttonLabel = stringResource(R.string.settings_my_contacts_add),
                onClick = { editing = -1 },
            )
            contacts.forEachIndexed { index, contact ->
                SettingDivider()
                SettingValueRow(
                    title = contact.name,
                    description = contact.aliases.takeIf { it.isNotEmpty() }?.joinToString(", "),
                    value = contact.phone,
                    onClick = { editing = index },
                )
            }
            SettingHint(stringResource(R.string.settings_my_contacts_hint))
        }
    }

    editing?.let { index ->
        val existing = contacts.getOrNull(index)
        MyContactDialog(
            initial = existing,
            onSave = { viewModel.save(index.takeIf { existing != null }, it); editing = null },
            onDelete = existing?.let { { viewModel.delete(index); editing = null } },
            onDismiss = { editing = null },
        )
    }
}

@Composable
private fun MyContactDialog(
    initial: MyContact?,
    onSave: (MyContact) -> Unit,
    onDelete: (() -> Unit)?,
    onDismiss: () -> Unit,
) {
    var name by remember { mutableStateOf(initial?.name.orEmpty()) }
    var phone by remember { mutableStateOf(initial?.phone.orEmpty()) }
    var aliases by remember { mutableStateOf(initial?.aliases?.joinToString(", ").orEmpty()) }
    AppAlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.settings_my_contacts_dialog_title)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                ContactField(stringResource(R.string.settings_my_contacts_name), name, KeyboardType.Text) { name = it }
                ContactField(stringResource(R.string.settings_my_contacts_phone), phone, KeyboardType.Phone) { phone = it }
                ContactField(stringResource(R.string.settings_my_contacts_aliases), aliases, KeyboardType.Text) {
                    aliases = it
                }
            }
        },
        confirmButton = {
            TextButton(
                enabled = name.isNotBlank() && phone.isNotBlank(),
                onClick = {
                    onSave(MyContact(name.trim(), phone.trim(),
                        aliases.split(',').map { it.trim() }.filter { it.isNotEmpty() }))
                },
            ) { Text(stringResource(R.string.settings_my_contacts_save)) }
        },
        dismissButton = {
            if (onDelete != null) {
                TextButton(onClick = onDelete) { Text(stringResource(R.string.settings_my_contacts_delete)) }
            } else {
                TextButton(onClick = onDismiss) { Text(stringResource(R.string.settings_my_contacts_cancel)) }
            }
        },
    )
}

@Composable
private fun ContactField(label: String, value: String, keyboardType: KeyboardType, onChange: (String) -> Unit) {
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
        label = { Text(label) },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = keyboardType),
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        colors = OutlinedTextFieldDefaults.colors(
            focusedTextColor = Color.White,
            unfocusedTextColor = Color.White,
            focusedBorderColor = AccentGreen,
            unfocusedBorderColor = CardBorder,
            focusedLabelColor = AccentGreen,
            unfocusedLabelColor = TextSecondary,
            cursorColor = AccentGreen,
        ),
    )
}
