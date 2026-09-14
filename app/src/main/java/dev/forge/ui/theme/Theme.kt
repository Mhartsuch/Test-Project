package dev.forge.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

/** Claude-inspired palette: warm cream, terracotta accent, soft ink. */
object ForgeColors {
    val Terracotta = Color(0xFFD97757)
    val TerracottaDeep = Color(0xFFC5613F)
    // light
    val CreamBg = Color(0xFFF4F3EE)
    val CreamSurface = Color(0xFFFFFFFF)
    val CreamSurface2 = Color(0xFFEDEBE3)
    val UserBubbleLight = Color(0xFFE8E5DA)
    val InkLight = Color(0xFF1F1E1D)
    val InkMutedLight = Color(0xFF6E6C66)
    val BorderLight = Color(0xFFDEDBD1)
    // dark
    val DarkBg = Color(0xFF262624)
    val DarkSurface = Color(0xFF30302E)
    val DarkSurface2 = Color(0xFF3A3A37)
    val UserBubbleDark = Color(0xFF3D3D3A)
    val InkDark = Color(0xFFEFEDE5)
    val InkMutedDark = Color(0xFFA8A69E)
    val BorderDark = Color(0xFF474744)
}

data class ForgeExtra(val userBubble: Color, val codeBg: Color, val border: Color, val muted: Color, val toolCard: Color)
val LocalForgeExtra = staticCompositionLocalOf { ForgeExtra(ForgeColors.UserBubbleLight, ForgeColors.CreamSurface2, ForgeColors.BorderLight, ForgeColors.InkMutedLight, ForgeColors.CreamSurface2) }

private val Light: ColorScheme = lightColorScheme(
    primary = ForgeColors.Terracotta, onPrimary = Color.White,
    background = ForgeColors.CreamBg, onBackground = ForgeColors.InkLight,
    surface = ForgeColors.CreamBg, onSurface = ForgeColors.InkLight,
    surfaceVariant = ForgeColors.CreamSurface2, onSurfaceVariant = ForgeColors.InkMutedLight,
    surfaceContainer = ForgeColors.CreamSurface, surfaceContainerHigh = ForgeColors.CreamSurface2,
    outline = ForgeColors.BorderLight, secondary = ForgeColors.InkMutedLight,
)
private val Dark: ColorScheme = darkColorScheme(
    primary = ForgeColors.Terracotta, onPrimary = Color.White,
    background = ForgeColors.DarkBg, onBackground = ForgeColors.InkDark,
    surface = ForgeColors.DarkBg, onSurface = ForgeColors.InkDark,
    surfaceVariant = ForgeColors.DarkSurface2, onSurfaceVariant = ForgeColors.InkMutedDark,
    surfaceContainer = ForgeColors.DarkSurface, surfaceContainerHigh = ForgeColors.DarkSurface2,
    outline = ForgeColors.BorderDark, secondary = ForgeColors.InkMutedDark,
)

val ForgeTypography = Typography(
    bodyLarge = TextStyle(fontFamily = FontFamily.Serif, fontSize = 17.sp, lineHeight = 26.sp),
    bodyMedium = TextStyle(fontFamily = FontFamily.Default, fontSize = 15.sp, lineHeight = 22.sp),
    bodySmall = TextStyle(fontFamily = FontFamily.Default, fontSize = 13.sp, lineHeight = 18.sp),
    titleLarge = TextStyle(fontFamily = FontFamily.Serif, fontSize = 24.sp, fontWeight = FontWeight.Medium),
    titleMedium = TextStyle(fontFamily = FontFamily.Default, fontSize = 16.sp, fontWeight = FontWeight.SemiBold),
    labelMedium = TextStyle(fontFamily = FontFamily.Default, fontSize = 12.sp, fontWeight = FontWeight.Medium),
)

@Composable
fun ForgeTheme(mode: String = "system", content: @Composable () -> Unit) {
    val dark = when (mode) { "dark" -> true; "light" -> false; else -> isSystemInDarkTheme() }
    val extra = if (dark) ForgeExtra(ForgeColors.UserBubbleDark, ForgeColors.DarkSurface, ForgeColors.BorderDark, ForgeColors.InkMutedDark, ForgeColors.DarkSurface)
                else ForgeExtra(ForgeColors.UserBubbleLight, ForgeColors.CreamSurface2, ForgeColors.BorderLight, ForgeColors.InkMutedLight, ForgeColors.CreamSurface)
    androidx.compose.runtime.CompositionLocalProvider(LocalForgeExtra provides extra) {
        MaterialTheme(colorScheme = if (dark) Dark else Light, typography = ForgeTypography, content = content)
    }
}
