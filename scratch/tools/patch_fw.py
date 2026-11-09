"""One-off patch of the firewall hook: operator-aware tokenizing, cd-relative paths,
Bash tamper guard, and glob errors no longer crash the hook. Run once."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
p = os.path.join(ROOT, ".claude", "hooks", "firewall.py")
s = open(p).read()

old_split = '''    try:
        words = shlex.split(cmd, posix=True)
    except ValueError:
        words = cmd.split()
'''
new_split = '''    if TAMPER_RE.search(cmd) and TAMPER_WRITE_RE.search(cmd):
        return "firewall files are read-only for the agent"
    words = shell_words(cmd)
    # Relative paths may be relative to a directory the command cd's into.
    bases = [cwd] + [resolve(words[i + 1], cwd) for i, w in enumerate(words[:-1])
                     if w in ("cd", "pushd")]
'''
assert old_split in s
s = s.replace(old_split, new_split)

old_loop = '''        path = resolve(cand, cwd)
        is_glob = any(c in cand for c in "*?[")
        if is_glob and glob_may_hit(path):
            return "glob could match a forbidden path"
        matches = glob.glob(path) if is_glob else [path]
        for m in matches:'''
new_loop = '''        is_glob = any(c in cand for c in "*?[")
        matches = []
        for base in bases:
            path = resolve(cand, base)
            if is_glob and glob_may_hit(path):
                return "glob could match a forbidden path"
            matches += safe_glob(path) if is_glob else [path]
        for m in matches:'''
assert old_loop in s
s = s.replace(old_loop, new_loop)

old_def = '''def check_bash(cmd, cwd):'''
new_def = '''TAMPER_RE = re.compile(r"\\.claude/(hooks|settings)")
TAMPER_WRITE_RE = re.compile(
    r">|\\btee\\b|sed\\s+-i|\\b(cp|mv|rm|ln|chmod|truncate|install|perl|ruby|node)\\b|"
    r"open\\(|write|unlink|replace\\(", re.I)


def shell_words(cmd):
    """Words of a shell command with operators (; | & < > ( )) split off as their own tokens."""
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        return list(lex)
    except ValueError:
        return [w for w in re.split(r"[\\s;|&<>()]+", cmd) if w]


def safe_glob(pattern):
    try:
        return glob.glob(pattern)
    except Exception:
        return []


def check_bash(cmd, cwd):'''
assert old_def in s
s = s.replace(old_def, new_def, 1)

old_gm = '''def glob_may_hit(pattern):
    """True if a glob pattern could match a forbidden dir, whether or not it exists."""
    parts'''
new_gm = '''def glob_may_hit(pattern):
    """True if a glob pattern could match a forbidden dir, whether or not it exists."""
    try:
        return _glob_may_hit(pattern)
    except Exception:
        return False


def _glob_may_hit(pattern):
    parts'''
assert old_gm in s
s = s.replace(old_gm, new_gm)
open(p, "w").write(s)
print("patched")
