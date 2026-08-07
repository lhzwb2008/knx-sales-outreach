const state = {
  leads: [],
  scripts: [],
  competitors: [],
  outreach: [],
  wechatTodos: [],
  currentLeadId: null,
  analysis: null,
  lastScript: null,
};

const MATERIAL_OPTIONS = ["案例资料", "白皮书", "近期市场活动介绍", "大师课"];

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];

let loadingDepth = 0;
let loadingOwnerBtn = null;

function showLoading(text = "智能助手处理中，请稍候…", btn = null) {
  loadingDepth += 1;
  $("#loadingText").textContent = text;
  $("#loadingModal").classList.remove("hidden");
  if (btn) {
    loadingOwnerBtn = btn;
    btn.disabled = true;
    btn.dataset._oldText = btn.textContent;
  }
}

function hideLoading() {
  loadingDepth = Math.max(0, loadingDepth - 1);
  if (loadingDepth === 0) {
    $("#loadingModal").classList.add("hidden");
    if (loadingOwnerBtn) {
      loadingOwnerBtn.disabled = false;
      if (loadingOwnerBtn.dataset._oldText) {
        loadingOwnerBtn.textContent = loadingOwnerBtn.dataset._oldText;
      }
      loadingOwnerBtn = null;
    }
  }
}

async function withLoading(text, fn, btn = null) {
  showLoading(text, btn);
  try {
    return await fn();
  } finally {
    hideLoading();
  }
}

async function api(path, options = {}) {
  const res = await fetch(path, options);
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { detail: text };
  }
  if (!res.ok) {
    const msg = data.detail || data.message || res.statusText;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.add("hidden"), 3200);
}

