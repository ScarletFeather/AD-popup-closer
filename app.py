"""自动识别广告弹窗并点击关闭按钮 —— 主程序（Flask Web UI + 检测线程）。"""
import ctypes
import json
import os
import subprocess
import sys
import threading
import time

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from flask import Flask, Response, jsonify, render_template, request

from config import BASE_DIR, DEFAULTS
from detector import Detector
from screen_capture import ScreenCapture
from clicker import click

# Windows 下开启 DPI 感知，保证截图像素坐标与鼠标坐标一致
if sys.platform == "win32":
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

app = Flask(__name__)

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

# ---------------- 全局状态 ----------------
state = {
    "running": False,
    "config": dict(DEFAULTS),
    "last_frame": None,        # BGR，带框预览图
    "last_full": None,         # 原始全分辨率帧（用于捕获模板）
    "stats": {"detected": 0, "clicked": 0, "ad": 0, "collected": 0, "fps": 0.0},
    "log": [],
}
_lock = threading.Lock()
_thread = None
_capture = ScreenCapture(DEFAULTS["monitor"])
_detector = Detector(state["config"])
_last_click = {}  # (cx // 20, cy // 20) -> time
_popup_proc = None  # 模拟广告弹窗子进程


def add_log(msg: str):
    with _lock:
        state["log"].append(f"[{time.strftime('%H:%M:%S')}] {msg}")
        state["log"] = state["log"][-200:]


def _load_config():
    cfg = dict(DEFAULTS)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def _save_config():
    keys = ("confidence", "interval", "click_enabled", "click_cooldown", "model_path",
            "two_stage", "collect_data")
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({k: state["config"][k] for k in keys}, f,
                      ensure_ascii=False, indent=2)
    except Exception as e:
        add_log(f"配置保存失败: {e}")


_FONT_CACHE = {}


def _cjk_font(size: int):
    if size not in _FONT_CACHE:
        font = None
        for path in ("C:/Windows/Fonts/msyh.ttc",
                     "C:/Windows/Fonts/simhei.ttf",
                     "C:/Windows/Fonts/simsun.ttc"):
            if os.path.exists(path):
                try:
                    font = ImageFont.truetype(path, size)
                    break
                except Exception:
                    continue
        _FONT_CACHE[size] = font
    return _FONT_CACHE[size]


def _render_labels(img, labels):
    """用 PIL 绘制中文标签（OpenCV putText 不支持中文，会显示成问号）。"""
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil)
    size = 16
    font = _cjk_font(size)
    for text, x, y, color_bgr in labels:
        rgb = (color_bgr[2], color_bgr[1], color_bgr[0])
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception:
            tw, th = len(text) * size, size + 4
        draw.rectangle([x - 2, y - 2, x + tw + 3, y + th + 2], fill=(20, 22, 26))
        draw.text((x, y), text, font=font, fill=rgb)
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


def draw_boxes(frame, dets):
    out = frame.copy()
    colors = {
        "ad": (90, 170, 255),     # 橙色：广告标识（不可点击）
    }
    labels = []
    for d in dets:
        x, y, w, h = d["x"], d["y"], d["w"], d["h"]
        kind = d.get("kind", "close")
        color = colors.get(kind, (80, 220, 120))  # 默认绿色
        cv2.rectangle(out, (x, y), (x + w, y + h), color, 2)
        if kind == "ad":
            labels.append((f"广告标识: {d['label']}", x, max(2, y - 6), color))
        else:
            cx, cy = x + w // 2, y + h // 2
            cv2.drawMarker(out, (cx, cy), color, cv2.MARKER_CROSS, 14, 2)
            labels.append((f"{d['label']} {d['confidence']:.2f}", x, max(2, y - 6), color))
    if labels:
        out = _render_labels(out, labels)
    return out


def _blank_frame():
    blank = np.zeros((360, 640, 3), dtype=np.uint8)
    cv2.putText(blank, "Click start to capture screen", (90, 190),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2, cv2.LINE_AA)
    return blank


def _ad_regions(badges, cfg):
    mx = int(cfg.get("ad_margin_x", 600))
    my = int(cfg.get("ad_margin_y", 600))
    return [(b["x"] - mx, b["y"] - my, b["x"] + b["w"] + mx, b["y"] + b["h"] + my) for b in badges]


def _in_regions(cx, cy, regions):
    return any(x1 <= cx <= x2 and y1 <= cy <= y2 for x1, y1, x2, y2 in regions)


