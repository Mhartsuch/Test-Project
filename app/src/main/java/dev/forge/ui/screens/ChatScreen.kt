package dev.forge.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import dev.forge.core.Role
import dev.forge.core.ToolCall
import dev.forge.ui.ChatViewModel
import dev.forge.ui.Markdown
import dev.forge.ui.UiMessage
import dev.forge.ui.theme.LocalForgeExtra
import kotlinx.coroutines.launch
import org.json.JSONObject

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(vm: ChatViewModel, onOpenSettings: () -> Unit, onMic: ((String) -> Unit) -> Unit, sharedText: String?) {
    val messages by vm.messages
    val title by vm.title
    val chats by vm.chats
    val running by vm.agent.running.collectAsState()
    val status by vm.agent.status.collectAsState()
    val approval by vm.agent.approval.collectAsState()
    val usage by vm.agent.usage.collectAsState()
    val drawer = rememberDrawerState(DrawerValue.Closed)
    val scope = rememberCoroutineScope()
    var input by remember(sharedText) { mutableStateOf(sharedText ?: "") }
    val listState = rememberLazyListState()
    val configured = vm.app.settings.isConfigured

    LaunchedEffect(messages.size, messages.lastOrNull()?.content?.length) {
        if (messages.isNotEmpty()) listState.animateScrollToItem(messages.size)
    }

    ModalNavigationDrawer(drawerState = drawer, drawerContent = {
        ModalDrawerSheet(drawerContainerColor = MaterialTheme.colorScheme.surfaceContainer, modifier = Modifier.width(300.dp)) {
            DrawerContent(chats = chats, currentId = vm.agent.conversation.collectAsState().value.id,
                onNew = { vm.newChat(); scope.launch { drawer.close() } },
                onOpen = { vm.open(it); scope.launch { drawer.close() } },
                onDelete = { vm.delete(it) },
                onSettings = { scope.launch { drawer.close() }; onOpenSettings() },
                usage = usage)
        }
    }) {
        Scaffold(
            containerColor = MaterialTheme.colorScheme.background,
            topBar = {
                CenterAlignedTopAppBar(
                    colors = TopAppBarDefaults.centerAlignedTopAppBarColors(containerColor = MaterialTheme.colorScheme.background),
                    navigationIcon = { IconButton(onClick = { scope.launch { drawer.open() } }) { Icon(Icons.Default.Menu, "Menu") } },
                    title = {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(title, style = MaterialTheme.typography.titleMedium, maxLines = 1)
                            Text(vm.app.settings.model.substringAfter('/').take(34), style = MaterialTheme.typography.labelMedium, color = LocalForgeExtra.current.muted)
                        }
                    },
                    actions = { IconButton(onClick = { vm.newChat() }) { Icon(Icons.Outlined.Edit, "New chat") } }
                )
            },
            bottomBar = {
                Column(Modifier.background(MaterialTheme.colorScheme.background)) {
                    approval?.let { ap -> ApprovalBar(ap.call, onApprove = { vm.approve(true) }, onDeny = { vm.approve(false) }) }
                    AnimatedVisibility(visible = running && status.isNotBlank()) {
                        Row(Modifier.padding(horizontal = 20.dp, vertical = 2.dp), verticalAlignment = Alignment.CenterVertically) {
                            CircularProgressIndicator(Modifier.size(12.dp), strokeWidth = 2.dp, color = MaterialTheme.colorScheme.primary)
                            Spacer(Modifier.width(8.dp)); Text(status, style = MaterialTheme.typography.bodySmall, color = LocalForgeExtra.current.muted)
                        }
                    }
                    Composer(value = input, onValueChange = { input = it }, running = running, enabled = configured,
                        onSend = { if (input.isNotBlank()) { vm.send(input.trim()); input = "" } },
                        onStop = { vm.stop() },
                        onMic = { onMic { heard -> input = (input + " " + heard).trim() } })
                }
            }
        ) { pad ->
            if (!configured) {
                Column(Modifier.padding(pad).fillMaxSize().padding(32.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("Welcome to Forge", style = MaterialTheme.typography.titleLarge)
                    Spacer(Modifier.height(8.dp))
                    Text("Add your OpenRouter key to start. GitHub is optional (needed for Forge to rebuild itself).", style = MaterialTheme.typography.bodyMedium, color = LocalForgeExtra.current.muted)
                    Spacer(Modifier.height(20.dp))
                    Button(onClick = onOpenSettings, colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)) { Text("Open settings") }
                }
            } else if (messages.isEmpty()) {
                EmptyState(Modifier.padding(pad), vm.app.settings.userName) { input = it }
            } else {
                LazyColumn(state = listState, modifier = Modifier.padding(pad).fillMaxSize(), contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp)) {
                    items(messages, key = { it.id }) { m -> MessageRow(m) }
                    item { Spacer(Modifier.height(8.dp)) }
                }
            }
        }
    }
}

