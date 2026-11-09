#!/usr/bin/env python3
"""Competition-data firewall: PreToolUse hook for every tool.

Blocks (exit 2) any tool call that references the competition data directory,
the derived local cache, or the private output directory. Fails closed: any
error inside the hook blocks the call.

The forbidden tokens are assembled from fragments so this file (and the tests)
can be read without themselves containing them.
"""
import fnmatch
import glob
import json
import os
import re
import shlex
import sys

HOME = os.path.expanduser("~")
PROJECT = os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

# Normalised forms (lowercase, separators/quotes stripped).
TOKENS = ("mt" + "ah", "local" + "cache", "private" + "out")
DATA_DIR = os.path.join(HOME, "mt" + "ah-data")
FORBIDDEN_DIRS = (
    DATA_DIR,
    os.path.join(PROJECT, "local" + "_cache"),
    os.path.join(PROJECT, "private" + "_out"),
)
# Write/Edit content may mention the tokens only in prose files and in the
# human-run private makefile (which the agent can never read or run).
CONTENT_EXEMPT_SUFFIXES = (".md",)
CONTENT_EXEMPT_NAMES = ("Makefile.private",)
# Never read, run or modify these, whatever the tool.
GUARDED_NAMES = ("Makefile.private",)
# Firewall files: the agent may read them but not change them once active.
TAMPER_PATHS = (
    os.path.join(PROJECT, ".claude", "settings.json"),
    os.path.join(PROJECT, ".claude", "settings.local.json"),
    os.path.join(PROJECT, ".claude", "hooks"),
)
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
CONTENT_KEYS = {"content", "new_string", "old_string", "new_source", "edits"}
PATH_KEYS = {"file_path", "path", "notebook_path", "pattern", "glob", "cwd"}
# Obfuscation that would defeat string matching.
OBFUSCATION = re.compile(
    r"base64\s+(-d|--decode|-D)|\beval\b|xxd\s+-r|\\x[0-9a-f]{2}|\bchr\(|"
    r"codecs\.decode|bytes\.fromhex|\[::-1\]|\|\s*rev\b",
    re.I,
)
# Recursive or listing commands aimed at a directory that contains the data.
TRAVERSAL_CMDS = {"find", "grep", "egrep", "rg", "ag", "ls", "tree", "du", "fd",
                  "rsync", "cp", "tar", "zip", "mdfind", "locate", "ack"}
SCAN_LIMIT = 2_000_000


def norm(text):
    return re.sub(r"[-_'\"`\\]", "", text.lower())


def has_token(text):
    t = norm(text)
    return any(tok in t for tok in TOKENS)


def real(path):
    return os.path.realpath(os.path.expanduser(os.path.expandvars(path)))


def resolve(p, cwd):
    e = os.path.expanduser(os.path.expandvars(p))
    return e if os.path.isabs(e) else os.path.join(cwd, e)


def under(path, root):
    return path == root or path.startswith(root.rstrip("/") + "/")


def is_ancestor_of_data(path):
    """True if traversing `path` would reach a forbidden directory."""
    return any(under(d, path) for d in FORBIDDEN_DIRS)


def path_forbidden(p):
    rp = real(p)
    if any(under(rp, d) for d in FORBIDDEN_DIRS):
        return True
    return os.path.basename(rp) in GUARDED_NAMES


def glob_may_hit(pattern):
    """True if a glob pattern could match a forbidden dir, whether or not it exists."""
    try:
        return _glob_may_hit(pattern)
    except Exception:
        return False


def _glob_may_hit(pattern):
    parts = [c for c in pattern.split("/") if c]
    for d in FORBIDDEN_DIRS:
        dparts = [c for c in d.split("/") if c]
        n = min(len(parts), len(dparts))
        if n and all(fnmatch.fnmatch(dparts[i].lower(), parts[i].lower()) or parts[i] == "**"
                     for i in range(n)) and len(parts) >= len(dparts) - 0:
            return True
        if "**" in parts[:n] and all(fnmatch.fnmatch(dparts[i], parts[i])
                                     for i in range(parts.index("**"))):
            return True
    return False


def file_has_token(path):
    try:
        if os.path.isfile(path) and os.path.getsize(path) <= SCAN_LIMIT:
            with open(path, "r", errors="ignore") as f:
                return has_token(f.read())
    except OSError:
        pass
    return False


def walk_strings(obj, key=None):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_strings(v, k)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_strings(v, key)
    elif isinstance(obj, str):
        yield key, obj


def content_exempt(file_path):
    base = os.path.basename(file_path or "")
    return base.endswith(CONTENT_EXEMPT_SUFFIXES) or base in CONTENT_EXEMPT_NAMES


