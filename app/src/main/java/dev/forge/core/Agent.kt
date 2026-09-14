package dev.forge.core

import android.content.Intent
import android.util.Log
import dev.forge.ForgeApp
import dev.forge.service.AgentService
import dev.forge.tools.ToolContext
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

/**
 * The agent loop: stream a completion, execute tool calls, repeat until the model stops calling tools.
 * Runs inside a foreground service so long tasks continue while the screen is off.
 */
class Agent(private val app: ForgeApp) {
    private val TAG = "ForgeAgent"
    val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    data class Approval(val call: ToolCall, val decision: CompletableDeferred<Boolean>)

    private val _conversation = MutableStateFlow(newConversation())
    val conversation: StateFlow<Conversation> = _conversation
    private val _tick = MutableStateFlow(0L)
    /** Bumped on every visible change so the UI can re-snapshot. */
    val tick: StateFlow<Long> = _tick
    private val _running = MutableStateFlow(false)
    val running: StateFlow<Boolean> = _running
    private val _status = MutableStateFlow("")
    val status: StateFlow<String> = _status
    private val _approval = MutableStateFlow<Approval?>(null)
    val approval: StateFlow<Approval?> = _approval
    private val _usage = MutableStateFlow(Triple(0, 0, 0.0)) // prompt, completion, cost (session)
    val usage: StateFlow<Triple<Int, Int, Double>> = _usage

    private var job: Job? = null

    private fun bump() { _tick.value = _tick.value + 1 }

    fun newConversation(): Conversation = Conversation()

    fun startNew() { cancel(); _conversation.value = newConversation(); app.settings.lastConversationId = ""; bump() }

    fun open(id: String) {
        cancel()
        app.conversations.load(id)?.let { _conversation.value = it; app.settings.lastConversationId = id; bump() }
    }

    fun restoreLast() { app.settings.lastConversationId.takeIf { it.isNotBlank() }?.let { id -> app.conversations.load(id)?.let { _conversation.value = it; bump() } } }

    fun cancel() {
        job?.cancel(); job = null
        _approval.value?.decision?.complete(false); _approval.value = null
        val c = _conversation.value
        c.messages.lastOrNull()?.takeIf { it.streaming }?.let { it.streaming = false; if (it.content.isBlank() && it.toolCalls.isEmpty()) c.messages.remove(it) }
        _running.value = false; _status.value = ""; bump()
        app.conversations.save(c)
        app.stopService(Intent(app, AgentService::class.java))
    }

    fun send(text: String) {
        if (_running.value || text.isBlank()) return
        val conv = _conversation.value
        conv.messages += Message(Role.user, text).also { it.estimateTokens() }
        if (conv.messages.count { it.role == Role.user } == 1) conv.title = text.lines().first().take(48)
        app.settings.lastConversationId = conv.id
        bump()
        job = scope.launch {
            _running.value = true
            runCatching { app.startForegroundService(Intent(app, AgentService::class.java)) }
            try { loop(conv) } catch (e: Exception) { Log.e(TAG, "loop", e) } finally {
                _running.value = false; _status.value = ""; bump()
                app.conversations.save(conv)
                app.stopService(Intent(app, AgentService::class.java))
                AgentService.updateNotification(app, "Forge finished", conv.title)
            }
        }
    }

