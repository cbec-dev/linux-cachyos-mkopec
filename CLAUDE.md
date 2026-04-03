# linux-cachyos-frl

Repeatable build system that applies mkopec's AMDGPU HDMI 2.1 FRL patches on top of
CachyOS's kernel PKGBUILD to produce an installable Arch package (`linux-cachyos-frl`).
Enables 4K/120Hz over HDMI 2.1 on AMD GPUs (RX 9070 XT / RDNA 4 / DCN 4.0.1).

**Status: WORKING.** Full build produces installable packages.

---

## Files

| File | Purpose |
|------|---------|
| `build-cachyos-frl` | Main build script — runs full build pipeline |
| `update-kernel-ref` | Refreshes ref/cachyos-source-clean |
| `filter-patch.py` | Strips SKIP_PATHS files from mkopec's raw patch |
| `audit-frl-patches.py` | Line-by-line verification of fixup patches vs patched tree |

**Patch files (0002–0008) are NOT distributed.** They must be regenerated from
the mkopec patch + CachyOS clean source using the procedure below.

---

## Directory layout

```
~/Projects/linux-cachyos-frl/       ← this repo (scripts + patches)
├── build/                          ← build workspace (gitignored)
│   ├── linux-cachyos/              ← git clone of CachyOS PKGBUILD repo
│   ├── 0001-amdgpu-frl.patch       ← filtered mkopec patch (generated)
│   └── pkg/                        ← makepkg workspace
│       ├── PKGBUILD, config, *.patch
│       ├── build.log
│       └── src/cachyos-6.x.y-z/    ← extracted+patched kernel source
└── ref/                            ← read-only reference materials (gitignored)
    ├── cachyos-source-clean/       ← clean unpatched CachyOS source
    └── mkopec-patch/
        └── 0001-amdgpu-frl.patch   ← raw unfiltered mkopec patch
```

---

## How to build

```bash
build-cachyos-frl ~/Downloads/Patch.zip
sudo pacman -U build/pkg/linux-cachyos-frl*.pkg.tar.zst
```

Download Patch.zip: https://github.com/mkopec/linux/actions → latest "Generate patch" run → "Patch" artifact.

### Building a testing variant

`FRL_SUFFIX` is overridable via environment variable (default: `frl`). To build
a testing kernel that installs side-by-side with a known working `linux-cachyos-frl`:

```bash
FRL_SUFFIX=frl-testing build-cachyos-frl ~/Downloads/Patch.zip
sudo pacman -U build/pkg/linux-cachyos-frl-testing*.pkg.tar.zst
```

Both kernels will appear in the bootloader. This is useful for validating patches
against a new CachyOS version before replacing the production kernel.

## How to refresh the reference source (after CachyOS kernel version bump)

```bash
update-kernel-ref                          # refresh clean source only
update-kernel-ref ~/Downloads/Patch.zip   # also update mkopec patch
```

---

## Architecture

### Upstream sources

- **CachyOS kernel**: https://github.com/CachyOS/linux-cachyos (PKGBUILDs + configs)
  Actual kernel: torvalds/linux + BORE scheduler + HDMI VRR/ALLM + ntsync + etc.
- **mkopec FRL patches**: https://github.com/mkopec/linux branch `hdmi_frl`
  Generated as: `git diff origin/master origin/hdmi_frl`

### Why fixup patches exist

mkopec's patch is based on torvalds/linux. CachyOS already carries the HDMI
VRR/ALLM patchset, which overlaps with ~26 files from mkopec's patch. Three categories:

| Category | Handling |
|----------|----------|
| Fully covered by CachyOS VRR/ALLM | Skip in filter-patch.py SKIP_PATHS |
| Partially overlapping — first hunk reversed, FRL hunks missing | Skip + fixup patch |
| No overlap (pure FRL) | Apply directly via 0001 + `--forward` |

`dc_resource.c` has 6 hunks: 5 FRL (apply cleanly) + 1 ALLM (already in CachyOS,
produces expected `.rej`, harmless).

### Patch application order

