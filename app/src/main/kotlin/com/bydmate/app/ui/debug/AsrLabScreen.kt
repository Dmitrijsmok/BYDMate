package com.bydmate.app.ui.debug

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.bydmate.app.BuildConfig
import com.bydmate.app.voice.AsrLabResult
import com.bydmate.app.voice.speechPreRollDurations
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@Composable
fun AsrLabScreen(onBack: () -> Unit, viewModel: AsrLabViewModel = hiltViewModel()) {
    val selected by viewModel.store.selectedMs.collectAsStateWithLifecycle()
    val results by viewModel.store.results.collectAsStateWithLifecycle()
    val running by viewModel.running.collectAsStateWithLifecycle()
    var expanded by remember { mutableStateOf(false) }
    var exportError by remember { mutableStateOf<String?>(null) }
    val context = LocalContext.current
    val scope = androidx.compose.runtime.rememberCoroutineScope()
    val export = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/csv")) { uri: Uri? ->
        if (uri != null) scope.launch {
            exportError = withContext(Dispatchers.IO) {
                runCatching {
                    val output = context.contentResolver.openOutputStream(uri) ?: error("Cannot open destination")
                    output.bufferedWriter(Charsets.UTF_8).use { it.write(viewModel.store.csv()) }
                }.exceptionOrNull()?.let { "Ошибка экспорта: ${it.javaClass.simpleName}" }
            }
        }
    }
    val owner = LocalLifecycleOwner.current
    DisposableEffect(owner) {
        val observer = LifecycleEventObserver { _, event -> if (event == Lifecycle.Event.ON_STOP) viewModel.stop() }
        owner.lifecycle.addObserver(observer)
        onDispose {
            owner.lifecycle.removeObserver(observer)
            viewModel.stop()
        }
    }
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            TextButton(onClick = onBack) { Text("Назад в настройки") }
            Text("ASR Lab", style = MaterialTheme.typography.headlineSmall)
            Text("${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE}) · 16 кГц")
            Text("Только распознавание. Команды и AI не запускаются. Тестируйте на стоянке.")
            Text("SpeechPreRoll применяется к следующей фразе, включая обычные голосовые сессии. 0 мс — контроль.")
        }
        item {
            Column {
                Button(onClick = { expanded = true }, enabled = !running) { Text("SpeechPreRoll: $selected мс") }
                DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                    speechPreRollDurations.forEach { ms ->
                        DropdownMenuItem(text = { Text("$ms мс${if (ms == selected) " ✓" else ""}") }, onClick = {
                            viewModel.store.select(ms)
                            expanded = false
                        })
                    }
                }
            }
            Button(onClick = { if (running) viewModel.stop() else viewModel.start() }) {
                Text(if (running) "Остановить тест" else "PTT: начать один тест")
            }
            if (running) Text("Ожидание речи / распознавание… максимум 30 секунд")
            TextButton(onClick = { export.launch("BYDMate-ASR-Lab-${BuildConfig.VERSION_NAME}.csv") }, enabled = !running) {
                Text("Экспорт CSV (${results.size})")
            }
            TextButton(onClick = { viewModel.store.clear() }, enabled = !running) { Text("Очистить историю") }
            exportError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Text("Последние 100 тестов хранятся до закрытия процесса. Аудиозаписи не сохраняются.")
        }
        items(results) { result -> AsrLabResultCard(result) }
    }
}

@Composable
private fun AsrLabResultCard(result: AsrLabResult) {
    val formatter = remember { SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()) }
    val labels = listOf("PTT", "AudioRecord open", "AudioRecord ready", "First PCM", "VAD start", "Decode start", "Decode complete")
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("${formatter.format(Date(result.timestampMs))} · ${result.preRollMs} мс")
            SelectionContainer { Text(result.transcript.ifEmpty { "(пустой результат)" }, style = MaterialTheme.typography.titleMedium) }
            result.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            HorizontalDivider()
            result.stagesNs.forEachIndexed { index, stage ->
                val sincePtt = stage?.let { (it - result.stagesNs.first()!!) / 1_000_000.0 }
                Text("${labels[index]}: ${sincePtt?.let { "%.1f".format(Locale.ROOT, it) } ?: "—"} мс от PTT")
            }
            Text("PCM: VAD ${result.vadSamples ?: "—"}, decode ${result.decodedSamples ?: "—"} samples")
        }
    }
}
