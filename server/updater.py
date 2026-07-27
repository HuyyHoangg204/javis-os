#!/usr/bin/env python
"""Updater tách rời của Javis cho bản GIT checkout (Windows + Linux systemd + Mac/nohup).
Server spawn DETACHED:

    python updater.py --old-sha <sha> --old-version <v> --target <v> --port <p> --server-pid <pid>

Chuỗi: stop server -> git pull (stash nếu cây bẩn) -> pip install -> start -> chờ /health ~90s.
/health không lên → git reset --hard <old-sha> -> pip -> start (rollback tự động).
3 chế độ restart (service_mode): windows (bat/vbs), systemd (systemctl), nohup (Mac hoặc
Linux không systemd: kill PID server cũ rồi tự chạy lại uvicorn nền như install.sh).
Chỉ dùng stdlib (chạy được cả khi bản mới hỏng dependency)."""
import argparse
import datetime
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))
import update_state as us  # noqa: E402


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(us.STATE_DIR / "update.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def run(cmd):
    log("$ " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode != 0:
        log(f"  (rc={r.returncode}) " + (r.stderr or r.stdout or "").strip()[:500])
    return r


def venv_python():
    p = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return str(p) if p.exists() else sys.executable


def has_systemd():
    try:
        r = subprocess.run(["systemctl", "list-unit-files"], capture_output=True, text=True)
        return r.returncode == 0 and "javis.service" in (r.stdout or "")
    except Exception:
        return False


def service_mode(osname=None, systemd=None):
    """windows | systemd | nohup - cách stop/start server theo nền tảng. Mac không có
    systemctl (và Linux cài không systemd) chạy kiểu nohup: kill PID + tự chạy lại uvicorn."""
    osname = osname or os.name
    if osname == "nt":
        return "windows"
    if systemd is None:
        systemd = has_systemd()
    return "systemd" if systemd else "nohup"


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _kill_pid(pid, timeout_s=15):
    import signal
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if not _pid_alive(pid):
            return
        time.sleep(0.5)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass


def _pids_on_port(port):
    """PID đang giữ cổng (lsof có sẵn trên Mac lẫn đa số Linux). Fallback khi thiếu --server-pid."""
    try:
        r = subprocess.run(["lsof", "-ti", f"tcp:{port}"], capture_output=True, text=True)
        return [int(x) for x in (r.stdout or "").split() if x.strip().isdigit()]
    except Exception:
        return []


def stop_server(mode, server_pid=0, port=""):
    if mode == "windows":
        run(["cmd", "/c", str(ROOT / "stop-javis.bat")])
    elif mode == "systemd":
        subprocess.run(["systemctl", "stop", "javis"], capture_output=True, text=True)
    else:  # nohup: kill đúng PID server (mình là session riêng nên không chết theo)
        pids = [server_pid] if server_pid else []
        pids += [p for p in _pids_on_port(port) if p not in pids and p != os.getpid()]
        if not pids:
            log("Không tìm thấy tiến trình server để dừng (có thể đã tắt).")
        for p in pids:
            log(f"Dừng PID {p}…")
            _kill_pid(p)


def start_server(mode, port=""):
    if mode == "windows":
        subprocess.Popen(["wscript.exe", "//nologo", str(ROOT / "start-javis.vbs")],
                         cwd=str(ROOT), creationflags=0x00000008)  # DETACHED_PROCESS
    elif mode == "systemd":
        subprocess.run(["systemctl", "start", "javis"], capture_output=True, text=True)
    else:  # nohup: chạy lại uvicorn nền y như install.sh (fallback không systemd)
        host = os.getenv("JAVIS_HOST", "127.0.0.1")
        logf = open(us.STATE_DIR / "javis.log", "a", encoding="utf-8")
        subprocess.Popen(
            [venv_python(), "-m", "uvicorn", "main:app", "--host", host, "--port", str(port or "7777")],
            cwd=str(ROOT / "server"), stdout=logf, stderr=subprocess.STDOUT,
            start_new_session=True,
            env={**os.environ, "JAVIS_STATE_DIR": os.getenv("JAVIS_STATE_DIR", str(us.STATE_DIR))})


def git_dirty():
    r = run(["git", "status", "--porcelain", "--untracked-files=no"])
    return bool((r.stdout or "").strip())


def pip_install():
    return run([venv_python(), "-m", "pip", "install", "-r", "requirements.txt", "-q"])


def read_current_version():
    try:
        return (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except Exception:
        return "0.0.0"


def poll_health(port, timeout_s=90):
    url = f"http://127.0.0.1:{port}/health"
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=4) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(3)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old-sha", default="")
    ap.add_argument("--old-version", default="")
    ap.add_argument("--target", default="")
    ap.add_argument("--port", default=os.getenv("JAVIS_PORT", "7777"))
    ap.add_argument("--server-pid", type=int, default=0,
                    help="PID server đang chạy (để chế độ nohup kill đúng tiến trình)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.dry_run:
        print(f"PLAN: stop -> pull(stash nếu bẩn) -> pip -> start -> health({a.port}) "
              f"-> rollback(reset {a.old_sha or '?'}) nếu không lên")
        return 0

    target = a.target or None
    us.write_state({"phase": "preparing", "started_at": _now(), "finished_at": None,
                    "result": None, "error": None, "old_sha": a.old_sha,
                    "old_version": a.old_version, "target_version": target, "stashed": False})

    mode = service_mode()
    log(f"Chế độ restart: {mode}")

    log("Dừng server cũ…")
    stop_server(mode, a.server_pid, a.port)
    time.sleep(2)

    us.write_state({"phase": "pulling"})
    if git_dirty():
        log("Cây git có sửa đổi cục bộ → git stash (giữ lại, không mất).")
        run(["git", "stash"])
        us.write_state({"stashed": True})
    pull = run(["git", "pull", "--ff-only"])
    if pull.returncode != 0:
        log("git pull LỖI:\n" + (pull.stderr or pull.stdout or ""))
        start_server(mode, a.port)
        us.write_state({"phase": "error", "result": "pull_failed",
                        "error": (pull.stderr or "git pull thất bại")[:500], "finished_at": _now()})
        return 1

    us.write_state({"phase": "installing"})
    log("Cài thư viện…")
    pip_install()

    us.write_state({"phase": "restarting"})
    log("Khởi động bản mới…")
    start_server(mode, a.port)

    us.write_state({"phase": "health_check"})
    log("Kiểm tra sức khoẻ…")
    healthy = poll_health(a.port, 90)
    current = read_current_version()
    outcome = us.update_outcome(healthy, current, a.old_version, target)
    log(f"health={healthy} current={current} → {outcome}")

    if outcome == "success":
        us.record_boot_version(current)
        us.write_state({"phase": "done", "result": "success", "finished_at": _now()})
        return 0
    if outcome == "version_mismatch":
        us.write_state({"phase": "done", "result": "error",
                        "error": "Server lên nhưng phiên bản chưa đổi (pull chưa áp?). Xem update.log.",
                        "finished_at": _now()})
        return 1

    # need_rollback
    log("Bản mới KHÔNG lên được → tự lùi về bản cũ…")
    us.write_state({"phase": "rolling_back"})
    if not a.old_sha:
        us.write_state({"phase": "error", "result": "rollback_failed",
                        "error": "Không có commit cũ để lùi.", "finished_at": _now()})
        return 1
    run(["git", "reset", "--hard", a.old_sha])
    pip_install()
    # Bản mới có thể đang chạy dở (lên tiến trình nhưng /health đỏ) → dừng hẳn trước khi
    # bật bản cũ, kẻo nohup bind trùng cổng. Windows/systemd dừng lại cũng vô hại.
    stop_server(mode, 0, a.port)
    time.sleep(2)
    start_server(mode, a.port)
    if poll_health(a.port, 90):
        us.write_state({"phase": "done", "result": "rolled_back",
                        "error": "Bản mới lỗi, đã tự quay về bản cũ.", "finished_at": _now()})
        return 0
    us.write_state({"phase": "error", "result": "rollback_failed",
                    "error": "Bản mới lỗi và lùi bản cũng chưa lên. Xem update.log.", "finished_at": _now()})
    return 1


if __name__ == "__main__":
    sys.exit(main())
