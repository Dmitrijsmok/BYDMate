package com.bydmate.app.ui.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.bydmate.app.agent.MyContact
import com.bydmate.app.agent.MyContactsCodec
import com.bydmate.app.data.repository.SettingsRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

/** «Мои контакты»: the list the call_contact voice tool calls by name (MyContacts.kt). */
@HiltViewModel
class MyContactsViewModel @Inject constructor(
    private val settingsRepository: SettingsRepository,
) : ViewModel() {
    private val _contacts = MutableStateFlow<List<MyContact>>(emptyList())
    val contacts: StateFlow<List<MyContact>> = _contacts.asStateFlow()

    init {
        viewModelScope.launch {
            _contacts.value = MyContactsCodec.decode(
                settingsRepository.getString(SettingsRepository.KEY_MY_CONTACTS, ""))
        }
    }

    /** Replaces the contact at [index] (or adds one when null); a blank name or number is ignored. */
    fun save(index: Int?, contact: MyContact) {
        if (contact.name.isBlank() || contact.phone.isBlank()) return
        val list = _contacts.value.toMutableList()
        if (index != null && index in list.indices) list[index] = contact else list += contact
        persist(list)
    }

    fun delete(index: Int) {
        persist(_contacts.value.filterIndexed { i, _ -> i != index })
    }

    private fun persist(list: List<MyContact>) {
        _contacts.value = list
        // NonCancellable: leaving Settings right after «Сохранить» clears this ViewModel, and the
        // write must still land (field 1.1.7: a contact added, the call right after found nothing).
        viewModelScope.launch(NonCancellable) {
            settingsRepository.setString(SettingsRepository.KEY_MY_CONTACTS, MyContactsCodec.encode(list))
        }
    }
}
