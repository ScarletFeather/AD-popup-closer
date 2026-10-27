const $ = (s) => document.querySelector(s);

const el = {
  statusPill: $("#statusPill"),
  statusText: $("#statusText"),
  preview: $("#preview"),
  frameMeta: $("#frameMeta"),
  btnStart: $("#btnStart"),
  btnPopup: $("#btnPopup"),
  toggleClick: $("#toggleClick"),
  toggleTwoStage: $("#toggleTwoStage"),
  toggleCollect: $("#toggleCollect"),
  rangeConf: $("#rangeConf"), confVal: $("#confVal"),
  rangeInt: $("#rangeInt"), intVal: $("#intVal"),
  rangeCool: $("#rangeCool"), coolVal: $("#coolVal"),
  chips: $("#chips"),
  tplChip: $("#tplChip"),
  tplList: $("#tplList"),
  statDetected: $("#statDetected"), statClicked: $("#statClicked"), statFps: $("#statFps"), statAd: $("#statAd"), statCollected: $("#statCollected"),
  log: $("#log"),
};

let frameSize = null; // [w, h] 原始分辨率
let initialized = false;

// ---------- 预览（MJPEG 流式，低延迟） ----------
el.preview.src = "/api/stream";

// ---------- 状态轮询 ----------
async function refreshStatus() {
  try {
    const r = await (await fetch("/api/status")).json();
    const running = r.running;
    el.statusPill.dataset.state = running ? "running" : "stopped";
    el.statusText.textContent = running ? "检测中" : "已停止";
    el.btnStart.textContent = running ? "停止检测" : "开始检测";
    el.btnStart.classList.toggle("running", running);

    frameSize = r.frame_size;
    el.frameMeta.textContent = frameSize ? `${frameSize[0]}×${frameSize[1]}` : "—";

    el.statDetected.textContent = r.stats.detected;
    el.statClicked.textContent = r.stats.clicked;
    el.statAd.textContent = r.stats.ad;
    el.statCollected.textContent = r.stats.collected;
    el.statFps.textContent = r.stats.fps;

    if (!initialized) {
      el.toggleClick.checked = !!r.config.click_enabled;
      el.toggleTwoStage.checked = r.config.two_stage !== false;
      el.toggleCollect.checked = !!r.config.collect_data;
      initialized = true;
    }

    // 检测器状态
    el.chips.innerHTML = "";
    const yolo = document.createElement("span");
    yolo.className = "chip" + (r.detector.yolo ? " ok" : " muted");
    yolo.textContent = "YOLO: " + (r.detector.yolo ? "已加载" : "未加载");
    el.chips.appendChild(yolo);
    const tpl = document.createElement("span");
    tpl.className = "chip" + (r.detector.templates > 0 ? " ok" : " muted");
    tpl.textContent = "模板: " + r.detector.templates;
    el.chips.appendChild(tpl);
    const ocr = document.createElement("span");
    ocr.className = "chip" + (r.detector.ocr ? " ok" : " muted");
    ocr.textContent = "OCR: " + (r.detector.ocr ? "已加载" : "未加载");
    el.chips.appendChild(ocr);

    // 模板列表
    el.tplList.innerHTML = "";
    const tpls = await (await fetch("/api/templates")).json();
    if (tpls.templates.length === 0) {
      const li = document.createElement("li");
      li.className = "empty";
      li.textContent = "暂无模板";
      el.tplList.appendChild(li);
    } else {
      tpls.templates.forEach((name) => {
        const li = document.createElement("li");
        const span = document.createElement("span");
        span.textContent = name;
        const del = document.createElement("button");
        del.className = "tpl-del";
        del.textContent = "删除";
        del.onclick = async () => {
          await fetch("/api/templates/" + name, { method: "DELETE" });
          refreshStatus();
        };
        li.appendChild(span);
        li.appendChild(del);
        el.tplList.appendChild(li);
      });
    }

    el.log.textContent = r.log.slice(-50).join("\n");
    el.log.scrollTop = el.log.scrollHeight;
  } catch (e) { /* ignore */ }
}

// ---------- 控制 ----------
el.btnStart.onclick = async () => {
  const running = el.statusPill.dataset.state === "running";
  await fetch("/api/" + (running ? "stop" : "start"), { method: "POST" });
  refreshStatus();
};

el.btnPopup.onclick = async () => {
  await fetch("/api/popup", { method: "POST" });
};

el.toggleClick.onchange = () => pushSettings();
el.toggleTwoStage.onchange = () => pushSettings();
el.toggleCollect.onchange = () => pushSettings();
el.rangeConf.oninput = () => { el.confVal.textContent = (+el.rangeConf.value).toFixed(2); };
el.rangeConf.onchange = () => pushSettings();
el.rangeInt.oninput = () => { el.intVal.textContent = (+el.rangeInt.value).toFixed(1) + " s"; };
el.rangeInt.onchange = () => pushSettings();
el.rangeCool.oninput = () => { el.coolVal.textContent = (+el.rangeCool.value).toFixed(1) + " s"; };
el.rangeCool.onchange = () => pushSettings();

async function pushSettings() {
  await fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      confidence: +el.rangeConf.value,
      interval: +el.rangeInt.value,
      click_cooldown: +el.rangeCool.value,
      click_enabled: el.toggleClick.checked,
      two_stage: el.toggleTwoStage.checked,
      collect_data: el.toggleCollect.checked,
    }),
  });
}

// ---------- 定时器 ----------
setInterval(refreshStatus, 900);
refreshStatus();
