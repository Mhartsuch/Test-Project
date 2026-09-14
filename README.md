# Forge — a self-evolving coding agent for Android

Forge is a native Android app (Kotlin + Jetpack Compose) that talks to frontier models through
**OpenRouter**, has real tools on the device, remembers across sessions, and can **modify and rebuild
itself** when you ask for a new feature.

```
"Add a skill that reads .docx files"        → Forge writes a JS tool, reloads it, uses it. (seconds)
"Add a proper voice-chat screen"            → Forge edits its own Kotlin, pushes, CI builds, you tap Install. (minutes)
"Refactor my Flutter project's auth layer"  → Forge creates a task board, works for as long as it takes,
                                              compacts its own context, and keeps notes it can resume from.
```

## What's inside

| Layer | Details |
|---|---|
| **Models** | Any OpenRouter model with tool calling (browse + search the live list in Settings: Fable, Astra, DeepSeek, GLM, …). Reasoning effort control, streaming, cost tracking. |
| **Tools** | `fs_*` (read/write/edit/list/grep/unzip), `shell` (toybox sh), `http`, `logcat`, `device` (clipboard, TTS, STT, notifications, share…), memory, task board, chat search, settings. |
| **Memory** | Markdown files (`profile.md`, `areas/`, `topics/`, `people/`…) indexed into every prompt, plus full-text search over all past chats. |
| **Long-horizon** | Persistent task board with checklists + scratchpad notes re-injected each turn; automatic context compaction into structured summaries; foreground service so work continues with the screen off; 200 tool rounds per message by default. |
| **Self-evolution Tier 1** | Skills = `SKILL.md` playbook + `tool.js`. JS runs in a sandboxed WebView with a `forge.*` bridge (files, http, shell, device). New tools go live instantly with `skills_reload`. |
| **Self-evolution Tier 2** | Forge syncs its own source from your GitHub repo, edits Kotlin, commits via the Git Data API (no git binary needed), GitHub Actions builds the APK, Forge downloads the release and opens the installer. |
| **UI** | Claude-style: cream/terracotta theme, drawer with chats, serif body text, collapsible thinking + tool cards, approval bar for destructive tools, mic button, share-into-Forge. |

## Install (no computer required)

See **[INSTALL.md](INSTALL.md)** — three steps: upload this zip to a new GitHub repo, wait for the green
check, download the APK from *Releases*.

## First conversation

1. Settings → paste your OpenRouter key → *Browse* a model (pick one marked `tools ✓`).
2. Optional but recommended: Settings → Self-evolution → repo `you/forge` + a GitHub token.
3. Try: *"Sync your source and tell me the three most useful improvements you could make to yourself."*

## Layout

See [AGENT.md](AGENT.md) — it's written for Forge, but it's the map for you too.

## Security notes

- Forge can only **write** inside its own app directory (`/data/data/dev.forge/files`); it can read most of the device.
- The release signing key is **not** in this repo. CI reads it from the `FORGE_KEYSTORE_BASE64` and
  `FORGE_KEYSTORE_PASSWORD` secrets and shreds it after the build; local builds read a gitignored
  `keystore.properties`. See [SIGNING.md](SIGNING.md).
- Set **auto-approve** off in Settings if you want to confirm deletes, pushes and installs by hand.
