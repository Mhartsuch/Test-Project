package dev.forge.tools

import org.json.JSONObject
import java.io.File
import java.util.zip.ZipInputStream

object FileTools {
    private const val MAX_READ = 60_000

    fun all(): List<Tool> = listOf(read, write, edit, list, grep, delete, move, unzip)

    private val read = object : Tool("fs_read",
        "Read a text file. Relative paths resolve against the workspace. Use offset/limit (line numbers, 1-based) for large files.",
        Schema.obj("path" to Schema.str("File path"), "offset" to Schema.int("First line (1-based)"), "limit" to Schema.int("Max lines"), required = listOf("path"))) {
        override suspend fun run(args: JSONObject, ctx: ToolContext): String {
            val f = Sandbox.resolve(ctx.app, args.getString("path"))
            if (!f.exists()) return "ERROR: not found: $f"
            if (f.isDirectory) return "ERROR: is a directory (use fs_list)"
            val lines = f.readLines()
            val off = (args.optInt("offset", 1) - 1).coerceIn(0, lines.size)
            val lim = args.optInt("limit", 0).let { if (it <= 0) lines.size else it }
            val slice = lines.drop(off).take(lim)
            val text = slice.mapIndexed { i, l -> "${off + i + 1}\t$l" }.joinToString("\n")
            return (if (text.length > MAX_READ) text.take(MAX_READ) + "\n…[truncated; use offset/limit]" else text) +
                "\n[${lines.size} lines total]"
        }
    }

    private val write = object : Tool("fs_write",
        "Create or overwrite a file with the given content (creates parent dirs). Only inside Forge root/workspace.",
        Schema.obj("path" to Schema.str("File path"), "content" to Schema.str("Full file content"), required = listOf("path", "content"))) {
        override suspend fun run(args: JSONObject, ctx: ToolContext): String {
            val f = Sandbox.resolve(ctx.app, args.getString("path")); Sandbox.assertWritable(ctx.app, f)
            f.parentFile?.mkdirs(); f.writeText(args.getString("content"))
            return "wrote ${f.length()} bytes to $f"
        }
    }

    private val edit = object : Tool("fs_edit",
        "Replace an exact, unique substring in a file with new text. Fails if old_str is missing or ambiguous. Prefer this over fs_write for small changes.",
        Schema.obj("path" to Schema.str("File path"), "old_str" to Schema.str("Exact text to replace (must appear once)"), "new_str" to Schema.str("Replacement text"), required = listOf("path", "old_str", "new_str"))) {
        override suspend fun run(args: JSONObject, ctx: ToolContext): String {
            val f = Sandbox.resolve(ctx.app, args.getString("path")); Sandbox.assertWritable(ctx.app, f)
            if (!f.isFile) return "ERROR: not found: $f"
            val src = f.readText(); val old = args.getString("old_str")
            var count = 0; var at = if (old.isEmpty()) -1 else src.indexOf(old)
            while (at >= 0) { count++; at = src.indexOf(old, at + 1) }
            if (count == 0) return "ERROR: old_str not found. Read the file and copy the exact text."
            if (count > 1) return "ERROR: old_str matches $count times; include more surrounding context."
            f.writeText(src.replaceFirst(old, args.getString("new_str")))
            return "edited $f"
        }
    }

    private val list = object : Tool("fs_list",
        "List a directory tree (default depth 2). Shows sizes. Skips node_modules/.git/build.",
        Schema.obj("path" to Schema.str("Directory (default: workspace)"), "depth" to Schema.int("Max depth"))) {
        override suspend fun run(args: JSONObject, ctx: ToolContext): String {
            val dir = if (args.has("path")) Sandbox.resolve(ctx.app, args.getString("path")) else ctx.app.paths.workspace
            if (!dir.isDirectory) return "ERROR: not a directory: $dir"
            val depth = args.optInt("depth", 2)
            val sb = StringBuilder("$dir\n"); var n = 0
            fun walk(d: File, level: Int) {
                if (level > depth || n > 800) return
                d.listFiles()?.sortedWith(compareBy({ !it.isDirectory }, { it.name }))?.forEach { f ->
                    if (f.name in setOf("node_modules", ".git", "build", ".gradle")) return@forEach
                    n++; sb.append("  ".repeat(level)).append(if (f.isDirectory) "${f.name}/" else "${f.name} (${f.length()})").append('\n')
                    if (f.isDirectory) walk(f, level + 1)
                }
            }
            walk(dir, 1); if (n > 800) sb.append("…[truncated]")
            return sb.toString()
        }
    }

