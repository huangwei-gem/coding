#!/usr/bin/env python3
"""Agnes AI 创作工坊 - 一键启动脚本"""

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
    except Exception as e:
        return f""


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

    # ── 2. 检查依赖 ──
    print_step(2, "Check dependencies")

    deps = {"flask": "flask", "requests": "requests"}
    for mod, pkg in deps.items():
        try:
            __import__(mod)
            print_ok(f"{pkg} ready")
        except ImportError:
            print_info(f"Installing {pkg} ...")
            rc = subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg, "-q"],
                capture_output=True
            ).returncode
            if rc != 0:
                print_err(f"Install failed: {pkg}")
                input("\nPress Enter to exit ...")
                sys.exit(1)
            print_ok(f"{pkg} installed")

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

    os.chdir(AI_CANVAS_DIR)
    env = os.environ.copy()
    if api_key:
        env["AGNES_API_KEY"] = api_key

    with open(LOG_FILE, "w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            [sys.executable, "app.py"],
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
