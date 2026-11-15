#!/usr/bin/env python3
"""Skill Install Gate: look at a Claude Code skill before you install it.

Give it the folder or ZIP you downloaded. It makes a temporary copy, reads
the copy, and tells you:

  1. whether there is a licence, and which kind
  2. telemetry wording and network code
  3. code that would run at install time
  4. code or instructions that change Claude settings, hooks or permissions
  5. instructions that tell the model to run something every time
  6. paid or cloud paths (cloud, publish, auth, login)
  7. files it could not read (binaries, archives)
  8. whether there is a SKILL.md with a name and a description

The verdict is one of MAY INSTALL, CHECK FIRST or DO NOT INSTALL, with the
reason for each row.

Skill Install Gate is a check aid. MAY INSTALL means none of the listed
patterns were found. It is not a statement that the skill is harmless.

Standard library only. Makes no network requests. Never runs anything from
the skill. The original folder or ZIP is not changed; the temporary copy is
deleted when the check ends.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
import zipfile

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import gate_patterns as gp  # noqa: E402

__version__ = "1.0.0"

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 200 * 1024 * 1024
MAX_FILES = 5000
DETAIL_LIMIT = 12

OK, NOTE, CHECK, STOP = "ok", "NOTE", "CHECK FIRST", "DO NOT INSTALL"
_RANK = {OK: 0, NOTE: 1, CHECK: 2, STOP: 3}
VERDICT = {0: "MAY INSTALL", 1: "MAY INSTALL", 2: "CHECK FIRST", 3: "DO NOT INSTALL"}
EXIT = {"MAY INSTALL": 0, "CHECK FIRST": 1, "DO NOT INSTALL": 3}

ROWS = [
    ("licence", "is there a licence, and which kind"),
    ("telemetry and network", "telemetry wording and code that can reach the network"),
    ("install-time code", "scripts and commands that run when the skill is installed"),
    ("settings and hooks", "code or instructions that change Claude settings, hooks or permissions"),
    ("run-every-time lines", "instructions that tell the model to run something every time"),
    ("paid or cloud paths", "cloud, publish, auth and login wording"),
    ("unreadable files", "binaries, archives and oversized files this tool cannot read"),
    ("skill file", "a SKILL.md with a name and a description"),
]

DISCLAIMER = ("Skill Install Gate is a check aid. It looks for the patterns listed above and "
              "nothing else. MAY INSTALL means none of them were found; it is not a statement "
              "that the skill is harmless.")

_BINARY_SUFFIXES = (".exe", ".dll", ".so", ".dylib", ".node", ".wasm", ".jar", ".class", ".pyc",
                    ".pyo", ".bin", ".msi", ".app", ".deb", ".rpm")
_ARCHIVE_SUFFIXES = (".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".whl")
_INSTALL_FILES = re.compile(r"^(?:setup\.py|install(?:er)?\.(?:sh|bash|ps1|bat|cmd|py|js)|"
                            r"postinstall\.[a-z0-9]+|Makefile|makefile)$")
_LICENCE_NAME = re.compile(r"^(licen[sc]e|copying|unlicense)([.-][a-z0-9.-]+)?$", re.IGNORECASE)
_COMMAND_IN_LINE = re.compile(r"`[^`\n]+`|\b(?:curl|wget|npx|npm|bash|sh|zsh|pwsh|powershell|"
                              r"python3?|node|deno|bun)\b|https?://", re.IGNORECASE)
_FRONT_NAME = re.compile(r"^name\s*:\s*(.+?)\s*$", re.MULTILINE)
_FRONT_DESCRIPTION = re.compile(r"^description\s*:\s*(\S.*)$", re.MULTILINE)


class GateError(Exception):
    pass


def harden_streams():
    """Never crash on a console that cannot print a character (cp949, cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except Exception:
            pass


# ------------------------------------------------------- the temporary copy

def _safe_member(name):
    name = name.replace("\\", "/")
    parts = name.split("/")
    return not (name.startswith("/") or ".." in parts or re.match(r"^[A-Za-z]:", name))


_BAD_NAME_CHARS = re.compile(r"[<>:\"|?*\x00-\x1f]")
_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL"} | set("COM%d" % i for i in range(1, 10)) | set(
    "LPT%d" % i for i in range(1, 10))


def _disk_name(part):
    """A name that can exist on any system, for the temporary copy only."""
    safe = _BAD_NAME_CHARS.sub("_", part).rstrip(" .") or "_"
    if safe.split(".")[0].upper() in _RESERVED_NAMES:
        safe = "_" + safe
    return safe


