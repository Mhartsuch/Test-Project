package dev.forge.self

import java.io.File

/**
 * Skills = folders with SKILL.md (+ optional tool.js). SKILL.md bodies are appended to the system
 * prompt when their triggers match the latest user message, so the agent gets playbooks on demand.
 */
class SkillStore(private val dir: File) {
    data class Skill(val name: String, val description: String, val triggers: List<String>, val markdown: String, val js: String?, val folder: File)

    fun bootstrapIfEmpty() {
        if (dir.listFiles().isNullOrEmpty()) {
            write("example-echo", """---
name: example-echo
description: Example skill showing how JS tools are declared. Safe to delete.
triggers: [example skill, echo tool]
---
This skill exists to show the pattern. `tool.js` declares one tool, `example-echo_echo`, which returns its input reversed.
To add a real capability, write a new skill with `skill_write` and reload with `skills_reload`.
""", """// Declared tools become callable as <skill>_<fn>
forge.declare({
  name: "echo",
  description: "Returns the given text reversed (demo of the JS tool runtime).",
  parameters: { type: "object", properties: { text: { type: "string", description: "Text" } }, required: ["text"] }
});
export function echo(args) {
  forge.log("echo called");
  return args.text.split("").reverse().join("");
}
""")
            write("voice", """---
name: voice
description: Voice chat — speak replies aloud (TTS) and take spoken input (STT) through the device
triggers: [voice, speak, say it, read it aloud, talk to me, listen]
---
When the user wants a spoken conversation:
1. Keep answers short (1–3 sentences) and call `voice_speak` with the text.
2. To hear the user, call `voice_listen`; it returns the transcript. Then respond and speak again.
3. Stop the loop when the user says "stop" or asks for text.
If TTS/STT is unavailable the tools return an ERROR string — tell the user and fall back to text.
""", """forge.declare({ name: "speak", description: "Speak text aloud with the device TTS engine.",
  parameters: { type: "object", properties: { text: { type: "string" } }, required: ["text"] } });
forge.declare({ name: "listen", description: "Open the microphone and return what the user said.",
  parameters: { type: "object", properties: {} } });
export function speak(args) { return forge.android("tts", { text: args.text }); }
export function listen() { return forge.android("stt", {}); }
""")
        }
    }

    fun write(name: String, markdown: String, js: String?) {
        val f = File(dir, name).apply { mkdirs() }
        File(f, "SKILL.md").writeText(markdown)
        if (js != null) File(f, "tool.js").writeText(js) else File(f, "tool.js").delete()
    }

    fun get(name: String): Skill? = load(File(dir, name))

    fun all(): List<Skill> = dir.listFiles { f -> f.isDirectory }.orEmpty().sortedBy { it.name }.mapNotNull { load(it) }

    fun renderIndex(): String = all().joinToString("\n") { "- ${it.name}: ${it.description}${if (it.js != null) " [has tools]" else ""}" }

    /** Skill bodies whose triggers appear in the text (or that have no triggers). */
    fun matching(text: String): List<Skill> {
        val t = text.lowercase()
        return all().filter { s -> s.triggers.any { t.contains(it.lowercase()) } }
    }

    private fun load(folder: File): Skill? {
        val md = File(folder, "SKILL.md").takeIf { it.isFile }?.readText() ?: return null
        val fm = frontmatter(md)
        val triggers = fm["triggers"]?.trim('[', ']')?.split(",")?.map { it.trim().trim('"', '\'') }?.filter { it.isNotEmpty() } ?: emptyList()
        return Skill(fm["name"] ?: folder.name, fm["description"] ?: "", triggers, md, File(folder, "tool.js").takeIf { it.isFile }?.readText(), folder)
    }

    private fun frontmatter(md: String): Map<String, String> {
        if (!md.startsWith("---")) return emptyMap()
        val end = md.indexOf("\n---", 3).takeIf { it > 0 } ?: return emptyMap()
        return md.substring(3, end).lines().mapNotNull { l -> l.indexOf(':').takeIf { it > 0 }?.let { l.substring(0, it).trim() to l.substring(it + 1).trim() } }.toMap()
    }
}
