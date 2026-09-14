package dev.forge.core

import org.json.JSONObject

/**
 * Long-horizon context management.
 *
 * Strategy (in order):
 *  1. Tool results older than the last few turns are truncated to a short head (they can be re-read from disk).
 *  2. When the estimated token count still exceeds `compactAt`, the oldest uncompacted messages are
 *     summarized by the model into a single "summary" message that preserves decisions, file paths,
 *     open problems and next steps. Originals stay on disk (marked compacted) so nothing is lost.
 *  3. The current task board + memory index is always re-injected via the system prompt, so the
 *     agent can recover its place even after aggressive compaction or an app restart.
 */
object ContextManager {
    /** ~4 chars/token is good enough for budgeting across model families. */
    fun estimateTokens(s: String): Int = if (s.isEmpty()) 0 else (s.length / 3.6).toInt() + 1

    const val TOOL_RESULT_KEEP_RECENT = 6
    const val TOOL_RESULT_TRUNCATE_TO = 1200

    /** Build the wire message list from a conversation, applying truncation of stale tool output. */
    fun buildWire(system: String, messages: List<Message>): List<JSONObject> {
        val active = messages.filter { !it.compacted }
        val out = ArrayList<JSONObject>(active.size + 1)
        out += JSONObject().put("role", "system").put("content", system)
        val toolIdx = active.withIndex().filter { it.value.role == Role.tool }.map { it.index }
        val keepFrom = if (toolIdx.size > TOOL_RESULT_KEEP_RECENT) toolIdx[toolIdx.size - TOOL_RESULT_KEEP_RECENT] else -1
        active.forEachIndexed { i, m ->
            val wire = m.toWire()
            if (m.role == Role.tool && i < keepFrom && m.content.length > TOOL_RESULT_TRUNCATE_TO) {
                wire.put("content", m.content.take(TOOL_RESULT_TRUNCATE_TO) + "\n…[truncated ${m.content.length - TOOL_RESULT_TRUNCATE_TO} chars; re-run the tool if you need this again]")
            }
            out += wire
        }
        return out
    }

    fun estimate(system: String, messages: List<Message>): Int =
        estimateTokens(system) + messages.filter { !it.compacted }.sumOf { it.tokens.takeIf { t -> t > 0 } ?: it.estimateTokens() }

    /**
     * Chooses which messages to fold into a summary: everything except the trailing `keepTail` tokens,
     * never splitting an assistant tool-call from its tool results.
     */
    fun selectForCompaction(messages: List<Message>, keepTailTokens: Int): List<Message> {
        val active = messages.filter { !it.compacted && !it.isSummary }
        var tail = 0
        var cut = active.size
        for (i in active.indices.reversed()) {
            tail += active[i].tokens.takeIf { it > 0 } ?: active[i].estimateTokens()
            if (tail > keepTailTokens) { cut = i; break }
        }
        // don't start the tail on a tool result (would orphan it)
        while (cut < active.size && active[cut].role == Role.tool) cut++
        return active.subList(0, cut)
    }

    val SUMMARY_SYSTEM = """You are compacting the working memory of an autonomous coding agent so it can continue a long task.
Write a dense, factual summary in markdown with these sections:
## Goal
## Decisions & constraints
## Files touched (paths + what changed)
## Current state / what works
## Open problems / errors seen
## Next steps (ordered)
## Facts to remember (user preferences, ids, URLs, commands that worked)
Preserve exact file paths, function names, error strings and commands. Do not invent anything. Be complete but concise."""

    fun renderForSummary(msgs: List<Message>): String = buildString {
        for (m in msgs) {
            when (m.role) {
                Role.user -> append("USER: ").append(m.content).append("\n\n")
                Role.assistant -> {
                    if (m.content.isNotBlank()) append("ASSISTANT: ").append(m.content).append("\n")
                    m.toolCalls.forEach { append("ASSISTANT CALLED ${it.name}(${it.arguments.take(600)})\n") }
                    append("\n")
                }
                Role.tool -> append("TOOL ${m.toolName}: ").append(m.content.take(1500)).append("\n\n")
                Role.system -> {}
            }
        }
    }
}