def copy_to_temp(path):
    """Copy a folder, or unpack a ZIP, into a new temporary folder.

    Returns (temp folder, kind, label, unsafe entry names, names). names maps
    a path in the copy back to the entry's real name, for ZIP entries whose
    name had to be changed to exist on this disk. The caller deletes the temp
    folder. Nothing in the original is opened for writing.
    """
    label = os.path.basename(os.path.abspath(path).rstrip("/\\")) or "skill"
    temp = tempfile.mkdtemp(prefix="installgate-")
    unsafe = []
    names = {}
    try:
        if os.path.isdir(path):
            total = count = 0
            for folder, dirs, files in os.walk(path):
                for name in files:
                    count += 1
                    try:
                        total += os.path.getsize(os.path.join(folder, name))
                    except OSError:
                        pass
            if count > MAX_FILES or total > MAX_TOTAL_BYTES:
                raise GateError("the folder is too large to check (%d files, %d MB)"
                                % (count, total // (1024 * 1024)))
            shutil.copytree(path, os.path.join(temp, "copy"), symlinks=True)
            return temp, "folder", label, unsafe, names
        if os.path.isfile(path):
            if not zipfile.is_zipfile(path):
                raise GateError("the file is not a ZIP archive")
            target = os.path.join(temp, "copy")
            os.makedirs(target)
            with zipfile.ZipFile(path) as archive:
                infos = archive.infolist()
                if (len(infos) > MAX_FILES
                        or sum(info.file_size for info in infos) > MAX_TOTAL_BYTES):
                    raise GateError("the ZIP is too large to check")
                for info in infos:
                    name = info.filename.replace("\\", "/")
                    if not _safe_member(name):
                        unsafe.append(name)
                        continue
                    parts = [p for p in name.split("/") if p]
                    if not parts:
                        continue
                    disk_parts = [_disk_name(p) for p in parts]
                    disk_name = "/".join(disk_parts)
                    counter = 1
                    while names.get(disk_name, "/".join(parts)) != "/".join(parts):
                        counter += 1
                        disk_name = "/".join(disk_parts[:-1] + ["%d_%s" % (counter, disk_parts[-1])])
                    names[disk_name] = "/".join(parts)
                    destination = os.path.join(target, *disk_name.split("/"))
                    try:
                        if name.endswith("/"):
                            os.makedirs(destination, exist_ok=True)
                            continue
                        os.makedirs(os.path.dirname(destination), exist_ok=True)
                        data = archive.read(info)
                        with open(destination, "wb") as handle:
                            handle.write(data)
                    except Exception:
                        unsafe.append(name + " (could not be unpacked)")
            return temp, "zip", label, unsafe, names
        raise GateError("no such file or folder")
    except Exception:
        shutil.rmtree(temp, True)
        raise


def skill_root(copy):
    """The folder that holds the skill: the copy, or its only top folder."""
    names = os.listdir(copy)
    if len(names) == 1 and os.path.isdir(os.path.join(copy, names[0])):
        return os.path.join(copy, names[0])
    return copy


def read_entries(root, copy=None, names=None):
    """(relative path, size, bytes or None) for every file under root.

    With copy and names (from copy_to_temp), paths are reported under the
    names the entries have in the ZIP, not the names used on disk.
    """
    names = names or {}
    copy = copy or root
    depth = 0 if os.path.normpath(root) == os.path.normpath(copy) else 1
    entries = []
    for folder, dirs, files in os.walk(root):
        dirs.sort()
        for name in sorted(files):
            full = os.path.join(folder, name)
            on_disk = os.path.relpath(full, copy).replace("\\", "/")
            relative = "/".join(names.get(on_disk, on_disk).split("/")[depth:])
            if os.path.islink(full):
                entries.append((relative, 0, None))
                continue
            size = os.path.getsize(full)
            if size > MAX_FILE_BYTES:
                entries.append((relative, size, None))
                continue
            with open(full, "rb") as handle:
                entries.append((relative, size, handle.read()))
    return entries


def decode(data):
    if data is None:
        return None
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    if b"\x00" in data[:8192]:
        return None
    return data.decode("utf-8-sig", errors="replace")


# ----------------------------------------------------------------- checking

def _shorten(text, width=80):
    text = " ".join(text.split())
    return text if len(text) <= width else text[:width - 3] + "..."


def _line_text(text, line):
    lines = text.splitlines()
    return lines[line - 1] if 0 < line <= len(lines) else ""


def inspect(entries, unsafe=()):
    """Run every check. Returns (findings, facts).

    A finding is {"row", "level", "file", "line", "text"}. facts holds the
    licence kind, the skill name and counts.
    """
    findings = []
    facts = {"licence": "none", "name": "", "files": len(entries), "code_files": 0,
             "hosts": []}

    def add(row, level, file, line=0, text=""):
        findings.append({"row": row, "level": level, "file": file, "line": line, "text": text})

    for name in unsafe:
        add("unreadable files", STOP, name, text="ZIP entry with an absolute or parent path; "
                                                 "it was not unpacked")

    licence_files = [(name, data) for name, size, data in entries
                     if "/" not in name and _LICENCE_NAME.match(name)]
    if not licence_files:
        add("licence", CHECK, ".", text="no licence file: nothing says you may use, change or "
                                        "share this skill")
    else:
        kind = gp.licence_kind(decode(licence_files[0][1]) or "")
        facts["licence"] = kind
        if kind == "other":
            add("licence", CHECK, licence_files[0][0],
                text="not one of the well-known licences; read it before you use the skill")

    skill_files = [name for name, size, data in entries if name.lower() == "skill.md"]
    if not skill_files:
        add("skill file", CHECK, ".", text="no SKILL.md at the top: this may not be a skill, "
                                           "or the skill sits in a sub-folder")
    hosts = set()

    for name, size, data in entries:
        lower = name.lower()
        base = lower.split("/")[-1]
        if data is None:
            add("unreadable files", NOTE, name, text="larger than 2 MB or a link; not read")
            continue
        if lower.endswith(_BINARY_SUFFIXES):
            add("unreadable files", CHECK, name, text="binary or compiled file; this tool cannot "
                                                      "read what it does")
            continue
        if lower.endswith(_ARCHIVE_SUFFIXES):
            add("unreadable files", CHECK, name, text="archive; its contents were not checked")
            continue
        text = decode(data)
        if text is None:
            if not lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf",
                                   ".woff", ".woff2", ".ttf", ".otf", ".mp3", ".mp4", ".wav")):
                add("unreadable files", CHECK, name, text="binary file of an unknown kind")
            continue

        is_code = gp.is_code(name)
        is_markdown = lower.endswith((".md", ".markdown", ".txt"))
        is_skill = lower == "skill.md"
        if is_code:
            facts["code_files"] += 1
        if _INSTALL_FILES.match(name.split("/")[-1]):
            add("install-time code", CHECK, name, text="install script; read it before you run it")

        if is_skill:
            front = text.split("---", 2)[1] if text.lstrip().startswith("---") and text.count("---") >= 2 else ""
            match = _FRONT_NAME.search(front)
            if match:
                facts["name"] = match.group(1).strip("\"'")
            if not match or not _FRONT_DESCRIPTION.search(front):
                add("skill file", CHECK, name, text="the frontmatter has no name or no description")

        for line, ident, label, matched in gp.find(gp.TELEMETRY, text):
            add("telemetry and network", CHECK, name, line, "%s: %s" % (label, _shorten(matched, 50)))
        if is_code:
            for line, ident, label, matched in gp.find(gp.NETWORK, text):
                add("telemetry and network", CHECK, name, line,
                    "%s: %s" % (label, _shorten(matched.strip(), 50)))
        for match in gp.URL.finditer(text):
            hosts.add(match.group(1).lower())

        for line, ident, label, matched in gp.find(gp.INSTALL_TIME, text):
            level = STOP if ident == "pipe-to-shell" else CHECK
            if ident == "npm-lifecycle" and base != "package.json":
                continue
            add("install-time code", level, name, line, "%s: %s" % (label, _shorten(matched, 50)))

        for line, ident, label, matched in gp.find(gp.SETTINGS_CHANGES, text):
            add("settings and hooks", STOP if is_code else CHECK, name, line,
                "%s: %s" % (label, _shorten(matched, 50)))

        if is_markdown:
            seen_lines = set()
            for line, ident, label, matched in gp.find(gp.RUN_EVERY_TIME, text):
                if line in seen_lines:
                    continue
                seen_lines.add(line)
                whole = _line_text(text, line)
                level = STOP if (is_skill and _COMMAND_IN_LINE.search(whole)) else CHECK
                add("run-every-time lines", level, name, line, _shorten(whole.strip()))

        if is_code or is_skill:
            seen_words = set()
            for line, ident, label, matched in gp.find(gp.PAID_OR_CLOUD, text):
                key = (line, matched.lower())
                if key in seen_words:
                    continue
                seen_words.add(key)
                add("paid or cloud paths", CHECK, name, line, "%s: %s" % (label, matched))
        else:
            count = len(gp.find(gp.PAID_OR_CLOUD, text))
            if count:
                add("paid or cloud paths", NOTE, name, text="%d mention(s) in this document" % count)

    facts["hosts"] = sorted(hosts)
    if hosts:
        add("telemetry and network", NOTE, ".", text="addresses written in the files: %s"
            % ", ".join(sorted(hosts)[:8]) + (" ..." if len(hosts) > 8 else ""))
    order = dict((name, index) for index, (name, _) in enumerate(ROWS))
    findings.sort(key=lambda item: (order[item["row"]], -_RANK[item["level"]], item["file"],
                                    item["line"]))
    return findings, facts


