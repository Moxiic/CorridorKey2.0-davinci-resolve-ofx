"""Compare old/new worker overhead and pixel parity on real CUDA inference.

The first job per process is warmup and excluded from speedup. Small synthetic
frames isolate block-management overhead; results are not a 1080p/4K fps claim.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def measure(worker, work):
    work.mkdir(parents=True, exist_ok=True)
    for name in ("stop", "request.json", "ready.json", "done.json", "error.txt"):
        (work / name).unlink(missing_ok=True)
    h, w, count = 128, 192, 6
    y, x = np.indices((h, w))
    for i in range(count):
        rgba = np.full((h, w, 4), [.03, .55, .02, 1], dtype="<f4")
        mask = ((x - 90 - i) / 30)**2 + ((y - 64) / 48)**2 < 1
        rgba[mask] = [.65, .2, .12, 1]
        rgba[40:48, 90:100, :3] = [2, .5, -.01]
        rgba.tofile(work / f"source_{i:06d}.bin")
        hint = np.zeros_like(rgba); hint[..., 3] = mask
        hint.tofile(work / f"hint_{i:06d}.bin")
    log = (work / "console.log").open("w")
    process = subprocess.Popen([sys.executable, str(worker), "--root", str(ROOT), "--work", str(work)],
        stdout=log, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    def wait(name):
        deadline = time.monotonic() + 600
        while not (work / name).exists():
            if process.poll() is not None: raise RuntimeError(f"Worker exited: {work / 'console.log'}")
            if time.monotonic() > deadline: raise TimeoutError(name)
            time.sleep(.025)
    times = []
    try:
        wait("ready.json")
        for index, (mode, low) in enumerate(((0, True), (0, True), (1, True), (2, True), (2, False))):
            settings = work / "settings.json"
            settings.write_text(json.dumps(dict(auto_vram=False, hann_chunk=4, hann_stride=2,
                low_vram=low, carry_hint=index != 4)))
            request = dict(protocol=2, width=w, height=h, count=count, start=index * count, index=1,
                mode=mode, quality=.95, colorspace=1, premult=False, output=2,
                despill=.5, despeckle=0, refiner=1, settings=str(settings), staged_token="benchmark-bake")
            (work / "done.json").unlink(missing_ok=True)
            (work / "request.tmp").write_text(json.dumps(request))
            start = time.monotonic()
            (work / "request.tmp").rename(work / "request.json")
            wait("done.json")
            seconds = time.monotonic() - start
            if not json.loads((work / "done.json").read_text())["ok"]:
                raise RuntimeError((work / "error.txt").read_text())
            image = np.fromfile(work / "output.bin", dtype="<f4")
            if image.size != h*w*4 or not np.isfinite(image).all(): raise RuntimeError("Invalid output")
            np.save(work / f"result_{index}.npy", image)
            times.append(seconds)
            print(f"{work.name} job {index}: {seconds:.3f}s", flush=True)
    finally:
        (work / "stop").touch()
        try: process.wait(timeout=10)
        except subprocess.TimeoutExpired: process.kill(); process.wait()
        log.close()
    return times


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    args = parser.parse_args()
    directory = ROOT / "ofx/build-benchmark"
    before = measure(args.baseline.resolve(), directory / "before")
    after = measure(ROOT / "ofx/backend/worker.py", directory / "after")
    diffs = [float(np.max(np.abs(np.load(directory / 'before' / f'result_{i}.npy') -
                                np.load(directory / 'after' / f'result_{i}.npy')))) for i in range(5)]
    report = dict(before_seconds=before, after_seconds=after, max_abs_error=diffs,
        warm_speedup=sum(before[1:]) / sum(after[1:]), width=192, height=128,
        frames_per_block=6, note="Warmup excluded; synthetic block overhead benchmark, not a full-resolution fps claim.")
    (directory / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)
    if any(d > 1e-6 for d in diffs): raise RuntimeError("Pixel parity regression")