TAMPER_RE = re.compile(r"\.claude/(hooks|settings)")
TAMPER_WRITE_RE = re.compile(
    r">|\btee\b|sed\s+-i|\b(cp|mv|rm|ln|chmod|truncate|install|perl|ruby|node)\b|"
    r"open\(|write|unlink|replace\(", re.I)


def shell_words(cmd):
    """Words of a shell command with operators (; | & < > ( )) split off as their own tokens."""
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        return list(lex)
    except ValueError:
        return [w for w in re.split(r"[\s;|&<>()]+", cmd) if w]


def safe_glob(pattern):
    try:
        return glob.glob(pattern)
    except Exception:
        return []


def check_bash(cmd, cwd):
    if has_token(cmd):
        return "command references competition data"
    if OBFUSCATION.search(cmd):
        return "command uses decoding/eval that could hide a data path"
    if re.search(r"\bmake\b[^\n;|&]*\bprivate-", cmd):
        return "make private-* targets are human-run only"
    if TAMPER_RE.search(cmd) and TAMPER_WRITE_RE.search(cmd):
        return "firewall files are read-only for the agent"
    words = shell_words(cmd)
    # Relative paths may be relative to a directory the command cd's into.
    bases = [cwd] + [resolve(words[i + 1], cwd) for i, w in enumerate(words[:-1])
                     if w in ("cd", "pushd")]
    cmd_names = {os.path.basename(w) for w in words}
    traversal = bool(cmd_names & TRAVERSAL_CMDS) or "-R" in words or "-r" in words
    for w in words:
        if w.startswith("-") and "=" not in w:
            continue
        cand = w.split("=", 1)[1] if w.startswith("-") else w
        if not cand:
            continue
        is_glob = any(c in cand for c in "*?[")
        matches = []
        for base in bases:
            path = resolve(cand, base)
            if is_glob and glob_may_hit(path):
                return "glob could match a forbidden path"
            matches += safe_glob(path) if is_glob else [path]
        for m in matches:
            if path_forbidden(m):
                return "command touches a forbidden path"
            rp = real(m)
            if traversal and os.path.isdir(rp) and is_ancestor_of_data(rp):
                return "recursive/listing command over a directory that contains competition data"
            if file_has_token(rp):
                return "command uses a file that references competition data"
            if rp.endswith(".py") and os.path.isfile(rp):
                d = os.path.dirname(rp)
                for sib in glob.glob(os.path.join(d, "*.py")):
                    if file_has_token(sib):
                        return "script's sibling module references competition data"
    if re.search(r"(^|[\s;&|(])(cd|pushd)\s+(~|\$HOME|/Users/?|/)(\s|$|;|&)", cmd) and \
            re.search(r"\b(find|grep\s+-\w*r|rg|ls\s+-\w*R|tree|du)\b", cmd):
        return "recursive command after changing to a directory that contains competition data"
    return None


def check(event):
    tool = event.get("tool_name", "")
    ti = event.get("tool_input", {}) or {}
    cwd = event.get("cwd") or os.getcwd()

    if tool == "Bash":
        return check_bash(ti.get("command", ""), ti.get("cwd") or cwd)

    target = ti.get("file_path") or ti.get("notebook_path") or ""
    for key, val in walk_strings(ti):
        if tool in WRITE_TOOLS and key in CONTENT_KEYS:
            if content_exempt(target):
                continue
            if has_token(val):
                return "written code may not reference competition data"
            continue
        if has_token(val):
            return "tool input references competition data"
        if key in PATH_KEYS and val:
            p = resolve(val, cwd)
            if key in ("pattern", "glob") and tool == "Glob" and glob_may_hit(
                    os.path.join(real(ti.get("path") or cwd), val)):
                return "glob could match a forbidden path"
            if path_forbidden(p):
                return "tool targets a forbidden path"
            if tool in ("Grep", "Glob") and os.path.isdir(real(p)) and is_ancestor_of_data(real(p)):
                return "search over a directory that contains competition data"
            if tool in WRITE_TOOLS and any(under(real(p), t) for t in TAMPER_PATHS):
                return "firewall files are read-only for the agent"
    if tool in ("Grep", "Glob") and not ti.get("path") and is_ancestor_of_data(real(cwd)):
        return "search over a directory that contains competition data"
    return None


def main():
    try:
        event = json.loads(sys.stdin.read() or "{}")
        reason = check(event)
    except Exception as e:  # fail closed
        reason = "firewall error (fail closed): %s" % type(e).__name__
    if reason:
        sys.stderr.write("BLOCKED by data firewall: %s. See PLAN.md section 0.\n" % reason)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