```
CachyOS kernel tarball (includes CachyOS's own patches baked in)
  ↓  0001-amdgpu-frl.patch       (~94 files, --forward || true)
  ↓  0002 drm_edid.c             (rename fn + struct param + update 2 call sites)
  ↓  0003 dc_types.h             (2 new structs + 2 new fields in dc_edid_caps)
  ↓  0004 link/Makefile          (link_hwss_hpo_frl.o + link_frl_training.o)
  ↓  0005 drm_connector.h        (new struct + replace fields in 2 existing structs)
  ↓  0006 amdgpu_dm_helpers.c    (FRL + DSC population body)
  ↓  0007 amdgpu_dm.c            (4 hunks: FRL signal type + YCbCr420 guard + dc_is_hdmi_signal + connector type)
  ↓  0008 intel_dp.c             (4 field refs: hdmi.X → hdmi.frl_cap.X, dsc_cap.X → dsc_cap.frl_cap.X)
```

### SKIP_PATHS in filter-patch.py

Fully covered by CachyOS VRR/ALLM (all hunks reversed — skip entirely):
`drm_connector.c`, `drm_crtc.c`, `drm_mode_config.c`, `drm_atomic_uapi.c`,
`amdgpu_dm.c`, `amdgpu_dm.h`, `amdgpu_dm_helpers.c`, `dc.h`, `dc_stream.h`,
`dm_helpers.h`, `ddc_service_types.h`, `freesync.c`, `info_packet.c`,
`mod_info_packet.h`, `amd_shared.h`

Partial overlaps with FRL bits handled by fixup patches:
`drm_edid.c` (→ 0002), `drm_connector.h` (→ 0005), `intel_dp.c` (→ 0008),
`dc_types.h` (→ 0003), `link/Makefile` (→ 0004)

