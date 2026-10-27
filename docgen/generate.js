const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, AlignmentType, HeadingLevel, LevelFormat
} = require("docx");

const SONG = { ascii: "宋体", hAnsi: "宋体", eastAsia: "宋体" };
const HEI = { ascii: "黑体", hAnsi: "黑体", eastAsia: "黑体" };

function title(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 120 },
    children: [new TextRun({ text, bold: true, size: 32, font: HEI })]
  });
}

function info(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 200 },
    children: [new TextRun({ text, size: 24 })]
  });
}

function heading(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text })]
  });
}

function body(text, opts = {}) {
  return new Paragraph({
    spacing: { line: 340, after: 60 },
    indent: opts.noIndent ? undefined : { firstLine: 480 },
    children: [new TextRun({ text, bold: opts.bold })]
  });
}

function ref(text) {
  return new Paragraph({
    numbering: { reference: "refs", level: 0 },
    spacing: { line: 320, after: 40 },
    children: [new TextRun({ text })]
  });
}

const children = [
  title("基于YOLO与OCR的广告弹窗自动识别与关闭系统"),
  info("姓名：马翰荣　　学号：37220232203776"),

  heading("一、项目的背景及意义"),
  body("随着互联网尤其是视频、资讯类平台（如Bilibili等）的普及，页面中充斥着大量广告弹窗与贴片广告。这些广告往往以“广告”文字标识出现，其关闭按钮（“×”“跳过广告”“关闭”等）位置不固定、样式多样；部分广告甚至没有传统意义上的关闭按钮，而是需要点击“跳过”等文字按钮才能跳过。频繁、被动的广告干扰严重影响了用户的浏览体验和操作效率。"),
  body("本项目旨在设计并实现一个桌面端的广告弹窗自动识别与关闭工具：通过实时截屏，利用计算机视觉技术自动定位广告标识与关闭/跳过按钮，并模拟鼠标点击将其关闭。项目的意义在于：一方面切实改善用户体验，减少广告对正常浏览的干扰；另一方面作为“数字媒体导论”课程的实践项目，将目标检测、OCR文字识别、图像模板匹配等技术综合应用到真实场景中，锻炼工程实现与算法评估能力。"),

  heading("二、所使用方法与改进方向"),
  body("本项目采用“多通道融合”的检测策略，融合三种技术手段：", { noIndent: true }),
  body("（1）YOLO目标检测：加载自定义训练的关闭按钮检测模型，对屏幕中的“×”“关闭”等按钮进行目标检测，输出检测框与置信度。"),
  body("（2）模板匹配：使用OpenCV对“×”关闭按钮模板进行多尺度matchTemplate匹配，配合非极大值抑制（NMS）去除重复框，适用于无模型时的快速识别。"),
  body("（3）OCR文字识别：使用轻量级RapidOCR识别屏幕文字，将“广告”“推广”等识别为广告标识（仅定位、不点击），将“跳过”“跳过广告”“关闭”“取消”等识别为可点击动作按钮。"),
  body("系统通过mss实时截屏、OpenCV绘制检测结果、pyautogui模拟点击，并开启Windows DPI感知保证坐标一致；整体以Flask提供Web可视化界面，支持实时预览、参数调节与模板交互式采集。"),
  body("改进方向：①训练更大规模、更多场景的YOLO专属数据集，提升关闭按钮检测的鲁棒性；②引入“先定位广告区域，再在区域内查找关闭按钮”的两阶段策略，降低误触；③加入多帧时序信息进行目标去重与轨迹判断，避免重复点击与误触；④针对B站等平台无关闭按钮的广告，重点优化“跳过”类文字按钮的识别与点击。"),

  heading("三、所使用的数据"),
  body("（1）模板数据：由用户在可视化界面中交互式框选采集的“×”关闭按钮截图，存放于templates目录。"),
  body("（2）YOLO训练数据：可选的自定义数据集，包含关闭/跳过按钮的标注图像（YOLO格式），用于训练close_button.pt模型。"),
  body("（3）OCR模型：采用RapidOCR内置的PP-OCR预训练模型（文字检测+识别），无需自建数据即可识别中英文。"),
  body("（4）测试数据：B站等真实网站广告弹窗截图与实时屏幕画面，用于端到端效果评估。"),

  heading("四、算法评价方法"),
  body("（1）目标检测指标：精确率（Precision）、召回率（Recall）、F1值及mAP，用于衡量检测框的定位与分类准确性；同时统计检测框与真实框的交并比（IoU）。"),
  body("（2）OCR识别指标：字符/文本识别准确率，以及“广告”“跳过”等关键词的召回情况。"),
  body("（3）端到端指标：在真实广告场景下的广告识别成功率、关闭/跳过成功率、平均响应时间，以及误触率（是否误点非广告内容）。"),
  body("（4）系统性能指标：单帧检测耗时、帧率（FPS）与CPU占用，用于评估实时性。"),

  heading("五、主要参考文献"),
  ref("Redmon J, Divvala S, Girshick R, et al. You Only Look Once: Unified, Real-Time Object Detection[C]// IEEE CVPR, 2016: 779-788."),
  ref("Jocher G, Chaurasia A, Qiu J. Ultralytics YOLOv8[EB/OL]. https://github.com/ultralytics/ultralytics, 2023."),
  ref("Du Y, Li C, Guo R, et al. PP-OCR: A Practical Ultra Lightweight OCR System[C]// ACM MM, 2020."),
  ref("Bradski G. The OpenCV Library[J]. Dr. Dobb's Journal of Software Tools, 2000."),
  ref("OpenCV. Template Matching Documentation[EB/OL]. https://docs.opencv.org/4.x/df/dfb/group__imgproc__object.html."),
  ref("RapidAI. rapidocr_onnxruntime[EB/OL]. https://github.com/RapidAI/RapidOCR."),
];

const doc = new Document({
  styles: {
    default: {
      document: { run: { font: SONG, size: 24 } }
    },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: HEI },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 0 }
      }
    ]
  },
  numbering: {
    config: [
      {
        reference: "refs",
        levels: [
          {
            level: 0, format: LevelFormat.DECIMAL, text: "[%1]", alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 360, hanging: 360 } } }
          }
        ]
      }
    ]
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: 11906, height: 16838 }, // A4
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
        }
      },
      children
    }
  ]
});

const outPath = "C:/资料/学校/数字媒体导论/项目建议书.docx";
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(outPath, buf);
  console.log("saved:", outPath, "(" + buf.length + " bytes)");
});
