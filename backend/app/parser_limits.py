"""Resource limits for dedicated parser children, never the API process."""
import os

_job_handle = None


def constrain(memory_mb=512, cpu_seconds=45):
    memory = memory_mb * 1024 * 1024
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes as w

        class Basic(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                        ("flags", w.DWORD), ("min_working", ctypes.c_size_t), ("max_working", ctypes.c_size_t),
                        ("process_count", w.DWORD), ("affinity", ctypes.c_size_t), ("priority", w.DWORD), ("scheduling", w.DWORD)]

        class Extended(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", ctypes.c_ulonglong * 6),
                        ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                        ("peak_process", ctypes.c_size_t), ("peak_job", ctypes.c_size_t)]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.argtypes, kernel.CreateJobObjectW.restype = [ctypes.c_void_p, w.LPCWSTR], w.HANDLE
        kernel.SetInformationJobObject.argtypes, kernel.SetInformationJobObject.restype = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD], w.BOOL
        kernel.AssignProcessToJobObject.argtypes, kernel.AssignProcessToJobObject.restype = [w.HANDLE, w.HANDLE], w.BOOL
        kernel.GetCurrentProcess.restype = w.HANDLE
        handle = kernel.CreateJobObjectW(None, None)
        information = Extended()
        information.basic.flags = 0x100 | 0x2  # PROCESS_MEMORY and PROCESS_TIME
        information.basic.process_time = cpu_seconds * 10_000_000
        information.process_memory = memory
        if (not handle or not kernel.SetInformationJobObject(handle, 9, ctypes.byref(information), ctypes.sizeof(information))
                or not kernel.AssignProcessToJobObject(handle, kernel.GetCurrentProcess())):
            raise RuntimeError("Parser resource limits could not be established")
        global _job_handle
        _job_handle = handle  # Keep the dedicated child job alive until process exit.
        mechanism = "WINDOWS_JOB_OBJECT"
    else:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
        mechanism = "POSIX_RLIMIT"
    return {"mechanism": mechanism, "memory_bytes": memory, "cpu_seconds": cpu_seconds}
