"""gate_patterns.py: the pattern lists used by Release Gate and Skill Install Gate.

One file, shared by both tools, so that "what counts as a key" or "what counts
as network code" means the same thing before you ship and before you install.

Every pattern is a plain regular expression you can read and change. A pattern
finding something means "look here". It does not mean the thing is harmful,
and finding nothing does not mean the package is safe.

Standard library only. This file reads nothing and writes nothing.
"""
from __future__ import annotations

import re

PATTERNS_VERSION = "1.0.0"

_I = re.IGNORECASE
_M = re.MULTILINE


def _rx(pattern, flags=0):
    return re.compile(pattern, flags)


# --------------------------------------------------------------------- keys
# (id, label, regex, group that holds the secret value)
KEYS = [
    ("sk-key", "API key (sk- prefix)", _rx(r"\bsk-[A-Za-z0-9_-]{20,}"), 0),
    ("aws-key-id", "AWS access key id", _rx(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), 0),
    ("github-token", "GitHub token", _rx(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"), 0),
    ("slack-token", "Slack token", _rx(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), 0),
    ("google-key", "Google API key", _rx(r"\bAIza[0-9A-Za-z_-]{30,}"), 0),
    ("payment-key", "payment provider key", _rx(r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{16,}"), 0),
    ("private-key", "private key block", _rx(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----"), 0),
    ("jwt", "JSON web token",
     _rx(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}"), 0),
]

# Shapes that are often secrets but are also often harmless (hashes, samples).
KEY_LIKE = [
    ("assigned-secret", "value assigned to a key, secret, token or password name",
     _rx(r"\b(?:api[_-]?key|secret|token|passwd|password|access[_-]?key)\b[\"']?\s*[:=]\s*"
         r"[\"']([^\"'\s]{16,})[\"']", _I), 1),
    ("long-hex", "long hex string (may be a hash)", _rx(r"\b[0-9a-fA-F]{40,}\b"), 0),
]

_PLACEHOLDER_RE = _rx(r"your|example|sample|dummy|changeme|placeholder|xxxx|\.\.\.|<|>|\$\{|\{\{|%s", _I)


def is_placeholder(value):
    """True for values such as YOUR_API_KEY_HERE or xxxxxxxx that are not secrets."""
    return bool(_PLACEHOLDER_RE.search(value)) or len(set(value)) <= 2


def mask(value):
    """Show the shape of a secret without showing the secret."""
    value = value.strip()
    head = value[:4] if len(value) > 12 else value[:2]
    return "%s***(%d chars)" % (head, len(value))


# ------------------------------------------------------------ absolute paths
ABSOLUTE_PATHS = [
    ("windows-path", "Windows absolute path",
     _rx(r"(?<![A-Za-z0-9\\])[A-Za-z]:\\{1,2}[A-Za-z0-9_.-]+")),
    ("windows-path-slash", "Windows absolute path (forward slashes)",
     _rx(r"(?<![A-Za-z0-9\\])[A-Za-z]:/(?!/)[A-Za-z0-9_.-]+")),
    ("mac-home", "macOS home path", _rx(r"/" + r"Users/[A-Za-z0-9._-]+")),
    ("linux-home", "Linux home path", _rx(r"/" + r"home/[A-Za-z0-9._-]+")),
]

# ------------------------------------------------------------- network code
# Looked for in code files only.
NETWORK = [
    ("py-import", "Python network module import",
     _rx(r"^\s*(?:import|from)\s+(?:urllib|urllib3|requests|socket|http\.client|httpx|aiohttp|"
         r"ftplib|smtplib|websockets?)\b", _M)),
    ("py-call", "Python network call",
     _rx(r"\b(?:urlopen|urlretrieve)\s*\(|\brequests\.(?:get|post|put|patch|delete|request|Session)\b|"
         r"\bsocket\.(?:socket|create_connection)\b|\bhttp\.client\b")),
    ("js-fetch", "JavaScript fetch, XHR, beacon or WebSocket",
     _rx(r"\bfetch\s*\(|\bXMLHttp" r"Request\b|\bnavigator\.sendBeacon\b|\bnew\s+WebSocket\b")),
    ("js-module", "JavaScript network module",
     _rx(r"(?:require\(\s*|from\s+)[\"'](?:node:)?(?:https?|net|dgram|axios|node-fetch|got|request|"
         r"ws|undici)[\"']")),
    ("shell-download", "shell download command",
     _rx(r"\b(?:curl|wget)\b[^\n]*\bhttps?://|\bInvoke-(?:WebRequest|RestMethod)\b|"
         r"\bStart-BitsTransfer\b|\bnc\s+-[a-z]", _I)),
]

URL = _rx(r"https?://([A-Za-z0-9.-]+)(?::\d+)?[^\s\"'<>)\]]*")

# ----------------------------------------------- telemetry (Skill Install Gate)
TELEMETRY = [
    ("telemetry-word", "telemetry or analytics wording",
     _rx(r"\b(?:telemetry|analytics|posthog|sentry|mixpanel|amplitude|datadog|segment\.io|"
         r"google-analytics|gtag|beacon|tracking[_-]?id|usage[_-]?(?:stats|data|report))\b", _I)),
    ("event-sender", "command that sends events",
     _rx(r"\bnpx\b[^\n]*\bevents?\b|\btrack(?:Event)?\s*\(|\bcapture\s*\(\s*[\"']", _I)),
]

# -------------------------------------------- install-time code (Install Gate)
INSTALL_TIME = [
    ("npm-lifecycle", "npm lifecycle script",
     _rx(r"[\"'](?:preinstall|install|postinstall|prepare|prepublish)[\"']\s*:")),
    ("allow-scripts", "allowScripts setting", _rx(r"\ballowScripts\b")),
    ("package-install", "package install command",
     _rx(r"\b(?:pip3?|npm|npx|yarn|pnpm|brew|apt(?:-get)?|choco|winget|cargo|gem)\s+"
         r"(?:install|add|i)\b", _I)),
    ("pipe-to-shell", "download piped into a shell",
     _rx(r"\b(?:curl|wget)\b[^\n|]*\|\s*(?:sudo\s+)?(?:ba|z)?sh\b|\biex\s*\(|"
         r"\bInvoke-Expression\b", _I)),
]

SETTINGS_CHANGES = [
    ("settings-file", "mentions the Claude settings file",
     _rx(r"settings(?:\.local)?\.json|\.claude[\\/](?:settings|hooks)", _I)),
    ("hook-event", "names a hook event",
     _rx(r"\b(?:PreToolUse|PostToolUse|UserPromptSubmit|SessionStart|SessionEnd|"
         r"SubagentStop|PreCompact)\b|[\"']Stop[\"']\s*:")),
    ("permission-change", "changes permissions or bypasses prompts",
     _rx(r"dangerously|bypassPermissions|skip-permissions|\"allow\"\s*:\s*\[", _I)),
]

# "Run this every time the skill opens" style instructions, in skill text.
RUN_EVERY_TIME = [
    ("always-run", "tells the model to run something every time",
     _rx(r"\b(?:every time|each time|whenever|always|on (?:every|each) (?:run|use|load|start|"
         r"invocation)|before (?:anything|doing anything|you (?:start|begin|respond|answer))|"
         r"at the (?:start|beginning) of (?:every|each))\b[^\n]{0,100}?"
         r"\b(?:run|execute|invoke|call|launch|curl|wget|npx|bash|sh|python3?|node)\b", _I)),
    ("run-always", "tells the model to run something every time",
     _rx(r"\b(?:run|execute|invoke|launch)\b[^\n]{0,100}?"
         r"\b(?:every time|each time|whenever (?:this|the) skill|on (?:every|each) "
         r"(?:run|use|load|start|invocation)|before (?:anything|doing anything) else)\b", _I)),
    ("always-run-ko", "tells the model to run something every time (Korean)",
     _rx(r"(?:열 때마다|쓸 때마다|실행할 때마다|매번|항상|시작할 때)[^\n]{0,60}?"
         r"(?:실행|돌려|호출|run|curl|npx|bash|python|node)")),
    ("must-not-skip", "tells the model it must not skip a command",
     _rx(r"\b(?:must|required to|do not skip|never skip|mandatory)\b[^\n]{0,60}?"
         r"\b(?:run|execute|curl|npx|bash)\b[^\n]{0,60}?\b(?:first|before|every|each)\b", _I)),
]

PAID_OR_CLOUD = [
    ("cloud-word", "cloud, publish, auth or login wording",
     _rx(r"\b(?:cloud|publish(?:es|ed|ing)?|auth(?:enticate|entication|orize)?|log[ -]?in|"
         r"sign[ -]?(?:in|up)|oauth|api[ _-]?key|subscription|license[ _-]?key|upgrade to|"
         r"paid plan|premium)\b", _I)),
]

# ------------------------------------------------- wording a person should read
REFUND_WORDS = _rx(r"\b(?:refunds?|refundable|money[- ]back|guarantee[ds]?|warrant(?:y|ies)|"
                   r"risk[- ]free|no questions asked)\b|환불|보증|보장", _I)

PRICE = _rx(r"(?<![A-Za-z0-9])(?:US)?\$\s?((?:\d{1,3}(?:,\d{3})+|\d{1,6})(?:[.,]\d{1,2})?)(?!\d)|"
            r"\b(\d{1,6}(?:\.\d{1,2})?)\s?(?:USD|dollars?)\b|"
            r"(?<![A-Za-z0-9])[₩€£]\s?(\d[\d,.]*)|"
            r"\b(\d[\d,]*)\s?(?:KRW|원)(?![가-힣A-Za-z])", _I)

# -------------------------------------------------------- files by their name
STRAY_DIRS = ("__pycache__", ".git", ".svn", ".hg", "node_modules", ".idea", ".vscode",
              ".pytest_cache", ".mypy_cache", ".venv", "venv", ".claude")
STRAY_FILES = (".env", ".DS_Store", "Thumbs.db", "desktop.ini", ".npmrc", ".pypirc",
               "id_rsa", "id_ed25519", ".netrc", "npm-debug.log")
STRAY_SUFFIXES = (".pyc", ".pyo", ".swp", ".swo", ".bak", ".tmp", ".orig", ".pem", ".key",
                  ".p12", ".pfx", "~")
STRAY_PREFIXES = (".env.",)
STRAY_OK = (".env.example", ".env.sample", ".env.template")

CODE_SUFFIXES = (".py", ".pyw", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".sh", ".bash",
                 ".zsh", ".ps1", ".psm1", ".bat", ".cmd", ".rb", ".go", ".rs", ".php", ".pl")
TEXT_SUFFIXES = CODE_SUFFIXES + (
    ".md", ".markdown", ".txt", ".rst", ".json", ".jsonl", ".toml", ".yaml", ".yml", ".ini",
    ".cfg", ".conf", ".csv", ".tsv", ".xml", ".html", ".htm", ".css", ".svg", ".env", ".lock")

LICENCE_KINDS = [
    ("MIT", _rx(r"\bMIT License\b|Permission is hereby granted, free of charge", _I)),
    ("Apache-2.0", _rx(r"Apache License\s*,?\s*Version 2\.0", _I)),
    ("BSD", _rx(r"Redistribution and use in source and binary forms", _I)),
    ("GPL", _rx(r"GNU (?:AFFERO |LESSER )?GENERAL PUBLIC LICENSE", _I)),
    ("MPL-2.0", _rx(r"Mozilla Public License,? v(?:ersion)?\.? ?2\.0", _I)),
    ("ISC", _rx(r"\bISC License\b|Permission to use, copy, modify, and/or distribute", _I)),
    ("Unlicense", _rx(r"This is free and unencumbered software released into the public domain", _I)),
]


def licence_kind(text):
    """Name of a well-known licence, or "other" when the text matches none."""
    for name, pattern in LICENCE_KINDS:
        if pattern.search(text):
            return name
    return "other"


def is_stray(name):
    """Why a file or folder name looks like something left in by accident, or ""."""
    base = name.rstrip("/").split("/")[-1]
    parts = name.rstrip("/").split("/")
    for part in parts[:-1] if not name.endswith("/") else parts:
        if part in STRAY_DIRS:
            return "inside %s/" % part
    if base in STRAY_DIRS and name.endswith("/"):
        return "folder %s/" % base
    if base in STRAY_OK:
        return ""
    if base in STRAY_FILES:
        return "file %s" % base
    for prefix in STRAY_PREFIXES:
        if base.startswith(prefix):
            return "file %s*" % prefix
    for suffix in STRAY_SUFFIXES:
        if base.endswith(suffix) and base != suffix:
            return "*%s file" % suffix
    return ""


def is_code(name):
    return name.lower().endswith(CODE_SUFFIXES)


def is_text_name(name):
    base = name.split("/")[-1]
    lower = base.lower()
    return (lower.endswith(TEXT_SUFFIXES) or "." not in base
            or lower.startswith(("license", "licence", "readme", "changelog", "notice")))


def line_of(text, position):
    return text.count("\n", 0, position) + 1


def find(patterns, text):
    """All matches of a pattern list in a text: (line, id, label, matched text)."""
    found = []
    for entry in patterns:
        ident, label, pattern = entry[0], entry[1], entry[2]
        for match in pattern.finditer(text):
            found.append((line_of(text, match.start()), ident, label, match.group()))
    found.sort(key=lambda item: item[0])
    return found


def find_keys(text):
    """Key findings: (line, id, label, masked value, definite).

    definite is True for well-known key formats and False for look-alikes.
    Placeholder values are left out.
    """
    found = []
    seen = set()
    for definite, patterns in ((True, KEYS), (False, KEY_LIKE)):
        for ident, label, pattern, group in patterns:
            for match in pattern.finditer(text):
                value = match.group(group)
                if is_placeholder(value):
                    continue
                span = match.span(group)
                if any(span[0] < end and start < span[1] for start, end in seen):
                    continue
                seen.add(span)
                found.append((line_of(text, match.start()), ident, label, mask(value), definite))
    found.sort(key=lambda item: item[0])
    return found
