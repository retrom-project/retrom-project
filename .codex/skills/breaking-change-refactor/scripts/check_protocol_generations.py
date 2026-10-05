#!/usr/bin/env python3
"""Block protocol-generation changes in an enabled breaking-refactor workflow.

Compare the complete working tree with an explicit development base, including
untracked source files. This is a delivery gate, not a runtime compatibility check.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import subprocess
import sys


VERSION_KEY = (
    r"(?:schema_?version|provider_?api(?:_?version)?|api_?version|"
    r"protocol_?version|contract_?version|format_?version|wire_?version)"
)
FIELD = re.compile(
    rf"\b(?P<key>{VERSION_KEY})(?:V[1-9][0-9]*)?[\"']?\]?\s*(?::|[=!<>]{{1,3}})\s*"
    r"(?:int(?:32|64)?\()?['\"]?[vV]?(?P<version>[1-9][0-9]*)\b(?!\.)"
    r"(?P<extra>(?:\s*\|\s*[1-9][0-9]*)*)",
    re.IGNORECASE,
)
SCHEMA_FIELD = re.compile(
    rf"[\"']?(?P<key>{VERSION_KEY})[\"']?\s*:\s*\{{?\s*"
    r"(?:(?:[\"']?type[\"']?\s*:\s*[\"']?integer[\"']?[,]?\s*))?"
    r"[\"']?(?:const|enum)[\"']?\s*:\s*(?:\[\s*|-\s*)?"
    r"(?P<version>[1-9][0-9]*)\b(?P<extra>(?:\s*,\s*[1-9][0-9]*|\s*\n\s*-\s*[1-9][0-9]*)*)",
    re.IGNORECASE,
)
DECLARATION = re.compile(
    r"\b(?:type|interface|class|enum|struct)\s+"
    r"(?P<family>[A-Za-z_][A-Za-z0-9_]*?)[vV](?P<version>[1-9][0-9]*)\b"
)
PATH_GENERATION = re.compile(r"(^|[-_./])([vV])([1-9][0-9]*)(?=$|[-_./])")
API_PATH = re.compile(r"(?P<family>/(?:api|protocol|rpc)/)[vV](?P<version>[1-9][0-9]*)(?=/|[\"'`\s]|$)")
CODE_SUFFIXES = {".go", ".py", ".ts", ".tsx", ".js", ".mjs", ".cts", ".mts", ".c", ".cpp", ".h", ".hpp", ".rs", ".java", ".json", ".yaml", ".yml", ".proto"}


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE)


def paths(payload: bytes) -> set[str]:
    return {value.decode("utf-8") for value in payload.split(b"\0") if value}


def source_file(path: str) -> bool:
    value = Path(path)
    # Invalid-input fixtures and test assertions are not protocol declarations.
    return value.suffix in CODE_SUFFIXES and not (
        {"test", "tests", "testdata", "fixtures", "__tests__"} & set(value.parts)
        or re.search(r"(?:^test_|[._-]test[._-]|[._-]spec[._-])", value.name)
    )


def path_identity(path: str) -> tuple[str, tuple[int, ...]]:
    versions = tuple(int(match[3]) for match in PATH_GENERATION.finditer(path))
    return PATH_GENERATION.sub(lambda match: match[1] + "v#", path), versions


def signals(text: str) -> dict[str, list[tuple[int, int]]]:
    found: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for expression, kind in [(FIELD, "field"), (SCHEMA_FIELD, "field"), (DECLARATION, "type"), (API_PATH, "path")]:
        for match in expression.finditer(text):
            name = match.groupdict().get("key") or match["family"]
            if kind == "field":
                name = name.lower().replace("_", "")
            line = text.count("\n", 0, match.start()) + 1
            # Documentation comments do not define a protocol identity.
            prefix = text[text.rfind("\n", 0, match.start()) + 1:match.start()].lstrip()
            if prefix.startswith(("//", "#", "*", "/*")):
                continue
            found[f"{kind}:{name}"].append((int(match["version"]), line))
            for extra in re.findall(r"[1-9][0-9]*", match.groupdict().get("extra") or ""):
                found[f"{kind}:{name}"].append((int(extra), line))
    return found


def read_base(root: Path, base: str, path: str) -> str:
    return git(root, "show", f"{base}:{path}").decode("utf-8", errors="replace")


def check(root: Path, base_ref: str) -> dict:
    root = Path(git(root, "rev-parse", "--show-toplevel").decode().strip())
    base = git(root, "rev-parse", "--verify", f"{base_ref}^{{commit}}").decode().strip()
    base_paths = paths(git(root, "ls-tree", "-rz", "--name-only", base))
    working = paths(git(root, "diff", "--no-ext-diff", "--name-only", "--no-renames", "-z", base))
    working |= paths(git(root, "ls-files", "--others", "--exclude-standard", "-z"))
    staged = paths(git(root, "diff", "--cached", "--no-ext-diff", "--name-only", "--no-renames", "-z", base))
    index_paths = paths(git(root, "ls-files", "-z"))
    families: dict[str, list[tuple[str, tuple[int, ...]]]] = defaultdict(list)
    for path in base_paths:
        family, versions = path_identity(path)
        families[family].append((path, versions))
    findings = []
    checked = []
    established_fields: dict[tuple[str, str], set[int]] = {}

    def established(path: str, identity: str) -> set[int]:
        # A new implementation file may consume a format already owned by its
        # package. Do not misclassify that as introducing a new protocol version.
        key = (str(Path(path).parent), identity)
        if key not in established_fields:
            values = set()
            for candidate in base_paths:
                if str(Path(candidate).parent) == key[0] and source_file(candidate):
                    values.update(version for version, _ in signals(read_base(root, base, candidate)).get(identity, []))
            established_fields[key] = values
        return established_fields[key]
    def inspect(path: str, text: str, layer: str):
        checked.append(path)
        family, versions = path_identity(path)
        predecessors = families.get(family, [])
        old_path = path if path in base_paths else None
        if versions and path not in base_paths:
            previous = max((entry[1] for entry in predecessors), default=())
            if any(version > 1 for version in versions) and (not previous or versions > previous):
                findings.append({"layer": layer, "path": path, "line": 1, "identity": "versioned-file-path", "before": list(previous), "after": list(versions)})
            if predecessors:
                old_path = max(predecessors, key=lambda entry: entry[1])[0]
        old = signals(read_base(root, base, old_path)) if old_path else {}
        new = signals(text) if source_file(path) else {}
        for identity, values in new.items():
            previous = {version for version, _line in old.get(identity, [])}
            if not previous and identity.startswith("field:") and any(version > 1 for version, _ in values):
                previous = established(path, identity)
            for version, line in values:
                if version > max(previous, default=1):
                    findings.append({"layer": layer, "path": path, "line": line, "identity": identity, "before": sorted(previous), "after": version})
    for path in sorted(working | staged):
        if not source_file(path) and not (Path(path).suffix == ".md" and PATH_GENERATION.search(path)):
            continue
        current = root / path
        if path in working and current.is_file():
            if current.is_symlink():
                raise ValueError(f"cannot inspect source symlink: {path}")
            inspect(path, current.read_text(encoding="utf-8"), "working-tree")
        if path in staged and path in index_paths:
            inspect(path, git(root, "show", f":{path}").decode("utf-8"), "index")
    # The two field parsers can identify the same declaration.
    unique = {json.dumps(item, sort_keys=True): item for item in findings}
    return {
        "status": "FAIL" if unique else "PASS", "baseCommit": base,
        "headCommit": git(root, "rev-parse", "HEAD").decode().strip(),
        "includesIndexWorkingTreeAndUntracked": True, "checkedFiles": sorted(set(checked)),
        "findings": list(unique.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--base", required=True, help="recorded development base; do not substitute the changed HEAD")
    args = parser.parse_args()
    try:
        result = check(args.repo, args.base)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(json.dumps({"status": "ERROR", "reason": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if result["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
