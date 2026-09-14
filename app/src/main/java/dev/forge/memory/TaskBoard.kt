package dev.forge.memory

import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID

/**
 * Long-horizon task board. Each task is a JSON file with a goal, ordered steps (with status),
 * running notes, and a status. Rendered into the system prompt each turn.
 */
class TaskBoard(private val dir: File) {

    data class Step(val id: Int, var text: String, var status: String) // pending|active|done|blocked
    data class Task(
        val id: String, var title: String, var goal: String, var status: String, // active|paused|done|abandoned
        val steps: MutableList<Step>, val notes: MutableList<String>, val created: Long, var updated: Long
    )

    private fun fileOf(id: String) = File(dir, "$id.json")

    fun create(title: String, goal: String, steps: List<String>): Task {
        val t = Task(UUID.randomUUID().toString().take(8), title, goal, "active",
            steps.mapIndexed { i, s -> Step(i + 1, s, if (i == 0) "active" else "pending") }.toMutableList(),
            mutableListOf(), System.currentTimeMillis(), System.currentTimeMillis())
        save(t); return t
    }

    fun get(id: String): Task? = fileOf(id).takeIf { it.exists() }?.let { parse(JSONObject(it.readText())) }

    fun all(): List<Task> = dir.listFiles { f -> f.extension == "json" }.orEmpty()
        .mapNotNull { runCatching { parse(JSONObject(it.readText())) }.getOrNull() }.sortedByDescending { it.updated }

    fun active(): List<Task> = all().filter { it.status == "active" }

    fun save(t: Task) {
        t.updated = System.currentTimeMillis()
        fileOf(t.id).writeText(toJson(t).toString(2))
    }

    fun render(focusId: String?): String {
        val tasks = active()
        if (tasks.isEmpty()) return ""
        return buildString {
            for (t in tasks) {
                val focus = if (t.id == focusId) " (this chat)" else ""
                appendLine("### [${t.id}] ${t.title}$focus — ${t.status}")
                appendLine("Goal: ${t.goal}")
                t.steps.forEach { s ->
                    val mark = when (s.status) { "done" -> "[x]"; "active" -> "[>]"; "blocked" -> "[!]"; else -> "[ ]" }
                    appendLine("  $mark ${s.id}. ${s.text}")
                }
                if (t.notes.isNotEmpty()) {
                    appendLine("Notes (last ${minOf(8, t.notes.size)}):")
                    t.notes.takeLast(8).forEach { appendLine("  - $it") }
                }
            }
        }
    }

    private fun toJson(t: Task) = JSONObject()
        .put("id", t.id).put("title", t.title).put("goal", t.goal).put("status", t.status)
        .put("steps", JSONArray().apply { t.steps.forEach { put(JSONObject().put("id", it.id).put("text", it.text).put("status", it.status)) } })
        .put("notes", JSONArray(t.notes)).put("created", t.created).put("updated", t.updated)

    private fun parse(o: JSONObject): Task {
        val steps = o.getJSONArray("steps").let { a -> (0 until a.length()).map { val s = a.getJSONObject(it); Step(s.getInt("id"), s.getString("text"), s.getString("status")) } }
        val notes = o.optJSONArray("notes")?.let { a -> (0 until a.length()).map { a.getString(it) } } ?: emptyList()
        return Task(o.getString("id"), o.getString("title"), o.getString("goal"), o.getString("status"),
            steps.toMutableList(), notes.toMutableList(), o.optLong("created"), o.optLong("updated"))
    }
}
