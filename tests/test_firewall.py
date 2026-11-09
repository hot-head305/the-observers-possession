"""The data firewall must block every route to competition data.

Forbidden names are assembled from fragments so this file never contains them
(the hook blocks running scripts that do).
"""
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, ".claude", "hooks", "firewall.py")
HOME = os.path.expanduser("~")
DATA = "~/" + "mt" + "ah-data"
CACHE = "local" + "_cache"
OUT = "private" + "_out"


def run(tool, tool_input, cwd=ROOT):
    event = {"tool_name": tool, "tool_input": tool_input, "cwd": cwd}
    env = dict(os.environ, CLAUDE_PROJECT_DIR=ROOT)
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(event),
                       capture_output=True, text=True, env=env)
    return p.returncode


def bash(cmd):
    return run("Bash", {"command": cmd})


BLOCKED_BASH = [
    f"cat {DATA}/tactical/x.xml",
    f"head -n 5 {DATA}/broadcast/a.txt",
    f"python -c \"open('{DATA}/tactical/x').read()\"",
    f"python3 -c \"import kloppy; kloppy.metrica.load_tracking_epts('{DATA}/tactical/m.xml', '{DATA}/tactical/r.txt')\"",
    f"ffmpeg -i {DATA}/broadcast/video.mp4 -f null -",
    f"ffprobe {DATA}/broadcast/video.mp4",
    f"cat $HOME/{'mt'}{'ah'}-data/tactical/x",
    f"cat ~/MT{'AH'}-DATA/x",
    "cat ~/mt" + "'ah'-data/x",
    "cat ~/mt" + "\\ah-data/x",
    "cat ~/mt*/tac*/*",
    "ls ~/mt?h-d*",
    f"ls {CACHE}",
    f"cat {OUT}/result.txt",
    f"cp -r {OUT} /tmp/x",
    "find ~ -name '*.xml'",
    "find / -name '*.xml'",
    "grep -r possession ~",
    "ls -R $HOME",
    "ls ~",
    "du -sh /Users/" + os.path.basename(HOME),
    "cd ~ && find . -name '*.xml'",
    "echo bWF0YWg= | base64 -d | xargs cat",
    "eval \"$X\"",
    "python3 -c \"print(bytes.fromhex('6d74'))\"",
    "make private-meta",
    "make -f Makefile.private private-meta",
    "cat Makefile.private",
    "cat README.md; cat Makefile.private; echo",
    "echo x && cat Makefile.private|head",
    "cd vendor && cat ../Makefile.private",
    "python3 -c \"open('.claude/hooks/firewall.py','w')\"",
    "echo '{}' > .claude/settings.json",
    "sed -i '' s/a/b/ .claude/hooks/firewall.py",
]


def test_operator_glued_file_is_scanned(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("see " + DATA + "\n")
    assert bash(f"cat {f}; echo done") == 2
    assert bash(f"cd {tmp_path} && cat notes.txt") == 2


@pytest.mark.parametrize("cmd", BLOCKED_BASH)
def test_bash_blocked(cmd):
    assert bash(cmd) == 2, cmd


def test_script_referencing_data_is_blocked(tmp_path):
    script = tmp_path / "evil.py"
    script.write_text("open('" + DATA + "/tactical/x').read()\n")
    assert bash(f"python3 {script}") == 2


def test_sibling_module_referencing_data_is_blocked(tmp_path):
    (tmp_path / "helper.py").write_text("P = '" + DATA + "'\n")
    (tmp_path / "main.py").write_text("import helper\n")
    assert bash(f"python3 {tmp_path / 'main.py'}") == 2


def test_symlink_into_data_is_blocked(tmp_path):
    link = tmp_path / "innocent"
    os.symlink(os.path.expanduser(DATA), link)
    assert bash(f"cat {link}/tactical/x") == 2
    assert run("Read", {"file_path": str(link / "x")}) == 2


@pytest.mark.parametrize("tool,ti", [
    ("Read", {"file_path": os.path.expanduser(DATA) + "/tactical/x.xml"}),
    ("Read", {"file_path": os.path.join(ROOT, OUT, "r.txt")}),
    ("Read", {"file_path": os.path.join(ROOT, "Makefile.private")}),
    ("Grep", {"pattern": "ball", "path": os.path.expanduser(DATA)}),
    ("Grep", {"pattern": "ball", "path": HOME}),
    ("Grep", {"pattern": "ball", "path": "/"}),
    ("Glob", {"pattern": "**/*.xml", "path": HOME}),
    ("Glob", {"pattern": DATA + "/**"}),
    ("Edit", {"file_path": os.path.join(ROOT, CACHE, "a.py"), "old_string": "a", "new_string": "b"}),
    ("Write", {"file_path": os.path.join(ROOT, "src", "x.py"), "content": "P='" + DATA + "'"}),
    ("Write", {"file_path": os.path.join(ROOT, ".claude", "settings.json"), "content": "{}"}),
    ("Edit", {"file_path": HOOK, "old_string": "a", "new_string": "b"}),
    ("mcp__desktop-commander__read_file", {"path": os.path.expanduser(DATA) + "/x"}),
])
def test_other_tools_blocked(tool, ti):
    assert run(tool, ti) == 2, (tool, ti)


def test_repo_wide_search_is_blocked():
    # The repo holds the derived cache/output dirs, so repo-wide traversal is refused.
    assert run("Glob", {"pattern": "**/*.csv", "path": ROOT}) == 2
    assert run("Grep", {"pattern": "ball"}) == 2
    assert bash("grep -rn ball .") == 2


def test_grep_without_path_from_home_is_blocked():
    assert run("Grep", {"pattern": "ball"}, cwd=HOME) == 2


@pytest.mark.parametrize("tool,ti", [
    ("Bash", {"command": "ls"}),
    ("Bash", {"command": "git rev-parse HEAD"}),
    ("Bash", {"command": "python3 -c \"print(1)\""}),
    ("Bash", {"command": "grep -rn spell vendor/"}),
    ("Bash", {"command": "cat .claude/hooks/firewall.py | head -5"}),
    ("Bash", {"command": "ls vendor; echo ok"}),
    ("Bash", {"command": "python3 -c \"import re; re.compile('[a-z]+')\" [x"}),
    ("Read", {"file_path": os.path.join(ROOT, "PLAN.md")}),
    ("Read", {"file_path": HOOK}),
    ("Grep", {"pattern": "possession", "path": os.path.join(ROOT, "vendor")}),
    ("Write", {"file_path": os.path.join(ROOT, "PLAN.md"), "content": "never read " + DATA}),
    ("Write", {"file_path": os.path.join(ROOT, "scratch", "a.py"), "content": "print(1)"}),
])
def test_allowed(tool, ti):
    assert run(tool, ti) == 0, (tool, ti)


def test_malformed_input_fails_closed():
    p = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True)
    assert p.returncode == 2


def test_this_file_has_no_literal_tokens():
    # Otherwise the hook would block running these tests.
    sys.path.insert(0, os.path.dirname(HOOK))
    import firewall
    assert not firewall.has_token(open(__file__).read())