    private suspend fun loop(conv: Conversation) {
        val s = app.settings
        var rounds = 0
        while (rounds++ < s.maxToolRounds) {
            maybeCompact(conv)
            val lastUser = conv.messages.lastOrNull { it.role == Role.user }?.content ?: ""
            val skills = app.skills.matching(lastUser)
            val system = Prompts.system(app, conv) + skills.joinToString("") { "\n\n## Skill: ${it.name}\n${it.markdown}" }
            val wire = ContextManager.buildWire(system, conv.messages)
            val assistant = Message(Role.assistant, streaming = true)
            conv.messages += assistant; bump()
            _status.value = "Thinking…"
            AgentService.updateNotification(app, "Forge is working", conv.title)

            val partial = HashMap<Int, Triple<String, String, StringBuilder>>() // index -> (id, name, args)
            var error: String? = null
            var lastBump = 0L
            app.client.stream(s.model, wire, app.tools.schemas(), s.temperature, s.reasoningEffort) { ev ->
                when (ev) {
                    is StreamEvent.Text -> { assistant.content += ev.delta; _status.value = "Writing…" }
                    is StreamEvent.Reasoning -> { assistant.reasoning += ev.delta; _status.value = "Thinking…" }
                    is StreamEvent.ToolCallDelta -> {
                        val cur = partial[ev.index] ?: Triple("", "", StringBuilder())
                        partial[ev.index] = Triple(ev.id ?: cur.first, ev.name ?: cur.second, cur.third.apply { ev.argsDelta?.let { append(it) } })
                        _status.value = "Preparing tools…"
                    }
                    is StreamEvent.Usage -> _usage.value = Triple(_usage.value.first + ev.prompt, _usage.value.second + ev.completion, _usage.value.third + (ev.cost ?: 0.0))
                    is StreamEvent.Error -> error = ev.message
                    is StreamEvent.Done -> {}
                }
                val now = System.currentTimeMillis()
                if (now - lastBump > 60) { lastBump = now; bump() }
            }
            partial.toSortedMap().values.forEach { (id, name, args) ->
                if (name.isNotBlank()) assistant.toolCalls += ToolCall(id.ifBlank { "call_${System.nanoTime()}" }, name, args.toString().ifBlank { "{}" })
            }
            assistant.streaming = false; assistant.estimateTokens(); bump()
            if (error != null) {
                assistant.content += "\n\n**Error:** $error"
                if (error!!.contains("HTTP 401") || error!!.contains("HTTP 402")) assistant.content += "\n\nCheck your OpenRouter key/credits in Settings."
                bump(); return
            }
            if (assistant.toolCalls.isEmpty()) break

            app.conversations.save(conv)
            // Execute tool calls (in parallel when the model requested several)
            val results = withContext(Dispatchers.IO) {
                assistant.toolCalls.map { call -> async { call to execute(call, conv) } }.awaitAll()
            }
            results.forEach { (call, out) -> conv.messages += Message(Role.tool, out, toolCallId = call.id, toolName = call.name).also { it.estimateTokens() } }
            bump()
        }
        if (rounds >= s.maxToolRounds) conv.messages += Message(Role.assistant, "Stopped: reached the maximum of ${s.maxToolRounds} tool rounds. Say *continue* to keep going.")
    }

    private suspend fun execute(call: ToolCall, conv: Conversation): String {
        val tool = app.tools.get(call.name) ?: return "ERROR: unknown tool '${call.name}'. Available: ${app.tools.names().joinToString()}"
        val args = runCatching { JSONObject(call.arguments) }.getOrElse { return "ERROR: arguments are not valid JSON: ${it.message}" }
        if (tool.needsApproval && !app.settings.autoApproveTools) {
            val d = CompletableDeferred<Boolean>(); _approval.value = Approval(call, d)
            _status.value = "Waiting for approval: ${call.name}"; bump()
            val ok = d.await(); _approval.value = null
            if (!ok) return "DENIED by user."
        }
        _status.value = "Running ${call.name}…"; bump()
        val t0 = System.currentTimeMillis()
        val out = runCatching { tool.run(args, ToolContext(app, conv)) }.getOrElse { "ERROR: ${it::class.simpleName}: ${it.message}" }
        Log.i(TAG, "${call.name} took ${System.currentTimeMillis() - t0}ms → ${out.take(120).replace('\n', ' ')}")
        return if (out.length > 120_000) out.take(120_000) + "\n…[truncated ${out.length - 120_000} chars]" else out
    }

    /** Fold old turns into a summary when the context grows past the threshold. */
    private suspend fun maybeCompact(conv: Conversation) {
        val s = app.settings
        val system = Prompts.system(app, conv)
        if (ContextManager.estimate(system, conv.messages) < s.compactAtTokens) return
        val victims = ContextManager.selectForCompaction(conv.messages, keepTailTokens = s.compactAtTokens / 3)
        if (victims.size < 4) return
        _status.value = "Compacting context…"; bump()
        val prior = conv.messages.lastOrNull { it.isSummary && !it.compacted }
        val text = (prior?.let { "PREVIOUS SUMMARY:\n${it.content}\n\n" } ?: "") + ContextManager.renderForSummary(victims)
        val summary = runCatching { app.client.complete(s.effectiveSummaryModel, ContextManager.SUMMARY_SYSTEM, text, 6000) }
            .getOrElse { Log.w(TAG, "compaction failed: ${it.message}"); return }
        victims.forEach { it.compacted = true }; prior?.compacted = true
        val insertAt = conv.messages.indexOfFirst { !it.compacted }.let { if (it < 0) conv.messages.size else it }
        conv.messages.add(insertAt, Message(Role.user, "[Context summary — earlier part of this conversation was compacted]\n\n$summary", isSummary = true).also { it.estimateTokens() })
        app.conversations.save(conv); bump()
    }

    /** Optional: ask the model for a better title after the first exchange. */
    fun refreshTitle(conv: Conversation) = scope.launch {
        if (conv.messages.size < 2) return@launch
        val first = conv.messages.first { it.role == Role.user }.content.take(1500)
        runCatching { app.client.complete(app.settings.effectiveSummaryModel, "Reply with a 3–6 word title for this chat. No quotes, no punctuation.", first, 30) }
            .getOrNull()?.trim()?.takeIf { it.isNotBlank() }?.let { conv.title = it.take(60); app.conversations.save(conv); bump() }
    }
}
