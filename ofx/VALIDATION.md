# Validation — 23 October 2026

## Optimization pass — 8 November 2026

29 regression tests passed. Real CUDA comparison against baseline commit
`4f9f8b1` used six 192x128 HDR frames per job, Hann 4/2, and all three hint modes
plus normal/low-VRAM paths. Complete output arrays matched with maximum absolute
error **0.0** in all five jobs, including warmup.

| Warm job (first process warmup excluded) | Baseline | Optimized |
|---|---:|---:|
| No hint / low VRAM | 6.188 s | 1.562 s |
| First-frame hint / low VRAM | 5.594 s | 1.579 s |
| Full hints / low VRAM | 5.843 s | 1.610 s |
| Full hints / normal, carry off | 5.360 s | 1.687 s |

Warm jobs totaled 22.985 s before and 6.438 s after: **3.57x faster** for this
small-block overhead benchmark. First-job times were 12.343 s and 12.265 s;
initial loading still costs time. These are not full-HD/4K frame rates and do
not establish a playback speed or a full-clip speedup inside Resolve.

The final CPU-retention RAM guard was exercised in the optimized run. The idle
policy and transient/permanent Windows-lock behavior have regression tests.
Full Resolve UI processing was not re-run during this optimization pass.
Research and implementation details: `OPTIMIZATION_NOTES.md`.

## Fusion compatibility fix — 24 October 2026

The first real Fusion use completed backend inference at 1920x1080, but the
render returned `kOfxStatErrUnsupported` afterward. The plugin unconditionally
called the optional persistent-message API when clearing its status. Status
notifications are now isolated from render success; error reporting falls back
to the ordinary message API and also writes `host-error.txt` in the instance's
temporary folder. A native CTest simulates unsupported persistent messages,
including a failing fallback, and passes without letting exceptions escape.

After rebuilding and installing the fix, Resolve's Fusion scripting API
successfully evaluated the CorridorKey output on the user's 1920x1080 image
sequence: a non-null image was returned, with 1920x1080 output dimensions.
The node was connected between MediaIn1 and MediaOut1. This verifies a render
inside Fusion; broader footage quality and Color-page behavior remain untested.

The checks below describe the original backend validation.

Windows x64, NVIDIA GeForce RTX 5080 (16 GB), Python 3.11,
PyTorch 2.9.1+cu128, OpenCV 4.11.0.86. Native bundle compiled in Release
using Zig 0.14.1 / Clang 19.1.7 and CMake/Ninja.

- **Build:** succeeded; x64 DLL loads and registers one OpenFX image-effect
  plugin, `org.corridorkey.community.v2`, version 2.0.
- **Regression suite:** 14 tests passed, including real worker subprocess IPC,
  failure/recovery, source and hint invalidation, display-only cache reuse,
  HDR/signed transfer, alpha association, reconstruction mix and despeckle.
- **Actual CUDA inference:** four jobs passed with the real downloaded v2,
  C-RADIO, MoGe and RVM weights. Each used six synthetic 192x128 float frames,
  Hann chunk 4 / stride 2 (two overlapping windows).

| Hint mode | Carry | Low VRAM | Result |
|---|---|---|---|
| No hint | On | On | Passed |
| First-frame external hint | On | On | Passed |
| Full external hints | On | On | Passed |
| Full external hints | Off | Off | Passed |

All returned float RGBA at the requested resolution, with finite values and
alpha within [0,1]. RGB retained negative values (about -0.0103) and values
above 1 (up to 2.147). The foundation downloads were verified against their
publishers' hashes: C-RADIO and MoGe SHA-256, RVM's upstream MD5 check.
The machine-readable run report is generated at `ofx/build-smoke/report.json`.

**Original 23 October Resolve check:** the local Resolve 21.1 startup log recorded
`OFX: loading org.corridorkey.community.v2`. Its scripting connection did not
become available then, so no render inside Resolve was verified at that time. Real-shot quality,
Color-page alpha wiring, Fusion rendering, 4K performance, cancellation inside
Resolve, and optional BiRefNet inference still need host/footage testing.
Synthetic backend tests are not a claim of those results.

Run the commands in `README.md` here to reproduce the checks. Model files and
the isolated CUDA environment are local assets excluded from Git.
