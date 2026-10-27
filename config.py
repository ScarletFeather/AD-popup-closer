"""全局配置与默认参数。"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "models")
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

# 确保目录存在
os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(TEMPLATE_DIR, exist_ok=True)

DEFAULTS = {
    # YOLO 模型路径（不存在时自动退回到模板匹配）
    "model_path": os.path.join(MODEL_DIR, "close_button.pt"),
    # 关闭按钮模板目录
    "template_dir": TEMPLATE_DIR,
    # 检测置信度阈值
    "confidence": 0.7,
    # 检测间隔（秒）
    "interval": 0.5,
    # 是否真正执行点击（默认关闭，先只预览，安全）
    "click_enabled": False,
    # 同一区域点击冷却时间（秒），避免重复点击
    "click_cooldown": 2.0,
    # 屏幕序号（mss 的 monitor 索引，0 表示主屏）
    "monitor": 0,
    # 关闭按钮类名关键词（YOLO 类别命中即视为关闭按钮）
    "close_labels": ["close", "close_button", "close-btn", "关闭", "x", "x_btn"],
    # OCR：广告标识关键词（仅识别、不可点击，用于定位广告内容）
    "ad_keywords": ["广告", "推广", "赞助"],
    # OCR：可点击的动作文案（跳过/关闭等，命中即点击其中心）
    "action_keywords": ["跳过", "关闭", "取消", "稍后"],
    # 两阶段：先定位广告区域，仅在该区域内点击（降低误触）
    "two_stage": True,
    # 广告区域扩展边距（像素）
    "ad_margin_x": 600,
    "ad_margin_y": 600,
    # 训练数据采集：识别到广告时自动截取广告区域并导出 YOLO 标注
    "collect_data": False,
    "dataset_dir": os.path.join(BASE_DIR, "dataset"),
    # 同一广告区域去重间隔（秒）
    "collect_interval": 2.0,
    # OCR 识别间隔（秒）：调小识别更及时，代价是更占 CPU
    "ocr_interval": 0.5,
    # 是否启用 OCR 文字识别通道
    "ocr_enabled": True,
}
