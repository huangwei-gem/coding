"""BOSS 直聘自动化助手 - Web UI 入口"""
import threading
import time
import json
import atexit
from pathlib import Path

from flask import Flask, render_template, jsonify, request

from config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG, DASHBOARD_DIR, LOG_FILE
from core.browser import BrowserManager
from core.automation import AutomationEngine

# ------------------------------------------------------------
# Flask app
# ------------------------------------------------------------
app = Flask(__name__)

# ------------------------------------------------------------
# Global state
# ------------------------------------------------------------
browser_mgr = BrowserManager()
engine: AutomationEngine | None = None
_engine_lock = threading.Lock()
_automation_thread: threading.Thread | None = None

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _safe_read_logs() -> list[str]:
    try:
        if LOG_FILE.exists():
            return LOG_FILE.read_text(encoding="utf-8").strip().split("\n")
        return []
    except Exception:
        return []

def _get_engine():
    global engine
    if engine is None and browser_mgr.page:
        engine = AutomationEngine(browser_mgr.page)
    return engine

# ------------------------------------------------------------
# Routes
# ------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html", dashboard_dir=DASHBOARD_DIR)

@app.route("/api/status")
def api_status():
    """获取浏览器/登录/自动化运行状态"""
    info = browser_mgr.get_cookie_info() if browser_mgr.page else {}

    running = False
    with _engine_lock:
        if engine:
            running = engine.is_running

    cities = [{"name": k, "code": v} for k, v in browser_mgr.city_dict.items()]

    return jsonify({
        "browser_connected": browser_mgr.page is not None,
        "logged_in": browser_mgr.is_logged_in,
        "automation_running": running,
        "cookie_count": info.get("cookie_count", 0),
        "cookie_info": info,
        "cities": cities,
    })

@app.route("/api/connect", methods=["POST"])
def api_connect():
    """启动浏览器并尝试恢复登录（源文件 4-37行流程）"""
    try:
        page = browser_mgr.start()
        info = browser_mgr.get_cookie_info()
        return jsonify({
            "success": True,
            "logged_in": browser_mgr.is_logged_in,
            "cookie_count": info.get("cookie_count", 0),
            "cities": [{"name": k, "code": v} for k, v in browser_mgr.city_dict.items()],
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/check-login", methods=["POST"])
def api_check_login():
    """用户确认登录 → 保存cookie → 刷新 → 获取城市（源文件 22-56行流程）"""
    try:
        if browser_mgr.confirm_login_and_fetch_cities():
            info = browser_mgr.get_cookie_info()
            return jsonify({
                "logged_in": True,
                "cookie_count": info.get("cookie_count", 0),
                "cities": [{"name": k, "code": v} for k, v in browser_mgr.city_dict.items()],
            })
        return jsonify({"logged_in": False})
    except Exception as e:
        return jsonify({"logged_in": False, "error": str(e)})

@app.route("/api/logout", methods=["POST"])
def api_logout():
    """清除 Cookie"""
    try:
        browser_mgr.logout()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/cities", methods=["POST"])
def api_cities():
    """获取已缓存的城市列表"""
    # 自动化运行期间禁止切换页面
    with _engine_lock:
        if engine and engine.is_running:
            return jsonify({"success": False, "error": "自动化正在运行"}), 400
    return jsonify({
        "success": True,
        "cities": [{"name": k, "code": v} for k, v in browser_mgr.city_dict.items()],
    })

@app.route("/api/start-automation", methods=["POST"])
def api_start_automation():
    """在后台线程启动自动化"""
    global _automation_thread

    if not browser_mgr.page or not browser_mgr.is_logged_in:
        return jsonify({"success": False, "error": "浏览器未连接或未登录"}), 400

    if not browser_mgr.city_dict:
        return jsonify({"success": False, "error": "城市数据未加载，请重新登录"}), 400

    with _engine_lock:
        eng = _get_engine()
        if eng and eng.is_running:
            return jsonify({"success": False, "error": "自动化已在运行中"}), 400

    data = request.get_json() or {}
    keywords = data.get("job_keywords", ["数据分析"])
    cfg = {
        "job_keywords": keywords if isinstance(keywords, list) else [keywords],
        "city": data.get("city", "上海"),
        "message": data.get("message", ""),
        "scroll_times": int(data.get("scroll_times", 5)),
        "send_images": data.get("send_images", True),
    }

    if not cfg["message"]:
        cfg["message"] = config.DEFAULT_MESSAGE

    image_dir = str(DASHBOARD_DIR) if cfg["send_images"] and DASHBOARD_DIR.exists() else None

    def _run():
        with _engine_lock:
            eng = _get_engine()
            if eng:
                eng.run(
                    city_dict=browser_mgr.city_dict,
                    job_keywords=cfg["job_keywords"],
                    city=cfg["city"],
                    message=cfg["message"],
                    image_dir=image_dir,
                    scroll_times=cfg["scroll_times"],
                )

    _automation_thread = threading.Thread(target=_run, daemon=True)
    _automation_thread.start()

    return jsonify({"success": True, "config": cfg})

@app.route("/api/stop-automation", methods=["POST"])
def api_stop_automation():
    with _engine_lock:
        if engine:
            engine.stop()
    return jsonify({"success": True})

@app.route("/api/restart", methods=["POST"])
def api_restart():
    """完全重启：停止自动化 → 关闭浏览器 → 重新启动浏览器"""
    global engine, _automation_thread
    try:
        # 1. 停止自动化
        with _engine_lock:
            if engine:
                engine.stop()
                time.sleep(1)
                engine = None
        # 2. 关闭浏览器
        browser_mgr.quit()
        # 3. 重新启动浏览器
        page = browser_mgr.start()
        info = browser_mgr.get_cookie_info()
        return jsonify({
            "success": True,
            "logged_in": browser_mgr.is_logged_in,
            "cookie_count": info.get("cookie_count", 0),
            "cities": [{"name": k, "code": v} for k, v in browser_mgr.city_dict.items()],
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/logs")
def api_logs():
    lines = _safe_read_logs()
    return jsonify({"logs": lines})

# ------------------------------------------------------------
# Cleanup
# ------------------------------------------------------------
def _cleanup():
    if browser_mgr:
        try:
            if engine:
                engine.stop()
            browser_mgr.quit()
        except Exception:
            pass

atexit.register(_cleanup)

# ------------------------------------------------------------
# Entry
# ------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 50)
    print("  BOSS 直聘 自动化助手 v2.0")
    print(f"  打开浏览器访问: http://{FLASK_HOST}:{FLASK_PORT}")
    print("=" * 50)
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG, use_reloader=False)
