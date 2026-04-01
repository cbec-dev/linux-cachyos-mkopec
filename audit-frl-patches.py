#!/usr/bin/env python3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PATCH_DIR = SCRIPT_DIR
SRC_DIR = SCRIPT_DIR / "build" / "pkg" / "src" / "cachyos-6.19.10-1"

FIXUP_PATCHES = [
    "0002-amdgpu-frl-edid-fixup.patch",
    "0003-amdgpu-frl-dc-types-fixup.patch",
    "0004-amdgpu-frl-link-makefile-fixup.patch",
    "0005-amdgpu-frl-connector-header-fixup.patch",
    "0006-amdgpu-frl-dm-helpers-fixup.patch",
    "0007-amdgpu-frl-amdgpu-dm-fixup.patch",
    "0008-amdgpu-frl-intel-dp-fixup.patch",
]

MAIN_PATCH = SCRIPT_DIR / "build" / "pkg" / "src" / "0001-amdgpu-frl.patch"

KNOWN_REJ = {
    "drivers/gpu/drm/amd/display/dc/core/dc_resource.c",
}

EXPECTED_ABSENT_FROM_TREE = {
    "drivers/gpu/drm/amd/display/dc/dc_types.h",
    "drivers/gpu/drm/amd/display/dc/link/Makefile",
}


def parse_hunks(patch_path):
    """Yield (target_rel_path, [add_lines], [remove_lines]) per file section."""
    with open(patch_path) as f:
        lines = f.readlines()

    target = None
    adds = []
    removes = []

    for line in lines:
        if line.startswith("+++ b/"):
            if target is not None:
                yield target, adds, removes
            target = line[6:].strip()
            adds = []
            removes = []
        elif line.startswith("@@"):
            pass
        elif line.startswith("+") and not line.startswith("+++"):
            adds.append(line[1:].rstrip("\n"))
        elif line.startswith("-") and not line.startswith("---"):
            removes.append(line[1:].rstrip("\n"))

    if target is not None:
        yield target, adds, removes


def check_additions(target_rel, adds):
    src_file = SRC_DIR / target_rel
    if not src_file.exists():
        return [f"FILE NOT FOUND: {src_file}"]

    file_lines = set(src_file.read_text().splitlines())
    errors = []
    for line in adds:
        if line.strip() == "":
            continue
        if line not in file_lines:
            errors.append(f"MISSING: {repr(line)}")
    return errors


def check_removals(target_rel, removes, adds_set):
    src_file = SRC_DIR / target_rel
    if not src_file.exists():
        return []

    file_lines = set(src_file.read_text().splitlines())
    errors = []
    for line in removes:
        if line.strip() == "":
            continue
        if line in adds_set:
            continue
        if line in file_lines:
            errors.append(f"STILL PRESENT: {repr(line)}")
    return errors


def run_patch(patch_path, label, skip_files=None, only_files=None, skip_removals=False):
    skip_files = skip_files or set()
    total = 0
    failed = 0
    results = []

    for target, adds, removes in parse_hunks(patch_path):
        if target in skip_files:
            results.append((target, "SKIP", []))
            continue
        if only_files is not None and target not in only_files:
            continue

        add_errors = check_additions(target, adds)
        rem_errors = [] if skip_removals else check_removals(target, removes, set(adds))
        errors = add_errors + rem_errors
        total += 1
        status = "PASS" if not errors else "FAIL"
        if errors:
            failed += 1
        results.append((target, status, errors))

    print(f"\n{'='*65}")
    print(f"  {label}")
    print(f"{'='*65}")
    for target, status, errors in results:
        if status == "SKIP":
            print(f"  [SKIP] {target}")
        else:
            print(f"  [{status}] {target}")
            for e in errors:
                print(f"          {e}")
    print(f"  Files checked: {total}  Failed: {failed}")
    return failed


all_failures = 0

for name in FIXUP_PATCHES:
    path = PATCH_DIR / name
    all_failures += run_patch(path, name)

print(f"\n{'='*65}")
print(f"  0001-amdgpu-frl.patch (key FRL files only, adds/no removals)")
print(f"{'='*65}")

KEY_FRL_FILES = {
    "drivers/gpu/drm/amd/display/dc/core/dc_resource.c",
    "drivers/gpu/drm/amd/display/amdgpu_dm/amdgpu_dm.c",
    "drivers/gpu/drm/amd/display/amdgpu_dm/amdgpu_dm_helpers.c",
    "include/drm/drm_connector.h",
    "drivers/gpu/drm/drm_edid.c",
}

all_failures += run_patch(
    MAIN_PATCH,
    "0001 (key files, additions only)",
    skip_files=KNOWN_REJ,
    only_files=KEY_FRL_FILES,
    skip_removals=True,
)

print(f"\n{'='*65}")
print(f"  OVERALL: {'ALL PASS' if all_failures == 0 else f'{all_failures} FAILURE(S) FOUND'}")
print(f"{'='*65}\n")
sys.exit(0 if all_failures == 0 else 1)
