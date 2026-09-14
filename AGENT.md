# Forge — notes for the agent (you)

You are reading your own repository. Layout:

| Path | Purpose |
|---|---|
| `app/src/main/java/dev/forge/ForgeApp.kt` | Singleton wiring. Add new subsystems here. |
| `core/Agent.kt` | The loop: stream → tool calls → repeat. Compaction lives here (`maybeCompact`). |
| `core/OpenRouterClient.kt` | SSE streaming + tool calling against OpenRouter. |
| `core/ContextManager.kt` | Token budgeting, stale-tool-output truncation, compaction selection. |
| `core/Prompts.kt` | System prompt. Identity, self-evolution protocol, memory/task injection. |
| `tools/*.kt` | Built-in tools. Add a `Tool` object and register it in `ToolRegistry.init`. |
| `tools/JsToolRuntime.kt` | WebView-hosted JS runtime for hot-loaded skill tools (`forge.*` bridge). |
| `tools/AndroidTools.kt` | Device actions (clipboard, TTS, STT hook, notifications). Extend for voice. |
| `memory/*.kt` | Markdown memory, task board, conversation JSONL store. |
| `self/GitHubRepo.kt` | Git-over-REST: sync zipball, diff by blob sha, commit+push, CI status, releases. |
| `self/SelfUpdater.kt` | Downloads the release APK and opens the installer. |
| `ui/**` | Jetpack Compose UI (Claude-style). `Markdown.kt` is a small renderer. |
| `.github/workflows/build.yml` | Builds + publishes the APK on every push to `main`. Never delete. |

Rules of the road for editing yourself:
1. Small commits. One feature per push. Bump `versionName`/`versionCode`/`FORGE_VERSION` in `app/build.gradle.kts`.
2. Don't add Gradle dependencies unless necessary; when you do, use google()/mavenCentral() artifacts only.
3. Keep the tool registry, updater, and workflow intact — those are your lifeline.
4. Before a native change, ask: can this be a skill (`SKILL.md` + `tool.js`) instead? Skills need no rebuild.
5. If the build fails, `self_build_status(log=true)`, fix the exact error, push again.