NOT skipped — applies via --forward with 1 expected .rej:
`dc_resource.c` (hunk #4 ALLM rejected, 5 FRL hunks apply)

### PKGBUILD modifications (sed in build-cachyos-frl)

1. `_processor_opt=zen4` — CONFIG_MZEN4 (matches official script-znver4.sh)
2. `_use_auto_optimization=no` — matches official script-znver4.sh
3. FRL patches injected into `source=()` array (0001–0008)
4. `_pkgsuffix` renamed to `cachyos-${FRL_SUFFIX}` (no conflict with stock kernel)
5. Patch loop wrapped: `*amdgpu-frl*` uses `--forward || true`
6. `b2sums` gets 8 `SKIP` entries (one per FRL patch file)

### Build configuration

| Setting | Value |
|---------|-------|
| Scheduler | EEVDF + BORE (CachyOS default) |
| LTO | Clang ThinLTO |
| CPU tuning | zen4 (CONFIG_MZEN4) |
| Tick rate | 1000 Hz |
| Preempt | full (low-latency) |
| Hugepages | always |

---

## Generating fixup patches (0002–0008)

The patch files are not checked in — they must be regenerated from the mkopec
patch and the CachyOS clean source. This section is the authoritative reference
for what each patch must contain. **Always use mkopec's patch as the source of
truth**, not this document alone — the patch may evolve between kernel versions.

### Prerequisites

```bash
update-kernel-ref ~/Downloads/Patch.zip   # populates ref/cachyos-source-clean + ref/mkopec-patch
```

### Method for each patch

1. Extract mkopec's hunks for the target file:
   `filterdiff -i "a/path/to/file" ref/mkopec-patch/0001-amdgpu-frl.patch`
2. Read the CachyOS clean source file to see current state.
3. Identify which changes mkopec wants that CachyOS doesn't already have.
   - VRR/ALLM changes (vrr_cap, allm, fapa_start_location, gaming_info, etc.)
     are **already in CachyOS** — do NOT duplicate them.
   - FRL-specific changes (frl_cap structs, SIGNAL_TYPE_HDMI_FRL, FRL training
     objects, dc_is_hdmi_signal, etc.) are **missing** — these go in fixups.
4. Copy the clean source file, apply changes, generate diff:
   ```bash
   cp ref/cachyos-source-clean/path/to/file /tmp/file.orig
   cp /tmp/file.orig /tmp/file
   # edit /tmp/file to apply FRL changes
   diff -u /tmp/file.orig /tmp/file \
       | sed 's|/tmp/file.orig|a/path/to/file|;s|/tmp/file|b/path/to/file|' \
       > 00XX-fixup.patch
   ```
5. **Strip timestamps** from `---`/`+++` lines (audit-frl-patches.py parses
   `+++ b/path` and timestamps break path extraction):
   ```bash
   sed -i 's|\t[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\} [0-9:.]* [-+][0-9]\{4\}$||' 00XX-fixup.patch
   ```
6. Dry-run: `patch -p1 --dry-run -d ref/cachyos-source-clean < 00XX-fixup.patch`

### What each fixup must contain

**0002 — `drivers/gpu/drm/drm_edid.c`**

Rename function and update its signature + all call sites:
- `drm_get_max_frl_rate(int max_frl_rate, u8 *max_lanes, u8 *max_rate_per_lane)`
  → `drm_parse_max_frl_rate(int max_frl_rate, struct drm_hdmi_frl_cap *frl)`
- Function body: replace `*max_lanes`/`*max_rate_per_lane` with local vars,
  then assign `frl->max_lanes`, `frl->max_rate`, `frl->max_rate_per_lane` at end.
- Call site in `drm_parse_dsc_info`: `drm_parse_max_frl_rate(dsc_max_frl_rate, &hdmi_dsc->frl_cap)`
- Call site in `drm_parse_hdmi_forum_scds`: `drm_parse_max_frl_rate(max_frl_rate, &hdmi->frl_cap)`

Do NOT include: `drm_parse_hdmi_gaming_info`, VRR debug prints, ALLM fields — CachyOS has these.

**0003 — `drivers/gpu/drm/amd/display/dc/dc_types.h`**

Add two new struct definitions BEFORE `struct dc_edid_caps`:
- `struct dc_hdmi_frl_caps { max_rate, max_rate_per_lane, max_lanes }` (uint8_t fields)
- `struct dc_hdmi_dsc_caps { v1p2, all_bpp, native_420, max_bpc, total_chunk_kbytes,
  max_slices, max_clk, struct dc_hdmi_frl_caps frl }`

Add two fields to `struct dc_edid_caps` under the `/* HDMI 2.1 caps */` comment,
BEFORE the existing `bool allm`:
- `struct dc_hdmi_frl_caps frl_caps;`
- `struct dc_hdmi_dsc_caps dsc_caps;`

Do NOT add: `allm`, `fva`, `hdmi_vrr` bools — CachyOS already has them.

**0004 — `drivers/gpu/drm/amd/display/dc/link/Makefile`**

Add two object files:
- `link_hwss_hpo_frl.o` to the `LINK_HWSS` variable (hwss section)
- `link_frl_training.o` to the `LINK_PROTOCOLS` variable (protocols section)

Note: CachyOS may not have `link_hwss_virtual.o` or `link_dp_panel_replay.o`
that mkopec's base has — check actual Makefile content, don't blindly copy
mkopec's hunks.

**0005 — `include/drm/drm_connector.h`**

Add new struct `drm_hdmi_frl_cap { max_rate, max_rate_per_lane, max_lanes }`
(u8 fields). **Place it BEFORE `struct drm_hdmi_vrr_cap`** (after `struct drm_scdc`),
matching mkopec's ordering.

Replace fields in `struct drm_hdmi_dsc_cap`:
- Remove `u8 max_lanes` and `u8 max_frl_rate_per_lane`
- Add `struct drm_hdmi_frl_cap frl_cap`

Replace fields in `struct drm_hdmi_info`:
- Remove `u8 max_frl_rate_per_lane` and `u8 max_lanes`
- Add `struct drm_hdmi_frl_cap frl_cap`

Do NOT add: `fapa_start_location`, `allm`, `vrr_cap`, `drm_allm_mode` enum,
allm/passive_vrr properties — CachyOS already has all of these.

**0006 — `drivers/gpu/drm/amd/display/amdgpu_dm/amdgpu_dm_helpers.c`**

Expand `populate_hdmi_info_from_connector()` body. CachyOS has only
`edid_caps->scdc_present = hdmi->scdc.supported;` — add FRL + DSC population:
- Declare `struct dc_hdmi_dsc_caps *dsc = &edid_caps->dsc_caps;`
- FRL block: copy `hdmi->frl_cap.{max_rate, max_lanes, max_rate_per_lane}`
  into `edid_caps->frl_caps.*` (early return if `max_rate == 0`)
- DSC block: copy `hdmi->dsc_cap.{v_1p2, all_bpp, native_420, bpc_supported,
  max_slices, total_chunk_kbytes}` into `dsc->*`, plus `hdmi->dsc_cap.frl_cap.*`
  into `dsc->frl.*` (early return if `!v_1p2`)

Do NOT include: the `edid_hdmi`/`allm`/`fva`/`hdmi_vrr` population in
`dm_helpers_parse_edid_caps` — CachyOS already has that block. Do NOT include
the `dm_is_freesync_pcon_whitelist` / `dm_get_adaptive_sync_support_type`
refactoring — those are VRR changes.

**0007 — `drivers/gpu/drm/amd/display/amdgpu_dm/amdgpu_dm.c`**

This patch needs exactly **4 hunks**:

1. **`emulated_link_detect`**: Add `case SIGNAL_TYPE_HDMI_FRL:` block (I2C
   transaction, HDMI_FRL signal) after the existing `SIGNAL_TYPE_HDMI_TYPE_A` case.

2. **`fill_stream_properties_from_drm_display_mode`** (YCbCr420 fallback):
   Wrap the existing `timing_out->pixel_encoding = PIXEL_ENCODING_YCBCR420`
   block with an FRL guard:
   ```c
   if (!stream->link->link_enc->features.flags.bits.IS_HDMI_FRL_CAPABLE ||
       stream->sink->edid_caps.frl_caps.max_rate == 0) {
   ```
   Include the comment: `/* If pixel clock exceeds max HDMI TMDS clock, and
   FRL is not possible, try to fall back to 4:2:0 encoding for TMDS */`

3. **`create_stream_for_sink`** (hfvsif_infopacket): Change
   `stream->signal == SIGNAL_TYPE_HDMI_TYPE_A` to
   `dc_is_hdmi_signal(stream->signal)` so FRL streams also get
   `mod_build_hf_vsif_infopacket()` called. **This is critical — without it
   HDMI FRL streams never build their HF-VSIF infopacket.**

4. **`to_drm_connector_type`**: Add `case SIGNAL_TYPE_HDMI_FRL:` fallthrough
   to the `SIGNAL_TYPE_HDMI_TYPE_A` case returning `DRM_MODE_CONNECTOR_HDMIA`.

Do NOT include: suspend/shutdown FRL disable, DC_OVERRIDE_PCON_VRR_ID_CHECK,
allm_mode state tracking, freesync_on_desktop, ADAPTIVE_SYNC_TYPE_HDMI /
ADAPTIVE_SYNC_TYPE_PCON_ALLOWED rewrites, HDMI CEC / allm property attachment,
allm_changed commit_tail logic, parse_amd_vsdb refactoring, monitor_range_from_hdmi,
or any of the large amdgpu_dm_update_freesync_caps rewrite — CachyOS carries
all of that via its VRR/ALLM patchset.

**0008 — `drivers/gpu/drm/i915/display/intel_dp.c`**

In `intel_dp_hdmi_sink_max_frl()`, update 4 field references:
- `info->hdmi.max_lanes` → `info->hdmi.frl_cap.max_lanes`
- `info->hdmi.max_frl_rate_per_lane` → `info->hdmi.frl_cap.max_rate_per_lane`
- `info->hdmi.dsc_cap.max_lanes` → `info->hdmi.dsc_cap.frl_cap.max_lanes`
- `info->hdmi.dsc_cap.max_frl_rate_per_lane` → `info->hdmi.dsc_cap.frl_cap.max_rate_per_lane`

### Verification

After generating all patches, verify the full pipeline:

```bash
# 1. Create test tree
rsync -a ref/cachyos-source-clean/ /tmp/frl-test-tree/

# 2. Generate filtered 0001
python3 filter-patch.py ref/mkopec-patch/0001-amdgpu-frl.patch /tmp/frl-test-tree/0001.patch

# 3. Apply 0001 (expect dc_resource.c hunk #4 rejection — that's the ALLM hunk)
cd /tmp/frl-test-tree && patch -p1 --forward < 0001.patch || true

# 4. Apply fixups 0002–0008 (all must apply cleanly, no fuzz)
for p in 0002 0003 0004 0005 0006 0007 0008; do
    patch -p1 < /path/to/${p}-*.patch
done

# 5. Run audit (symlink test tree to expected path first)
mkdir -p build/pkg/src && ln -sfn /tmp/frl-test-tree build/pkg/src/cachyos-X.Y.Z-N
cp /tmp/frl-test-tree/0001.patch build/pkg/src/0001-amdgpu-frl.patch
python3 audit-frl-patches.py   # must report ALL PASS
```

### Common mistakes

- **Timestamps in patch headers**: `diff -u` adds timestamps to `---`/`+++`
  lines. The audit script parses `+++ b/path` by stripping from char 6 — a
  timestamp suffix makes it look for a nonexistent file. Always strip them.
- **Including VRR/ALLM changes**: CachyOS already has `drm_hdmi_vrr_cap`,
  `drm_parse_hdmi_gaming_info`, `allm`, `fapa_start_location`, `vrr_cap`,
  allm properties, freesync_on_desktop, adaptive_sync refactoring, etc.
  Including these in fixups will double-apply or conflict.
- **Missing `dc_is_hdmi_signal` in 0007**: Without this, FRL streams skip
  the hfvsif_infopacket build in `create_stream_for_sink`. Easy to miss
  because it looks like a VRR/ALLM change, but it's FRL-critical.
- **Wrong struct placement in 0005**: `struct drm_hdmi_frl_cap` must go
  BEFORE `struct drm_hdmi_vrr_cap` (after `struct drm_scdc`), not after it.
  mkopec's patch defines it there because `drm_hdmi_dsc_cap` (which comes
  after `drm_hdmi_vrr_cap`) uses it as a member.
