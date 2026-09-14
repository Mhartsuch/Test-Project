package dev.forge.memory

import java.io.File

/**
 * Markdown memory, modelled on Claude's memory filesystem:
 *   profile.md, preferences.md, topics/, areas/, people/, projects/ (markdown files)
 * Files carry a small frontmatter (name, description) so an index can be rendered cheaply.
 */
class MemoryFiles(private val dir: File) {

    fun bootstrapIfEmpty() {
        if (dir.listFiles().isNullOrEmpty()) {
            write("profile.md", "---\nname: profile\ndescription: Who the user is\n---\n\n(nothing known yet — ask the user or infer from conversation and record it here)\n")
            write("preferences.md", "---\nname: preferences\ndescription: How the user wants Forge to behave\n---\n\n- Prefers concise answers with code.\n")
            listOf("topics", "areas", "people", "projects").forEach { File(dir, it).mkdirs() }
        }
    }

    fun file(rel: String): File {
        val f = File(dir, rel.trimStart('/')).canonicalFile
        require(f.path.startsWith(dir.canonicalPath)) { "memory path escapes memory dir" }
        return f
    }

    fun read(rel: String): String = file(rel).takeIf { it.isFile }?.readText() ?: ""

    fun write(rel: String, content: String) { file(rel).apply { parentFile?.mkdirs() }.writeText(content) }

    fun append(rel: String, line: String) {
        val f = file(rel).apply { parentFile?.mkdirs() }
        f.appendText((if (f.exists() && f.length() > 0 && !f.readText().endsWith("\n")) "\n" else "") + line + "\n")
    }

    fun delete(rel: String) = file(rel).delete()

    fun list(): List<File> = dir.walkTopDown().filter { it.isFile && it.extension == "md" }.sortedBy { it.path }.toList()

    fun description(f: File): String = runCatching {
        f.useLines { lines -> lines.take(12).firstOrNull { it.startsWith("description:") }?.removePrefix("description:")?.trim() }
    }.getOrNull() ?: f.readText().lineSequence().firstOrNull { it.isNotBlank() && !it.startsWith("---") }?.take(100) ?: ""

    fun index(): String = list().joinToString("\n") { "- ${it.relativeTo(dir).path} — ${description(it)}" }

    /** Case-insensitive grep across all memory files; returns "path:line: text". */
    fun search(query: String, max: Int = 40): List<String> {
        val q = query.lowercase()
        val out = mutableListOf<String>()
        for (f in list()) {
            f.readLines().forEachIndexed { i, l ->
                if (out.size < max && l.lowercase().contains(q)) out += "${f.relativeTo(dir).path}:${i + 1}: ${l.trim()}"
            }
        }
        return out
    }
}