@Composable
private fun EmptyState(modifier: Modifier, name: String, onSuggest: (String) -> Unit) {
    val greeting = if (name.isNotBlank()) "Good to see you, $name" else "What are we building?"
    Column(modifier.fillMaxSize().padding(horizontal = 28.dp), verticalArrangement = Arrangement.Center) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(28.dp).clip(CircleShape).background(MaterialTheme.colorScheme.primary))
            Spacer(Modifier.width(12.dp)); Text(greeting, style = MaterialTheme.typography.titleLarge)
        }
        Spacer(Modifier.height(24.dp))
        listOf(
            "Sync your source and tell me what you can improve about yourself",
            "Add a skill that lets you read .csv files and summarize them",
            "Add voice chat: speak my replies with TTS and listen with the mic",
            "Start a new Kotlin project in the workspace and set up a task board",
        ).forEach { s ->
            Surface(Modifier.fillMaxWidth().padding(vertical = 4.dp).clickable { onSuggest(s) }, shape = RoundedCornerShape(14.dp),
                color = MaterialTheme.colorScheme.surfaceContainer, border = androidx.compose.foundation.BorderStroke(1.dp, LocalForgeExtra.current.border)) {
                Text(s, Modifier.padding(14.dp), style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

@Composable
private fun MessageRow(m: UiMessage) {
    val extra = LocalForgeExtra.current
    when {
        m.isSummary -> Surface(Modifier.fillMaxWidth().padding(vertical = 6.dp), shape = RoundedCornerShape(12.dp), color = extra.toolCard, border = androidx.compose.foundation.BorderStroke(1.dp, extra.border)) {
            Expandable(header = { Text("Context compacted — summary", style = MaterialTheme.typography.labelMedium, color = extra.muted) }) { Markdown(m.content.substringAfter("\n\n")) }
        }
        m.role == Role.user -> Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), horizontalArrangement = Arrangement.End) {
            Surface(shape = RoundedCornerShape(20.dp, 20.dp, 4.dp, 20.dp), color = extra.userBubble, modifier = Modifier.widthIn(max = 320.dp)) {
                Text(m.content, Modifier.padding(horizontal = 16.dp, vertical = 10.dp), style = MaterialTheme.typography.bodyLarge)
            }
        }
        else -> Column(Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
            if (m.reasoning.isNotBlank()) {
                Expandable(header = { Text(if (m.streaming && m.content.isBlank()) "Thinking…" else "Thought process", style = MaterialTheme.typography.labelMedium, color = extra.muted) }) {
                    Text(m.reasoning, style = MaterialTheme.typography.bodySmall, color = extra.muted)
                }
            }
            if (m.content.isNotBlank()) Markdown(m.content)
            else if (m.streaming && m.toolCalls.isEmpty() && m.reasoning.isBlank()) TypingDots()
            m.toolCalls.forEach { c -> ToolCard(c, m.toolResults[c.id].orEmpty()) }
        }
    }
}

@Composable
private fun TypingDots() {
    Row(Modifier.padding(vertical = 8.dp)) { repeat(3) { Box(Modifier.padding(end = 4.dp).size(7.dp).clip(CircleShape).background(LocalForgeExtra.current.muted)) } }
}

@Composable
fun Expandable(initially: Boolean = false, header: @Composable () -> Unit, body: @Composable () -> Unit) {
    var open by remember { mutableStateOf(initially) }
    Column(Modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth().clickable { open = !open }.padding(vertical = 6.dp, horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(if (open) Icons.Default.ExpandLess else Icons.Default.ExpandMore, null, tint = LocalForgeExtra.current.muted, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(6.dp)); header()
        }
        AnimatedVisibility(open) { Box(Modifier.padding(start = 8.dp, bottom = 6.dp)) { body() } }
    }
}

@Composable
private fun ToolCard(call: ToolCall, result: String) {
    val extra = LocalForgeExtra.current
    val argsPreview = remember(call.arguments) {
        runCatching { val o = JSONObject(call.arguments); o.keys().asSequence().joinToString("  ") { k -> "$k: ${o.get(k).toString().replace('\n', ' ').take(60)}" } }.getOrDefault(call.arguments.take(80))
    }
    val done = result.isNotEmpty()
    val failed = result.startsWith("ERROR") || result.startsWith("DENIED")
    Surface(Modifier.fillMaxWidth().padding(vertical = 4.dp), shape = RoundedCornerShape(12.dp), color = extra.toolCard, border = androidx.compose.foundation.BorderStroke(1.dp, extra.border)) {
        Expandable(header = {
            Column {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(when { !done -> Icons.Outlined.HourglassEmpty; failed -> Icons.Outlined.ErrorOutline; else -> Icons.Outlined.CheckCircle }, null,
                        tint = if (failed) MaterialTheme.colorScheme.error else if (done) MaterialTheme.colorScheme.primary else extra.muted, modifier = Modifier.size(16.dp))
                    Spacer(Modifier.width(6.dp))
                    Text(call.name, style = MaterialTheme.typography.labelMedium.copy(fontFamily = FontFamily.Monospace, fontSize = 13.sp))
                }
                Text(argsPreview, style = MaterialTheme.typography.bodySmall, color = extra.muted, maxLines = 2)
            }
        }) {
            Column {
                Text("Arguments", style = MaterialTheme.typography.labelMedium, color = extra.muted)
                Text(runCatching { JSONObject(call.arguments).toString(2) }.getOrDefault(call.arguments).take(4000), fontFamily = FontFamily.Monospace, fontSize = 12.sp, lineHeight = 16.sp)
                if (done) {
                    Spacer(Modifier.height(6.dp)); Text("Result", style = MaterialTheme.typography.labelMedium, color = extra.muted)
                    Text(result.take(6000) + if (result.length > 6000) "\n…" else "", fontFamily = FontFamily.Monospace, fontSize = 12.sp, lineHeight = 16.sp)
                }
            }
        }
    }
}

