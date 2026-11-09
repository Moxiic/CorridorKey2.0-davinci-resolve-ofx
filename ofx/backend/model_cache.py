"""Conservative CPU model retention; never reserve idle CUDA memory."""
import ctypes
import os


def available_ram():
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_uint32), ("load", ctypes.c_uint32)] + [
                (name, ctypes.c_uint64) for name in ("total", "available", "page_total",
                    "page_available", "virtual_total", "virtual_available", "extended")]
        status = MemoryStatus(); status.length = ctypes.sizeof(status)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(MemoryStatus)]
        kernel.GlobalMemoryStatusEx.restype = ctypes.c_int
        return status.available if kernel.GlobalMemoryStatusEx(ctypes.byref(status)) else 0
    try:
        return os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    except (ValueError, AttributeError, OSError):
        return 0


def retention_fits(free_bytes, model_bytes):
    # Require the full model size plus 2 GiB headroom even when part of the model
    # is already on CPU. On memory-constrained systems, keep the old unload path.
    return free_bytes >= model_bytes + 2 * 1024**3


def can_retain(model):
    if os.environ.get("CORRIDORKEY2_CPU_MODEL_CACHE", "1") == "0":
        return False
    size = sum(p.numel() * p.element_size() for p in model.parameters())
    size += sum(b.numel() * b.element_size() for b in model.buffers())
    return retention_fits(available_ram(), size)
