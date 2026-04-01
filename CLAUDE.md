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
| `0002-amdgpu-frl-edid-fixup.patch` | drm_edid.c: rename fn + update call sites |
| `0003-amdgpu-frl-dc-types-fixup.patch` | dc_types.h: struct defs + field injection |
| `0004-amdgpu-frl-link-makefile-fixup.patch` | link/Makefile: add FRL .o files |
| `0005-amdgpu-frl-connector-header-fixup.patch` | drm_connector.h: struct drm_hdmi_frl_cap + frl_cap fields |
| `0006-amdgpu-frl-dm-helpers-fixup.patch` | amdgpu_dm_helpers.c: FRL/DSC population |
| `0007-amdgpu-frl-amdgpu-dm-fixup.patch` | amdgpu_dm.c: SIGNAL_TYPE_HDMI_FRL cases |
| `0008-amdgpu-frl-intel-dp-fixup.patch` | intel_dp.c: update frl_cap field references |

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
  ↓  0002 drm_edid.c             (rename drm_get_max_frl_rate → drm_parse_max_frl_rate)
  ↓  0003 dc_types.h             (struct dc_hdmi_frl_caps + dc_hdmi_dsc_caps + fields)
  ↓  0004 link/Makefile          (link_hwss_hpo_frl.o + link_frl_training.o)
  ↓  0005 drm_connector.h        (struct drm_hdmi_frl_cap, frl_cap in dsc_cap + hdmi_info)
  ↓  0006 amdgpu_dm_helpers.c    (FRL + DSC population in populate_hdmi_info_from_connector)
  ↓  0007 amdgpu_dm.c            (SIGNAL_TYPE_HDMI_FRL in 3 switch/if locations)
  ↓  0008 intel_dp.c             (frl_cap.max_lanes, frl_cap.max_rate_per_lane refs)
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
4. `_pkgsuffix` renamed to `cachyos-frl` (no conflict with stock kernel)
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

Expected kernel: `6.x.y-1-cachyos-frl`

## AMDGPU module parameters

```bash
echo "options amdgpu allm_mode=2" | sudo tee /etc/modprobe.d/amdgpu-allm.conf
```

`allm_mode`: 0=disabled, 1=dynamic (based on VRR), 2=always on
`hdmi_vrr_desktop_mode`: true=always active (default), false=disabled — set via kernel cmdline in `/boot/limine/limine.conf`