def row_level(findings, row):
    levels = [item["level"] for item in findings if item["row"] == row]
    return max(levels, key=lambda level: _RANK[level]) if levels else OK


def verdict_of(findings):
    worst = max([_RANK[item["level"]] for item in findings] or [0])
    return VERDICT[worst]


def where(item):
    return "%s:%d" % (item["file"], item["line"]) if item["line"] else item["file"]


def summary_rows(findings, facts):
    rows = []
    for name, meaning in ROWS:
        group = [item for item in findings if item["row"] == name]
        level = row_level(findings, name)
        if name == "licence" and level == OK:
            detail = facts["licence"]
        elif name == "skill file" and level == OK:
            detail = "found"
        else:
            detail = "%d" % len(group)
        rows.append((level, name, detail, meaning))
    return rows


def render_text(label, kind, findings, facts, detail_limit=DETAIL_LIMIT, title=None):
    lines = [title or "Skill Install Gate %s  (patterns %s)" % (__version__, gp.PATTERNS_VERSION),
             "Skill: %s  (%s, %d files, %d code files; checked in a temporary copy, "
             "original untouched)" % (label, kind, facts["files"], facts["code_files"]),
             "Name in SKILL.md: %s" % (facts["name"] or "(none)"), ""]
    for level, name, detail, meaning in summary_rows(findings, facts):
        lines.append("  %-15s %-22s %-6s %s" % (level, name, detail, meaning))
    shown = [item for item in findings]
    if shown:
        lines.extend(["", "Reasons"])
        for name, _ in ROWS:
            group = [item for item in shown if item["row"] == name]
            if not group:
                continue
            lines.append("  %s" % name)
            for item in group[:detail_limit]:
                lines.append("    %-15s %s  %s" % (item["level"], where(item), item["text"]))
            if len(group) > detail_limit:
                lines.append("    ... and %d more" % (len(group) - detail_limit))
    verdict = verdict_of(findings)
    lines.extend(["", "Verdict: " + verdict])
    stops = sorted(set(item["row"] for item in findings if item["level"] == STOP))
    checks = sorted(set(item["row"] for item in findings if item["level"] == CHECK))
    if stops:
        lines.append("Why: do not install as it is, because of: %s." % ", ".join(stops))
    if checks:
        lines.append("%s: %s." % ("Also check" if stops else "Why: check first", ", ".join(checks)))
    if not stops and not checks:
        lines.append("Why: none of the listed patterns were found.")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


