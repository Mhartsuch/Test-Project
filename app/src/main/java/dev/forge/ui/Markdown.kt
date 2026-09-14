package dev.forge.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import dev.forge.ui.theme.LocalForgeExtra

/**
 * Small dependency-free markdown renderer: headings, fenced code, bullets, numbered lists,
 * blockquotes, paragraphs; inline bold/italic/code. Good enough for chat; the agent can upgrade it.
 */
@Composable
fun Markdown(text: String, modifier: Modifier = Modifier) {
    val extra = LocalForgeExtra.current
    val lines = text.lines()
    var i = 0
    Column(modifier) {
        while (i < lines.size) {
            val l = lines[i]
            when {
                l.trimStart().startsWith("```") -> {
                    val lang = l.trim().removePrefix("```").trim()
                    val buf = StringBuilder(); i++
                    while (i < lines.size && !lines[i].trimStart().startsWith("```")) { buf.append(lines[i]).append('\n'); i++ }
                    i++
                    Column(Modifier.fillMaxWidth().padding(vertical = 6.dp).clip(RoundedCornerShape(10.dp)).background(extra.codeBg)) {
                        if (lang.isNotEmpty()) Text(lang, Modifier.padding(start = 12.dp, top = 6.dp), style = MaterialTheme.typography.labelMedium, color = extra.muted)
                        Row(Modifier.horizontalScroll(rememberScrollState()).padding(12.dp)) {
                            Text(buf.toString().trimEnd('\n'), fontFamily = FontFamily.Monospace, fontSize = 13.sp, lineHeight = 18.sp, color = MaterialTheme.colorScheme.onSurface)
                        }
                    }
                }
                l.startsWith("#") -> {
                    val level = l.takeWhile { it == '#' }.length
                    val style = when (level) { 1 -> MaterialTheme.typography.titleLarge; 2 -> MaterialTheme.typography.titleMedium.copy(fontSize = 19.sp); else -> MaterialTheme.typography.titleMedium }
                    Text(inline(l.drop(level).trim()), Modifier.padding(top = 10.dp, bottom = 4.dp), style = style, color = MaterialTheme.colorScheme.onSurface); i++
                }
                Regex("^\\s*([-*•]|\\d+\\.)\\s+").containsMatchIn(l) -> {
                    val m = Regex("^(\\s*)([-*•]|\\d+\\.)\\s+(.*)").find(l)!!
                    val indent = m.groupValues[1].length / 2
                    val marker = if (m.groupValues[2].endsWith(".")) m.groupValues[2] else "•"
                    Row(Modifier.padding(start = (indent * 14).dp, top = 2.dp, bottom = 2.dp)) {
                        Text("$marker ", style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurface)
                        Text(inline(m.groupValues[3]), style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurface)
                    }; i++
                }
                l.startsWith(">") -> {
                    Row(Modifier.padding(vertical = 4.dp)) {
                        Column(Modifier.padding(end = 10.dp).background(MaterialTheme.colorScheme.primary).padding(horizontal = 1.dp)) {}
                        Text(inline(l.removePrefix(">").trim()), style = MaterialTheme.typography.bodyLarge, fontStyle = FontStyle.Italic, color = extra.muted)
                    }; i++
                }
                l.isBlank() -> { i++ }
                else -> {
                    val buf = StringBuilder(l)
                    i++
                    while (i < lines.size && lines[i].isNotBlank() && !lines[i].trimStart().startsWith("```") && !lines[i].startsWith("#") && !Regex("^\\s*([-*•]|\\d+\\.)\\s+").containsMatchIn(lines[i]) && !lines[i].startsWith(">")) { buf.append('\n').append(lines[i]); i++ }
                    Text(inline(buf.toString()), Modifier.padding(vertical = 4.dp), style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurface)
                }
            }
        }
    }
}

/** Inline: **bold**, *italic*, `code`, [text](url) shown as text. */
fun inline(s: String): AnnotatedString = buildAnnotatedString {
    var i = 0
    while (i < s.length) {
        when {
            s.startsWith("**", i) -> { val e = s.indexOf("**", i + 2); if (e > 0) { withStyle(SpanStyle(fontWeight = FontWeight.Bold)) { append(s.substring(i + 2, e)) }; i = e + 2 } else { append(s[i]); i++ } }
            s[i] == '`' -> { val e = s.indexOf('`', i + 1); if (e > 0) { withStyle(SpanStyle(fontFamily = FontFamily.Monospace, fontSize = 14.sp, background = androidx.compose.ui.graphics.Color(0x22888888))) { append(s.substring(i + 1, e)) }; i = e + 1 } else { append(s[i]); i++ } }
            s[i] == '*' && i + 1 < s.length && s[i + 1] != ' ' -> { val e = s.indexOf('*', i + 1); if (e > 0) { withStyle(SpanStyle(fontStyle = FontStyle.Italic)) { append(s.substring(i + 1, e)) }; i = e + 1 } else { append(s[i]); i++ } }
            s[i] == '[' -> { val m = Regex("^\\[([^\\]]+)\\]\\(([^)]+)\\)").find(s.substring(i)); if (m != null) { withStyle(SpanStyle(color = androidx.compose.ui.graphics.Color(0xFFD97757))) { append(m.groupValues[1]) }; i += m.value.length } else { append(s[i]); i++ } }
            else -> { append(s[i]); i++ }
        }
    }
}
