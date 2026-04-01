#!/usr/bin/env python3
"""
Filter mkopec's HDMI FRL patch for CachyOS compatibility.

Removes:
  - Non-kernel files (.github/, .gitignore)
  - DRM core files that CachyOS already carries via the HDMI VRR/ALLM patchset.

If new conflicts appear in future versions, add the paths to SKIP_PATHS below.
"""
import sys
import re

# Files to exclude from the patch entirely.
SKIP_PATHS = {
    # Non-kernel repo files
    '.github/',
    '.gitignore',

    # DRM core changes already carried by CachyOS (HDMI VRR/ALLM patchset).
    'drivers/gpu/drm/drm_edid.c',
    'drivers/gpu/drm/drm_connector.c',
    'drivers/gpu/drm/drm_crtc.c',
    'drivers/gpu/drm/drm_mode_config.c',
    'drivers/gpu/drm/drm_atomic_uapi.c',
    'drivers/gpu/drm/i915/display/intel_dp.c',
    'include/drm/drm_connector.h',
    'include/drm/drm_crtc.h',
    'include/drm/drm_mode_config.h',

    # AMDGPU files already carried by CachyOS (VRR/ALLM patchset).
    # Confirmed all hunks "Reversed (or previously applied)" on clean source.
    'drivers/gpu/drm/amd/display/amdgpu_dm/amdgpu_dm.c',
    'drivers/gpu/drm/amd/display/amdgpu_dm/amdgpu_dm.h',
    'drivers/gpu/drm/amd/display/amdgpu_dm/amdgpu_dm_helpers.c',
    'drivers/gpu/drm/amd/display/dc/dc.h',
    'drivers/gpu/drm/amd/display/dc/dc_stream.h',
    'drivers/gpu/drm/amd/display/dc/dm_helpers.h',
    'drivers/gpu/drm/amd/display/include/ddc_service_types.h',
    'drivers/gpu/drm/amd/display/modules/freesync/freesync.c',
    'drivers/gpu/drm/amd/display/modules/info_packet/info_packet.c',
    'drivers/gpu/drm/amd/display/modules/inc/mod_info_packet.h',
    'drivers/gpu/drm/amd/include/amd_shared.h',

    # These have partial overlaps handled by fixup patches (0002-0007).
    # The main patch hunks either fail or double-apply; fixups cover the
    # FRL-specific bits that CachyOS is missing.
    # NOTE: dc_resource.c is intentionally NOT skipped — it has 5 FRL hunks
    # that apply cleanly. Only hunk #4 (ALLM, already in CachyOS) fails, and
    # --forward || true handles that gracefully via .rej.
    'drivers/gpu/drm/amd/display/dc/dc_types.h',
    'drivers/gpu/drm/amd/display/dc/link/Makefile',

    # NOTE: drivers/gpu/drm/display/drm_dp_helper.c has real FRL changes
    # (hdmi->max_lanes → hdmi->frl_cap.max_lanes) but CachyOS already
    # carries this change. Kept in patch for --forward to handle.
}

DIFF_HEADER = re.compile(r'^diff --git a/(\S+) b/\S+')


def should_skip(path):
    for skip in SKIP_PATHS:
        if skip.endswith('/'):
            if path.startswith(skip):
                return True
        elif path == skip:
            return True
    return False


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input.patch> <output.patch>", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1], 'r') as f:
        lines = f.readlines()

    out_lines = []
    skipping = False
    skipped_files = []
    kept_count = 0

    for line in lines:
        m = DIFF_HEADER.match(line)
        if m:
            path = m.group(1)
            if should_skip(path):
                skipping = True
                skipped_files.append(path)
            else:
                skipping = False
                kept_count += 1

        if not skipping:
            out_lines.append(line)

    # Write output, ensuring it ends with a newline
    with open(sys.argv[2], 'w') as f:
        f.writelines(out_lines)
        if out_lines and not out_lines[-1].endswith('\n'):
            f.write('\n')

    print(f"Filtered patch: {kept_count} files kept, {len(skipped_files)} skipped", file=sys.stderr)
    for s in skipped_files:
        print(f"  skipped: {s}", file=sys.stderr)


if __name__ == '__main__':
    main()