import os
import shutil
from pathlib import Path


def resources_text():
    cpus = os.cpu_count() or 1
    load = load_average()
    memory = memory_info()
    disk = shutil.disk_usage(disk_path())

    lines = ["<b>Ресурсы системы</b>"]
    if load:
        lines.append("CPU load: <code>{:.2f}, {:.2f}, {:.2f}</code> ({} CPU)".format(load[0], load[1], load[2], cpus))
    else:
        lines.append("CPU: <code>{} CPU</code>, load average недоступен".format(cpus))

    if memory:
        total, available = memory
        used = total - available
        ram_pct = used / total * 100
        lines.append("RAM: <code>{} / {}</code> ({:.0f}%)".format(gb(used), gb(total), ram_pct))
    else:
        lines.append("RAM: <code>недоступно</code>")

    disk_pct = disk.used / disk.total * 100
    lines.append("Disk: <code>{} / {}</code> ({:.0f}%)".format(gb(disk.used), gb(disk.total), disk_pct))

    return "\n".join(lines)


def load_average():
    try:
        return os.getloadavg()
    except (AttributeError, OSError):
        return None


def memory_info():
    if os.name == "nt":
        return windows_memory_info()
    return linux_memory_info()


def linux_memory_info():
    try:
        mem = {}
        with open("/proc/meminfo") as file:
            for line in file:
                key, value = line.split(":", 1)
                mem[key] = int(value.split()[0]) * 1024
        return mem["MemTotal"], mem["MemAvailable"]
    except (OSError, KeyError, ValueError):
        return None


def windows_memory_info():
    try:
        import ctypes

        class MemoryStatusEx(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatusEx()
        status.dwLength = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return int(status.ullTotalPhys), int(status.ullAvailPhys)
    except Exception:
        return None


def disk_path():
    if os.name == "nt":
        return Path.cwd().anchor or os.getcwd()
    return "/"


def gb(value):
    return "{:.1f} GB".format(value / 1024**3)
