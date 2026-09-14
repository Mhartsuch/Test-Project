package dev.forge.ui

import androidx.compose.runtime.State
import androidx.compose.runtime.mutableStateOf
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dev.forge.ForgeApp
import dev.forge.core.Message
import dev.forge.core.Role
import dev.forge.core.ToolCall
import dev.forge.memory.ConversationStore
import kotlinx.coroutines.launch

/** Immutable snapshot for Compose. */
data class UiMessage(
    val id: String, val role: Role, val content: String, val reasoning: String, val streaming: Boolean,
    val toolCalls: List<ToolCall>, val toolResults: Map<String, String>, val isSummary: Boolean,
)

class ChatViewModel : ViewModel() {
    val app = ForgeApp.instance
    val agent = app.agent

    private val _messages = mutableStateOf<List<UiMessage>>(emptyList())
    val messages: State<List<UiMessage>> = _messages
    private val _title = mutableStateOf("New chat")
    val title: State<String> = _title
    private val _chats = mutableStateOf<List<ConversationStore.Summary>>(emptyList())
    val chats: State<List<ConversationStore.Summary>> = _chats

    init {
        agent.restoreLast()
        viewModelScope.launch { agent.tick.collect { snapshot() } }
        refreshChats()
    }

    private fun snapshot() {
        val conv = agent.conversation.value
        val results = conv.messages.filter { it.role == Role.tool }.associate { (it.toolCallId ?: "") to it.content }
        _messages.value = conv.messages.filter { it.role != Role.tool && it.role != Role.system }.map { m ->
            UiMessage(m.id, m.role, m.content, m.reasoning, m.streaming, m.toolCalls.toList(), m.toolCalls.associate { it.id to (results[it.id] ?: "") }, m.isSummary)
        }
        _title.value = conv.title
    }

    fun send(text: String) { agent.send(text); if (agent.conversation.value.messages.size <= 1) viewModelScope.launch { kotlinx.coroutines.delay(4000); agent.refreshTitle(agent.conversation.value); refreshChats() } }
    fun stop() = agent.cancel()
    fun newChat() { agent.startNew(); refreshChats() }
    fun open(id: String) { agent.open(id) }
    fun delete(id: String) { app.conversations.delete(id); if (agent.conversation.value.id == id) agent.startNew(); refreshChats() }
    fun refreshChats() { _chats.value = app.conversations.listSummaries() }
    fun approve(ok: Boolean) { agent.approval.value?.decision?.complete(ok) }
}