function esc(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function tierClass(tier = "") {
  if (String(tier).includes("P0")) return "p0";
  if (String(tier).includes("P1")) return "p1";
  if (String(tier).includes("P2")) return "p2";
  if (String(tier).includes("P3")) return "p3";
  return "";
}

function priorityRank(lead) {
  const score = Number(lead.last_score);
  if (!Number.isNaN(score)) return score;
  const tier = String(lead.last_tier || "");
  if (tier.includes("P0")) return 90;
  if (tier.includes("P1")) return 70;
  if (tier.includes("P2")) return 50;
  if (tier.includes("P3")) return 30;
  return -1;
}

function sortByPriority(leads) {
  return [...leads].sort((a, b) => priorityRank(b) - priorityRank(a));
}

function field(label, name, value = "", type = "text", full = false) {
  let control;
  if (type === "textarea") control = `<textarea name="${name}">${esc(value)}</textarea>`;
  else if (type === "select") control = value;
  else if (type === "checkbox") {
    return `<label class="check full"><input type="checkbox" name="${name}" ${value ? "checked" : ""}/> ${esc(label)}</label>`;
  } else control = `<input name="${name}" type="${type}" value="${esc(value)}" />`;
  return `<label class="${full ? "full" : ""}">${esc(label)}${control}</label>`;
}

function formToObject(form) {
  const fd = new FormData(form);
  const obj = {};
  for (const [k, v] of fd.entries()) obj[k] = v;
  form.querySelectorAll('input[type="checkbox"]').forEach((el) => {
    obj[el.name] = el.checked;
  });
  return obj;
}

function switchView(name) {
  $$(".side-item").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${name}`));
  if (name === "home") loadHome();
  if (name === "import") renderImportLeads();
  if (name === "analyze") renderAnalyzeTable();
  if (name === "script") renderScriptView();
  if (name === "record") renderRecordView();
  if (name === "wechat") renderWechat();
  if (name === "competitors") renderCompetitors();
  if (name === "scripts") renderScripts();
}

async function loadAll() {
  const [leads, scripts, competitors, outreach, wechatTodos, health] = await Promise.all([
    api("/api/leads"),
    api("/api/scripts"),
    api("/api/competitors"),
    api("/api/outreach"),
    api("/api/wechat-todos"),
    api("/api/health"),
  ]);
  Object.assign(state, { leads, scripts, competitors, outreach, wechatTodos });
  const badge = $("#readyBadge");
  if (health.assistant_ready) {
    badge.textContent = "智能助手已就绪";
    badge.className = "badge ok";
  } else {
    badge.textContent = "智能助手未配置";
    badge.className = "badge warn";
  }
}

// 数字滚动动效
function animateValue(el, target) {
  const to = Number(target) || 0;
  const dur = 700;
  const t0 = performance.now();
  const tick = (t) => {
    const p = Math.min(1, (t - t0) / dur);
    const eased = 1 - Math.pow(1 - p, 3);
    el.textContent = Math.round(to * eased);
    if (p < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

// 进度条按宽度入场
function animateBars(container) {
  requestAnimationFrame(() => {
    container.querySelectorAll(".bar > i").forEach((bar) => {
      const w = bar.dataset.w || "0";
      bar.style.width = `${w}%`;
    });
  });
}

// 总览客户卡片
function leadCard(l) {
  return `<article class="lead-card" data-lead="${esc(l.id)}">
    <span class="co">${esc(l.company)}</span>
    <span class="who">${esc(l.name || "客户")} · ${esc(l.title || "职位未知")} · ${esc(l.phone || "无电话")}</span>
    <div class="foot">
      <span class="pill ${tierClass(l.last_tier)}">${esc(l.last_tier || "未评分")}</span>
      ${l.last_score != null ? `<span class="score">${esc(l.last_score)} 分</span>` : `<span class="score">${esc(l.status || "待分析")}</span>`}
    </div>
  </article>`;
}

function bindLeadCards(container, onPick) {
  container.querySelectorAll(".lead-card").forEach((el) => {
    el.onclick = () => onPick(el.dataset.lead);
  });
}

function leadLabel(l) {
  return `${l.company} · ${l.name || "客户"}`;
}

function tableLeadsSimple(rows) {
  if (!rows.length) return `<p class="muted">暂无客户，请先上传名单。</p>`;
  return `<table><thead><tr>
    <th>公司</th><th>联系人</th><th>电话</th><th>职位</th><th>状态</th><th>优先级</th>
  </tr></thead><tbody>
  ${rows
    .map(
      (l) => `<tr class="clickable" data-lead="${esc(l.id)}">
      <td><strong>${esc(l.company)}</strong></td>
      <td>${esc(l.name)}</td>
      <td>${esc(l.phone || "-")}</td>
      <td>${esc(l.title || "-")}</td>
      <td>${esc(l.status || "-")}</td>
      <td><span class="pill ${tierClass(l.last_tier)}">${esc(l.last_tier || "未评分")}</span>
        ${l.last_score != null ? `<div class="muted">${esc(l.last_score)} 分</div>` : ""}</td>
    </tr>`
    )
    .join("")}
  </tbody></table>`;
}

async function loadHome() {
  const dash = await api("/api/dashboard");
  const c = dash.counts;
  $("#statGrid").innerHTML = [
    ["客户名单", c.leads],
    ["已分析", c.analyzed],
    ["已触达", c.called],
    ["待加微信", c.wechat_pending],
  ]
    .map(([k, v]) => `<div class="stat"><div class="k">${k}</div><div class="v">0</div></div>`)
    .join("");
  // 数字滚动
  const values = [c.leads, c.analyzed, c.called, c.wechat_pending];
  $$("#statGrid .stat .v").forEach((el, i) => animateValue(el, values[i]));

  const steps = dash.steps || {};
  const labels = { 1: "上传名单", 2: "需求分析", 3: "话术触达", 4: "记录过程", 5: "微信待办" };
  const max = Math.max(1, ...Object.values(steps));
  $("#stepBars").innerHTML = [1, 2, 3, 4, 5]
    .map(
      (n) => `<div class="tier-row"><span>${n}. ${labels[n]}</span><div class="bar"><i data-w="${(((steps[n] || 0) / max) * 100).toFixed(1)}"></i></div><strong>${steps[n] || 0}</strong></div>`
    )
    .join("");
  animateBars($("#stepBars"));

  $("#homeWechat").innerHTML = (dash.pending_wechat || []).length
    ? dash.pending_wechat
        .map(
          (t) => `<div class="list-item"><div><strong>${esc(t.company)}</strong><div class="muted">${esc(t.materials_to_send || "")}</div></div><span class="pill">${esc(t.due_at || "")}</span></div>`
        )
        .join("")
    : `<p class="muted">暂无微信待办。</p>`;

  const sorted = sortByPriority(state.leads);
  $("#homeLeads").innerHTML = sorted.length
    ? sorted.map(leadCard).join("")
    : `<p class="muted">暂无客户，请先到「上传名单」导入 Excel。</p>`;
  bindLeadCards($("#homeLeads"), (id) => {
    state.currentLeadId = id;
    switchView("analyze");
    openAnalyzeLead(id);
  });
}

function renderImportLeads() {
  $("#importLeads").innerHTML = tableLeadsSimple(state.leads);
  $$("#importLeads tr.clickable").forEach((tr) => {
    tr.onclick = () => {
      state.currentLeadId = tr.getAttribute("data-lead");
      switchView("analyze");
      openAnalyzeLead(state.currentLeadId, true);
    };
  });
}

function clipText(s, n = 90) {
  const t = String(s || "").replace(/\s+/g, " ").trim();
  if (!t) return "";
  return t.length > n ? `${t.slice(0, n)}…` : t;
}

function productTags(raw) {
  const parts = String(raw || "")
    .split(/[、，,/\n]+/)
    .map((x) => x.trim())
    .filter(Boolean);
  if (!parts.length) return `<span class="muted">暂无推荐</span>`;
  return parts
    .slice(0, 4)
    .map((p) => `<span class="tag">${esc(p)}</span>`)
    .join("");
}

function leadDateTs(lead, fields) {
  for (const f of fields) {
    const v = lead?.[f];
    if (!v) continue;
    const t = Date.parse(v);
    if (!Number.isNaN(t)) return t;
  }
  return 0;
}

function tierKey(lead) {
  const tier = String(lead.last_tier || "");
  if (tier.includes("P0")) return "P0";
  if (tier.includes("P1")) return "P1";
  if (tier.includes("P2")) return "P2";
  if (tier.includes("P3")) return "P3";
  return "none";
}

function getAnalyzeFilters() {
  return {
    tier: $("#analyzeFilterTier")?.value || "all",
    status: $("#analyzeFilterStatus")?.value || "all",
    sort: $("#analyzeSortBy")?.value || "priority",
    q: ($("#analyzeSearch")?.value || "").trim().toLowerCase(),
  };
}

function filterAndSortLeads(leads) {
  const { tier, status, sort, q } = getAnalyzeFilters();
  let rows = [...leads];

  if (tier !== "all") {
    rows = rows.filter((l) => tierKey(l) === tier);
  }
  if (status === "analyzed") {
    rows = rows.filter((l) => Boolean(l.need_analysis));
  } else if (status === "pending") {
    rows = rows.filter((l) => !l.need_analysis);
  }
  if (q) {
    rows = rows.filter((l) => {
      const hay = `${l.company || ""} ${l.name || ""} ${l.phone || ""} ${l.title || ""}`.toLowerCase();
      return hay.includes(q);
    });
  }

  const cmpStr = (a, b) => String(a || "").localeCompare(String(b || ""), "zh");
  rows.sort((a, b) => {
    switch (sort) {
      case "priority_asc":
        return priorityRank(a) - priorityRank(b) || cmpStr(a.company, b.company);
      case "score": {
        const sa = Number(a.last_score);
        const sb = Number(b.last_score);
        const na = Number.isNaN(sa) ? -1 : sa;
        const nb = Number.isNaN(sb) ? -1 : sb;
        return nb - na || cmpStr(a.company, b.company);
      }
      case "date_desc":
        return (
          leadDateTs(b, ["last_analyzed_at", "updated_at", "created_at"]) -
            leadDateTs(a, ["last_analyzed_at", "updated_at", "created_at"]) ||
          cmpStr(a.company, b.company)
        );
      case "date_asc":
        return (
          leadDateTs(a, ["last_analyzed_at", "updated_at", "created_at"]) -
            leadDateTs(b, ["last_analyzed_at", "updated_at", "created_at"]) ||
          cmpStr(a.company, b.company)
        );
      case "created_desc":
        return leadDateTs(b, ["created_at", "updated_at"]) - leadDateTs(a, ["created_at", "updated_at"]);
      case "created_asc":
        return leadDateTs(a, ["created_at", "updated_at"]) - leadDateTs(b, ["created_at", "updated_at"]);
      case "company":
        return cmpStr(a.company, b.company);
      case "priority":
      default:
        return priorityRank(b) - priorityRank(a) || cmpStr(a.company, b.company);
    }
  });
  return rows;
}

function formatShortDate(lead) {
  const raw = lead.last_analyzed_at || lead.updated_at || lead.created_at || "";
  if (!raw) return "";
  return String(raw).replace("T", " ").slice(0, 16);
}

function renderAnalyzeTable() {
  const all = state.leads;
  const rows = filterAndSortLeads(all);
  const countEl = $("#analyzeFilterCount");
  if (countEl) {
    countEl.textContent = rows.length === all.length ? `共 ${rows.length} 位客户` : `显示 ${rows.length} / ${all.length}`;
  }

  $("#analyzeTable").innerHTML = rows.length
    ? `<div class="analyze-list">${rows
        .map((l) => {
          const analyzed = Boolean(l.need_analysis);
          const when = formatShortDate(l);
          return `<article class="analyze-card clickable" data-lead="${esc(l.id)}">
            <div class="ac-left">
              <div class="ac-title">
                <strong>${esc(l.company)}</strong>
                <span class="pill ${tierClass(l.last_tier)}">${esc(l.last_tier || "未评分")}</span>
              </div>
              <div class="ac-meta">
                <span>${esc(l.name || "-")}</span>
                <span>${esc(l.title || "职位未知")}</span>
                <span>${esc(l.phone || "无电话")}</span>
                ${l.last_score != null ? `<span class="ac-score">${esc(l.last_score)} 分</span>` : ""}
                ${when ? `<span class="ac-date">${esc(when)}</span>` : ""}
              </div>
            </div>
            <div class="ac-mid">
              <div class="ac-label">${analyzed ? "需求摘要" : "分析状态"}</div>
              <p class="ac-summary">${esc(analyzed ? clipText(l.need_analysis, 96) : "尚未分析 · 点击后由智能助手自动分析")}</p>
            </div>
            <div class="ac-right">
              <div class="ac-label">推荐产品</div>
              <div class="tag-row">${analyzed ? productTags(l.recommended_products) : `<span class="muted">—</span>`}</div>
              <div class="ac-action">查看详情 →</div>
            </div>
          </article>`;
        })
        .join("")}</div>`
    : `<p class="muted">${all.length ? "没有符合筛选条件的客户。" : "暂无客户。请先在「上传名单」导入 Excel。"}</p>`;

  $$("#analyzeTable .analyze-card").forEach((card) => {
    card.onclick = () => openAnalyzeLead(card.dataset.lead, true);
  });
}

function renderDetailAnalysis(lead, extra = {}) {
  const hits = extra.rule_hits || [];
  const comps = extra.competitor_hits || [];
  $("#analyzeDetailTitle").textContent = lead.company || "客户详情";
  $("#analyzeDetailMeta").innerHTML = `
    <span>联系人：<strong>${esc(lead.name || "-")}</strong></span>
    <span>职位：${esc(lead.title || "-")}</span>
    <span>电话：${esc(lead.phone || "-")}</span>
    <span class="pill ${tierClass(lead.last_tier)}">${esc(lead.last_tier || "未评分")}</span>
    ${lead.last_score != null ? `<span>${esc(lead.last_score)} 分</span>` : ""}`;

  $("#analysisBox").innerHTML = `
    <div class="block">
      <h3>需求分析结果</h3>
      <p>${esc(lead.need_analysis || "暂无")}</p>
      ${lead.talk_angle ? `<p class="muted">切入角度：${esc(lead.talk_angle)}</p>` : ""}
      ${lead.priority_reason ? `<p class="muted">优先原因：${esc(lead.priority_reason)}</p>` : ""}
    </div>
    <div class="block">
      <h3>推荐产品和服务</h3>
      <div class="tag-row">${productTags(lead.recommended_products)}</div>
    </div>
    ${
      comps.length
        ? `<div class="block"><h3>客户现有方案参考</h3><ul>${comps
            .map((c) => `<li><strong>${esc(c.name)}</strong> — ${esc(c.strategy || "")}</li>`)
            .join("")}</ul></div>`
        : ""
    }
    ${
      hits.length
        ? `<div class="block"><h3>判断依据</h3><ul>${hits
            .slice(0, 5)
            .map((h) => `<li>${esc(h.need)} → ${esc(h.products)}</li>`)
            .join("")}</ul></div>`
        : ""
    }`;

  $("#supplementText").value = lead.manual_supplement || "";
}

async function runAiAnalyze(leadId, supplement = "", btn = null) {
  const res = await withLoading(
    "正在分析客户需求，请稍候…",
    () =>
      api("/api/ai/analyze-need", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lead_id: leadId, supplement }),
      }),
    btn
  );
  state.analysis = res;
  state.leads = await api("/api/leads");
  const lead = state.leads.find((l) => l.id === leadId) || res.lead;
  renderAnalyzeTable();
  renderDetailAnalysis(lead, res);
  return res;
}

async function openAnalyzeLead(id, autoAnalyze = false) {
  state.currentLeadId = id;
  const lead = state.leads.find((l) => l.id === id);
  if (!lead) return;
  const detail = $("#analyzeDetail");
  detail.classList.remove("hidden");
  renderDetailAnalysis(lead, state.analysis?.lead?.id === id ? state.analysis : {});
  window.scrollTo({ top: Math.max(0, detail.offsetTop - 18), behavior: "smooth" });

  if (autoAnalyze && !lead.need_analysis) {
    try {
      await runAiAnalyze(id, lead.manual_supplement || "");
      toast("需求分析完成");
    } catch (e) {
      toast(e.message);
    }
  }
}

function renderScriptView() {
  const sorted = sortByPriority(state.leads);
  if (!sorted.length) {
    $("#scriptBox").innerHTML = `<p class="muted">暂无客户。请先上传名单并完成需求分析。</p>`;
    return;
  }
  $("#scriptBox").innerHTML = sorted
    .map((l) => {
      const opener = l.phone_opener || "暂无预生成话术，请先到「需求分析」完成分析。";
      const wechat = l.wechat_invite || "方便加一下微信吗？我把同行业案例发您看一下。";
      const qs = (l.script_questions || []).map((q) => `<li>${esc(q)}</li>`).join("");
      return `<article class="script-card" data-lead="${esc(l.id)}">
        <div class="row" style="justify-content:space-between">
          <h3>${esc(l.company)} · ${esc(l.name || "客户")}</h3>
          <span class="pill ${tierClass(l.last_tier)}">${esc(l.last_tier || "未评分")}</span>
        </div>
        <div class="meta">${esc(l.title || "-")} · ${esc(l.phone || "-")}</div>
        <div class="meta">需求：${esc(l.need_analysis || "未分析")}</div>
        <div class="meta">推荐：${esc(l.recommended_products || "-")}</div>
        <div class="body"><strong>电话开场</strong><br/>${esc(opener)}</div>
        <div class="meta">加微：${esc(wechat)}</div>
        ${qs ? `<ul>${qs}</ul>` : ""}
        <div class="row-actions">
          <button class="btn small" data-use-script="${esc(l.id)}" type="button">使用此外呼并记录</button>
        </div>
      </article>`;
    })
    .join("");
  $$("[data-use-script]").forEach((btn) => {
    btn.onclick = () => {
      state.currentLeadId = btn.dataset.useScript;
      switchView("record");
      buildOutreachForm(state.currentLeadId, "");
      toast("已带入客户，可直接填写通话结果");
    };
  });
}

function buildOutreachForm(leadId, scriptId = "") {
  const leadOpts = state.leads
    .map((l) => `<option value="${esc(l.id)}" ${l.id === leadId ? "selected" : ""}>${esc(leadLabel(l))}</option>`)
    .join("");
  const scriptOpts = state.scripts
    .map((s) => `<option value="${esc(s.id)}" ${s.id === scriptId ? "selected" : ""}>${esc(s.name)}</option>`)
    .join("");
  const materialOpts = MATERIAL_OPTIONS.map((m) => `<option value="${esc(m)}">${esc(m)}</option>`).join("");
  $("#outreachForm").innerHTML = [
    field("客户", "lead_id", `<select name="lead_id">${leadOpts}</select>`, "select"),
    field("渠道", "channel", `<select name="channel"><option>电话</option><option>微信</option></select>`, "select"),
    field("使用话术", "script_id", `<select name="script_id"><option value="">现场发挥</option>${scriptOpts}</select>`, "select"),
    field("通话时长(分钟)", "duration_min", ""),
    field(
      "通话结果",
      "outcome",
      `<select name="outcome"><option>未接通</option><option>接通-忙线改约</option><option>接通-拒绝</option><option>接通-感兴趣</option><option>已加微</option></select>`,
      "select"
    ),
    field(
      "推进阶段",
      "deal_stage",
      `<select name="deal_stage"><option value="">无</option><option>需求确认</option><option>方案</option><option>成交</option><option>战败</option></select>`,
      "select"
    ),
    field("确认到的需求", "need_confirmed", "", "textarea", true),
    field("客户异议/顾虑", "objection", "", "textarea", true),
    field("下一步动作", "next_step", "", "text", true),
    field("通话细节备注", "notes", "", "textarea", true),
    field("对方同意加微信", "agree_wechat", false, "checkbox"),
    field("微信号线索/备注", "wechat_id_hint", ""),
    field(
      "待发送资料",
      "materials_to_send",
      `<select name="materials_to_send">${materialOpts}</select>`,
      "select"
    ),
    field("跟进人", "assignee", ""),
  ].join("");
}

function renderRecordView() {
  buildOutreachForm(state.currentLeadId || state.leads[0]?.id || "");
  $("#outreachTable").innerHTML = `<table><thead><tr>
    <th>时间</th><th>公司</th><th>结果</th><th>需求</th><th>资料</th><th>加微</th>
  </tr></thead><tbody>
  ${state.outreach
    .map((o) => {
      const lead = state.leads.find((l) => l.id === o.lead_id);
      return `<tr>
        <td>${esc((o.call_time || o.created_at || "").replace("T", " ").slice(0, 16))}</td>
        <td>${esc(lead?.company || o.lead_id)}</td>
        <td>${esc(o.outcome)}</td>
        <td>${esc(o.need_confirmed || "-")}</td>
        <td>${esc(o.materials_to_send || "-")}</td>
        <td>${o.agree_wechat ? "是" : "否"}</td>
      </tr>`;
    })
    .join("")}
  </tbody></table>`;
}

function renderWechat() {
  const rows = state.wechatTodos;
  $("#wechatTable").innerHTML = rows.length
    ? `<table><thead><tr>
      <th>到期</th><th>公司</th><th>联系人</th><th>电话</th><th>资料</th><th>跟进人</th><th>状态</th><th></th>
    </tr></thead><tbody>
    ${rows
      .map(
        (t) => `<tr>
        <td>${esc(t.due_at || "")}</td>
        <td><strong>${esc(t.company)}</strong></td>
        <td>${esc(t.contact_name)}</td>
        <td>${esc(t.phone || "")}</td>
        <td>${esc(t.materials_to_send || "")}</td>
        <td>${esc(t.assignee || "-")}</td>
        <td><span class="pill">${esc(t.status)}</span></td>
        <td>${
          t.status === "done"
            ? "-"
            : `<button class="btn small" data-done-w="${esc(t.id)}">已加微并发资料</button>`
        }</td>
      </tr>`
      )
      .join("")}
    </tbody></table>`
    : `<p class="muted">暂无待办。在「记录过程」勾选「对方同意加微信」后会出现。</p>`;
  $$("[data-done-w]").forEach(
    (b) =>
      (b.onclick = async () => {
        await api(`/api/wechat-todos/${b.dataset.doneW}/done`, { method: "POST" });
        state.wechatTodos = await api("/api/wechat-todos");
        renderWechat();
        toast("已完成微信待办");
      })
  );
}

function renderCompetitors() {
  $("#competitorsTable").innerHTML = `<table><thead><tr>
    <th>名称</th><th>强弱</th><th>关键词</th><th>应对策略</th><th></th>
  </tr></thead><tbody>
  ${state.competitors
    .map(
      (c) => `<tr>
      <td><strong>${esc(c.name)}</strong></td>
      <td><span class="pill ${esc(c.tier)}">${esc(c.tier)}</span></td>
      <td>${esc(c.keywords)}</td>
      <td>${esc(c.strategy)}</td>
      <td><button class="btn small ghost" data-edit-c="${esc(c.id)}">编辑</button></td>
    </tr>`
    )
    .join("")}
  </tbody></table>`;
  $$("[data-edit-c]").forEach((b) => (b.onclick = () => editCompetitor(b.dataset.editC)));
}

function editCompetitor(id) {
  const c = id ? state.competitors.find((x) => x.id === id) : null;
  $("#competitorEditor").classList.remove("hidden");
  $("#competitorForm").innerHTML = [
    `<input type="hidden" name="id" value="${esc(c?.id || "")}" />`,
    field("名称", "name", c?.name || ""),
    field("别名", "aliases", c?.aliases || ""),
    field("关键词", "keywords", c?.keywords || "", "text", true),
    field(
      "强弱",
      "tier",
      `<select name="tier">${["strong", "medium", "weak"]
        .map((t) => `<option value="${t}" ${c?.tier === t ? "selected" : ""}>${t}</option>`)
        .join("")}</select>`,
      "select"
    ),
    field("类别", "category", c?.category || ""),
    field("策略", "strategy", c?.strategy || "", "textarea", true),
  ].join("");
}

function renderScripts() {
  $("#scriptsTable").innerHTML = `<table><thead><tr>
    <th>名称</th><th>适用信号</th><th>开场白</th><th></th>
  </tr></thead><tbody>
  ${state.scripts
    .map(
      (s) => `<tr>
      <td>${esc(s.name)}</td>
      <td>${esc(s.signal)}</td>
      <td>${esc(s.body)}</td>
      <td><button class="btn small ghost" data-edit-s="${esc(s.id)}">编辑</button></td>
    </tr>`
    )
    .join("")}
  </tbody></table>`;
  $$("[data-edit-s]").forEach((b) => (b.onclick = () => editScript(b.dataset.editS)));
}

function editScript(id) {
  const s = id ? state.scripts.find((x) => x.id === id) : null;
  $("#scriptEditor").classList.remove("hidden");
  $("#scriptForm").innerHTML = [
    `<input type="hidden" name="id" value="${esc(s?.id || "")}" />`,
    field("名称", "name", s?.name || ""),
    field("信号", "signal", s?.signal || ""),
    field("渠道", "channel", s?.channel || "电话"),
    field("版本", "version", s?.version || "A"),
    field("电话开场白", "body", s?.body || "", "textarea", true),
    field("加微话术", "wechat", s?.wechat || "", "textarea", true),
  ].join("");
}

async function openHelp() {
  $("#helpModal").classList.remove("hidden");
  const meta = await api("/api/help");
  $("#helpSteps").innerHTML = meta.steps
    .map((s) => `<li><strong>${esc(s.title)}</strong> — ${esc(s.desc)}</li>`)
    .join("");
  const img = $("#helpImage");
  const status = $("#helpImageStatus");
  if (meta.image_ready) {
    img.src = `${meta.image_url}?t=${Date.now()}`;
    img.classList.remove("hidden");
    status.classList.add("hidden");
  } else {
    status.textContent = "正在生成流程图，请稍候…";
    status.classList.remove("hidden");
    img.classList.add("hidden");
    try {
      await withLoading("正在生成使用流程图…", () =>
        api("/api/help/generate-image", { method: "POST" })
      );
      img.src = `/assets/help-workflow.png?t=${Date.now()}`;
      img.classList.remove("hidden");
      status.classList.add("hidden");
    } catch {
      status.textContent = "流程图暂不可用，请先按上方五步说明使用。";
    }
  }
}

function bindUpload() {
  const zone = $("#uploadZone");
  const input = $("#excelFile");
  zone.onclick = () => input.click();
  zone.ondragover = (e) => {
    e.preventDefault();
    zone.classList.add("drag");
  };
  zone.ondragleave = () => zone.classList.remove("drag");
  zone.ondrop = (e) => {
    e.preventDefault();
    zone.classList.remove("drag");
    if (e.dataTransfer.files?.[0]) handleExcel(e.dataTransfer.files[0]);
  };
  input.onchange = () => {
    if (input.files?.[0]) handleExcel(input.files[0]);
  };
}

async function handleExcel(file) {
  const fd = new FormData();
  fd.append("file", file);
  try {
    const res = await withLoading("正在识别名单，请稍候…", async () => {
      const r = await fetch("/api/import/excel", { method: "POST", body: fd });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "导入失败");
      return data;
    });
    state.leads = await api("/api/leads");
    renderImportLeads();
    $("#importResult").classList.remove("hidden");
    $("#importResult").innerHTML = `<div class="block" style="background:#fff;border:1px solid var(--line);border-radius:14px;padding:0.85rem;margin-top:1rem">
      <strong>已导入 ${res.imported} 条客户</strong>
      <div class="muted">${esc(res.mapping_notes || "")}</div>
      <div class="row-actions"><button class="btn" id="btnAfterImport" type="button">去需求分析</button></div>
    </div>`;
    $("#btnAfterImport").onclick = () => switchView("analyze");
    toast(`导入完成：${res.imported} 条`);
  } catch (e) {
    toast(e.message);
  }
}

function bindEvents() {
  $$(".side-item, [data-go]").forEach((btn) => {
    btn.onclick = () => switchView(btn.dataset.view || btn.dataset.go);
  });
  $("#btnHelp").onclick = openHelp;
  $("#helpClose").onclick = () => $("#helpModal").classList.add("hidden");
  $("#helpModal").onclick = (e) => {
    if (e.target.id === "helpModal") $("#helpModal").classList.add("hidden");
  };

  bindUpload();

  $("#btnManualLead").onclick = async () => {
    const company = prompt("公司名称");
    if (!company) return;
    const name = prompt("联系人姓/称呼", "客户") || "客户";
    const phone = prompt("电话", "") || "";
    const title = prompt("职位", "") || "";
    await api("/api/leads", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ company, name, phone, title }),
    });
    state.leads = await api("/api/leads");
    renderImportLeads();
    toast("已补录");
  };

  $("#btnCloseAnalyze").onclick = () => {
    $("#analyzeDetail").classList.add("hidden");
    state.currentLeadId = null;
  };

  ["analyzeFilterTier", "analyzeFilterStatus", "analyzeSortBy"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.onchange = () => renderAnalyzeTable();
  });
  const searchEl = $("#analyzeSearch");
  if (searchEl) {
    let t = null;
    searchEl.oninput = () => {
      clearTimeout(t);
      t = setTimeout(() => renderAnalyzeTable(), 180);
    };
  }

  $("#btnReAnalyze").onclick = async () => {
    if (!state.currentLeadId) return;
    try {
      await runAiAnalyze(state.currentLeadId, $("#supplementText").value || "", $("#btnReAnalyze"));
      toast("已根据补充信息重新分析");
    } catch (e) {
      toast(e.message);
    }
  };

  $("#btnGoScriptFromAnalyze").onclick = () => {
    switchView("script");
  };

  $("#btnBatchAnalyze").onclick = async () => {
    const pending = state.leads.filter((l) => !l.need_analysis);
    if (!pending.length) {
      toast("没有待分析客户");
      return;
    }
    const btn = $("#btnBatchAnalyze");
    try {
      await withLoading(`正在分析 ${pending.length} 位客户…`, async () => {
        for (const lead of pending) {
          $("#loadingText").textContent = `正在分析：${lead.company}…`;
          await api("/api/ai/analyze-need", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ lead_id: lead.id, supplement: lead.manual_supplement || "" }),
          });
        }
      }, btn);
      state.leads = await api("/api/leads");
      renderAnalyzeTable();
      toast(`已完成 ${pending.length} 位客户分析`);
    } catch (e) {
      state.leads = await api("/api/leads");
      renderAnalyzeTable();
      toast(e.message);
    }
  };

  $("#btnSaveOutreach").onclick = async () => {
    const obj = formToObject($("#outreachForm"));
    obj.rule_ids = (state.analysis?.rule_hits || []).map((r) => r.rule_id).slice(0, 5);
    await api("/api/outreach", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(obj),
    });
    state.outreach = await api("/api/outreach");
    state.wechatTodos = await api("/api/wechat-todos");
    state.leads = await api("/api/leads");
    renderRecordView();
    toast(obj.agree_wechat ? "已保存，并生成微信待办" : "触达记录已保存");
    if (obj.agree_wechat) switchView("wechat");
  };

  $("#btnNewCompetitor").onclick = () => editCompetitor(null);
  $("#btnCancelCompetitor").onclick = () => $("#competitorEditor").classList.add("hidden");
  $("#btnSaveCompetitor").onclick = async () => {
    const obj = formToObject($("#competitorForm"));
    if (!obj.id) delete obj.id;
    try {
      await api("/api/competitors", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(obj),
      });
      state.competitors = await api("/api/competitors");
      $("#competitorEditor").classList.add("hidden");
      renderCompetitors();
      toast("已保存");
    } catch (e) {
      toast(e.message);
    }
  };

  $("#btnNewScript").onclick = () => editScript(null);
  $("#btnCancelScript").onclick = () => $("#scriptEditor").classList.add("hidden");
  $("#btnSaveScript").onclick = async () => {
    const obj = formToObject($("#scriptForm"));
    if (!obj.id) delete obj.id;
    await api("/api/scripts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(obj),
    });
    state.scripts = await api("/api/scripts");
    $("#scriptEditor").classList.add("hidden");
    renderScripts();
    toast("话术已保存");
  };
}

async function boot() {
  bindEvents();
  try {
    await loadAll();
    switchView("home");
  } catch (e) {
    toast(`启动失败：${e.message}`);
  }
}

boot();
