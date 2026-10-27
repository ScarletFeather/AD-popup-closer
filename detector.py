"""检测模块：三通道融合 —— YOLO + 模板匹配 + OCR。

- YOLO：加载 ultralytics 的 .pt 模型，命中「关闭」类关键词的框视为关闭按钮。
- 模板匹配：对 templates/ 目录下的“×”模板做多尺度 matchTemplate。
- OCR：用 RapidOCR 识别文字：
        「广告/推广」→ 广告标识（kind=ad，不可点击，用于两阶段定位与数据采集）；
        「跳过/关闭/取消」→ 动作按钮（kind=action，可点击）。

性能优化：
- 模板灰度图与多尺度版本按 mtime 缓存，避免每帧重复读图/缩放。
- 大分辨率屏幕先等比降采样到 1280 宽再匹配/识别，坐标再映射回原分辨率。
"""
import glob
import os
import time

import cv2
import numpy as np

# 模板匹配 / OCR 时搜索图的最大宽度（超过则降采样提速）
MAX_SEARCH_W = 1280
# 模板多尺度缩放系数
SCALES = (0.5, 0.7, 1.0, 1.3, 1.6)


class Detector:
    def __init__(self, config: dict):
        self.config = config
        self.model = None
        self.yolo_available = False
        self.ocr = None
        self.ocr_available = False
        self._close_labels = {str(x).lower() for x in config.get("close_labels", [])}
        self._ad_keywords = list(config.get("ad_keywords", ["广告"]))
        self._action_keywords = list(config.get("action_keywords", ["跳过", "关闭"]))
        self._last_ocr_time = 0.0
        self._ocr_cache = ([], [])  # (ad_dets, action_dets)
        self._tpl_cache = {}  # path -> ((mtime, size), (name, [(w, h, gray), ...]))
        self._try_load_yolo()
        self._try_load_ocr()

    def reload(self):
        """配置变化后重新加载关键词与模型。"""
        self._close_labels = {str(x).lower() for x in self.config.get("close_labels", [])}
        self._ad_keywords = list(self.config.get("ad_keywords", ["广告"]))
        self._action_keywords = list(self.config.get("action_keywords", ["跳过", "关闭"]))
        self._try_load_yolo()

    # ---------------- YOLO ----------------
    def _try_load_yolo(self):
        path = self.config.get("model_path")
        if not path or not os.path.exists(path):
            self.model = None
            self.yolo_available = False
            return
        try:
            from ultralytics import YOLO
            self.model = YOLO(path)
            self.yolo_available = True
            print(f"[detector] YOLO 模型已加载: {path}")
        except Exception as e:  # 缺失依赖或模型损坏时静默回退
            print(f"[detector] YOLO 加载失败，回退到模板匹配: {e}")
            self.model = None
            self.yolo_available = False

    def _yolo_detect(self, frame):
        dets = []
        if not self.yolo_available or self.model is None:
            return dets
        close_labels = self._close_labels
        conf = float(self.config.get("confidence", 0.5))
        results = self.model(frame, conf=conf, verbose=False)
        for r in results:
            names = r.names
            for box in r.boxes:
                cls = int(box.cls[0])
                name = str(names[cls])
                score = float(box.conf[0])
                low = name.lower()
                if low in close_labels or "close" in low or "关闭" in low:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    dets.append({
                        "x": int(x1), "y": int(y1),
                        "w": int(x2 - x1), "h": int(y2 - y1),
                        "confidence": score, "label": name, "source": "yolo",
                    })
        return dets

    # ---------------- OCR ----------------
    def _try_load_ocr(self):
        if not self.config.get("ocr_enabled", True):
            self.ocr = None
            self.ocr_available = False
            return
        try:
            from rapidocr_onnxruntime import RapidOCR
            self.ocr = RapidOCR()
            self.ocr_available = True
            print("[detector] OCR (RapidOCR) 已加载")
        except Exception as e:
            print(f"[detector] OCR 加载失败，跳过文字识别: {e}")
            self.ocr = None
            self.ocr_available = False

    def _ocr_detect(self, frame):
        """返回 (ad_dets, action_dets)。带节流：ocr_interval 秒内复用缓存。"""
        ad_dets, action_dets = [], []
        if not self.ocr_available or self.ocr is None:
            return ad_dets, action_dets
        now = time.time()
        if now - self._last_ocr_time < float(self.config.get("ocr_interval", 0.5)):
            return self._ocr_cache
        self._last_ocr_time = now
        gh, gw = frame.shape[:2]
        f = 1.0
        img = frame
        if gw > MAX_SEARCH_W:
            f = MAX_SEARCH_W / gw
            img = cv2.resize(frame, (MAX_SEARCH_W, max(1, int(gh * f))))
        try:
            result, _ = self.ocr(img)
        except Exception as e:
            print(f"[detector] OCR 推理失败: {e}")
            return ad_dets, action_dets
        if not result:
            self._ocr_cache = (ad_dets, action_dets)
            return ad_dets, action_dets
        inv = 1.0 / f
        for line in result:
            box, text, score = line
            text = str(text).strip()
            if not text:
                continue
            xs = [float(p[0]) for p in box]
            ys = [float(p[1]) for p in box]
            x = int(min(xs) * inv)
            y = int(min(ys) * inv)
            w = int((max(xs) - min(xs)) * inv)
            h = int((max(ys) - min(ys)) * inv)
            det = {"x": x, "y": y, "w": w, "h": h,
                   "confidence": float(score), "label": text, "source": "ocr"}
            if any(k in text for k in self._action_keywords):
                det["clickable"] = True
                det["kind"] = "action"
                action_dets.append(det)
            elif any(k in text for k in self._ad_keywords):
                det["clickable"] = False
                det["kind"] = "ad"
                ad_dets.append(det)
        self._ocr_cache = (ad_dets, action_dets)
        return ad_dets, action_dets

    # ---------------- 模板匹配 ----------------
    def _template_paths(self):
        d = self.config.get("template_dir", "")
        if not d:
            return []
        return sorted(
            glob.glob(os.path.join(d, "*.png"))
            + glob.glob(os.path.join(d, "*.jpg"))
            + glob.glob(os.path.join(d, "*.jpeg"))
        )

    def _load_templates(self):
        """返回 [(name, [(w, h, gray), ...]), ...]，带缓存与失效检测。"""
        result = []
        for p in self._template_paths():
            try:
                sig = (os.path.getmtime(p), os.path.getsize(p))
            except OSError:
                continue
            cached = self._tpl_cache.get(p)
            if cached and cached[0] == sig:
                result.append(cached[1])
                continue
            # cv2.imread 不支持含中文的路径，改用 np.fromfile + imdecode
            tpl = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
            if tpl is None:
                continue
            th, tw = tpl.shape[:2]
            name = os.path.basename(p)
            scaled = []
            for s in SCALES:
                w, h = max(2, int(tw * s)), max(2, int(th * s))
                scaled.append((w, h, cv2.resize(tpl, (w, h))))
            self._tpl_cache[p] = (sig, (name, scaled))
            result.append((name, scaled))
        for p in list(self._tpl_cache):
            if not os.path.exists(p):
                del self._tpl_cache[p]
        return result

    def _template_detect(self, frame):
        dets = []
        threshold = float(self.config.get("confidence", 0.7))
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gh, gw = gray.shape[:2]
        f = 1.0
        if gw > MAX_SEARCH_W:
            f = MAX_SEARCH_W / gw
            gray = cv2.resize(gray, (MAX_SEARCH_W, max(1, int(gh * f))))
            gh, gw = gray.shape[:2]
        inv = 1.0 / f
        for name, scaled in self._load_templates():
            for w, h, tpl in scaled:
                ew, eh = max(2, int(w * f)), max(2, int(h * f))
                if ew > gw or eh > gh:
                    continue
                t = cv2.resize(tpl, (ew, eh)) if (ew, eh) != (w, h) else tpl
                res = cv2.matchTemplate(gray, t, cv2.TM_CCOEFF_NORMED)
                ys, xs = np.where(res >= threshold)
                for y, x in zip(ys, xs):
                    dets.append({
                        "x": int(x * inv), "y": int(y * inv),
                        "w": int(w), "h": int(h),
                        "confidence": float(res[y, x]),
                        "label": name, "source": "template",
                        "clickable": True, "kind": "close",
                    })
        return dets

    # ---------------- 统一检测 ----------------
    def detect(self, frame):
        """返回检测框列表（kind: close/action/ad），可点击与广告标识分开做 NMS。"""
        ad_dets, action_dets = self._ocr_detect(frame)
        yolo = self._yolo_detect(frame)
        tpl = self._template_detect(frame)
        for d in yolo:
            d["clickable"] = True
            d["kind"] = "close"
        clickable = self._nms(yolo + tpl + action_dets)
        badges = self._nms(ad_dets)
        return clickable + badges

    def _nms(self, dets, iou_threshold: float = 0.3):
        if not dets:
            return []
        boxes = np.array(
            [[d["x"], d["y"], d["x"] + d["w"], d["y"] + d["h"]] for d in dets],
            dtype=np.float32,
        )
        scores = np.array([d["confidence"] for d in dets], dtype=np.float32)
        keep = cv2.dnn.NMSBoxes(
            boxes.tolist(), scores.tolist(), score_threshold=0.0, nms_threshold=iou_threshold
        )
        if len(keep) == 0:
            return []
        out = [dets[int(i)] for i in np.atleast_1d(keep).flatten()]
        out.sort(key=lambda d: d["confidence"], reverse=True)
        return out

    def status(self):
        return {
            "yolo": self.yolo_available,
            "templates": len(self._template_paths()),
            "ocr": self.ocr_available,
        }
