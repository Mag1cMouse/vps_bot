import os


class MinecraftLog:
    def __init__(self, path):
        self.path = path

    def exists(self):
        return os.path.exists(self.path)

    def readable(self):
        return os.access(self.path, os.R_OK)

    def size(self):
        try:
            return os.path.getsize(self.path)
        except OSError:
            return 0

    def read_from(self, offset):
        try:
            size = os.path.getsize(self.path)
            if offset > size:
                offset = 0
            with open(self.path, "rb") as file:
                file.seek(offset)
                return file.read().decode("utf-8", errors="replace")
        except OSError:
            return None

    def tail(self, limit=220_000):
        try:
            size = os.path.getsize(self.path)
            with open(self.path, "rb") as file:
                file.seek(max(0, size - limit))
                return file.read().decode("utf-8", errors="replace")
        except OSError:
            return None


def ready_line(text):
    if not text:
        return None

    for line in reversed(text.splitlines()):
        if "Done (" in line and 'For help, type "help"' in line:
            return line
    return None
