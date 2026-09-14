# Installing Forge on your phone

Forge builds itself in the cloud, so you never need Android Studio.

## 1. Put the source on GitHub (2 minutes)

1. Go to https://github.com/new → name it `forge` → **Private** → Create.
2. Unzip `forge-android.zip` on any computer (or in a file manager on the phone).
3. On the empty repo page click **uploading an existing file**, drag in **everything inside the unzipped folder**
   (including the hidden `.github` folder — on macOS press ⌘⇧. to show it), commit to `main`.

   *Alternative with git:* `cd forge-android && git init && git add -A && git commit -m "Forge" && git branch -M main && git remote add origin git@github.com:YOU/forge.git && git push -u origin main`

4. Add the signing secrets — **Settings → Secrets and variables → Actions** → `FORGE_KEYSTORE_BASE64`
   and `FORGE_KEYSTORE_PASSWORD`. [SIGNING.md](SIGNING.md) covers generating the key; the build fails
   without them, because every build has to be signed with the same key for self-updates to install.
5. Open the **Actions** tab. "Build Forge APK" runs automatically (≈6–8 minutes the first time).

## 2. Install the APK (1 minute)

1. When the workflow is green, open **Releases** (right sidebar) → download `Forge-0.1.0.apk` on your phone.
2. Tap it → allow installs from your browser/file app if asked → Install → Open.

## 3. Configure Forge (2 minutes)

In the app: **☰ → Settings**

| Field | Value |
|---|---|
| OpenRouter API key | from https://openrouter.ai/keys |
| Model | tap *Browse*, search e.g. `fable`, `deepseek`, `glm`; choose one with `tools ✓` |
| Repository | `YOU/forge` |
| GitHub token | https://github.com/settings/personal-access-tokens → *Fine-grained* → repository `forge` → permissions **Contents: Read & write**, **Actions: Read**, **Metadata: Read** (add **Workflows: Read & write** if you want Forge allowed to edit its own CI file) |

Tap **Save**. That's it — Forge can now read, edit, push and reinstall itself.

## Updating later

You don't. Ask Forge for the change; it pushes, waits for the build, and opens the installer. If you ever
want to force it: Settings → *Install latest build*.

## Building locally instead (optional)

Android Studio Ladybug+ → *Open* the folder → Run. Or `./gradlew assembleRelease`
(needs JDK 17 and the Android SDK; the wrapper is included).

## Troubleshooting

- **Build failed on GitHub** — open the failed run, read the log, and paste the error into Forge; it can fix its own build.
- **"App not installed"** — you're installing a build signed with a different key over an older one. Uninstall Forge first (only needed if you rotated the signing key; see [SIGNING.md](SIGNING.md)).
- **Tools not appearing after a skill change** — say *"skills_reload"* or restart the app.
- **logcat is empty** — run once from a computer: `adb shell pm grant dev.forge android.permission.READ_LOGS`.
