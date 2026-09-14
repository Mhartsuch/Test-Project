package dev.forge.tools

import org.json.JSONArray
import org.json.JSONObject

object MemoryTools {
    fun all(): List<Tool> = listOf(memRead, memWrite, memAppend, memSearch, memDelete,
        taskCreate, taskUpdate, taskNote, taskList, chatsSearch, settingsGet, settingsSet)

    private val memRead = object : Tool("memory_read", "Read a memory markdown file (e.g. profile.md, areas/forge.md).",
        Schema.obj("path" to Schema.str("Relative path inside memory dir"), required = listOf("path"))) {
        override suspend fun run(args: JSONObject, ctx: ToolContext) = ctx.app.memory.read(args.getString("path")).ifEmpty { "(empty or missing)" }
    }
    private val memWrite = object : Tool("memory_write",
        "Create/overwrite a memory file. Use frontmatter (name, description). Put durable facts only: user identity, preferences, projects, decisions. Link related files with [[name]].",
        Schema.obj("path" to Schema.str("Relative path, e.g. areas/my-app.md"), "content" to Schema.str("Full markdown"), required = listOf("path", "content"))) {
        override suspend fun run(args: JSONObject, ctx: ToolContext): String { ctx.app.memory.write(args.getString("path"), args.getString("content")); return "saved ${args.getString("path")}" }
    }
    private val memAppend = object : Tool("memory_append", "Append a line to a memory file (creates it if missing).",
        Schema.obj("path" to Schema.str("Relative path"), "line" to Schema.str("Line to append"), required = listOf("path", "line"))) {
        override suspend fun run(args: JSONObject, ctx: ToolContext): String { ctx.app.memory.append(args.getString("path"), args.getString("line")); return "appended" }
    }
    private val memSearch = object : Tool("memory_search", "Grep all memory files for a phrase.",
        Schema.obj("query" to Schema.str("Search text"), required = listOf("query"))) {
        override suspend fun run(args: JSONObject, ctx: ToolContext) = ctx.app.memory.search(args.getString("query")).joinToString("\n").ifEmpty { "no matches" }
    }
    private val memDelete = object : Tool("memory_delete", "Delete a memory file.", Schema.obj("path" to Schema.str("Relative path"), required = listOf("path"))) {
        override val needsApproval = true
        override suspend fun run(args: JSONObject, ctx: ToolContext) = if (ctx.app.memory.delete(args.getString("path"))) "deleted" else "not found"
    }

    private val taskCreate = object : Tool("task_create",
        "Create a long-horizon task with an ordered checklist. Attaches it to this chat. Do this before any multi-step work.",
        Schema.obj("title" to Schema.str("Short title"), "goal" to Schema.str("What done looks like"), "steps" to Schema.arr("Ordered steps"), required = listOf("title", "goal", "steps"))) {
        override suspend fun run(args: JSONObject, ctx: ToolContext): String {
            val steps = args.getJSONArray("steps").let { a -> (0 until a.length()).map { a.getString(it) } }
            val t = ctx.app.tasks.create(args.getString("title"), args.getString("goal"), steps)
            ctx.conversation.taskId = t.id
            return "created task ${t.id} with ${steps.size} steps"
        }
    }
    private val taskUpdate = object : Tool("task_update",
        "Update a task: mark steps done/active/blocked, add steps, or change task status (active|paused|done|abandoned).",
        Schema.obj("task_id" to Schema.str("Task id (default: this chat's task)"),
            "step_status" to Schema.str("JSON object {stepId: status}"),
            "add_steps" to Schema.arr("New steps to append"),
            "status" to Schema.str("Task status"), "title" to Schema.str("New title"))) {
        override suspend fun run(args: JSONObject, ctx: ToolContext): String {
            val id = args.optString("task_id", "").ifEmpty { ctx.conversation.taskId ?: return "ERROR: no task; task_create first" }
            val t = ctx.app.tasks.get(id) ?: return "ERROR: task $id not found"
            args.optString("step_status", "").takeIf { it.isNotBlank() }?.let { js ->
                val o = JSONObject(js); o.keys().forEach { k -> t.steps.firstOrNull { it.id == k.toIntOrNull() }?.status = o.getString(k) }
            }
            args.optJSONArray("add_steps")?.let { a -> for (i in 0 until a.length()) t.steps += dev.forge.memory.TaskBoard.Step(t.steps.size + 1, a.getString(i), "pending") }
            args.optString("status", "").takeIf { it.isNotBlank() }?.let { t.status = it }
            args.optString("title", "").takeIf { it.isNotBlank() }?.let { t.title = it }
            if (t.steps.none { it.status == "active" }) t.steps.firstOrNull { it.status == "pending" }?.status = "active"
            ctx.app.tasks.save(t)
            return "updated:\n" + ctx.app.tasks.render(t.id)
        }
    }
    private val taskNote = object : Tool("task_note", "Append a scratchpad note (finding, error, decision) to the task. Survives compaction.",
        Schema.obj("note" to Schema.str("Note text"), "task_id" to Schema.str("Task id (default: this chat's)"), required = listOf("note"))) {
        override suspend fun run(args: JSONObject, ctx: ToolContext): String {
            val id = args.optString("task_id", "").ifEmpty { ctx.conversation.taskId ?: return "ERROR: no task" }
            val t = ctx.app.tasks.get(id) ?: return "ERROR: task not found"
            t.notes += args.getString("note"); ctx.app.tasks.save(t); return "noted (${t.notes.size} notes)"
        }
    }
    private val taskList = object : Tool("task_list", "List all tasks (any status) with ids.", Schema.obj()) {
        override suspend fun run(args: JSONObject, ctx: ToolContext) =
            ctx.app.tasks.all().joinToString("\n") { "[${it.id}] ${it.status} — ${it.title} (${it.steps.count { s -> s.status == "done" }}/${it.steps.size})" }.ifEmpty { "no tasks" }
    }
    private val chatsSearch = object : Tool("chats_search", "Search past conversations for a phrase.", Schema.obj("query" to Schema.str("Text"), required = listOf("query"))) {
        override suspend fun run(args: JSONObject, ctx: ToolContext) = ctx.app.conversations.search(args.getString("query")).joinToString("\n").ifEmpty { "no matches" }
    }
    private val settingsGet = object : Tool("settings_get", "Read Forge's current settings (model, context budget, repo…). Secrets are never returned.", Schema.obj()) {
        override suspend fun run(args: JSONObject, ctx: ToolContext) = JSONObject(ctx.app.settings.snapshot()).toString(2)
    }
    private val settingsSet = object : Tool("settings_set", "Change a setting: model, summaryModel, maxContextTokens, compactAtTokens, maxToolRounds, temperature, reasoningEffort, githubRepo, githubBranch.",
        Schema.obj("key" to Schema.str("Setting name"), "value" to Schema.str("New value"), required = listOf("key", "value"))) {
        override suspend fun run(args: JSONObject, ctx: ToolContext): String {
            val s = ctx.app.settings; val v = args.getString("value")
            when (args.getString("key")) {
                "model" -> s.model = v; "summaryModel" -> s.summaryModel = v
                "maxContextTokens" -> s.maxContextTokens = v.toInt(); "compactAtTokens" -> s.compactAtTokens = v.toInt()
                "maxToolRounds" -> s.maxToolRounds = v.toInt(); "temperature" -> s.temperature = v.toFloat()
                "reasoningEffort" -> s.reasoningEffort = v; "githubRepo" -> s.githubRepo = v; "githubBranch" -> s.githubBranch = v
                else -> return "ERROR: unknown key"
            }
            return "ok"
        }
    }
}
