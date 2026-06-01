/* ============================================================
   PulmoAgent — GUI Demo / app.js
   Author: 程炜  2022021006000102  杭州电子科技大学
   Pipeline state machine + animation driver
   ============================================================ */

(() => {
  // ---------- shorthand ----------
  const $  = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));

  // ---------- global state ----------
  let DATA = null;      // cases.json
  let DEBATES = null;   // debates.json
  let KG = null;        // kg.json

  let caseObj = null;
  let debateObj = null;

  let stage = 0;         // 0..5
  let playing = false;
  let abortToken = 0;    // increments on reset/case-switch to abort in-flight stage anims
  let speed = 2;

  // ---------- constants ----------
  const STAGE_LABELS = ["数据输入", "SAT 分割", "SCR 量化", "GraphRAG 检索", "多智能体辩论", "最终诊断"];

  // mock slice counts per case (slightly varied)
  const SLICE_COUNTS = {
    "P_2026_0142": 512,
    "P_2026_0203": 384,
    "C_2026_0087": 640,
    "B_2026_0044": 512
  };

  const LOAD_PIPELINE = [
    { text: "读取 DICOM 序列 (.dcm × N)",  step: 0, dur: 0 },
    { text: "重采样至 1.0 × 1.0 × 1.0 mm", step: 1, dur: 380 },
    { text: "HU 范围裁剪 [−1024, +600]",   step: 2, dur: 320 },
    { text: "Lung ROI 自动定位 (3D bbox)", step: 3, dur: 380 },
    { text: "送入 SAT-Nano 推理流水线",    step: 4, dur: 360 }
  ];

  const SEG_ORDER = [
    { leg: "lung",   ids: ["anat-lung-l", "anat-lung-r"],   labels: ["lbl-lung-l", "lbl-lung-r"], pct: "21.4%" },
    { leg: "airway", ids: ["anat-airway", "anat-airway2"],  labels: ["lbl-airway"],               pct: "0.6%"  },
    { leg: "pa",     ids: ["anat-pa"],                       labels: ["lbl-pa"],                   pct: "0.9%"  },
    { leg: "aa",     ids: ["anat-aa"],                       labels: ["lbl-aa"],                   pct: "0.5%"  },
    { leg: "pv",     ids: ["anat-pv", "anat-pv2"],           labels: ["lbl-pv"],                   pct: "0.4%"  },
    { leg: "ra",     ids: ["anat-ra"],                       labels: ["lbl-ra"],                   pct: "1.3%"  },
    { leg: "rv",     ids: ["anat-rv"],                       labels: ["lbl-rv"],                   pct: "1.5%"  },
    { leg: "lv",     ids: ["anat-lv"],                       labels: ["lbl-lv"],                   pct: "1.8%"  }
  ];

  const SCR_FORMULAS = [
    { tag: "STRUCT",  name: "PA/AO 比值", src: "(3.1) ESC/ERS 2022",   math: "PA/AO = d(MPA) / d(Asc.Aorta)", key: "PA_AO_ratio", thresh: 1.0  },
    { tag: "STRUCT",  name: "RV/LV 比值", src: "(3.2) ATS/ERS PH-CLD", math: "RV/LV = d(RV) / d(LV)",        key: "RV_LV_ratio", thresh: 1.0  },
    { tag: "DENSITY", name: "%LAA-950",   src: "(3.3) GOLD 2024",       math: "100 · |{v: HU(v) < −950}| / |lung|", key: "LAA_950_pct", thresh: 20.0 },
    { tag: "DENSITY", name: "MLD",        src: "(3.4) GOLD 2024",       math: "mean( HU(v) | v ∈ lung )",      key: "MLD_HU",     thresh: -870, dir: "lt" },
    { tag: "VESSEL",  name: "BV5/TBV",    src: "(3.5) PVRI WSPH",       math: "V(vessel; r<2.5 mm) / V(vessel; total)", key: "BV5_ratio", thresh: 0.20, dir: "lt" }
  ];

  // SCR right-panel rows — k:label, unit, ref
  const SCR_DEF = {
    struct: [
      { k: "PA_d_mm",     label: "PA 直径",     unit: "mm",  ref: "≤29",      dir: "hi" },
      { k: "AO_d_mm",     label: "AO 直径",     unit: "mm",  ref: "—" },
      { k: "PA_AO_ratio", label: "PA/AO",       unit: "",    ref: ">1.0 ⚠",   dir: "hi", thresh: 1.0 },
      { k: "RPA_d_mm",    label: "RPA 直径",    unit: "mm",  ref: "≤24" },
      { k: "RV_d_mm",     label: "RV 直径",     unit: "mm",  ref: "—" },
      { k: "LV_d_mm",     label: "LV 直径",     unit: "mm",  ref: "—" },
      { k: "RV_LV_ratio", label: "RV/LV",       unit: "",    ref: ">1.0 ⚠",   dir: "hi", thresh: 1.0 },
      { k: "RA_a_mm",     label: "RA 大径",     unit: "mm",  ref: "≤45" }
    ],
    density: [
      { k: "LAA_950_pct", label: "%LAA-950",    unit: "%",   ref: "≥20% ⚠",   dir: "hi", thresh: 20 },
      { k: "LAA_856_pct", label: "%LAA-856",    unit: "%",   ref: "≥30% ⚠",   dir: "hi", thresh: 30 },
      { k: "MLD_HU",      label: "MLD",         unit: "HU",  ref: "<−870 ⚠",  dir: "lo", thresh: -870 },
      { k: "is_dual_phase", label: "双相",      unit: "",    ref: "—" }
    ],
    vessel: [
      { k: "BV5_mL",      label: "BV5",         unit: "mL",  ref: "—" },
      { k: "BV10_mL",     label: "BV10",        unit: "mL",  ref: "—" },
      { k: "BV5_ratio",   label: "BV5/TBV",     unit: "",    ref: "<0.20 ⚠",  dir: "lo", thresh: 0.20 },
      { k: "TAC",         label: "TAC",         unit: "mm",  ref: "≥10",      dir: "lo", thresh: 10 },
      { k: "branches",    label: "血管分支数",   unit: "",    ref: "—" },
      { k: "pa_wall_calcification", label: "PA 壁钙化", unit: "", ref: "—" }
    ]
  };

  // agent class shortcut
  const AGENT_CLASS = {
    "PulmonologistAgent": { cls: "pulmo",  short: "P", name: "PulmonologistAgent" },
    "CardiologistAgent":  { cls: "cardio", short: "C", name: "CardiologistAgent"  },
    "RadiologistAgent":   { cls: "radio",  short: "R", name: "RadiologistAgent"   }
  };

  // ============================================================
  // boot
  // ============================================================
  document.addEventListener("DOMContentLoaded", boot);

  async function boot() {
    try {
      const [c, d, k] = await Promise.all([
        fetch("data/cases.json").then(r => r.json()),
        fetch("data/debates.json").then(r => r.json()),
        fetch("data/kg.json").then(r => r.json())
      ]);
      DATA = c; DEBATES = d; KG = k;
    } catch (err) {
      console.error("[PulmoAgent] data load failed:", err);
      document.body.insertAdjacentHTML("beforeend",
        `<div style="position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);
          padding:20px;background:#1c0a14;color:#ff8aa3;border:1px solid #ef4f6c;
          border-radius:8px;font-family:monospace;font-size:13px;">
          数据加载失败 — 请通过本地 HTTP 服务器打开 (例如：<br/>
          <code>python -m http.server 8080</code><br/>
          然后访问 <code>http://localhost:8080</code>)
        </div>`);
      return;
    }
    populateCases();
    renderSystemCard();
    renderFileList();
    selectCase(DATA.cases[0].id);
    wireControls();
    renderStaticKG();
    renderFormulas();

    // optional autoplay via ?autoplay=1 or ?stage=N (for screenshots / demo recording)
    const params = new URLSearchParams(location.search);
    if (params.get("case")) selectCase(params.get("case"));
    if (params.get("speed")) { speed = parseFloat(params.get("speed")); $("#speed").value = speed; }
    if (params.get("autoplay")) {
      setTimeout(() => run(0), 200);
    }
  }

  // ============================================================
  // left rail — case picker / patient / system
  // ============================================================
  function populateCases() {
    const sel = $("#case-select");
    sel.innerHTML = "";
    DATA.cases.forEach(c => {
      const tag = c.ground_truth === "COPD-PH" ? "PH" : "COPD";
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = `[${tag}] ${c.display_id} · ${c.patient.age}岁${c.patient.sex} · ${c.patient.presenting.slice(0,14)}`;
      sel.appendChild(opt);
    });
    sel.addEventListener("change", e => selectCase(e.target.value));
  }

  function renderPatient() {
    const p = caseObj.patient;
    const gtCls = caseObj.ground_truth === "COPD-PH" ? "" : "copd";
    $("#patient-card").innerHTML = `
      <div class="patient-row"><span class="k">case_id</span><span class="v">${caseObj.display_id}</span></div>
      <div class="patient-row"><span class="k">年龄 / 性别</span><span class="v">${p.age} 岁 / ${p.sex}</span></div>
      <div class="patient-row"><span class="k">吸烟史</span><span class="v">${p.pack_years} pk·yr · ${p.smoking}</span></div>
      <div class="patient-row"><span class="k">slice</span><span class="v">${caseObj.scan_metadata.slice_thickness_mm} mm</span></div>
      <div class="patient-row"><span class="k">设备</span><span class="v">${caseObj.scan_metadata.manufacturer.split(" ")[0]}</span></div>
      <div class="patient-row" style="grid-column: 1 / -1; flex-direction:column; align-items:flex-start; gap:3px;">
        <span class="k">主诉</span>
        <span class="v" style="font-size:11.5px; line-height:1.5; font-family: var(--sans); color: var(--text-soft);">${p.presenting}</span>
      </div>
      <div class="patient-row gt">
        <span class="k">Ground Truth</span>
        <span class="gt-badge ${gtCls}">${caseObj.ground_truth}</span>
      </div>
    `;
  }

  function renderSystemCard() {
    const s = DATA.system, k = DATA.kg_stats;
    $("#system-card").innerHTML = `
      <div class="row"><span class="k">SAT</span><span class="v">${s.sat_model.split(" ")[0]}</span></div>
      <div class="row"><span class="k">RAG</span><span class="v">${k.nodes} · ${k.edges}</span></div>
      <div class="row"><span class="k">LLM</span><span class="v">GPT-4o / Sonnet-4.5</span></div>
      <div class="row"><span class="k">GPU</span><span class="v">2× RTX 3090</span></div>
    `;
  }

  // ============================================================
  // case switch
  // ============================================================
  function selectCase(id) {
    caseObj = DATA.cases.find(c => c.id === id);
    debateObj = DEBATES[id];
    if (!caseObj || !debateObj) { console.error("[PulmoAgent] unknown case", id); return; }
    $("#case-select").value = id;
    abortToken++;
    playing = false;
    setPlayBtn();
    renderPatient();
    renderDicomTags();
    syncFileSelection();
    resetStages();
    renderStaticSCR();         // right panel — empty
    $("#scr-json-name").textContent = `SCR · ${caseObj.id}.json`;
  }

  function renderFileList() {
    const host = $("#dicom-files");
    host.innerHTML = "";
    DATA.cases.forEach(c => {
      const n = SLICE_COUNTS[c.id] || 512;
      const isPH = c.ground_truth === "COPD-PH";
      const row = document.createElement("div");
      row.className = "file-row";
      row.dataset.case = c.id;
      row.innerHTML = `
        <div class="ficon">📁</div>
        <div class="fmain">
          <div class="fname">${c.id}/  (${n} × .dcm)</div>
          <div class="fmeta">${c.scan_metadata.manufacturer} · ${c.scan_metadata.slice_thickness_mm} mm · ${c.scan_metadata.phase}</div>
        </div>
        <div class="ftag ${isPH ? "" : "copd"}">${c.ground_truth}</div>
      `;
      row.addEventListener("click", () => selectCase(c.id));
      host.appendChild(row);
    });
  }

  function syncFileSelection() {
    $$("#dicom-files .file-row").forEach(r => {
      r.classList.toggle("selected", r.dataset.case === caseObj.id);
    });
    $("#loader-path").textContent = `/data/dicom/2026/${caseObj.id}/`;
  }

  function renderDicomTags() {
    const m = caseObj.scan_metadata, p = caseObj.patient;
    $("#dt-pid").textContent   = caseObj.id;
    $("#dt-age").textContent   = `${p.age}Y`;
    $("#dt-sex").textContent   = p.sex === "男" ? "M" : "F";
    $("#dt-manuf").textContent = m.manufacturer;
    $("#dt-st").textContent    = `${m.slice_thickness_mm} mm`;
    $("#dt-n").textContent     = `${SLICE_COUNTS[caseObj.id] || 512}`;
  }

  // ============================================================
  // stage / scene transitions
  // ============================================================
  function setStage(n) {
    stage = n;
    // timeline
    $$(".timeline li").forEach(li => {
      const s = +li.dataset.stage;
      li.classList.toggle("active", s === n);
      li.classList.toggle("done",   s < n);
    });
    // tabs
    $$(".stage-tab").forEach(t => {
      const s = +t.dataset.stage;
      t.classList.toggle("active", s === n);
      t.classList.toggle("done",   s < n);
    });
    // scenes — stage N shows scene N (0..5)
    $$(".scene").forEach(sc => {
      const s = +sc.dataset.scene;
      sc.classList.toggle("active", s === n);
    });
    // progress — total 5 main stages after input; show 0/5 .. 5/5
    $("#prog-fill").style.width = `${(n / 5) * 100}%`;
    $("#prog-label").textContent = `STAGE ${n} / 5 · ${STAGE_LABELS[n]}`;
  }

  function resetStages() {
    setStage(0);
    // scene 0 — loader reset
    $$(".lp-step").forEach(s => { s.classList.remove("active", "done"); });
    $("#load-bar-fill").style.width = "0%";
    $("#load-text").textContent = "等待用户载入扫描 — 请点选左侧 DICOM 序列后载入";
    $("#load-text").classList.remove("done");
    $("#scan-line").classList.remove("on");
    $("#scan-line").style.top = "0%";
    $("#scan-label").textContent = `SLICE 000 / ${SLICE_COUNTS[caseObj.id] || 512} · WAITING`;
    // scene 1
    SEG_ORDER.forEach(s => {
      s.ids.forEach(id => $("#" + id).classList.remove("detected", s.leg));
      $$(`.legend-item[data-leg="${s.leg}"]`).forEach(el => { el.classList.remove("on"); el.querySelector(".pct").textContent = "—"; });
    });
    $$(".anat-label").forEach(l => l.classList.remove("shown"));
    $("#seg-progress").textContent = "0 / 8";
    // scene 2
    $("#scr-json").textContent = "";
    $$("#formula-list .formula-row").forEach(r => {
      r.classList.remove("shown");
      const res = r.querySelector(".math .result"); if (res) res.textContent = "—";
      const ineq = r.querySelector(".math .ineq"); if (ineq) ineq.textContent = "";
    });
    // right SCR rows
    $$(".scr-row").forEach(r => r.classList.remove("shown"));
    // scene 3
    $$("#kg-svg .kg-edge").forEach(e => e.classList.remove("hl"));
    $$("#kg-svg .kg-node-disease, #kg-svg .kg-node-indicator, #kg-svg .kg-node-concept, #kg-svg .kg-node-source").forEach(n => n.classList.remove("hl"));
    $("#kg-chunks").innerHTML = "";
    $("#kg-retrieved").textContent = "0";
    // scene 4
    $("#mdt-rounds").innerHTML = "";
    $("#coord-state").innerHTML = `ROUND <span class="vote">—</span> · WAITING`;
    // scene 5
    $("#verdict-title").textContent = "—";
    $("#verdict-conf-num").textContent = "0.00";
    $("#verdict-conf-fill").style.width = "0%";
    $("#verdict-ev").innerHTML = "";
    $("#vm-round").textContent = "—";
    $("#vm-trace").textContent = "—";
    $("#vm-fb").textContent = "false";
    $("#gt-v").textContent = "—"; $("#gt-v").className = "v";
    $("#pred-v").textContent = "—"; $("#pred-v").className = "v";
    $("#match-text").textContent = "—"; $("#match-text").className = "verdict-match";
    $("#fallback-card").classList.remove("shown");
    $("#fallback-text").textContent = "—";
    $("#verdict-main").classList.remove("copd");
  }

  // ============================================================
  // SCENE 0 — DICOM input / CT loader
  // ============================================================
  async function playStage0(tok) {
    setStage(0);
    const total = SLICE_COUNTS[caseObj.id] || 512;
    $("#load-text").classList.remove("done");
    $("#scan-line").classList.add("on");

    // Step 0: read DICOM — animate scan line + slice counter + bar
    const steps = $$(".lp-step");
    steps.forEach(s => s.classList.remove("active", "done"));
    steps[0].classList.add("active");
    $("#load-text").textContent = LOAD_PIPELINE[0].text;

    const stepDur = 1100 / speed;
    const startT = performance.now();
    await new Promise(resolve => {
      const tick = () => {
        if (tok !== abortToken) { resolve(); return; }
        const t = Math.min(1, (performance.now() - startT) / stepDur);
        const cur = Math.floor(t * total);
        $("#scan-label").textContent = `SLICE ${String(cur).padStart(3,"0")} / ${total} · READING`;
        $("#load-bar-fill").style.width = `${t * 40}%`;       // 0→40% during scan
        $("#scan-line").style.top = `${(t * 100) % 100}%`;
        if (t < 1) requestAnimationFrame(tick); else resolve();
      };
      requestAnimationFrame(tick);
    });
    if (tok !== abortToken) return;
    steps[0].classList.remove("active"); steps[0].classList.add("done");
    $("#scan-label").textContent = `SLICE ${total} / ${total} · OK`;

    // Steps 1..4 — discrete pipeline ticks
    let progress = 40;
    for (let i = 1; i < LOAD_PIPELINE.length; i++) {
      if (tok !== abortToken) return;
      steps[i].classList.add("active");
      $("#load-text").textContent = LOAD_PIPELINE[i].text;
      await sleep(LOAD_PIPELINE[i].dur / speed);
      steps[i].classList.remove("active");
      steps[i].classList.add("done");
      progress += 60 / (LOAD_PIPELINE.length - 1);
      $("#load-bar-fill").style.width = `${Math.min(progress, 100)}%`;
    }

    $("#load-bar-fill").style.width = `100%`;
    $("#load-text").textContent = `✓ 数据预处理完成 — 启动 SAT-Nano 分割`;
    $("#load-text").classList.add("done");
    $("#scan-line").classList.remove("on");
    await sleep(450 / speed);
  }

  // ============================================================
  // SCENE 1 — SAT-Nano segmentation
  // ============================================================
  async function playStage1(tok) {
    setStage(1);
    let count = 0;
    for (const seg of SEG_ORDER) {
      if (tok !== abortToken) return;
      // toggle shape + legend
      seg.ids.forEach(id => {
        const el = $("#" + id);
        el.classList.add("detected", seg.leg);
      });
      seg.labels.forEach(id => $("#" + id).classList.add("shown"));
      $$(`.legend-item[data-leg="${seg.leg}"]`).forEach(el => {
        el.classList.add("on");
        el.querySelector(".pct").textContent = seg.pct;
      });
      count++;
      $("#seg-progress").textContent = `${count} / 8`;
      await sleep(420 / speed);
    }
    await sleep(380 / speed);
  }

  // ============================================================
  // SCENE 2 — SCR computation
  // ============================================================
  function renderFormulas() {
    const host = $("#formula-list"); host.innerHTML = "";
    SCR_FORMULAS.forEach(f => {
      const row = document.createElement("div");
      row.className = "formula-row";
      row.dataset.key = f.key;
      row.innerHTML = `
        <div class="title">
          <span class="tag">${f.tag}</span>
          <span class="name">${f.name}</span>
          <span class="src">${f.src}</span>
        </div>
        <div class="math">${escapeHTML(f.math)} = <span class="result">—</span> <span class="ineq"></span></div>
      `;
      host.appendChild(row);
    });
  }

  function renderStaticSCR() {
    // empty placeholders for each section row
    for (const [section, defs] of Object.entries(SCR_DEF)) {
      const host = $("#scr-" + section);
      host.innerHTML = "";
      defs.forEach(d => {
        const row = document.createElement("div");
        row.className = "scr-row";
        row.dataset.key = d.k;
        row.innerHTML = `
          <span class="k">${d.label}</span>
          <span class="v"><span class="val">—</span><span class="unit">${d.unit ? " " + d.unit : ""}</span></span>
          <span class="ref">${d.ref || ""}</span>
        `;
        host.appendChild(row);
      });
    }
    // qualitative — case-specific, rendered when scene 2 runs
    $("#scr-qual").innerHTML = "";
  }

  function fmtNum(v) {
    if (typeof v === "number") return Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(2);
    if (v === true)  return "true";
    if (v === false) return "false";
    if (v == null)   return "—";
    return String(v);
  }

  function flagFor(def, v) {
    if (def.thresh == null) return null;
    if (def.dir === "hi" && v > def.thresh) return "flag-hi";
    if (def.dir === "lo" && v < def.thresh) return "flag-hi"; // lo means: less than thresh is BAD
    return null;
  }

  function fillScrSection(section, sourceObj) {
    const defs = SCR_DEF[section];
    defs.forEach((d, i) => {
      const row = $(`#scr-${section} .scr-row[data-key="${d.k}"]`);
      if (!row) return;
      const v = sourceObj[d.k];
      row.querySelector(".val").textContent = fmtNum(v);
      const flag = flagFor(d, v);
      if (flag) row.classList.add(flag);
    });
  }

  async function playStage2(tok) {
    setStage(2);
    // 1) render formulas one by one with computed values
    const struct  = caseObj.structural_metrics;
    const density = caseObj.density_metrics;
    const vessel  = caseObj.vessel_tree_metrics;

    const valFor = (key) => {
      if (key in struct)  return struct[key];
      if (key in density) return density[key];
      if (key in vessel)  return vessel[key];
      return null;
    };

    let jsonAccum = "{\n";
    const append = (frag) => { $("#scr-json").innerHTML += frag; };

    // top-level header
    append(colorJSON(`  "case_id": ${JSON.stringify(caseObj.id)},\n`));
    append(colorJSON(`  "schema_version": "3.3",\n`));

    // ---- structural_metrics ----
    append(colorJSON(`  "structural_metrics": {\n`));
    for (const d of SCR_DEF.struct) {
      if (tok !== abortToken) return;
      const v = struct[d.k];
      // mark formula if matches
      const f = SCR_FORMULAS.find(f => f.key === d.k);
      if (f) {
        const row = $(`.formula-row[data-key="${d.key || ""}"]`) || $(`.formula-row[data-key="${f.key}"]`);
        showFormula(f, v);
      }
      // right panel scr row
      const row = $(`#scr-struct .scr-row[data-key="${d.k}"]`);
      if (row) {
        row.classList.add("shown");
        row.querySelector(".val").textContent = fmtNum(v);
        const flag = flagFor(d, v); if (flag) row.classList.add(flag);
      }
      append(colorJSON(`    "${d.k}": ${fmtJSONVal(v)},\n`, true));
      await sleep(140 / speed);
    }
    append(colorJSON(`  },\n`));

    // ---- density_metrics ----
    append(colorJSON(`  "density_metrics": {\n`));
    for (const d of SCR_DEF.density) {
      if (tok !== abortToken) return;
      const v = density[d.k];
      const f = SCR_FORMULAS.find(f => f.key === d.k);
      if (f) showFormula(f, v);
      const row = $(`#scr-density .scr-row[data-key="${d.k}"]`);
      if (row) {
        row.classList.add("shown");
        row.querySelector(".val").textContent = fmtNum(v);
        const flag = flagFor(d, v); if (flag) row.classList.add(flag);
      }
      append(colorJSON(`    "${d.k}": ${fmtJSONVal(v)},\n`, true));
      await sleep(140 / speed);
    }
    append(colorJSON(`  },\n`));

    // ---- vessel_tree_metrics ----
    append(colorJSON(`  "vessel_tree_metrics": {\n`));
    for (const d of SCR_DEF.vessel) {
      if (tok !== abortToken) return;
      const v = vessel[d.k];
      const f = SCR_FORMULAS.find(f => f.key === d.k);
      if (f) showFormula(f, v);
      const row = $(`#scr-vessel .scr-row[data-key="${d.k}"]`);
      if (row) {
        row.classList.add("shown");
        row.querySelector(".val").textContent = fmtNum(v);
        const flag = flagFor(d, v); if (flag) row.classList.add(flag);
      }
      append(colorJSON(`    "${d.k}": ${fmtJSONVal(v)},\n`, true));
      await sleep(140 / speed);
    }
    append(colorJSON(`  },\n`));

    // ---- qualitative_findings ----
    append(colorJSON(`  "qualitative_findings": {\n`));
    const qualHost = $("#scr-qual");
    qualHost.innerHTML = "";
    const qualEntries = Object.entries(caseObj.qualitative_findings);
    for (const [k, v] of qualEntries) {
      if (tok !== abortToken) return;
      const row = document.createElement("div");
      row.className = "scr-row shown";
      row.innerHTML = `
        <span class="k">${k}</span>
        <span class="v" style="text-align:right; max-width:60%; white-space:normal;">${v}</span>
      `;
      qualHost.appendChild(row);
      append(colorJSON(`    "${k}": ${JSON.stringify(v)},\n`, true));
      await sleep(140 / speed);
    }
    append(colorJSON(`  }\n}\n`));
    // auto-scroll to bottom
    const json = $("#scr-json");
    json.scrollTop = json.scrollHeight;
    await sleep(380 / speed);
  }

  function showFormula(f, v) {
    const row = $(`#formula-list .formula-row[data-key="${f.key}"]`);
    if (!row) return;
    row.classList.add("shown");
    const res = row.querySelector(".math .result");
    const ineq = row.querySelector(".math .ineq");
    res.textContent = fmtNum(v);
    let mark = "";
    if (f.thresh != null) {
      const bad = (f.dir === "lt") ? (v < f.thresh) : (v > f.thresh);
      const cmp = (f.dir === "lt") ? "<" : ">";
      if (bad) mark = `  ${cmp} ${f.thresh}  ⚠`;
      else     mark = ``;
    }
    ineq.textContent = mark;
  }

  function fmtJSONVal(v) {
    if (typeof v === "string")  return `<span class="str">${JSON.stringify(v)}</span>`;
    if (typeof v === "number")  return `<span class="num">${v}</span>`;
    if (typeof v === "boolean") return `<span class="bool">${v}</span>`;
    if (v === null)             return `<span class="null">null</span>`;
    return JSON.stringify(v);
  }

  function colorJSON(text, highlight = false) {
    // crude tokenizer for key strings: "abc":
    let out = escapeHTML(text)
      .replace(/&quot;([\w\-]+)&quot;:/g, (m, k) => `<span class="k">"${k}"</span>:`);
    if (highlight) out = `<span class="hl">${out}</span>`;
    return out;
  }

  function escapeHTML(s) {
    return s.replace(/[&<>"']/g, c => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  }

  // ============================================================
  // SCENE 3 — PulmoKG / GraphRAG
  // ============================================================
  function renderStaticKG() {
    const svg = $("#kg-svg");
    const W = 1000, H = 600;
    // pre-compute pixel positions
    KG.nodes.forEach(n => { n.px = 30 + n.x * (W - 60); n.py = 40 + n.y * (H - 80); });

    let edgeHTML = "";
    KG.edges.forEach((e, i) => {
      const from = KG.nodes.find(n => n.id === e.from);
      const to   = KG.nodes.find(n => n.id === e.to);
      if (!from || !to) return;
      // curve slightly
      const mx = (from.px + to.px) / 2;
      const my = (from.py + to.py) / 2 - 18;
      edgeHTML += `<path class="kg-edge" data-from="${e.from}" data-to="${e.to}" d="M ${from.px} ${from.py} Q ${mx} ${my} ${to.px} ${to.py}" />`;
    });

    let nodeHTML = "";
    KG.nodes.forEach(n => {
      nodeHTML += `<circle class="kg-node-${n.type}" data-id="${n.id}" cx="${n.px}" cy="${n.py}" r="${n.size}"/>`;
      nodeHTML += `<text class="kg-node-text" x="${n.px}" y="${n.py + n.size + 12}">${escapeHTML(n.label)}</text>`;
    });

    svg.innerHTML = edgeHTML + nodeHTML;
  }

  async function playStage3(tok) {
    setStage(3);
    // clear previous highlights
    $$("#kg-svg .kg-edge").forEach(e => e.classList.remove("hl"));
    $$("#kg-svg circle").forEach(c => c.classList.remove("hl"));
    $("#kg-chunks").innerHTML = "";
    $("#kg-retrieved").textContent = "0";

    const chunks = debateObj.kg_retrieval;
    let count = 0;
    for (const ch of chunks) {
      if (tok !== abortToken) return;
      count++;
      $("#kg-retrieved").textContent = String(count);
      // highlight node corresponding to chunk (rough match)
      const target = guessKgNode(ch);
      if (target) {
        const node = $(`#kg-svg circle[data-id="${target}"]`);
        if (node) node.classList.add("hl");
        $$(`#kg-svg .kg-edge[data-to="${target}"], #kg-svg .kg-edge[data-from="${target}"]`).forEach(p => p.classList.add("hl"));
      }
      // append chunk card
      const card = document.createElement("div");
      card.className = "kg-chunk";
      card.innerHTML = `
        <div class="head">
          <span class="id">${ch.id}</span>
          <span class="src">${ch.source}</span>
          <span class="score">score=${ch.score.toFixed(2)}</span>
        </div>
        <div class="body">${escapeHTML(ch.chunk)}</div>
        <div class="supports">supports → <b>${escapeHTML(ch.supports)}</b></div>
      `;
      $("#kg-chunks").appendChild(card);
      requestAnimationFrame(() => card.classList.add("shown"));
      await sleep(540 / speed);
    }
    await sleep(380 / speed);
  }

  function guessKgNode(chunk) {
    // prefer explicit node_id emitted by the real GraphRAG backend
    if (chunk.node_id) return chunk.node_id;
    const c = chunk.chunk.toLowerCase();
    if (chunk.id.includes("0418") || c.includes("laa-950") || c.includes("肺气肿"))   return "LAA_950";
    if (chunk.id.includes("0926") || c.includes("pa/ao"))                              return "PA_AO";
    if (chunk.id.includes("1107") || c.includes("rv/lv"))                              return "RV_LV";
    if (chunk.id.includes("1503") || c.includes("bv5"))                                return "BV5";
    if (chunk.id.includes("0312") || c.includes("out-of-proportion"))                  return "COPD-PH";
    if (chunk.id.includes("0712") || c.includes("钙化"))                               return "PA_CALC";
    if (chunk.id.includes("0612"))                                                      return "EMPHYSEMA";
    if (chunk.id.includes("1812") || c.includes("cteph"))                              return "CTEPH";
    return null;
  }

  // ============================================================
  // SCENE 4 — multi-agent MDT debate
  // ============================================================
  async function playStage4(tok) {
    setStage(4);
    $("#mdt-rounds").innerHTML = "";

    const rounds = debateObj.rounds;
    for (let i = 0; i < rounds.length; i++) {
      if (tok !== abortToken) return;
      const r = rounds[i];
      $("#coord-state").innerHTML = `ROUND <span class="vote">${r.round}</span> · DELIBERATING`;

      // container
      const block = document.createElement("div");
      block.className = "round-block";
      block.innerHTML = `
        <div class="round-head">
          <span class="badge">ROUND ${r.round}</span>
          <span class="vote-result">vote · pending</span>
        </div>
        <div class="round-grid"></div>
        <div class="round-synth" style="display:none;">
          <span class="lead">SYNTHESIS</span><span class="synth-text"></span>
        </div>
      `;
      $("#mdt-rounds").appendChild(block);
      requestAnimationFrame(() => block.classList.add("shown"));
      block.scrollIntoView({ behavior: "smooth", block: "end" });

      const grid = block.querySelector(".round-grid");

      for (const resp of r.responses) {
        if (tok !== abortToken) return;
        const meta = AGENT_CLASS[resp.agent] || { cls: "pulmo", short: "?", name: resp.agent };
        const card = document.createElement("div");
        card.className = `agent-msg ${meta.cls}`;
        card.innerHTML = `
          <div class="agent-head">
            <div class="agent-avatar ${meta.cls}">${meta.short}</div>
            <span class="name">${meta.name}</span>
            <span class="agent-claim" data-claim="${resp.claim}">${resp.claim}</span>
          </div>
          <div class="conf-bar"><div class="fill" style="width:0%"></div></div>
          <div class="conf-text">
            <span>confidence = <b>${resp.confidence.toFixed(2)}</b></span>
            <span class="control ${resp.control}">${resp.control}</span>
          </div>
          <ul class="agent-ev">
            ${resp.evidence.map(e => `<li>${escapeHTML(e)}</li>`).join("")}
          </ul>
          <div class="agent-cot"><span class="tag">CoT</span>${escapeHTML(resp.cot)}</div>
        `;
        grid.appendChild(card);
        await sleep(40);
        card.classList.add("shown");
        // animate confidence bar
        const fill = card.querySelector(".conf-bar .fill");
        requestAnimationFrame(() => { fill.style.width = `${resp.confidence * 100}%`; });
        await sleep(700 / speed);
      }

      // vote
      const voteStr = Object.entries(r.vote).map(([k,v]) => `${k}=${v}`).join(" / ");
      const winner = Object.entries(r.vote).sort((a,b) => b[1]-a[1])[0];
      const reachedConsensus = winner[1] >= Math.ceil(r.responses.length / 2 + (r.responses.length % 2 === 0 ? 1 : 0));
      // ≥⌈n/2⌉ with n=3 → ≥2
      const need = Math.ceil(r.responses.length / 2);
      const ok = winner[1] >= need + (r.responses.length === 3 ? 0 : 0); // for n=3, need 2; here ⌈3/2⌉ = 2
      block.querySelector(".vote-result").innerHTML =
        `vote · <b>${voteStr}</b> ${winner[1] >= 2 ? "✓" : "✗"}`;

      const synthBox = block.querySelector(".round-synth");
      synthBox.style.display = "block";
      synthBox.querySelector(".synth-text").textContent = " " + r.synthesis;

      $("#coord-state").innerHTML = `ROUND <span class="vote">${r.round}</span> · ${winner[1] >= 2 ? "CONSENSUS ✓" : "NO CONSENSUS"}`;
      await sleep(780 / speed);
    }

    $("#coord-state").innerHTML = `ROUND <span class="vote">${rounds.length}</span> · COMPLETE`;
    await sleep(400 / speed);
  }

  // ============================================================
  // SCENE 5 — verdict
  // ============================================================
  async function playStage5(tok) {
    setStage(5);
    const f = debateObj.final;
    const isPH = f.diagnosis === "COPD-PH";
    const verdictMain = $("#verdict-main");
    verdictMain.classList.toggle("copd", !isPH);

    $("#verdict-title").textContent = f.diagnosis;

    // confidence animate
    const num = $("#verdict-conf-num");
    const fill = $("#verdict-conf-fill");
    fill.style.width = "0%";
    let acc = 0; const target = f.confidence;
    const dur = 1000 / speed; const t0 = performance.now();
    await new Promise(resolve => {
      const tick = () => {
        if (tok !== abortToken) { resolve(); return; }
        const t = Math.min(1, (performance.now() - t0) / dur);
        const v = target * easeOut(t);
        num.textContent = v.toFixed(2);
        fill.style.width = `${v * 100}%`;
        if (t < 1) requestAnimationFrame(tick); else resolve();
      };
      requestAnimationFrame(tick);
    });

    // evidence chain
    const ev = $("#verdict-ev"); ev.innerHTML = "";
    for (const e of f.evidence_chain) {
      if (tok !== abortToken) return;
      const li = document.createElement("li");
      li.textContent = e;
      ev.appendChild(li);
      await sleep(160 / speed);
    }

    $("#vm-round").textContent = String(caseObj.consensus_round);
    $("#vm-trace").textContent = f.trace_id;
    $("#vm-fb").textContent    = String(!!f.fallback_triggered);

    // GT compare
    const gt = caseObj.ground_truth;
    const pred = f.diagnosis;
    const gtCls = gt === "COPD-PH" ? "ph" : "copd";
    const predCls = pred === "COPD-PH" ? "ph" : "copd";
    const gtV = $("#gt-v"); gtV.textContent = gt; gtV.className = `v ${gtCls}`;
    const predV = $("#pred-v"); predV.textContent = pred; predV.className = `v ${predCls}`;
    const match = $("#match-text");
    if (gt === pred) {
      match.textContent = `✓ 与 Ground Truth 一致`;
      match.className = "verdict-match";
    } else {
      match.textContent = `✗ 与 Ground Truth 不一致`;
      match.className = "verdict-match miss";
    }

    if (f.fallback_triggered) {
      $("#fallback-card").classList.add("shown");
      $("#fallback-text").textContent = f.fallback_recommendation || "建议人工复核";
    }
  }

  function easeOut(t) { return 1 - Math.pow(1 - t, 3); }

  // ============================================================
  // pipeline runner
  // ============================================================
  async function run(fromStage = 0) {
    abortToken++; const tok = abortToken;
    playing = true; setPlayBtn();

    if (fromStage <= 0) { await playStage0(tok); if (tok !== abortToken) return; }
    if (fromStage <= 1) { await playStage1(tok); if (tok !== abortToken) return; }
    if (fromStage <= 2) { await playStage2(tok); if (tok !== abortToken) return; }
    if (fromStage <= 3) { await playStage3(tok); if (tok !== abortToken) return; }
    if (fromStage <= 4) { await playStage4(tok); if (tok !== abortToken) return; }
    if (fromStage <= 5) { await playStage5(tok); if (tok !== abortToken) return; }

    setStage(5);
    playing = false; setPlayBtn();
  }

  async function stepOnce() {
    abortToken++; const tok = abortToken;
    const next = Math.min(stage + 1, 5);
    if (next === 0)      await playStage0(tok);
    else if (next === 1) await playStage1(tok);
    else if (next === 2) await playStage2(tok);
    else if (next === 3) await playStage3(tok);
    else if (next === 4) await playStage4(tok);
    else if (next === 5) await playStage5(tok);
  }

  // ============================================================
  // controls
  // ============================================================
  function setPlayBtn() {
    const lbl = $("#btn-play-label");
    if (playing)         lbl.textContent = "暂停";
    else if (stage >= 5) lbl.textContent = "重新播放";
    else if (stage > 0)  lbl.textContent = "继续";
    else                 lbl.textContent = "运行流水线";
  }

  function wireControls() {
    $("#btn-play").addEventListener("click", () => {
      if (playing) {
        abortToken++;        // pause = abort current chain
        playing = false; setPlayBtn(); return;
      }
      if (stage >= 5) { resetStages(); run(0); return; }
      // continue from next stage; if currently at stage 0 idle, start at 0
      run(stage === 0 ? 0 : stage + 1);
    });
    $("#btn-step").addEventListener("click", () => {
      if (stage >= 5) return;
      stepOnce();
    });
    $("#btn-reset").addEventListener("click", () => {
      abortToken++; playing = false;
      resetStages(); setPlayBtn();
    });
    // "载入选中扫描" button — same as primary play
    const loadBtn = $("#btn-load");
    if (loadBtn) loadBtn.addEventListener("click", () => {
      if (playing) return;
      abortToken++;
      resetStages();
      run(0);
    });
    $("#speed").addEventListener("change", (e) => { speed = parseFloat(e.target.value); });

    // tab click — jump to that scene (if already explored)
    $$(".stage-tab").forEach(t => {
      t.addEventListener("click", () => {
        const s = +t.dataset.stage;
        if (s <= stage) {
          setStage(s);
        }
      });
    });
  }

})();