    private val grep = object : Tool("fs_grep",
        "Search files for a regex. Returns path:line: text. Optional glob filter like *.kt.",
        Schema.obj("pattern" to Schema.str("Regex (case-insensitive)"), "path" to Schema.str("Root dir (default workspace)"), "glob" to Schema.str("Filename glob, e.g. *.kt"), "max" to Schema.int("Max matches (default 60)"), required = listOf("pattern"))) {
        override suspend fun run(args: JSONObject, ctx: ToolContext): String {
            val root = if (args.has("path")) Sandbox.resolve(ctx.app, args.getString("path")) else ctx.app.paths.workspace
            val re = Regex(args.getString("pattern"), RegexOption.IGNORE_CASE)
            val glob = args.optString("glob", "").takeIf { it.isNotEmpty() }?.let { Regex("^" + Regex.escape(it).replace("\\*", ".*").replace("\\?", ".") + "$") }
            val max = args.optInt("max", 60); val out = mutableListOf<String>()
            root.walkTopDown().onEnter { it.name !in setOf("node_modules", ".git", "build", ".gradle") }.filter { it.isFile && (glob == null || glob.matches(it.name)) && it.length() < 2_000_000 }.forEach { f ->
                if (out.size >= max) return@forEach
                runCatching { f.readLines().forEachIndexed { i, l -> if (out.size < max && re.containsMatchIn(l)) out += "${f.relativeTo(root).path}:${i + 1}: ${l.trim().take(200)}" } }
            }
            return if (out.isEmpty()) "no matches" else out.joinToString("\n")
        }
    }

    private val delete = object : Tool("fs_delete", "Delete a file or directory (recursive) inside Forge root.",
        Schema.obj("path" to Schema.str("Path"), required = listOf("path"))) {
        override val needsApproval = true
        override suspend fun run(args: JSONObject, ctx: ToolContext): String {
            val f = Sandbox.resolve(ctx.app, args.getString("path")); Sandbox.assertWritable(ctx.app, f)
            return if (f.deleteRecursively()) "deleted $f" else "ERROR: could not delete $f"
        }
    }

    private val move = object : Tool("fs_move", "Move/rename a file or directory inside Forge root.",
        Schema.obj("from" to Schema.str("Source"), "to" to Schema.str("Destination"), required = listOf("from", "to"))) {
        override suspend fun run(args: JSONObject, ctx: ToolContext): String {
            val a = Sandbox.resolve(ctx.app, args.getString("from")); val b = Sandbox.resolve(ctx.app, args.getString("to"))
            Sandbox.assertWritable(ctx.app, a); Sandbox.assertWritable(ctx.app, b); b.parentFile?.mkdirs()
            return if (a.renameTo(b)) "moved to $b" else "ERROR: move failed"
        }
    }

    private val unzip = object : Tool("fs_unzip", "Extract a zip file into a directory inside Forge root.",
        Schema.obj("zip" to Schema.str("Zip path"), "dest" to Schema.str("Destination dir"), required = listOf("zip", "dest"))) {
        override suspend fun run(args: JSONObject, ctx: ToolContext): String {
            val z = Sandbox.resolve(ctx.app, args.getString("zip")); val d = Sandbox.resolve(ctx.app, args.getString("dest"))
            Sandbox.assertWritable(ctx.app, d); d.mkdirs(); var n = 0
            ZipInputStream(z.inputStream().buffered()).use { zin ->
                var e = zin.nextEntry
                while (e != null) {
                    val out = File(d, e.name).normalize(); require(out.path.startsWith(d.path)) { "zip slip" }
                    if (e.isDirectory) out.mkdirs() else { out.parentFile?.mkdirs(); out.outputStream().use { zin.copyTo(it) }; n++ }
                    e = zin.nextEntry
                }
            }
            return "extracted $n files to $d"
        }
    }
}
