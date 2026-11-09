# Optimization research — 8 November 2026

The installed runtime remains PyTorch 2.9.1/CUDA 12.8. Changes target the measured
wrapper overhead; the upstream neural architecture, weights, color contract and
Hann-window algorithms are unchanged.

## Applied

- Reuse CPU-resident model parameters between blocks of one explicit clip bake.
  Restore the original unload behavior for ordinary preview requests and when
  RAM is constrained. Retention requires the model's full byte size plus 2 GiB
  available headroom; idle retained weights are released after 30 seconds.
  GPU models are offloaded and the CUDA allocator's unused blocks are released
  after each inference job, preserving sharing with Resolve/other nodes.
- Reset runtime memory-chunk controls before reusing a model, so switching from
  low-VRAM to normal inference cannot retain an earlier profile accidentally.
  Compare checkpoint/foundation file metadata before reuse to detect replacements.
- Skip source RGBA reads/color conversion when reconstruction mix does not need
  it. Matte output also skips foreground EXR decoding and all RGB compositing.
- Coalesce clip progress/Inspector updates to at most four per second. Terminal
  states always publish immediately. This reduces filesystem traffic and local
  Fusion scripting round trips, especially when frames are already cached.
- Use unique, closed temporary files plus bounded retries for atomic publication
  on Windows. Status/UI update failures no longer discard rendered frames.
  This addresses an observed prior job failure at frame 190/360 caused by a
  transient access-denied error replacing `progress.json`.

`CORRIDORKEY2_CPU_MODEL_CACHE=0` disables CPU retention. Retained parameters consume
several GB of system RAM per recently active worker; they do not reserve idle
VRAM. No dependency upgrade or reduced-precision weight conversion is required.

## Evidence and sources

- [Official CorridorKey performance guidance](https://help.corridorkey.com/docs/performance/)
  distinguishes expensive inference from cheap recompositing and persistent host
  caching. It also reports that its experimental stage-1 compilation mode is
  slower on its measured configurations, so this update keeps eager inference.
- [PyTorch Module device moves](https://docs.pytorch.org/docs/stable/generated/torch.nn.Module.html)
  documents moving model parameters and buffers to CPU. This makes it possible
  to retain loaded weights without retaining the idle GPU allocation.
- [PyTorch 2.9 empty_cache](https://docs.pytorch.org/docs/2.9/generated/torch.cuda.memory.empty_cache.html)
  releases unoccupied allocator memory for other GPU applications; it does not
  free live model tensors. CPU offload must precede it.
- [Python atomic replacement](https://docs.python.org/3/library/os.html#os.replace)
  and [Windows MoveFileEx](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw)
  underpin atomic publication. Windows transient sharing failures are retried;
  actual missing-path/permissions/disk failures still propagate on required IPC.
- [OpenFX thread safety](https://openfx.readthedocs.io/en/main/Reference/ofxThreadSafety.html)
  supports keeping host/UI interaction in supported actions or the Fusion helper,
  without introducing host API calls from new native background threads.

## Reproducible validation

`ofx/tests/benchmark_worker.py` launches baseline and optimized workers separately,
warms each up, then compares four real CUDA inference jobs: no hint, first hint,
full hints, and full hints with carry disabled/normal memory mode. It uses six
192x128 HDR synthetic frames per job and compares complete float RGBA outputs.
This isolates model-load/block overhead; it is not a 1080p/4K throughput claim.

The local machine-readable results are in `ofx/build-benchmark/report.json`.
The baseline source used for this run is Git commit `4f9f8b1` (before this update).
Tests include transient lock retries, permanent failures preserving prior status,
progress throttling, nonfatal UI failures, unnecessary source-read elimination,
and bounded CPU-model retention. See `VALIDATION.md` for results.
