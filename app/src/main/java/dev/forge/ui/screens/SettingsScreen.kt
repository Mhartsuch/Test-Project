package dev.forge.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import dev.forge.BuildConfig
import dev.forge.ForgeApp
import dev.forge.core.ModelInfo
import dev.forge.ui.theme.LocalForgeExtra
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(onBack: () -> Unit, onThemeChanged: (String) -> Unit) {
    val app = ForgeApp.instance; val s = app.settings
    val scope = rememberCoroutineScope()
    val extra = LocalForgeExtra.current
    var key by remember { mutableStateOf(s.openRouterKey) }
    var model by remember { mutableStateOf(s.model) }
    var summaryModel by remember { mutableStateOf(s.summaryModel) }
    var ghToken by remember { mutableStateOf(s.githubToken) }
    var ghRepo by remember { mutableStateOf(s.githubRepo) }
    var ghBranch by remember { mutableStateOf(s.githubBranch) }
    var maxCtx by remember { mutableStateOf(s.maxContextTokens.toString()) }
    var compactAt by remember { mutableStateOf(s.compactAtTokens.toString()) }
    var rounds by remember { mutableStateOf(s.maxToolRounds.toString()) }
    var effort by remember { mutableStateOf(s.reasoningEffort) }
    var auto by remember { mutableStateOf(s.autoApproveTools) }
    var theme by remember { mutableStateOf(s.darkMode) }
    var userName by remember { mutableStateOf(s.userName) }
    var pickerFor by remember { mutableStateOf<String?>(null) }
    var models by remember { mutableStateOf<List<ModelInfo>>(emptyList()) }
    var loadingModels by remember { mutableStateOf(false) }
    var msg by remember { mutableStateOf("") }

    fun save() {
        s.openRouterKey = key.trim(); s.model = model.trim(); s.summaryModel = summaryModel.trim()
        s.githubToken = ghToken.trim(); s.githubRepo = ghRepo.trim(); s.githubBranch = ghBranch.trim().ifBlank { "main" }
        s.maxContextTokens = maxCtx.toIntOrNull() ?: 120_000; s.compactAtTokens = compactAt.toIntOrNull() ?: 90_000
        s.maxToolRounds = rounds.toIntOrNull() ?: 200; s.reasoningEffort = effort; s.autoApproveTools = auto
        s.darkMode = theme; s.userName = userName.trim(); onThemeChanged(theme)
        msg = "Saved"
    }
    fun loadModels() { if (models.isEmpty() && !loadingModels) { loadingModels = true; scope.launch { runCatching { models = app.client.listModels() }.onFailure { msg = "Model list: ${it.message}" }; loadingModels = false } } }

    Scaffold(containerColor = MaterialTheme.colorScheme.background, topBar = {
        TopAppBar(title = { Text("Settings") }, colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
            navigationIcon = { IconButton(onClick = { save(); onBack() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } },
            actions = { TextButton(onClick = { save() }) { Text("Save") } })
    }) { pad ->
        Column(Modifier.padding(pad).fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp)) {
            if (msg.isNotBlank()) Text(msg, color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.bodySmall)

            Section("OpenRouter")
            OutlinedTextField(key, { key = it }, label = { Text("API key") }, singleLine = true, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth())
            ModelField("Model", model, { model = it }) { pickerFor = "model"; loadModels() }
            ModelField("Summary/title model (blank = same)", summaryModel, { summaryModel = it }) { pickerFor = "summary"; loadModels() }
            Text("Reasoning effort", style = MaterialTheme.typography.labelMedium, color = extra.muted, modifier = Modifier.padding(top = 8.dp))
            Row { listOf("none", "low", "medium", "high").forEach { e -> FilterChip(selected = effort == e, onClick = { effort = e }, label = { Text(e) }, modifier = Modifier.padding(end = 6.dp)) } }

            Section("Self-evolution (GitHub)")
            Text("Forge pushes its own source here; GitHub Actions builds the APK. Create a repo from the Forge zip, then a fine-grained token with Contents + Actions read/write.", style = MaterialTheme.typography.bodySmall, color = extra.muted)
            OutlinedTextField(ghRepo, { ghRepo = it }, label = { Text("Repository (owner/name)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(ghBranch, { ghBranch = it }, label = { Text("Branch") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(ghToken, { ghToken = it }, label = { Text("GitHub token") }, singleLine = true, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth())
            Row(Modifier.padding(top = 6.dp)) {
                OutlinedButton(onClick = { save(); scope.launch { msg = runCatching { app.github.syncSource(app.paths.selfSource) }.getOrElse { "Sync failed: ${it.message}" } } }) { Text("Sync source now") }
                Spacer(Modifier.width(8.dp))
                OutlinedButton(onClick = { save(); scope.launch { msg = runCatching { app.updater.installLatest() }.getOrElse { "Update failed: ${it.message}" } } }) { Text("Install latest build") }
            }

            Section("Long-horizon")
            OutlinedTextField(maxCtx, { maxCtx = it }, label = { Text("Max context tokens") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(compactAt, { compactAt = it }, label = { Text("Compact when above (tokens)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(rounds, { rounds = it }, label = { Text("Max tool rounds per message") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 4.dp)) {
                Switch(checked = auto, onCheckedChange = { auto = it }); Spacer(Modifier.width(8.dp))
                Text("Auto-approve destructive tools (delete, push, install)", style = MaterialTheme.typography.bodyMedium)
            }

            Section("Appearance")
            Row { listOf("system", "light", "dark").forEach { t -> FilterChip(selected = theme == t, onClick = { theme = t }, label = { Text(t) }, modifier = Modifier.padding(end = 6.dp)) } }
            OutlinedTextField(userName, { userName = it }, label = { Text("Your name (optional)") }, singleLine = true, modifier = Modifier.fillMaxWidth())

            Section("About")
            Text("Forge ${BuildConfig.FORGE_VERSION} · ${app.tools.names().size} tools · ${app.skills.all().size} skills · root ${app.paths.root}", style = MaterialTheme.typography.bodySmall, color = extra.muted)
            Spacer(Modifier.height(40.dp))
        }
    }

    pickerFor?.let { which ->
        var q by remember { mutableStateOf("") }
        AlertDialog(onDismissRequest = { pickerFor = null }, confirmButton = { TextButton(onClick = { pickerFor = null }) { Text("Close") } },
            title = { Text("Choose model") }, text = {
                Column(Modifier.heightIn(max = 480.dp)) {
                    OutlinedTextField(q, { q = it }, placeholder = { Text("Search: fable, deepseek, glm…") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    if (loadingModels) LinearProgressIndicator(Modifier.fillMaxWidth().padding(vertical = 8.dp))
                    val filtered = models.filter { q.isBlank() || it.id.contains(q, true) || it.name.contains(q, true) }.sortedByDescending { it.supportsTools }
                    LazyColumn { items(filtered.take(200), key = { it.id }) { m ->
                        Column(Modifier.fillMaxWidth().clickable { if (which == "model") model = m.id else summaryModel = m.id; pickerFor = null }.padding(vertical = 8.dp)) {
                            Text(m.id, style = MaterialTheme.typography.bodyMedium)
                            Text("${m.contextLength / 1000}k ctx · ${if (m.supportsTools) "tools ✓" else "no tools"} · \$${"%.2f".format(m.promptPrice * 1_000_000)}/\$${"%.2f".format(m.completionPrice * 1_000_000)} per M", style = MaterialTheme.typography.bodySmall, color = extra.muted)
                        }
                    } }
                }
            })
    }
}

@Composable private fun Section(t: String) { Text(t, Modifier.padding(top = 20.dp, bottom = 6.dp), style = MaterialTheme.typography.titleMedium) }

@Composable private fun ModelField(label: String, value: String, onChange: (String) -> Unit, onPick: () -> Unit) {
    OutlinedTextField(value, onChange, label = { Text(label) }, singleLine = true, modifier = Modifier.fillMaxWidth().padding(top = 6.dp),
        trailingIcon = { TextButton(onClick = onPick) { Text("Browse") } })
}
