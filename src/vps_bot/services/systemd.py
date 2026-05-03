import subprocess
from datetime import datetime


def run_command(command, timeout=60):
    try:
        process = subprocess.run(command, text=True, capture_output=True, timeout=timeout)
        return process.returncode, (process.stdout + process.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, "Команда выполнялась слишком долго."


class SystemdService:
    is_mock = False

    def __init__(self, service_name):
        self.service_name = service_name

    def systemctl(self, action, timeout=60):
        return run_command(["/usr/bin/sudo", "-n", "/usr/bin/systemctl", action, self.service_name], timeout=timeout)

    def is_active(self):
        code, output = self.systemctl("is-active", timeout=10)
        return code == 0, output or "unknown"

    def journal_tail(self):
        code, output = run_command(
            ["/usr/bin/sudo", "-n", "/usr/bin/journalctl", "-u", self.service_name, "-n", "80", "--no-pager"],
            timeout=20,
        )
        return output or "Журнал пуст."

    def show_info(self):
        code, output = run_command(
            ["/usr/bin/systemctl", "show", self.service_name, "-p", "MainPID", "-p", "ActiveEnterTimestamp", "-p", "NRestarts"],
            timeout=10,
        )
        info = {}
        if code == 0:
            for line in output.splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    info[key] = value
        return info


class MockSystemdService:
    is_mock = True

    def __init__(self, service_name):
        self.service_name = service_name
        self.active = False
        self.started_at = None
        self.restarts = 0

    def systemctl(self, action, timeout=60):
        if action in ("start", "restart"):
            self.active = True
            self.started_at = datetime.now()
            if action == "restart":
                self.restarts += 1
        elif action == "stop":
            self.active = False
        elif action != "is-active":
            return 1, "Mock systemd does not support action: {}".format(action)

        return 0, "mock {}".format(action)

    def is_active(self):
        return self.active, "active" if self.active else "inactive"

    def journal_tail(self):
        return "Mock journal: systemd не вызывался."

    def show_info(self):
        if not self.active:
            return {"MainPID": "0", "NRestarts": str(self.restarts)}

        return {
            "MainPID": "4242",
            "ActiveEnterTimestamp": self.started_at.strftime("%Y-%m-%d %H:%M:%S") if self.started_at else "",
            "NRestarts": str(self.restarts),
        }