@Composable
private fun ApprovalBar(call: ToolCall, onApprove: () -> Unit, onDeny: () -> Unit) {
    Surface(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp), shape = RoundedCornerShape(14.dp), color = MaterialTheme.colorScheme.surfaceContainerHigh) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("Allow ${call.name}?", style = MaterialTheme.typography.titleMedium)
                Text(call.arguments.take(120), style = MaterialTheme.typography.bodySmall, color = LocalForgeExtra.current.muted, maxLines = 2)
            }
            TextButton(onClick = onDeny) { Text("Deny") }
            Button(onClick = onApprove, colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)) { Text("Allow") }
        }
    }
}

@Composable
private fun Composer(value: String, onValueChange: (String) -> Unit, running: Boolean, enabled: Boolean, onSend: () -> Unit, onStop: () -> Unit, onMic: () -> Unit) {
    val extra = LocalForgeExtra.current
    Surface(Modifier.fillMaxWidth().padding(start = 12.dp, end = 12.dp, top = 6.dp, bottom = 12.dp).navigationBarsPadding().imePadding(),
        shape = RoundedCornerShape(24.dp), color = MaterialTheme.colorScheme.surfaceContainer, border = androidx.compose.foundation.BorderStroke(1.dp, extra.border)) {
        Column {
            TextField(value = value, onValueChange = onValueChange, enabled = enabled,
                placeholder = { Text("Ask Forge to build, fix, or improve itself…", color = extra.muted) },
                modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp, max = 200.dp),
                colors = TextFieldDefaults.colors(focusedContainerColor = Color.Transparent, unfocusedContainerColor = Color.Transparent, disabledContainerColor = Color.Transparent,
                    focusedIndicatorColor = Color.Transparent, unfocusedIndicatorColor = Color.Transparent, disabledIndicatorColor = Color.Transparent),
                keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences, imeAction = ImeAction.Default), maxLines = 8,
                textStyle = MaterialTheme.typography.bodyMedium)
            Row(Modifier.fillMaxWidth().padding(start = 8.dp, end = 8.dp, bottom = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onMic, enabled = enabled) { Icon(Icons.Outlined.Mic, "Voice input", tint = extra.muted) }
                Spacer(Modifier.weight(1f))
                if (running) {
                    FilledIconButton(onClick = onStop, colors = IconButtonDefaults.filledIconButtonColors(containerColor = MaterialTheme.colorScheme.onSurface), modifier = Modifier.size(38.dp)) {
                        Icon(Icons.Default.Stop, "Stop", tint = MaterialTheme.colorScheme.surface)
                    }
                } else {
                    FilledIconButton(onClick = onSend, enabled = enabled && value.isNotBlank(), modifier = Modifier.size(38.dp),
                        colors = IconButtonDefaults.filledIconButtonColors(containerColor = MaterialTheme.colorScheme.primary, disabledContainerColor = extra.border)) {
                        Icon(Icons.Default.ArrowUpward, "Send", tint = Color.White)
                    }
                }
            }
        }
    }
}

