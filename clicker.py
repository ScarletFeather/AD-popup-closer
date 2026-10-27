"""鼠标点击模块。"""
import pyautogui

# 点击间加入短暂停顿，并启用“把鼠标甩到左上角即中止”的失效保护
pyautogui.PAUSE = 0.05
pyautogui.FAILSAFE = True


def click(x: int, y: int) -> None:
    """在屏幕坐标 (x, y) 处单击一次。"""
    pyautogui.click(int(x), int(y))
