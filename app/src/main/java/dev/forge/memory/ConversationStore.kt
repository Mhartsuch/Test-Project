package dev.forge.memory

import dev.forge.core.Conversation
import dev.forge.core.Message
import org.json.JSONObject
import java.io.File

/** JSONL-on-disk conversation persistence. First line is the header, remaining lines are messages. */
class ConversationStore(private val dir: File) {

    private fun fileOf(id: String) = File(dir, "$id.jsonl")

    fun save(c: Conversation) {
        c.updated = System.currentTimeMillis()
        val header = JSONObject().put("id", c.id).put("title", c.title).put("created", c.created)
            .put("updated", c.updated).put("taskId", c.taskId ?: JSONObject.NULL)
        val tmp = File(dir, "${c.id}.tmp")
        tmp.bufferedWriter().use { w ->
            w.write(header.toString()); w.newLine()
            for (m in c.messages) if (!m.streaming) { w.write(m.toStorage().toString()); w.newLine() }
        }
        tmp.renameTo(fileOf(c.id))
    }

    fun load(id: String): Conversation? {
        val f = fileOf(id).takeIf { it.exists() } ?: return null
        val lines = f.readLines().filter { it.isNotBlank() }
        if (lines.isEmpty()) return null
        val h = JSONObject(lines[0])
        val c = Conversation(h.getString("id"), h.optString("title", "Chat"), h.optLong("created"), h.optLong("updated"),
            taskId = h.optString("taskId", "").ifEmpty { null })
        lines.drop(1).forEach { l -> runCatching { c.messages += Message.fromStorage(JSONObject(l)) } }
        c.messages.forEach { it.estimateTokens() }
        return c
    }

    fun delete(id: String) = fileOf(id).delete()

    data class Summary(val id: String, val title: String, val updated: Long)

    fun listSummaries(): List<Summary> = dir.listFiles { f -> f.extension == "jsonl" }.orEmpty().mapNotNull { f ->
        runCatching {
            val h = JSONObject(f.bufferedReader().use { it.readLine() })
            Summary(h.getString("id"), h.optString("title", "Chat"), h.optLong("updated"))
        }.getOrNull()
    }.sortedByDescending { it.updated }

    /** Full-text search across transcripts (for the `chats_search` tool). */
    fun search(query: String, max: Int = 20): List<String> {
        val q = query.lowercase(); val out = mutableListOf<String>()
        for (s in listSummaries()) {
            val c = load(s.id) ?: continue
            for (m in c.messages) if (out.size < max && m.content.lowercase().contains(q)) {
                val i = m.content.lowercase().indexOf(q)
                out += "[${s.title}] (${m.role}) …${m.content.substring(maxOf(0, i - 80), minOf(m.content.length, i + 120)).replace("\n", " ")}…"
            }
        }
        return out
    }
}