- **Makefile context mismatch**: CachyOS's `link/Makefile` may differ from
  mkopec's base (e.g., missing `link_hwss_virtual.o`, `link_dp_panel_replay.o`).
  Always read the actual CachyOS Makefile instead of copying mkopec hunks verbatim.

---

## Conflict resolution workflow (for future kernel/patch updates)

### 1. Refresh ref/

```bash
update-kernel-ref ~/Downloads/Patch.zip
```

### 2. Dry-run unfiltered patch against clean source

```bash
cd ref/cachyos-source-clean
patch -p1 --dry-run --forward < ref/mkopec-patch/0001-amdgpu-frl.patch 2>&1 \
    | grep -E 'FAILED|Reversed|ignored'
```

### 3. Inspect individual files with filterdiff

```bash
filterdiff -i "a/path/to/file.c" ref/mkopec-patch/0001-amdgpu-frl.patch

filterdiff -i "a/path/to/file.c" ref/mkopec-patch/0001-amdgpu-frl.patch \
    | patch -p1 --dry-run --forward -d ref/cachyos-source-clean
```

### 4. Categorize conflicts

- **All hunks "Reversed"** → add to SKIP_PATHS in filter-patch.py
- **Mix: first reversed, later hunks are FRL** → SKIP_PATHS + new fixup patch
- **Pure offset** → applies with fuzz, leave in 0001

