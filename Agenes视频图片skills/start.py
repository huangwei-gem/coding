#!/usr/bin/env python3
"""Agnes AI 创作工坊 - 一键启动脚本（使用项目虚拟环境）"""

import os
import sys
import subprocess
import time
import socket
import webbrowser

# 解决 Windows 控制台 GBK 编码问题
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        os.system("chcp 65001 >nul")

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_CANVAS_DIR = os.path.join(PROJECT_DIR, "ai-canvas")
VENV_DIR = os.path.join(PROJECT_DIR, "venv")
LOG_FILE = os.path.join(os.environ.get("TEMP", "."), "agnes_web.log")


# ─── 输出 ───
def print_step(n, msg):   print(f"\n[{n}/5] {msg}")
def print_ok(msg):        print(f"  [OK] {msg}")
def print_info(msg):      print(f"  ... {msg}")
def print_err(msg):       print(f"  [!!] {msg}")


def run_raw(cmd):
    """运行命令，返回 stdout 字符串（自动处理 GBK/UTF-8）"""
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=10)
        out = r.stdout
        if out:
            try:
                return out.decode("utf-8")
            except UnicodeDecodeError:
                return out.decode("gbk", errors="replace")
        return ""
    except Exception:
        return ""


def port_in_use(port, host="127.0.0.1"):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def kill_port(port, host="127.0.0.1"):
    out = run_raw(["netstat", "-ano"])
    for line in out.splitlines():
        if f"{host}:{port}" in line and "LISTENING" in line:
            parts = line.strip().split()
            if parts:
                pid = parts[-1]
                subprocess.run(["taskkill", "/F", "/PID", pid],
                               capture_output=True)


def read_tail(path, n=5):
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            return "".join(lines[-n:])
    except Exception:
        return "(cannot read log)"


def venv_python():
    """Return the path to the venv's Python interpreter, or None."""
    if sys.platform == "win32":
        py = os.path.join(VENV_DIR, "Scripts", "python.exe")
    else:
        py = os.path.join(VENV_DIR, "bin", "python")
    return py if os.path.exists(py) else None


def ensure_venv():
    """Create venv + install requirements if not already done.
    Falls back to system Python if venv fails."""
    # Check if existing venv has flask
    py_exe = venv_python()
    if py_exe:
        check = subprocess.run([py_exe, "-c", "import flask"], capture_output=True)
        if check.returncode == 0:
            print_ok("Virtual environment ready")
            return True
        print_info("Venv exists but missing packages, recreating ...")
        subprocess.run(["rm", "-rf", VENV_DIR] if sys.platform != "win32" else ["cmd", "/c", f"rmdir /s /q \"{VENV_DIR}\""],
                       capture_output=True)

    print_info("Creating virtual environment (with system packages) ...")
    rc = subprocess.run(
        [sys.executable, "-m", "venv", "--system-site-packages", VENV_DIR],
        capture_output=True
    )
    if rc.returncode != 0:
        err = rc.stderr.decode("gbk", errors="replace") if rc.stderr else ""
        print_err(f"Failed to create venv: {err.strip()}")
        return False

    # Try to pip install requirements (optional, system packages may be enough)
    if sys.platform == "win32":
        pip_exe = os.path.join(VENV_DIR, "Scripts", "pip.exe")
    else:
        pip_exe = os.path.join(VENV_DIR, "bin", "pip")
    req_file = os.path.join(PROJECT_DIR, "requirements.txt")
    if os.path.exists(pip_exe) and os.path.exists(req_file):
        print_info("Installing dependencies ...")
        rc2 = subprocess.run(
            [pip_exe, "install", "-r", req_file, "-q"],
            capture_output=True
        )
        if rc2.returncode == 0:
            print_ok("Dependencies installed")
        else:
            print_info("pip install skipped (using system packages)")

    py_exe = venv_python()
    if py_exe:
        check = subprocess.run([py_exe, "-c", "import flask"], capture_output=True)
        if check.returncode == 0:
            print_ok("Virtual environment ready")
            return True

    print_err("Venv created but flask not available")
    return False


def main():
    print("=" * 47)
    print("  Agnes AI -- chuang zuo gong fang")
    print("=" * 47)

    # ── 1. 检查 Python ──
    print_step(1, "Check Python")
    if sys.version_info < (3, 8):
        print_err(f"Python too old: {sys.version}")
        print_info("Download: https://www.python.org/downloads/")
        input("\nPress Enter to exit ...")
        sys.exit(1)
    print_ok(f"Python {sys.version.split()[0]}")

    # ── 2. 虚拟环境 ──
    print_step(2, "Virtual environment")
    venv_ok = ensure_venv()

    # ── 3. 检查 API Key ──
    print_step(3, "Check API key")
    api_key = os.environ.get("AGNES_API_KEY", "")
    if not api_key:
        print_info("AGNES_API_KEY not set")
        key = input("\nEnter your Agnes API Key (or press Enter to skip): ").strip()
        if key:
            os.environ["AGNES_API_KEY"] = key
            api_key = key
            print_ok("API Key set (session only)")
        else:
            print_info("Skip -- API calls will fail")
    else:
        print_ok("AGNES_API_KEY is set")

    # ── 4. 启动 Web 服务 ──
    print_step(4, "Start server")
    if not os.path.isdir(AI_CANVAS_DIR):
        print_err(f"Directory not found: ai-canvas")
        input("\nPress Enter to exit ...")
        sys.exit(1)

    if port_in_use(5000):
        print_info("Port 5000 busy, cleaning ...")
        kill_port(5000)
        time.sleep(1)

    # 选择 Python
    py_exe = venv_python() if venv_ok else sys.executable
    print_info(f"Using: {py_exe}")

    os.chdir(AI_CANVAS_DIR)
    env = os.environ.copy()
    if api_key:
        env["AGNES_API_KEY"] = api_key

    with open(LOG_FILE, "w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            [py_exe, "app.py"],
            stdout=log, stderr=subprocess.STDOUT,
            env=env, cwd=AI_CANVAS_DIR
        )

    print_info("Waiting for server ...")
    for i in range(20):
        time.sleep(1)
        if port_in_use(5000):
            print_ok(f"Ready ({i+1}s)")
            break
    else:
        print_err("Server startup timeout")
        print_info("Last log lines:")
        print(f"  {read_tail(LOG_FILE).strip()}")
        print_info(f"Full log: {LOG_FILE}")
        input("\nPress Enter to exit ...")
        proc.terminate()
        sys.exit(1)

    # ── 5. 打开浏览器 ──
    print_step(5, "Open browser")
    webbrowser.open("http://127.0.0.1:5000")
    print_ok("Browser opened")

    print(f"""
{'=' * 47}
  Agnes AI is running
{'=' * 47}

  URL:   http://127.0.0.1:5000
  Log:   {LOG_FILE}

  Press Enter to stop server and exit
{'=' * 47}
""")
    input()

    print("\nStopping server ...")
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        pass
    kill_port(5000)
    print("Stopped. Closing in 3s ...")
    time.sleep(3)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted, exiting ...")
        time.sleep(1)
