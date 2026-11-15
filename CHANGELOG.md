# Changelog

## 1.0.0 - 2026-11-13

First release.

- `installgate.py <skill folder or zip>`: checks a temporary copy; the original is never changed and nothing from the skill is run.
- Eight rows: licence, telemetry and network, install-time code, settings and hooks, run-every-time lines, paid or cloud paths, unreadable files, skill file.
- Verdict: MAY INSTALL, CHECK FIRST or DO NOT INSTALL, with the file and line for each reason.
- Several skills in one run, with a summary.
- Unsafe ZIP entries are not unpacked; entry names that cannot exist on the local disk are handled.
- `gate_patterns.py`: every pattern in one readable file, shared with Release Gate.
- `make_sample.py`: builds five made-up skills to try the tool on.
- 41 unit tests.
