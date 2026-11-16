---
name: skill-install-gate
description: Reads a downloaded skill (folder or ZIP) before you install it and says MAY INSTALL, CHECK FIRST or DO NOT INSTALL, with the reasons. Use when the user asks, for example, "is this skill safe to install", "check this downloaded skill", "install gate", "이 스킬 설치해도 돼?".
---

# skill-install-gate

Reads a downloaded skill (folder or ZIP) before you install it and says MAY INSTALL, CHECK FIRST or DO NOT INSTALL, with the reasons. A small Python tool shipped in this plugin: standard library only, nothing to install, runs locally.

## Run

Use `python` (Windows: `py -3` also works; macOS/Linux: `python3`). On Windows add `-X utf8` if the console shows broken characters.

    python "${CLAUDE_PLUGIN_ROOT}/installgate.py" <skill-folder or skill.zip>
    python "${CLAUDE_PLUGIN_ROOT}/installgate.py" <skill-one> <skill-two.zip>

Run it from the user's project folder and pass the path they mean. If no path is given, ask which folder or file to check.

## Read the result

Report the verdict first, then each finding. Do not install anything yourself; the user decides.

Show the tool's own output (shortened if long) and then a two- or three-line summary. Do not change the user's files unless they ask.