def _do_click(d, cfg):
    """执行点击（带区域冷却与统计），成功返回 True。"""
    cx = d["x"] + d["w"] // 2
    cy = d["y"] + d["h"] // 2
    key = (cx // 20, cy // 20)
    now = time.time()
    if now - _last_click.get(key, 0) < cfg.get("click_cooldown", 2.0):
        return False
    try:
        click(cx, cy)
        _last_click[key] = now
        with _lock:
            state["stats"]["clicked"] += 1
        add_log(f"点击 {d['label']} @({cx},{cy}) conf={d['confidence']:.2f}")
        return True
    except Exception as e:
        add_log(f"点击失败: {e}")
        return False


_CLASSES = ["ad", "close", "action"]
_KIND_TO_CLS = {"ad": 0, "close": 1, "action": 2}
_last_collect = {}


def _ensure_dataset(cfg):
    d = cfg.get("dataset_dir", os.path.join(BASE_DIR, "dataset"))
    os.makedirs(os.path.join(d, "images"), exist_ok=True)
    os.makedirs(os.path.join(d, "labels"), exist_ok=True)
    cls_path = os.path.join(d, "classes.txt")
    if not os.path.exists(cls_path):
        with open(cls_path, "w", encoding="utf-8") as f:
            f.write("\n".join(_CLASSES))
    return d


def _collect_samples(frame, dets, badges, cfg):
    """识别到广告时，自动截取广告区域并导出 YOLO 格式训练标注。"""
    if not badges:
        return
    d = _ensure_dataset(cfg)
    gh, gw = frame.shape[:2]
    now = time.time()
    mx = int(cfg.get("ad_margin_x", 600))
    my = int(cfg.get("ad_margin_y", 600))
    interval = float(cfg.get("collect_interval", 2.0))
    for b in badges:
        cx = b["x"] + b["w"] // 2
        cy = b["y"] + b["h"] // 2
        x1, y1 = max(0, cx - mx), max(0, cy - my)
        x2, y2 = min(gw, cx + mx), min(gh, cy + my)
        if x2 - x1 < 10 or y2 - y1 < 10:
            continue
        key = (x1 // 120, y1 // 120)
        if now - _last_collect.get(key, 0) < interval:
            continue
        _last_collect[key] = now
        crop = frame[y1:y2, x1:x2]
        w, h = x2 - x1, y2 - y1
        base = f"{time.strftime('%Y%m%d_%H%M%S')}_{int(now * 1000) % 100000}"
        ok, buf = cv2.imencode(".png", crop)
        if not ok:
            continue
        buf.tofile(os.path.join(d, "images", base + ".png"))
        lines = []
        for det in dets:
            kind = det.get("kind", "close")
            cls = _KIND_TO_CLS.get(kind)
            if cls is None:
                continue
            dx = det["x"] + det["w"] / 2
            dy = det["y"] + det["h"] / 2
            if not (x1 <= dx <= x2 and y1 <= dy <= y2):
                continue
            ncx = min(max((dx - x1) / w, 0.0), 1.0)
            ncy = min(max((dy - y1) / h, 0.0), 1.0)
            nbw = min(det["w"] / w, 1.0)
            nbh = min(det["h"] / h, 1.0)
            lines.append(f"{cls} {ncx:.6f} {ncy:.6f} {nbw:.6f} {nbh:.6f}")
        with open(os.path.join(d, "labels", base + ".txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        with _lock:
            state["stats"]["collected"] += 1
        add_log(f"采集训练样本 {base}.png（标注 {len(lines)} 个目标）")


def detection_loop():
    add_log("检测已启动")
    while True:
        with _lock:
            if not state["running"]:
                break
            cfg = dict(state["config"])
        t0 = time.time()
        try:
            frame = _capture.grab()
            dets = _detector.detect(frame)
            badges = [d for d in dets if d.get("kind") == "ad"]
            clickable = [d for d in dets if d.get("kind") != "ad"]

            # 两阶段过滤：先定位广告区域，仅在该区域内点击
            regions = _ad_regions(badges, cfg) if cfg.get("two_stage") else []

            def valid(d, fallback=True):
                if not cfg.get("two_stage"):
                    return True
                if not regions:
                    return fallback
                return _in_regions(d["x"] + d["w"] // 2, d["y"] + d["h"] // 2, regions)

            targets = [d for d in clickable if valid(d)]

            with _lock:
                state["stats"]["detected"] += len(dets)
                state["stats"]["ad"] += len(badges)
                state["last_full"] = frame.copy()
                state["last_frame"] = draw_boxes(frame, dets)

            if cfg.get("collect_data"):
                _collect_samples(frame, dets, badges, cfg)

            if cfg.get("click_enabled"):
                for d in targets:
                    _do_click(d, cfg)

            dt = time.time() - t0
            with _lock:
                state["stats"]["fps"] = round(1.0 / max(dt, 1e-3), 1)
        except Exception as e:
            add_log(f"检测异常: {e}")
        time.sleep(max(0.0, cfg.get("interval", 0.5) - (time.time() - t0)))
    add_log("检测已停止")


# ---------------- 页面 ----------------
@app.route("/")
def index():
    return render_template("index.html")


# ---------------- 流式预览（MJPEG） ----------------
@app.route("/api/stream")
def api_stream():
    def gen():
        while True:
            with _lock:
                frame = state["last_frame"]
            if frame is None:
                frame = _blank_frame()
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                       + buf.tobytes() + b"\r\n")
            time.sleep(0.1)
    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")


# ---------------- API ----------------
@app.route("/api/status")
def api_status():
    with _lock:
        cfg = dict(state["config"])
        full = state["last_full"]
        return jsonify({
            "running": state["running"],
            "config": cfg,
            "stats": state["stats"],
            "log": state["log"][-60:],
            "detector": _detector.status(),
            "frame_size": [int(full.shape[1]), int(full.shape[0])] if full is not None else None,
        })


@app.route("/api/start", methods=["POST"])
def api_start():
    global _thread
    with _lock:
        if state["running"]:
            return jsonify({"ok": True, "msg": "already running"})
        state["running"] = True
    _thread = threading.Thread(target=detection_loop, daemon=True)
    _thread.start()
    return jsonify({"ok": True})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    with _lock:
        state["running"] = False
    return jsonify({"ok": True})


@app.route("/api/popup", methods=["POST"])
def api_popup():
    """拉起独立的模拟广告弹窗进程。"""
    global _popup_proc
    if _popup_proc is not None and _popup_proc.poll() is None:
        return jsonify({"ok": True, "msg": "弹窗已在运行"})
    script = os.path.join(BASE_DIR, "simulate_popup.py")
    try:
        _popup_proc = subprocess.Popen([sys.executable, script], cwd=BASE_DIR)
        add_log("已弹出测试用广告弹窗")
    except Exception as e:
        add_log(f"弹出测试弹窗失败: {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500
    return jsonify({"ok": True})


@app.route("/api/settings", methods=["POST"])
def api_settings():
    data = request.get_json(force=True)
    with _lock:
        cfg = state["config"]
        model_changed = "model_path" in data and data["model_path"] != cfg.get("model_path")
        if "confidence" in data:
            cfg["confidence"] = float(data["confidence"])
        if "interval" in data:
            cfg["interval"] = float(data["interval"])
        if "click_enabled" in data:
            cfg["click_enabled"] = bool(data["click_enabled"])
        if "click_cooldown" in data:
            cfg["click_cooldown"] = float(data["click_cooldown"])
        if "two_stage" in data:
            cfg["two_stage"] = bool(data["two_stage"])
        if "collect_data" in data:
            cfg["collect_data"] = bool(data["collect_data"])
        if "model_path" in data:
            cfg["model_path"] = data["model_path"]
    if model_changed:
        _detector.reload()
    _save_config()
    return jsonify({"ok": True})


@app.route("/api/templates", methods=["GET"])
def api_templates():
    files = []
    d = state["config"].get("template_dir", "")
    if d and os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.lower().endswith((".png", ".jpg", ".jpeg")):
                files.append(f)
    return jsonify({"templates": files})


@app.route("/api/templates/<name>", methods=["DELETE"])
def api_delete_template(name):
    d = state["config"].get("template_dir", "")
    p = os.path.join(d, name)
    if os.path.isfile(p):
        os.remove(p)
        return jsonify({"ok": True})
    return jsonify({"ok": False, "msg": "not found"}), 404


if __name__ == "__main__":
    state["config"] = _load_config()
    _detector.config = state["config"]
    _detector.reload()
    add_log("服务已就绪")
    print("Open http://127.0.0.1:5000 in your browser.")
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