### 5. Write and test fixup patches

Always dry-run before wiring in:
```bash
patch -p1 --dry-run -d ref/cachyos-source-clean < 00XX-fixup.patch
```

### 6. Wire new fixup into build-cachyos-frl

In `prepare_build_dir()`:
- Add `cp` line for the new patch file
- Add patch name to the source array `sed` injection
- Increment the SKIP count in the b2sums `sed` (one SKIP per patch)
- Add patch name to `audit-frl-patches.py` FIXUP_PATCHES list

### 7. Test

```bash
build-cachyos-frl ~/Downloads/Patch.zip
python3 ~/Projects/linux-cachyos-frl/audit-frl-patches.py
```

---

## Post-install verification

```bash
uname -r
sudo dmesg | grep -i "frl\|HDMI FRL"
sudo dmesg | grep "HW_LINK_TRAINING"
xrandr --verbose | grep -A5 "HDMI"
```

Expected kernel: `6.x.y-1-cachyos-frl` (or `cachyos-frl-testing` for testing builds)

### Version numbering note

CachyOS uses `_tagrel` for the source tarball tag and `pkgrel` for the package
version — these can differ. For example, `cachyos-6.19.11-2.tar.gz` (source
tag `_tagrel=2`) produces package version `6.19.11-1` (`pkgrel=1`). The
extracted source directory is named after the tag (`src/cachyos-6.19.11-2/`),
not the package version.

**`audit-frl-patches.py`** has a hardcoded `SRC_DIR` path that includes this
directory name (e.g., `cachyos-6.19.11-2`). It must be updated when the CachyOS
source tag changes.

## AMDGPU module parameters

```bash
echo "options amdgpu allm_mode=2" | sudo tee /etc/modprobe.d/amdgpu-allm.conf
```

`allm_mode`: 0=disabled, 1=dynamic (based on VRR), 2=always on
`hdmi_vrr_desktop_mode`: true=always active (default), false=disabled — set via kernel cmdline in `/boot/limine/limine.conf`