def check(path):
    """Copy, inspect, delete the copy. Returns (label, kind, findings, facts)."""
    temp, kind, label, unsafe, names = copy_to_temp(path)
    try:
        copy = os.path.join(temp, "copy")
        root = skill_root(copy)
        findings, facts = inspect(read_entries(root, copy, names), unsafe)
    finally:
        shutil.rmtree(temp, True)
    return label, kind, findings, facts


# --------------------------------------------------------------------- cli

def build_parser():
    parser = argparse.ArgumentParser(
        prog="installgate.py",
        description="Check a Claude Code skill folder or ZIP before you install it. "
                    "Works on a temporary copy; never runs anything from the skill.",
    )
    parser.add_argument("skill", nargs="+", help="the skill folder or ZIP you downloaded; "
                                                 "several may be given")
    parser.add_argument("--details", type=int, default=DETAIL_LIMIT, metavar="N",
                        help="lines of detail per row (default: %d)" % DETAIL_LIMIT)
    parser.add_argument("--version", action="version",
                        version="skill-install-gate " + __version__)
    return parser


def main(argv=None):
    harden_streams()
    args = build_parser().parse_args(argv)
    results = []
    for index, path in enumerate(args.skill):
        try:
            label, kind, findings, facts = check(path)
        except (GateError, OSError) as exc:
            reason = exc.strerror if isinstance(exc, OSError) and exc.strerror else str(exc)
            sys.stderr.write("install-gate: %s: %s\n" % (os.path.basename(path.rstrip("/\\")), reason))
            return 2
        if index:
            print("")
        print(render_text(label, kind, findings, facts, max(1, args.details)))
        results.append((label, verdict_of(findings), findings))
    if len(results) > 1:
        print("")
        print("Summary")
        for label, verdict, findings in results:
            print("  %-15s %s" % (verdict, label))
    counted = sum(1 for _, _, findings in results for item in findings
                  if item["level"] in (CHECK, STOP))
    if counted:
        print("%d finding(s) to check. The HTML report, the ORIGIN.md draft and the install "
              "ledger are in Skill Install Gate Pro." % counted)
    return max(EXIT[verdict] for _, verdict, _ in results)


if __name__ == "__main__":
    sys.exit(main())