@Composable
private fun DrawerContent(chats: List<dev.forge.memory.ConversationStore.Summary>, currentId: String, onNew: () -> Unit, onOpen: (String) -> Unit, onDelete: (String) -> Unit, onSettings: () -> Unit, usage: Triple<Int, Int, Double>) {
    val extra = LocalForgeExtra.current
    Column(Modifier.fillMaxHeight().statusBarsPadding().padding(12.dp)) {
        Row(Modifier.padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(26.dp).clip(CircleShape).background(MaterialTheme.colorScheme.primary))
            Spacer(Modifier.width(10.dp)); Text("Forge", style = MaterialTheme.typography.titleLarge)
        }
        NavigationDrawerItem(label = { Text("New chat") }, icon = { Icon(Icons.Outlined.Edit, null) }, selected = false, onClick = onNew)
        NavigationDrawerItem(label = { Text("Settings") }, icon = { Icon(Icons.Outlined.Settings, null) }, selected = false, onClick = onSettings)
        Spacer(Modifier.height(12.dp)); Text("Chats", Modifier.padding(start = 16.dp, bottom = 4.dp), style = MaterialTheme.typography.labelMedium, color = extra.muted)
        LazyColumn(Modifier.weight(1f)) {
            items(chats, key = { it.id }) { c ->
                Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(if (c.id == currentId) MaterialTheme.colorScheme.surfaceContainerHigh else Color.Transparent)
                    .clickable { onOpen(c.id) }.padding(start = 16.dp, end = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(c.title, Modifier.weight(1f).padding(vertical = 10.dp), style = MaterialTheme.typography.bodyMedium, maxLines = 1)
                    IconButton(onClick = { onDelete(c.id) }, modifier = Modifier.size(32.dp)) { Icon(Icons.Outlined.DeleteOutline, "Delete", tint = extra.muted, modifier = Modifier.size(16.dp)) }
                }
            }
        }
        if (usage.first > 0) Text("Session: ${usage.first / 1000}k in / ${usage.second / 1000}k out" + (if (usage.third > 0) "  \$%.3f".format(usage.third) else ""), Modifier.padding(16.dp), style = MaterialTheme.typography.bodySmall, color = extra.muted)
    }
}
