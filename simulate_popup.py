"""模拟广告弹窗，用于测试自动关闭效果。

运行本脚本会在屏幕上弹出一个模拟广告窗口（含“广告”标识、“×”关闭按钮和“跳过广告”按钮），
并自动生成“×”模板 templates/close_x.png（与弹窗内图标像素一致），
配合主程序（app.py）验证自动识别与点击。

用法：
1. 运行 python app.py，打开 http://127.0.0.1:5000 ，点“开始检测”，打开“自动点击”。
2. 运行 python simulate_popup.py 弹出模拟广告。
3. 观察系统是否自动点掉“×”或“跳过广告”。
"""
import os
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TPL_DIR = os.path.join(BASE_DIR, "templates")


def make_x_icon(size=26, color=(90, 90, 90), bg=(240, 240, 240)):
    """生成一个“×”关闭按钮图标（与模板保持一致）。"""
    img = Image.new("RGB", (size, size), bg)
    d = ImageDraw.Draw(img)
    m = max(4, size // 5)
    d.line([(m, m), (size - m, size - m)], fill=color, width=3)
    d.line([(size - m, m), (m, size - m)], fill=color, width=3)
    return img


def main():
    os.makedirs(TPL_DIR, exist_ok=True)
    icon = make_x_icon()
    icon.save(os.path.join(TPL_DIR, "close_x.png"))

    root = tk.Tk()
    root.title("模拟广告弹窗")
    root.geometry("440x300")
    root.attributes("-topmost", True)
    root.configure(bg="white")

    # 标题栏：左侧“广告”标识，右侧“×”关闭按钮
    bar = tk.Frame(root, bg="#f0f0f0", height=36)
    bar.pack(fill="x")
    bar.pack_propagate(False)
    tk.Label(bar, text="广告", fg="#d32f2f", bg="#f0f0f0",
             font=("微软雅黑", 12, "bold")).pack(side="left", padx=12, pady=6)

    photo = ImageTk.PhotoImage(icon)
    close = tk.Label(bar, image=photo, bg="#f0f0f0", cursor="hand2")
    close.image = photo  # 防止被垃圾回收
    close.pack(side="right", padx=8, pady=4)
    close.bind("<Button-1>", lambda e: root.destroy())

    # 正文
    tk.Label(root, text="这是一条模拟广告内容", bg="white",
             font=("微软雅黑", 16)).pack(pady=46)

    # 右下角“跳过广告”按钮
    tk.Button(root, text="跳过广告", font=("微软雅黑", 12), command=root.destroy).pack(
        side="bottom", anchor="se", padx=16, pady=16)

    print("模拟广告弹窗已弹出（左上角“广告”、右上角“×”、右下角“跳过广告”）。")
    print("已生成模板：", os.path.join(TPL_DIR, "close_x.png"))
    print("关闭弹窗即可退出本脚本。")
    root.mainloop()


if __name__ == "__main__":
    main()
