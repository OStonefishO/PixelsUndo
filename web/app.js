/* PixelsUndo — studio client */
(() => {
  "use strict";

  // ------------------------------------------------------------------ helpers
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
  const round = Math.round;

  const els = {
    stage: $("#stage"),
    view: $("#view"),
    overlay: $("#overlay"),
    emptyState: $("#emptyState"),
    dropHint: $("#dropHint"),
    zoomBar: $("#zoomBar"),
    zoomLabel: $("#zoomLabel"),
    zoomIn: $("#zoomIn"),
    zoomOut: $("#zoomOut"),
    zoomFit: $("#zoomFit"),
    zoomActual: $("#zoomActual"),
    brushCursor: $("#brushCursor"),
    fileInput: $("#fileInput"),
    modeSwitch: $("#modeSwitch"),
    pixelPanel: $("#pixelPanel"),
    cleanPanel: $("#cleanPanel"),
    exportBtn: $("#exportBtn"),
    openBtn: $("#openBtn"),
    emptyOpen: $("#emptyOpen"),
    sampleBtn: $("#sampleBtn"),
    sampleWatermark: $("#sampleWatermark"),
    quitBtn: $("#quitBtn"),
    imageChipText: $("#imageChipText"),
    artChip: $("#artChip"),
    compareBtn: $("#compareBtn"),
    fitBtn: $("#fitBtn"),
    statusFile: $("#statusFile"),
    statusDims: $("#statusDims"),
    statusMessage: $("#statusMessage"),
    statusEngine: $("#statusEngine"),
    busyLayer: $("#busyLayer"),
    busyTitle: $("#busyTitle"),
    busyText: $("#busyText"),
    toastStack: $("#toastStack"),
    maskStatus: $("#maskStatus"),
    applyRepair: $("#applyRepair"),
    undoBase: $("#undoBase"),
    redoBase: $("#redoBase"),
    clearMask: $("#clearMask"),
    brushSize: $("#brushSize"),
    brushValue: $("#brushValue"),
    tolerance: $("#tolerance"),
    toleranceValue: $("#toleranceValue"),
    method: $("#method"),
    radius: $("#radius"),
    radiusValue: $("#radiusValue"),
    wandGroup: $("#wandGroup"),
    brushGroup: $("#brushGroup"),
    toolGrid: $("#toolGrid"),
    palette: $("#palette"),
    paletteNote: $("#paletteNote"),
    colorsGroup: $("#colorsGroup"),
    colors: $("#colors"),
    colorsNumber: $("#colorsNumber"),
    colorChips: $("#colorChips"),
    colorChips: $("#colorChips"),
    levelBlack: $("#levelBlack"),
    levelWhite: $("#levelWhite"),
    levelGamma: $("#levelGamma"),
    levelOutBlack: $("#levelOutBlack"),
    levelOutWhite: $("#levelOutWhite"),
    levelBlackValue: $("#levelBlackValue"),
    levelWhiteValue: $("#levelWhiteValue"),
    levelGammaValue: $("#levelGammaValue"),
    levelOutBlackValue: $("#levelOutBlackValue"),
    levelOutWhiteValue: $("#levelOutWhiteValue"),
    resetLevels: $("#resetLevels"),
    pixels: $("#pixels"),
    pixelValue: $("#pixelValue"),
    outSize: $("#outSize"),
    saturation: $("#saturation"),
    saturationValue: $("#saturationValue"),
    contrast: $("#contrast"),
    contrastValue: $("#contrastValue"),
    brightness: $("#brightness"),
    brightnessValue: $("#brightnessValue"),
    outline: $("#outline"),
    outlineValue: $("#outlineValue"),
    ditherGroup: $("#ditherGroup"),
    presetGrid: $("#presetGrid"),
    sizeChips: $("#sizeChips"),
    resetPixel: $("#resetPixel"),
    exportModal: $("#exportModal"),
    quitModal: $("#quitModal"),
    closeExport: $("#closeExport"),
    cancelExport: $("#cancelExport"),
    doExport: $("#doExport"),
    exportName: $("#exportName"),
    exportThumb: $("#exportThumb"),
    exportSizePreview: $("#exportSizePreview"),
    exportNamePreview: $("#exportNamePreview"),
    exportFinalSize: $("#exportFinalSize"),
    exportBadge: $("#exportBadge"),
    exportTitle: $("#exportTitle"),
    formatGroup: $("#formatGroup"),
    formatNote: $("#formatNote"),
    scaleGrid: $("#scaleGrid"),
    scaleField: $("#scaleField"),
    cancelQuit: $("#cancelQuit"),
    confirmQuit: $("#confirmQuit"),
    statusRight: $(".status-right"),
    phoneBtn: $("#phoneBtn"),
    phoneModal: $("#phoneModal"),
    phoneQr: $("#phoneQr"),
    phoneUrl: $("#phoneUrl"),
    phoneHint: $("#phoneHint"),
    closePhone: $("#closePhone"),
    closePhoneFoot: $("#closePhoneFoot"),
    copyPhoneUrl: $("#copyPhoneUrl"),
    openPhoneUrl: $("#openPhoneUrl"),
    updateBtn: $("#updateBtn"),
    versionLabel: $("#versionLabel"),
    updateModal: $("#updateModal"),
    closeUpdate: $("#closeUpdate"),
    updateRecheck: $("#updateRecheck"),
    openRelease: $("#openRelease"),
    updateMark: $("#updateMark"),
    updateCurrent: $("#updateCurrent"),
    updateStatus: $("#updateStatus"),
    updateNotes: $("#updateNotes"),
    updateLatest: $("#updateLatest"),
    updateNotesText: $("#updateNotesText"),
  };

  const vctx = els.view.getContext("2d");
  const octx = els.overlay.getContext("2d");

  const DEFAULT_PARAMS = {
    pixels: 128,
    palette: "auto",
    colors: 20,
    dither: "none",
    saturation: 1.08,
    contrast: 1.04,
    brightness: 1.0,
    outline: 0.22,
    level_black: 0,
    level_white: 1,
    level_gamma: 1,
    level_out_black: 0,
    level_out_white: 1,
  };

  const PRESETS = {
    gameboy: { pixels: 160, palette: "gameboy", colors: 4, dither: "none", saturation: 1.0, contrast: 1.08, brightness: 1.02, outline: 0.35 },
    pico8: { pixels: 192, palette: "pico8", colors: 16, dither: "none", saturation: 1.12, contrast: 1.02, brightness: 1.0, outline: 0.18 },
    sweetie: { pixels: 220, palette: "sweetie16", colors: 16, dither: "bayer", saturation: 1.18, contrast: 0.98, brightness: 1.02, outline: 0.12 },
    mono: { pixels: 150, palette: "mono", colors: 2, dither: "fs", saturation: 1.0, contrast: 1.22, brightness: 1.05, outline: 0.5 },
  };

  const state = {
    mode: "pixel",
    session: null,
    baseBitmap: null,
    processedBitmap: null,
    processedUrl: "",
    previousBaseBitmap: null,
    artW: 0,
    artH: 0,
    colors: 0,
    view: { scale: 1, x: 0, y: 0 },
    W: 0,
    H: 0,
    dpr: 1,
    maskCanvas: null,
    maskCtx: null,
    maskScale: 1,
    maskActions: [],
    tool: "brush",
    brush: 28,
    drawing: false,
    currentStroke: null,
    pan: null,
    touchPoints: new Map(),
    pinch: null,
    spaceDown: false,
    showOriginal: false,
    processing: false,
    processTimer: 0,
    processAbort: null,
    processToken: 0,
    busy: 0,
    loadToken: 0,
    dirtyParams: true,
    export: { scale: 4, format: "png" },
    hasBaseHistory: false,
  };

  // ------------------------------------------------------------------ network
  async function api(path, payload, signal) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {}),
      signal,
    });
    let data = null;
    try {
      data = await response.json();
    } catch (error) {
      /* non-JSON error */
    }
    if (!response.ok || !data || !data.ok) {
      throw new Error((data && data.error) || `请求失败（${response.status}）`);
    }
    return data;
  }

  function toast(message, kind = "info") {
    const node = document.createElement("div");
    node.className = "toast" + (kind === "error" ? " is-error" : "");
    node.textContent = message;
    els.toastStack.appendChild(node);
    window.setTimeout(() => {
      node.classList.add("is-out");
      window.setTimeout(() => node.remove(), 240);
    }, 2800);
  }

  function showBusy(title = "处理中", text = "正在计算，请稍候…") {
    state.busy += 1;
    els.busyTitle.textContent = title;
    els.busyText.textContent = text;
    els.busyLayer.hidden = false;
  }

  function hideBusy() {
    state.busy = Math.max(0, state.busy - 1);
    if (state.busy === 0) els.busyLayer.hidden = true;
  }

  function setWorking(working, message) {
    els.statusRight.classList.toggle("is-working", working);
    if (message) els.statusMessage.textContent = message;
  }

  function loadImage(src) {
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error("图片解码失败"));
      image.src = src;
    });
  }

  function fileToDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(new Error("无法读取文件"));
      reader.readAsDataURL(file);
    });
  }

  // ------------------------------------------------------------------ canvas
  function resizeCanvas() {
    const rect = els.stage.getBoundingClientRect();
    state.W = Math.max(1, rect.width);
    state.H = Math.max(1, rect.height);
    state.dpr = Math.min(window.devicePixelRatio || 1, 2);
    [els.view, els.overlay].forEach((canvas) => {
      canvas.width = Math.round(state.W * state.dpr);
      canvas.height = Math.round(state.H * state.dpr);
      canvas.style.width = `${state.W}px`;
      canvas.style.height = `${state.H}px`;
    });
    render();
  }

  let checkerPattern = null;
  function getChecker(ctx) {
    if (checkerPattern && checkerPattern.ctx === ctx) return checkerPattern.pattern;
    const tile = document.createElement("canvas");
    tile.width = 24;
    tile.height = 24;
    const tctx = tile.getContext("2d");
    tctx.fillStyle = "#10141b";
    tctx.fillRect(0, 0, 24, 24);
    tctx.fillStyle = "#151a22";
    tctx.fillRect(0, 0, 12, 12);
    tctx.fillRect(12, 12, 12, 12);
    const pattern = ctx.createPattern(tile, "repeat");
    checkerPattern = { ctx, pattern };
    return pattern;
  }

  function render() {
    vctx.setTransform(state.dpr, 0, 0, state.dpr, 0, 0);
    vctx.clearRect(0, 0, state.W, state.H);
    octx.setTransform(state.dpr, 0, 0, state.dpr, 0, 0);
    octx.clearRect(0, 0, state.W, state.H);

    if (!state.session || !state.baseBitmap) return;

    const s = state.view.scale;
    const x = state.view.x;
    const y = state.view.y;
    const dw = state.session.width * s;
    const dh = state.session.height * s;
    const showOriginal = state.showOriginal;
    const useArt = state.mode === "pixel" && state.processedBitmap && !showOriginal;
    const beforeBitmap =
      state.mode === "clean" && state.previousBaseBitmap ? state.previousBaseBitmap : state.baseBitmap;
    const bitmap = showOriginal ? beforeBitmap : useArt ? state.processedBitmap : state.baseBitmap;

    vctx.save();
    vctx.beginPath();
    vctx.rect(x, y, dw, dh);
    vctx.clip();
    vctx.fillStyle = getChecker(vctx);
    vctx.fillRect(x, y, dw, dh);
    vctx.imageSmoothingEnabled = !useArt;
    vctx.imageSmoothingQuality = "high";
    vctx.drawImage(bitmap, x, y, dw, dh);
    vctx.restore();

    vctx.strokeStyle = "rgba(255,255,255,0.16)";
    vctx.lineWidth = 1;
    vctx.strokeRect(x + 0.5, y + 0.5, Math.max(0, dw - 1), Math.max(0, dh - 1));

    if (state.mode === "pixel" && state.processedBitmap && !showOriginal && state.artW > 0) {
      const cell = (state.session.width / state.artW) * s;
      if (cell >= 6) {
        vctx.save();
        vctx.beginPath();
        vctx.rect(x, y, dw, dh);
        vctx.clip();
        vctx.strokeStyle = "rgba(6,8,12,0.32)";
        vctx.lineWidth = 1;
        vctx.beginPath();
        const cols = Math.min(state.artW, 600);
        const rows = Math.min(state.artH, 600);
        for (let i = 1; i < cols; i += 1) {
          const px = Math.round(x + i * cell) + 0.5;
          vctx.moveTo(px, y);
          vctx.lineTo(px, y + dh);
        }
        for (let j = 1; j < rows; j += 1) {
          const py = Math.round(y + j * cell) + 0.5;
          vctx.moveTo(x, py);
          vctx.lineTo(x + dw, py);
        }
        vctx.stroke();
        vctx.restore();
      }
    }

    // Painted repair mask
    if (state.mode === "clean" && state.maskCanvas) {
      octx.save();
      octx.globalAlpha = 0.52;
      octx.imageSmoothingEnabled = true;
      octx.drawImage(state.maskCanvas, x, y, dw, dh);
      octx.restore();
    }
  }

  function fitView() {
    if (!state.session) return;
    const pad = Math.min(52, Math.max(24, state.W * 0.06));
    const s = Math.min((state.W - pad * 2) / state.session.width, (state.H - pad * 2) / state.session.height);
    state.view.scale = clamp(s, 0.02, 40);
    state.view.x = (state.W - state.session.width * state.view.scale) / 2;
    state.view.y = (state.H - state.session.height * state.view.scale) / 2;
    render();
    updateZoomLabel();
  }

  function updateZoomLabel() {
    const percent = state.view.scale * 100;
    els.zoomLabel.textContent = `${percent >= 100 ? round(percent) : percent.toFixed(percent < 10 ? 1 : 0)}%`;
  }

  function zoomAt(clientX, clientY, factor) {
    if (!state.session) return;
    const rect = els.stage.getBoundingClientRect();
    const mx = clientX - rect.left;
    const my = clientY - rect.top;
    const beforeX = (mx - state.view.x) / state.view.scale;
    const beforeY = (my - state.view.y) / state.view.scale;
    const scale = clamp(state.view.scale * factor, 0.02, 64);
    state.view.scale = scale;
    state.view.x = mx - beforeX * scale;
    state.view.y = my - beforeY * scale;
    render();
    updateZoomLabel();
  }

  function screenToImage(clientX, clientY) {
    const rect = els.stage.getBoundingClientRect();
    return {
      x: (clientX - rect.left - state.view.x) / state.view.scale,
      y: (clientY - rect.top - state.view.y) / state.view.scale,
    };
  }

  function cancelStrokeForPinch() {
    if (!state.drawing) return;
    state.drawing = false;
    state.currentStroke = null;
    els.overlay.classList.remove("painting");
    replayMask();
  }

  function touchPair() {
    return Array.from(state.touchPoints.values()).slice(0, 2);
  }

  function beginPinch() {
    const points = touchPair();
    if (points.length < 2) return;
    const [a, b] = points;
    cancelStrokeForPinch();
    state.pan = null;
    els.overlay.classList.remove("panning");
    state.pinch = {
      distance: Math.max(1, Math.hypot(b.x - a.x, b.y - a.y)),
      midX: (a.x + b.x) / 2,
      midY: (a.y + b.y) / 2,
      scale: state.view.scale,
      x: state.view.x,
      y: state.view.y,
    };
  }

  function updatePinch() {
    const pinch = state.pinch;
    const points = touchPair();
    if (!pinch || points.length < 2) return;
    const [a, b] = points;
    const distance = Math.max(1, Math.hypot(b.x - a.x, b.y - a.y));
    const midX = (a.x + b.x) / 2;
    const midY = (a.y + b.y) / 2;
    const rect = els.stage.getBoundingClientRect();
    const anchorX = pinch.midX - rect.left;
    const anchorY = pinch.midY - rect.top;
    const scale = clamp(pinch.scale * (distance / pinch.distance), 0.02, 64);
    const ratio = scale / pinch.scale;
    state.view.scale = scale;
    state.view.x = anchorX - (anchorX - pinch.x) * ratio + (midX - pinch.midX);
    state.view.y = anchorY - (anchorY - pinch.y) * ratio + (midY - pinch.midY);
    render();
    updateZoomLabel();
  }

  function isInsideImage(point) {
    return state.session && point.x >= 0 && point.y >= 0 && point.x <= state.session.width && point.y <= state.session.height;
  }

  // ------------------------------------------------------------------ controls
  function paintRange(input) {
    const min = Number(input.min) || 0;
    const max = Number(input.max) || 100;
    const value = Number(input.value);
    const ratio = ((value - min) / (max - min)) * 100;
    input.style.setProperty("--fill", `${clamp(ratio, 0, 100)}%`);
  }

  function readParams() {
    return {
      pixels: Number(els.pixels.value),
      palette: els.palette.value,
      colors: Number(els.colors.value),
      dither: $$("#ditherGroup button").find((btn) => btn.classList.contains("is-active"))?.dataset.dither || "none",
      saturation: Number(els.saturation.value) / 100,
      contrast: Number(els.contrast.value) / 100,
      brightness: Number(els.brightness.value) / 100,
      outline: Number(els.outline.value) / 100,
      level_black: Number(els.levelBlack.value) / 255,
      level_white: Number(els.levelWhite.value) / 255,
      level_gamma: Number(els.levelGamma.value) / 100,
      level_out_black: Number(els.levelOutBlack.value) / 255,
      level_out_white: Number(els.levelOutWhite.value) / 255,
    };
  }

  function updateParamLabels() {
    els.pixelValue.textContent = `${els.pixels.value} px`;
    els.colorsNumber.value = els.colors.value;
    els.saturationValue.textContent = `${els.saturation.value}%`;
    els.contrastValue.textContent = `${els.contrast.value}%`;
    els.brightnessValue.textContent = `${els.brightness.value}%`;
    els.outlineValue.textContent = `${els.outline.value}%`;
    els.brushValue.textContent = `${els.brushSize.value} px`;
    els.toleranceValue.textContent = els.tolerance.value;
    els.radiusValue.textContent = `${els.radius.value} px`;
    els.levelBlackValue.textContent = els.levelBlack.value;
    els.levelWhiteValue.textContent = els.levelWhite.value;
    els.levelGammaValue.textContent = (Number(els.levelGamma.value) / 100).toFixed(2);
    els.levelOutBlackValue.textContent = els.levelOutBlack.value;
    els.levelOutWhiteValue.textContent = els.levelOutWhite.value;

    const notes = {
      auto: "Median Cut",
      gameboy: "4 COLORS",
      pico8: "16 COLORS",
      sweetie16: "16 COLORS",
      sepia: "8 COLORS",
      mono: "2 COLORS",
      none: "TRUE COLOR",
    };
    els.paletteNote.textContent = notes[els.palette.value] || "PALETTE";
    els.colorsGroup.hidden = els.palette.value !== "auto";

    $$("#sizeChips button").forEach((btn) => {
      btn.classList.toggle("is-active", Number(btn.dataset.size) === Number(els.pixels.value));
    });
    $$("#colorChips button").forEach((btn) => {
      btn.classList.toggle("is-active", Number(btn.dataset.colors) === Number(els.colors.value));
    });
    $$("#ditherGroup button").forEach((btn) => {
      const active = btn.dataset.dither === ($$("#ditherGroup .is-active")[0]?.dataset.dither || "none");
      btn.classList.toggle("is-active", active);
    });

    updateEstimate();
    [els.pixels, els.colors, els.saturation, els.contrast, els.brightness, els.outline,
      els.levelBlack, els.levelWhite, els.levelGamma, els.levelOutBlack, els.levelOutWhite,
      els.brushSize, els.tolerance, els.radius].forEach(paintRange);
  }

  function updateEstimate() {
    if (!state.session) {
      els.outSize.textContent = "—";
      return;
    }
    const target = Number(els.pixels.value);
    const ratio = target / Math.max(state.session.width, state.session.height);
    els.outSize.textContent = `${Math.max(1, round(state.session.width * ratio))} × ${Math.max(1, round(state.session.height * ratio))}`;
  }

  function applyParamsToUi(params) {
    els.pixels.value = params.pixels;
    els.palette.value = params.palette;
    els.colors.value = params.colors;
    els.saturation.value = round(params.saturation * 100);
    els.contrast.value = round(params.contrast * 100);
    els.brightness.value = round(params.brightness * 100);
    els.outline.value = round(params.outline * 100);
    if (params.level_black !== undefined) els.levelBlack.value = round(params.level_black * 255);
    if (params.level_white !== undefined) els.levelWhite.value = round(params.level_white * 255);
    if (params.level_gamma !== undefined) els.levelGamma.value = round(params.level_gamma * 100);
    if (params.level_out_black !== undefined) els.levelOutBlack.value = round(params.level_out_black * 255);
    if (params.level_out_white !== undefined) els.levelOutWhite.value = round(params.level_out_white * 255);
    $$("#ditherGroup button").forEach((btn) => btn.classList.toggle("is-active", btn.dataset.dither === params.dither));
    updateParamLabels();
  }

  function applyPreset(name) {
    const preset = PRESETS[name];
    if (!preset) return;
    applyParamsToUi(preset);
    $$(".preset-card").forEach((card) => card.classList.toggle("is-active", card.dataset.preset === name));
    state.dirtyParams = true;
    scheduleProcess(true);
  }

  function resetPixelParams() {
    applyParamsToUi(DEFAULT_PARAMS);
    $$(".preset-card").forEach((card) => card.classList.remove("is-active"));
    state.dirtyParams = true;
    scheduleProcess(true);
  }

  function markManual() {
    $$(".preset-card").forEach((card) => card.classList.remove("is-active"));
    state.dirtyParams = true;
  }

  function setColorCount(value) {
    const next = clamp(Math.round(Number(value) || 20), 2, 64);
    els.colors.value = String(next);
    els.colorsNumber.value = String(next);
    markManual();
    updateParamLabels();
    scheduleProcess();
  }

  function resetLevels() {
    els.levelBlack.value = "0";
    els.levelWhite.value = "255";
    els.levelGamma.value = "100";
    els.levelOutBlack.value = "0";
    els.levelOutWhite.value = "255";
    markManual();
    updateParamLabels();
    scheduleProcess(true);
  }

  // --------------------------------------------------------------- pixel flow
  function scheduleProcess(immediate = false) {
    if (!state.session || state.mode !== "pixel") return;
    window.clearTimeout(state.processTimer);
    state.processTimer = window.setTimeout(processPixel, immediate ? 0 : 140);
  }

  async function processPixel() {
    if (!state.session || state.mode !== "pixel") return;
    if (state.processAbort) state.processAbort.abort();
    const controller = new AbortController();
    state.processAbort = controller;
    const token = ++state.processToken;
    state.processing = true;
    setWorking(true, "正在渲染像素画…");

    try {
      const data = await api(
        "/api/pixelate",
        { session: state.session.id, params: readParams() },
        controller.signal
      );
      if (token !== state.processToken) return;
      const bitmap = await loadImage(data.image);
      if (token !== state.processToken) return;
      state.processedBitmap = bitmap;
      state.processedUrl = data.image;
      state.artW = data.outWidth;
      state.artH = data.outHeight;
      state.colors = data.colors;
      state.dirtyParams = false;
      els.artChip.hidden = false;
      els.artChip.textContent = `${data.outWidth} × ${data.outHeight} px · ${data.colors} 色`;
      els.outSize.textContent = `${data.outWidth} × ${data.outHeight}`;
      render();
      setWorking(false, `像素化完成 · ${data.ms} ms`);
    } catch (error) {
      if (error.name === "AbortError") return;
      setWorking(false, "渲染失败");
      toast(error.message || "像素画渲染失败", "error");
    } finally {
      if (token === state.processToken) {
        state.processing = false;
        state.processAbort = null;
      }
    }
  }

  // --------------------------------------------------------------- load image
  async function loadSession(session) {
    const token = ++state.loadToken;
    state.session = session;
    state.processedBitmap = null;
    state.processedUrl = "";
    state.previousBaseBitmap = null;
    state.artW = 0;
    state.artH = 0;
    state.maskActions = [];
    state.currentStroke = null;
    state.showOriginal = false;
    try {
      const bitmap = await loadImage(session.image);
      if (token !== state.loadToken) return;
      state.baseBitmap = bitmap;
      initMaskCanvas();
      els.emptyState.hidden = true;
      els.zoomBar.hidden = false;
      els.exportBtn.disabled = false;
      els.fitBtn.disabled = false;
      els.compareBtn.disabled = false;
      els.imageChipText.textContent = session.name;
      els.imageChipText.title = session.name;
      els.statusFile.textContent = session.name;
      els.statusDims.textContent = `${session.width} × ${session.height} px`;
      els.statusMessage.textContent = "图片已载入";
      updateEstimate();
      updateMaskUi();
      updateHistoryUi();
      resizeCanvas();
      fitView();
      if (state.mode === "pixel") scheduleProcess(true);
      else render();
    } catch (error) {
      toast(error.message || "无法加载图片", "error");
    }
  }

  async function uploadFile(file) {
    if (!file || !file.type.startsWith("image/")) {
      toast("请选择 JPG、PNG 或 WebP 图片", "error");
      return;
    }
    showBusy("正在打开图片", file.name);
    try {
      const dataUrl = await fileToDataUrl(file);
      const data = await api("/api/upload", { image: dataUrl, name: file.name });
      await loadSession(data.session);
      toast("图片已载入，开始调整吧");
    } catch (error) {
      toast(error.message || "打开图片失败", "error");
    } finally {
      hideBusy();
    }
  }

  async function loadSample(kind = "landscape") {
    showBusy("正在准备示例", "生成一张用于体验的图片");
    try {
      const data = await api("/api/sample", { kind });
      await loadSession(data.session);
      toast(kind === "watermark" ? "已载入带水印示例，试试涂抹修复" : "示例已载入");
    } catch (error) {
      toast(error.message || "示例加载失败", "error");
    } finally {
      hideBusy();
    }
  }

  // ------------------------------------------------------------------- mask
  function initMaskCanvas() {
    if (!state.session) return;
    const maxSide = 2400;
    const scale = Math.min(1, maxSide / Math.max(state.session.width, state.session.height));
    state.maskScale = scale;
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, round(state.session.width * scale));
    canvas.height = Math.max(1, round(state.session.height * scale));
    state.maskCanvas = canvas;
    state.maskCtx = canvas.getContext("2d", { willReadFrequently: false });
    state.maskCtx.lineCap = "round";
    state.maskCtx.lineJoin = "round";
  }

  function maskPoint(point) {
    return { x: point.x * state.maskScale, y: point.y * state.maskScale };
  }

  function strokeStyle() {
    return "rgba(255, 64, 136, 1)";
  }

  function drawMaskDot(point, width, erase) {
    const ctx = state.maskCtx;
    const p = maskPoint(point);
    ctx.save();
    ctx.globalCompositeOperation = erase ? "destination-out" : "source-over";
    ctx.fillStyle = strokeStyle();
    ctx.beginPath();
    ctx.arc(p.x, p.y, Math.max(0.6, width / 2), 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  function drawMaskLine(from, to, width, erase) {
    const ctx = state.maskCtx;
    const a = maskPoint(from);
    const b = maskPoint(to);
    ctx.save();
    ctx.globalCompositeOperation = erase ? "destination-out" : "source-over";
    ctx.strokeStyle = strokeStyle();
    ctx.lineWidth = Math.max(0.6, width);
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
    ctx.restore();
  }

  function startStroke(point) {
    const width = (state.brush / state.view.scale) * state.maskScale;
    state.drawing = true;
    state.currentStroke = {
      type: "stroke",
      erase: state.tool === "eraser",
      width,
      points: [maskPoint(point)],
    };
    drawMaskDot(point, width, state.tool === "eraser");
    els.overlay.classList.add("painting");
    render();
  }

  function moveStroke(point) {
    if (!state.drawing || !state.currentStroke) return;
    const stroke = state.currentStroke;
    const previous = stroke.points[stroke.points.length - 1];
    const next = maskPoint(point);
    if (Math.hypot(next.x - previous.x, next.y - previous.y) < 0.35) return;
    drawMaskLine(
      { x: previous.x / state.maskScale, y: previous.y / state.maskScale },
      point,
      stroke.width,
      stroke.erase
    );
    stroke.points.push(next);
    render();
  }

  function endStroke() {
    if (!state.drawing || !state.currentStroke) {
      state.drawing = false;
      return;
    }
    if (state.currentStroke.points.length > 0) state.maskActions.push(state.currentStroke);
    state.currentStroke = null;
    state.drawing = false;
    els.overlay.classList.remove("painting");
    updateMaskUi();
  }

  async function replayMask() {
    if (!state.maskCtx) return;
    const { width, height } = state.maskCanvas;
    state.maskCtx.clearRect(0, 0, width, height);
    for (const action of state.maskActions) {
      if (action.type === "stroke") {
        const ctx = state.maskCtx;
        ctx.save();
        ctx.globalCompositeOperation = action.erase ? "destination-out" : "source-over";
        ctx.strokeStyle = strokeStyle();
        ctx.fillStyle = strokeStyle();
        ctx.lineWidth = action.width;
        const points = action.points;
        if (points.length === 1) {
          ctx.beginPath();
          ctx.arc(points[0].x, points[0].y, action.width / 2, 0, Math.PI * 2);
          ctx.fill();
        } else {
          ctx.beginPath();
          ctx.moveTo(points[0].x, points[0].y);
          for (let i = 1; i < points.length; i += 1) ctx.lineTo(points[i].x, points[i].y);
          ctx.stroke();
        }
        ctx.restore();
      } else if (action.type === "image") {
        try {
          const image = await loadImage(action.data);
          state.maskCtx.drawImage(image, 0, 0, width, height);
        } catch (error) {
          /* ignore broken history entry */
        }
      }
    }
    render();
  }

  async function undoMask() {
    if (!state.maskActions.length) return;
    state.maskActions.pop();
    await replayMask();
    updateMaskUi();
  }

  function clearMask(showToast = true) {
    if (!state.maskCanvas) return;
    state.maskCtx.clearRect(0, 0, state.maskCanvas.width, state.maskCanvas.height);
    state.maskActions = [];
    updateMaskUi();
    render();
    if (showToast) toast("蒙版已清空");
  }

  function updateMaskUi() {
    const count = state.maskActions.length;
    els.applyRepair.disabled = count === 0;
    els.clearMask.disabled = count === 0;
    els.maskStatus.textContent = count ? `已标记 ${count} 笔 · 等待修复` : "尚未标记区域";
  }

  async function wandSelect(point) {
    if (!state.session) return;
    showBusy("正在识别颜色", "寻找相连的相似像素");
    try {
      const data = await api("/api/select", {
        session: state.session.id,
        x: round(point.x),
        y: round(point.y),
        tolerance: Number(els.tolerance.value),
      });
      const image = await loadImage(data.mask);
      state.maskCtx.drawImage(image, 0, 0, state.maskCanvas.width, state.maskCanvas.height);
      state.maskActions.push({ type: "image", data: data.mask });
      updateMaskUi();
      render();
      toast(`已选中 ${(data.coverage * 100).toFixed(1)}% 的画面`);
    } catch (error) {
      toast(error.message || "选择失败", "error");
    } finally {
      hideBusy();
    }
  }

  function updateHistoryUi() {
    if (!state.session) {
      els.undoBase.disabled = true;
      els.redoBase.disabled = true;
      return;
    }
    els.undoBase.disabled = !state.session.canUndo;
    els.redoBase.disabled = !state.session.canRedo;
  }

  async function applyRepair() {
    if (!state.session || !state.maskActions.length) {
      toast("请先涂抹或选取水印区域", "error");
      return;
    }
    showBusy("正在修复画面", "读取周围像素并填补水印");
    const maskUrl = state.maskCanvas.toDataURL("image/png");
    try {
      const data = await api("/api/inpaint", {
        session: state.session.id,
        mask: maskUrl,
        method: els.method.value,
        radius: Number(els.radius.value),
      });
      const bitmap = await loadImage(data.image);
      state.previousBaseBitmap = state.baseBitmap;
      state.baseBitmap = bitmap;
      state.processedBitmap = null;
      state.processedUrl = "";
      state.artW = 0;
      state.artH = 0;
      state.dirtyParams = true;
      els.artChip.hidden = true;
      state.session = {
        ...state.session,
        width: data.width,
        height: data.height,
        version: data.version,
        canUndo: data.canUndo,
        canRedo: data.canRedo,
      };
      state.hasBaseHistory = true;
      clearMask(false);
      updateHistoryUi();
      updateCompareState();
      render();
      setWorking(false, `修复完成 · ${data.ms} ms`);
      toast("水印区域已修复，可继续微调或转为像素画");
    } catch (error) {
      setWorking(false, "修复失败");
      toast(error.message || "修复失败", "error");
    } finally {
      hideBusy();
    }
  }

  async function stepHistory(direction) {
    if (!state.session) return;
    showBusy(direction < 0 ? "正在撤销" : "正在重做", "恢复图片版本");
    try {
      const data = await api(direction < 0 ? "/api/undo" : "/api/redo", { session: state.session.id });
      const bitmap = await loadImage(data.image);
      state.baseBitmap = bitmap;
      state.previousBaseBitmap = null;
      state.processedBitmap = null;
      state.processedUrl = "";
      state.artW = 0;
      state.artH = 0;
      state.dirtyParams = true;
      els.artChip.hidden = true;
      state.session = {
        ...state.session,
        width: data.width,
        height: data.height,
        version: data.version,
        canUndo: data.canUndo,
        canRedo: data.canRedo,
      };
      updateCompareState();
      clearMask(false);
      updateHistoryUi();
      render();
      toast(direction < 0 ? "已撤销上一次修复" : "已重做修复");
    } catch (error) {
      toast(error.message || "操作失败", "error");
    } finally {
      hideBusy();
    }
  }

  // -------------------------------------------------------------- interaction
  function shouldPan(event) {
    if (!state.session) return false;
    if (event.button === 1 || event.button === 2) return true;
    if (state.spaceDown) return true;
    return state.mode === "pixel";
  }

  function updateBrushCursor(event) {
    if (!state.session || state.mode !== "clean" || state.tool === "wand" || state.spaceDown || state.drawing) {
      els.brushCursor.hidden = true;
      return;
    }
    const rect = els.stage.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    els.brushCursor.style.left = `${x}px`;
    els.brushCursor.style.top = `${y}px`;
    els.brushCursor.style.width = `${state.brush}px`;
    els.brushCursor.style.height = `${state.brush}px`;
    els.brushCursor.hidden = false;
  }

  function hideBrushCursor() {
    els.brushCursor.hidden = true;
  }

  function setupOverlayEvents() {
    els.overlay.addEventListener("pointerdown", (event) => {
      if (!state.session) return;
      try {
        els.overlay.setPointerCapture(event.pointerId);
      } catch (error) {
        /* synthetic pointers (automation) cannot be captured */
      }
      if (event.pointerType === "touch") {
        state.touchPoints.set(event.pointerId, { x: event.clientX, y: event.clientY });
        if (state.touchPoints.size === 2) {
          beginPinch();
          return;
        }
      }
      if (shouldPan(event)) {
        state.pan = {
          id: event.pointerId,
          startX: event.clientX,
          startY: event.clientY,
          x: state.view.x,
          y: state.view.y,
        };
        els.overlay.classList.add("panning");
        return;
      }
      if (state.mode !== "clean") return;
      const point = screenToImage(event.clientX, event.clientY);
      if (!isInsideImage(point)) return;
      if (state.tool === "wand") {
        wandSelect(point);
        return;
      }
      startStroke(point);
    });

    els.overlay.addEventListener("pointermove", (event) => {
      if (event.pointerType === "touch" && state.touchPoints.has(event.pointerId)) {
        state.touchPoints.set(event.pointerId, { x: event.clientX, y: event.clientY });
      }
      if (state.pinch) {
        updatePinch();
        return;
      }
      updateBrushCursor(event);
      if (state.pan && state.pan.id === event.pointerId) {
        state.view.x = state.pan.x + (event.clientX - state.pan.startX);
        state.view.y = state.pan.y + (event.clientY - state.pan.startY);
        render();
        return;
      }
      if (state.drawing) {
        const point = screenToImage(event.clientX, event.clientY);
        moveStroke(point);
      }
    });

    const endPointer = (event) => {
      if (event.pointerType === "touch") {
        state.touchPoints.delete(event.pointerId);
        if (state.touchPoints.size < 2) state.pinch = null;
      }
      if (state.pan && state.pan.id === event.pointerId) {
        state.pan = null;
        els.overlay.classList.remove("panning");
      }
      endStroke();
    };
    els.overlay.addEventListener("pointerup", endPointer);
    els.overlay.addEventListener("pointercancel", endPointer);
    els.overlay.addEventListener("pointerleave", () => {
      hideBrushCursor();
      if (state.drawing) endStroke();
    });
    els.overlay.addEventListener("contextmenu", (event) => event.preventDefault());

    els.stage.addEventListener("wheel", (event) => {
      if (!state.session) return;
      event.preventDefault();
      const factor = Math.exp(-event.deltaY * 0.0016);
      zoomAt(event.clientX, event.clientY, factor);
    }, { passive: false });
  }

  function setMode(mode) {
    state.mode = mode;
    $$("#modeSwitch .mode-btn").forEach((btn) => btn.classList.toggle("is-active", btn.dataset.mode === mode));
    els.pixelPanel.hidden = mode !== "pixel";
    els.cleanPanel.hidden = mode !== "clean";
    els.overlay.classList.toggle("painting", false);
    els.overlay.classList.toggle("wand", mode === "clean" && state.tool === "wand");
    els.overlay.classList.toggle("brush-mode", mode === "clean" && state.tool !== "wand");
    els.overlay.classList.toggle("idle", mode === "pixel" || state.tool === "wand");
    els.brushCursor.hidden = true;
    updateCompareState();
    if (mode === "pixel" && state.session) {
      scheduleProcess(true);
    } else {
      render();
    }
    if (mode === "clean") {
      els.statusMessage.textContent = state.session ? "涂抹水印区域后应用修复" : "打开一张带水印的图片";
    }
  }

  function updateCompareState() {
    if (!state.session) {
      els.compareBtn.disabled = true;
      return;
    }
    if (state.mode === "clean") {
      els.compareBtn.disabled = !state.previousBaseBitmap;
      els.compareBtn.querySelector("span").textContent = state.previousBaseBitmap ? "按住看修复前" : "按住对比";
    } else {
      els.compareBtn.disabled = false;
      els.compareBtn.querySelector("span").textContent = "按住对比";
    }
  }

  function setCompare(active) {
    if (!state.session) return;
    if (active && state.mode === "clean" && !state.previousBaseBitmap) return;
    state.showOriginal = active;
    els.compareBtn.classList.toggle("is-active", active);
    render();
  }

  // ------------------------------------------------------------------ export
  function outputDimensions() {
    if (!state.session) return { width: 0, height: 0 };
    if (state.mode === "clean") return { width: state.session.width, height: state.session.height };
    const scale = state.export.scale;
    if (!state.artW) return { width: 0, height: 0 };
    return { width: state.artW * scale, height: state.artH * scale };
  }

  function openExport() {
    if (!state.session) return;
    const clean = state.mode === "clean";
    if (!clean && !state.artW) {
      toast("像素画还在渲染，请稍候再导出", "error");
      return;
    }
    state.export.scale = 4;
    state.export.format = "png";
    els.exportTitle.textContent = clean ? "导出去水印图片" : "导出像素画";
    els.exportBadge.textContent = clean ? "修复图" : "像素画";
    els.scaleField.hidden = clean;
    els.exportName.value = clean ? cleanName(state.session.name) : pixelName(state.session.name);
    els.exportThumb.style.backgroundImage = `url("${state.processedUrl || state.session.image}")`;
    els.exportSizePreview.textContent = clean
      ? `${state.session.width} × ${state.session.height} px`
      : `${state.artW} × ${state.artH} art px`;
    $$("#scaleGrid button").forEach((btn) => btn.classList.toggle("is-active", Number(btn.dataset.scale) === 4));
    $$("#formatGroup button").forEach((btn) => btn.classList.toggle("is-active", btn.dataset.format === "png"));
    updateExportSummary();
    els.exportModal.hidden = false;
    window.setTimeout(() => els.exportName.focus(), 80);
  }

  function pixelName(name) {
    return `${String(name || "image").replace(/\.[^.]+$/, "")}-pixel`;
  }
  function cleanName(name) {
    return `${String(name || "image").replace(/\.[^.]+$/, "")}-clean`;
  }

  function updateExportSummary() {
    const { width, height } = outputDimensions();
    const extension = state.export.format === "jpg" ? "jpg" : state.export.format;
    const base = (els.exportName.value || "pixelsundo").replace(/\.(png|jpe?g|webp)$/i, "");
    els.exportNamePreview.textContent = `${base || "pixelsundo"}.${extension}`;
    els.exportFinalSize.textContent = width ? `${width} × ${height} px` : "—";
    const notes = { png: "无损 PNG", jpg: "JPEG · 95%", webp: "WebP · 95%" };
    els.formatNote.textContent = notes[state.export.format] || "PNG";
  }

  async function doExport() {
    if (!state.session) return;
    const base = (els.exportName.value || "pixelsundo").replace(/\.(png|jpe?g|webp)$/i, "").trim() || "pixelsundo";
    const extension = state.export.format === "jpg" ? "jpg" : state.export.format;
    els.doExport.disabled = true;
    const previous = els.doExport.innerHTML;
    els.doExport.textContent = "正在生成…";
    try {
      const response = await fetch("/api/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session: state.session.id,
          mode: state.mode === "clean" ? "base" : "pixel",
          params: readParams(),
          scale: state.export.scale,
          format: state.export.format,
          quality: 95,
          filename: base,
        }),
      });
      if (!response.ok) {
        let message = "导出失败";
        try {
          const data = await response.json();
          message = data.error || message;
        } catch (error) { /* ignore */ }
        throw new Error(message);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${base}.${extension}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 4000);
      els.exportModal.hidden = true;
      toast(`已导出 ${base}.${extension}`);
    } catch (error) {
      toast(error.message || "导出失败", "error");
    } finally {
      els.doExport.disabled = false;
      els.doExport.innerHTML = previous;
    }
  }

  // ------------------------------------------------------------------- tools
  function setTool(tool) {
    state.tool = tool;
    $$("#toolGrid .tool-btn").forEach((btn) => btn.classList.toggle("is-active", btn.dataset.tool === tool));
    els.brushGroup.hidden = tool === "wand";
    els.wandGroup.hidden = tool !== "wand";
    els.overlay.classList.toggle("wand", tool === "wand" && state.mode === "clean");
    els.overlay.classList.toggle("brush-mode", tool !== "wand" && state.mode === "clean");
    els.overlay.classList.toggle("idle", tool === "wand");
    render();
  }

  // ------------------------------------------------------------------- quit
  function openQuit() {
    els.quitModal.hidden = false;
  }

  async function quitApp() {
    try {
      await fetch("/api/shutdown", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    } catch (error) { /* server may already be down */ }
    els.quitModal.hidden = true;
    const overlay = document.createElement("div");
    overlay.className = "modal-backdrop";
    overlay.style.zIndex = "300";
    overlay.innerHTML = `
      <div class="modal modal-small" style="text-align:center">
        <div class="modal-body" style="padding:32px 26px 8px">
          <div class="eyebrow">GOODBYE</div>
          <h2 style="margin:0 0 10px;font-size:22px">PixelsUndo 已退出</h2>
          <p class="modal-copy">本地服务已经停止，现在可以安全关闭这个页面。<br/>下次双击启动脚本即可继续创作。</p>
        </div>
        <div class="modal-foot" style="justify-content:center;padding-bottom:28px">
          <button class="btn btn-primary" type="button" onclick="window.close()">关闭页面</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
  }

  // ------------------------------------------------------------------- phone
  let phoneInfo = null;

  async function openPhone() {
    els.phoneModal.hidden = false;
    if (phoneInfo) return;
    const qrWrap = els.phoneQr.parentElement;
    qrWrap.hidden = true;
    els.phoneUrl.textContent = "正在获取局域网地址…";
    els.phoneQr.hidden = true;
    try {
      const response = await fetch("/api/network", { cache: "no-store" });
      const info = await response.json();
      if (!info || !info.ok) throw new Error("无法获取网络地址");
      phoneInfo = info;
      els.phoneUrl.textContent = info.primary;
      if (info.lan) {
        qrWrap.hidden = false;
        els.phoneQr.src = `/api/qr.svg?v=${Date.now()}`;
        els.phoneQr.hidden = false;
        els.phoneHint.textContent = "手机与电脑连接同一个 Wi-Fi，用相机扫码即可打开。图片只在本机处理，不会上传。";
      } else {
        els.phoneQr.removeAttribute("src");
        els.phoneHint.textContent = "当前服务只监听本机。请通过「启动 PixelsUndo.bat」重新打开，手机会自动获得局域网地址。";
      }
    } catch (error) {
      els.phoneUrl.textContent = "获取失败";
      els.phoneHint.textContent = "请确认本地服务仍在运行，然后重新打开这个窗口。";
    }
  }

  async function copyPhoneLink() {
    if (!phoneInfo) return;
    const text = phoneInfo.primary;
    try {
      await navigator.clipboard.writeText(text);
      toast("局域网地址已复制");
      return;
    } catch (error) {
      /* Clipboard API is unavailable on plain http LAN pages. */
    }
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    try {
      document.execCommand("copy");
      toast("局域网地址已复制");
    } catch (error) {
      toast("复制失败，请手动记下地址", "error");
    }
    area.remove();
  }

  // ------------------------------------------------------------------- update
  let updateInfo = null;
  let updateCheckedAt = 0;

  function formatDate(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  }

  function renderUpdate() {
    if (!updateInfo) return;
    const current = updateInfo.current || "1.1.0";
    els.versionLabel.textContent = `v${current}`;
    els.updateCurrent.textContent = `v${current}`;
    els.updateMark.textContent = current.split(".").slice(0, 2).join(".");
    if (!updateInfo.ok) {
      els.updateStatus.textContent = updateInfo.message || "检查更新失败，请稍后再试";
      els.updateBtn.classList.remove("has-update");
      els.openRelease.disabled = true;
      els.updateNotes.hidden = true;
      return;
    }
    if (updateInfo.has_update) {
      els.updateStatus.textContent = `发现新版本 v${updateInfo.latest}`;
      els.updateLatest.textContent = formatDate(updateInfo.published_at);
      els.updateNotesText.textContent = updateInfo.notes || "作者暂未填写更新说明。";
      els.updateNotes.hidden = false;
      els.updateBtn.classList.add("has-update");
      els.updateBtn.querySelector("#updateText").textContent = `更新 v${updateInfo.latest}`;
      els.openRelease.disabled = false;
    } else {
      els.updateStatus.textContent = "已是最新版本";
      els.updateNotes.hidden = true;
      els.updateBtn.classList.remove("has-update");
      els.updateBtn.querySelector("#updateText").textContent = "检查更新";
      els.openRelease.disabled = false;
    }
  }

  async function checkForUpdate(force = false) {
    if (els.updateStatus) els.updateStatus.textContent = "正在连接 GitHub…";
    els.updateRecheck.disabled = true;
    try {
      const response = await fetch(`/api/update${force ? "?force=1" : ""}`, { cache: "no-store" });
      const data = await response.json();
      if (!data.ok) throw new Error(data.error || "检查更新失败");
      updateInfo = data.update;
      updateCheckedAt = Date.now();
      renderUpdate();
    } catch (error) {
      els.updateStatus.textContent = "检查更新失败，请检查网络连接";
      els.updateBtn.classList.remove("has-update");
      els.openRelease.disabled = true;
    } finally {
      els.updateRecheck.disabled = false;
    }
  }

  function openUpdate() {
    els.updateModal.hidden = false;
    if (!updateInfo || Date.now() - updateCheckedAt > 600000) checkForUpdate(false);
    else renderUpdate();
  }

  // ------------------------------------------------------------------- wiring
  function bindEvents() {
    els.openBtn.addEventListener("click", () => els.fileInput.click());
    els.emptyOpen.addEventListener("click", () => els.fileInput.click());
    els.exportBtn.addEventListener("click", openExport);
    els.fitBtn.addEventListener("click", fitView);
    els.sampleBtn.addEventListener("click", () => loadSample(state.mode === "clean" ? "watermark" : "landscape"));
    if (els.sampleWatermark) {
      els.sampleWatermark.addEventListener("click", () => loadSample("watermark"));
    }
    els.quitBtn.addEventListener("click", openQuit);
    els.cancelQuit.addEventListener("click", () => { els.quitModal.hidden = true; });
    els.confirmQuit.addEventListener("click", quitApp);

    els.phoneBtn.addEventListener("click", openPhone);
    [els.closePhone, els.closePhoneFoot].forEach((button) => {
      button.addEventListener("click", () => { els.phoneModal.hidden = true; });
    });
    els.phoneModal.addEventListener("pointerdown", (event) => {
      if (event.target === els.phoneModal) els.phoneModal.hidden = true;
    });
    els.copyPhoneUrl.addEventListener("click", copyPhoneLink);
    els.openPhoneUrl.addEventListener("click", () => {
      if (phoneInfo) window.open(phoneInfo.primary, "_blank", "noopener");
    });
    els.phoneQr.addEventListener("error", () => { els.phoneQr.hidden = true; });

    els.updateBtn.addEventListener("click", openUpdate);
    els.closeUpdate.addEventListener("click", () => { els.updateModal.hidden = true; });
    els.updateModal.addEventListener("pointerdown", (event) => {
      if (event.target === els.updateModal) els.updateModal.hidden = true;
    });
    els.updateRecheck.addEventListener("click", () => checkForUpdate(true));
    els.openRelease.addEventListener("click", () => {
      const url = (updateInfo && updateInfo.url) || "https://github.com/OStonefishO/PixelsUndo/releases/latest";
      window.open(url, "_blank", "noopener");
    });

    els.fileInput.addEventListener("change", (event) => {
      const file = event.target.files && event.target.files[0];
      if (file) uploadFile(file);
      event.target.value = "";
    });

    $$("#modeSwitch .mode-btn").forEach((btn) => {
      btn.addEventListener("click", () => setMode(btn.dataset.mode));
    });

    els.pixels.addEventListener("input", () => { markManual(); updateParamLabels(); scheduleProcess(); });
    $$("#sizeChips button").forEach((btn) => {
      btn.addEventListener("click", () => {
        els.pixels.value = btn.dataset.size;
        markManual();
        updateParamLabels();
        scheduleProcess();
      });
    });
    els.palette.addEventListener("change", () => { markManual(); updateParamLabels(); scheduleProcess(); });
    els.colors.addEventListener("input", () => {
      els.colorsNumber.value = els.colors.value;
      markManual();
      updateParamLabels();
      scheduleProcess();
    });
    els.colorsNumber.addEventListener("change", () => setColorCount(els.colorsNumber.value));
    els.colorChips.addEventListener("click", (event) => {
      const btn = event.target.closest("button[data-colors]");
      if (btn) setColorCount(btn.dataset.colors);
    });
    [els.saturation, els.contrast, els.brightness, els.outline].forEach((input) => {
      input.addEventListener("input", () => { markManual(); updateParamLabels(); scheduleProcess(); });
    });
    [els.levelBlack, els.levelWhite, els.levelGamma, els.levelOutBlack, els.levelOutWhite].forEach((input) => {
      input.addEventListener("input", () => { markManual(); updateParamLabels(); scheduleProcess(); });
    });
    els.resetLevels.addEventListener("click", resetLevels);
    $$("#ditherGroup button").forEach((btn) => {
      btn.addEventListener("click", () => {
        $$("#ditherGroup button").forEach((other) => other.classList.toggle("is-active", other === btn));
        markManual();
        updateParamLabels();
        scheduleProcess();
      });
    });
    $$(".preset-card").forEach((card) => {
      card.addEventListener("click", () => applyPreset(card.dataset.preset));
    });
    els.resetPixel.addEventListener("click", resetPixelParams);

    els.toolGrid.addEventListener("click", (event) => {
      const btn = event.target.closest(".tool-btn");
      if (btn) setTool(btn.dataset.tool);
    });
    els.brushSize.addEventListener("input", () => {
      state.brush = Number(els.brushSize.value);
      updateParamLabels();
    });
    els.tolerance.addEventListener("input", updateParamLabels);
    els.applyRepair.addEventListener("click", applyRepair);
    els.undoBase.addEventListener("click", () => stepHistory(-1));
    els.redoBase.addEventListener("click", () => stepHistory(1));
    els.clearMask.addEventListener("click", () => clearMask());

    els.compareBtn.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      els.compareBtn.setPointerCapture(event.pointerId);
      setCompare(true);
    });
    ["pointerup", "pointercancel", "pointerleave"].forEach((name) => {
      els.compareBtn.addEventListener(name, () => setCompare(false));
    });

    els.zoomIn.addEventListener("click", () => zoomAt(state.W / 2 + els.stage.getBoundingClientRect().left, state.H / 2 + els.stage.getBoundingClientRect().top, 1.25));
    els.zoomOut.addEventListener("click", () => zoomAt(state.W / 2 + els.stage.getBoundingClientRect().left, state.H / 2 + els.stage.getBoundingClientRect().top, 0.8));
    els.zoomFit.addEventListener("click", fitView);
    els.zoomActual.addEventListener("click", () => {
      if (!state.session) return;
      const centerX = els.stage.getBoundingClientRect().left + state.W / 2;
      const centerY = els.stage.getBoundingClientRect().top + state.H / 2;
      const factor = 1 / state.view.scale;
      zoomAt(centerX, centerY, factor);
    });

    // export modal
    els.closeExport.addEventListener("click", () => { els.exportModal.hidden = true; });
    els.cancelExport.addEventListener("click", () => { els.exportModal.hidden = true; });
    els.exportModal.addEventListener("pointerdown", (event) => {
      if (event.target === els.exportModal) els.exportModal.hidden = true;
    });
    els.exportName.addEventListener("input", updateExportSummary);
    $$("#scaleGrid button").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.export.scale = Number(btn.dataset.scale);
        $$("#scaleGrid button").forEach((other) => other.classList.toggle("is-active", other === btn));
        updateExportSummary();
      });
    });
    $$("#formatGroup button").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.export.format = btn.dataset.format;
        $$("#formatGroup button").forEach((other) => other.classList.toggle("is-active", other === btn));
        updateExportSummary();
      });
    });
    els.doExport.addEventListener("click", doExport);

    // drag & drop
    let dragDepth = 0;
    ["dragenter", "dragover"].forEach((name) => {
      window.addEventListener(name, (event) => {
        if (!event.dataTransfer || !Array.from(event.dataTransfer.types).includes("Files")) return;
        event.preventDefault();
        if (name === "dragenter") dragDepth += 1;
        els.stage.classList.add("is-dragging");
      });
    });
    window.addEventListener("dragleave", () => {
      dragDepth = Math.max(0, dragDepth - 1);
      if (dragDepth === 0) els.stage.classList.remove("is-dragging");
    });
    window.addEventListener("drop", (event) => {
      event.preventDefault();
      dragDepth = 0;
      els.stage.classList.remove("is-dragging");
      const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
      if (file) uploadFile(file);
    });

    window.addEventListener("paste", (event) => {
      const items = event.clipboardData && event.clipboardData.items;
      if (!items) return;
      for (const item of items) {
        if (item.type.startsWith("image/")) {
          const file = item.getAsFile();
          if (file) uploadFile(file);
          break;
        }
      }
    });

    window.addEventListener("keydown", (event) => {
      const tag = (event.target.tagName || "").toLowerCase();
      const typing = tag === "input" || tag === "textarea" || tag === "select";
      if (event.key === "Escape") {
        els.exportModal.hidden = true;
        els.quitModal.hidden = true;
        els.phoneModal.hidden = true;
        els.updateModal.hidden = true;
        return;
      }
      if (typing) return;
      if (event.code === "Space") {
        event.preventDefault();
        if (!state.spaceDown) {
          state.spaceDown = true;
          els.overlay.classList.add("panning");
          hideBrushCursor();
        }
        return;
      }
      if (event.key === "c" || event.key === "C") {
        setCompare(true);
        return;
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "o") {
        event.preventDefault();
        els.fileInput.click();
        return;
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        if (state.session) openExport();
        return;
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        if (state.mode === "clean" && state.maskActions.length) undoMask();
        return;
      }
      if (state.mode === "clean") {
        if (event.key === "b" || event.key === "B") setTool("brush");
        if (event.key === "e" || event.key === "E") setTool("eraser");
        if (event.key === "w" || event.key === "W") setTool("wand");
      }
      if (event.key === "[") {
        els.brushSize.value = Math.max(6, Number(els.brushSize.value) - 4);
        state.brush = Number(els.brushSize.value);
        updateParamLabels();
      }
      if (event.key === "]") {
        els.brushSize.value = Math.min(120, Number(els.brushSize.value) + 4);
        state.brush = Number(els.brushSize.value);
        updateParamLabels();
      }
      if (event.key === "0") fitView();
    });

    window.addEventListener("keyup", (event) => {
      if (event.code === "Space") {
        state.spaceDown = false;
        els.overlay.classList.remove("panning");
      }
      if (event.key === "c" || event.key === "C") setCompare(false);
    });
    window.addEventListener("blur", () => {
      state.spaceDown = false;
      els.overlay.classList.remove("panning");
      setCompare(false);
    });

    els.stage.addEventListener("pointerleave", hideBrushCursor);
    window.addEventListener("resize", resizeCanvas);
    if (window.ResizeObserver) {
      new ResizeObserver(() => resizeCanvas()).observe(els.stage);
    }
  }

  async function init() {
    bindEvents();
    updateParamLabels();
    state.brush = Number(els.brushSize.value);
    setTool("brush");
    setMode("pixel");
    resizeCanvas();
    try {
      const health = await fetch("/api/health").then((response) => response.json());
      els.statusEngine.textContent = health.opencv ? "PIXELSUNDO · OPENCV" : "PIXELSUNDO · NUMPY";
      if (health.version) {
        els.versionLabel.textContent = `v${health.version}`;
        els.updateCurrent.textContent = `v${health.version}`;
      }
    } catch (error) {
      els.statusEngine.textContent = "PIXELSUNDO";
    }
    checkForUpdate(false);
    // First-run nudge after the empty state settles.
    window.setTimeout(() => {
      if (!state.session) els.statusMessage.textContent = "等待打开图片";
    }, 600);

    // Convenience deep links: ?demo=landscape|watermark&mode=clean|pixel
    const query = new URLSearchParams(window.location.search);
    const demo = query.get("demo");
    const demoMode = query.get("mode");
    if (demoMode === "clean" || demoMode === "pixel") setMode(demoMode);
    if (demo === "landscape" || demo === "watermark") {
      await loadSample(demo);
      if (demo === "watermark") setMode("clean");
      fitView();
    }
  }

  if ("serviceWorker" in navigator && window.isSecureContext) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }

  init();
})();
