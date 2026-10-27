"""屏幕捕获模块：基于 mss，返回 BGR 格式的 numpy 图像。"""
import mss
import numpy as np


class ScreenCapture:
    def __init__(self, monitor_index: int = 0):
        self.sct = mss.mss()
        monitors = self.sct.monitors
        # monitors[0] 为“所有屏幕”，monitors[1] 为主屏
        idx = monitor_index + 1
        if idx < len(monitors):
            self.monitor = monitors[idx]
        else:
            self.monitor = monitors[1]

    def grab(self) -> np.ndarray:
        """截取屏幕，返回 BGR 三通道图像（numpy array）。"""
        shot = self.sct.grab(self.monitor)
        img = np.asarray(shot)  # BGRA
        return img[:, :, :3].copy()  # BGR

    def region_size(self):
        return self.monitor["width"], self.monitor["height"]
