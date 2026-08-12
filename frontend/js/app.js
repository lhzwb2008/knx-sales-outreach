const state = {
  leads: [],
  scripts: [],
  competitors: [],
  outreach: [],
  wechatTodos: [],
  currentLeadId: null,
  analysis: null,
  lastScript: null,
  analyzePage: 1,
};

const MATERIAL_OPTIONS = ["案例资料", "白皮书", "近期市场活动介绍", "大师课"];
const ANALYZE_PAGE_SIZE = 10;

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
  if (!el) return;
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
  if (name === "script" || name === "record") name = "analyze";
  $$(".side-item").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${name}`));
  if (name === "home") loadHome();
  if (name === "import") renderImportLeads();
  if (name === "analyze") renderAnalyzeTable();
  if (name === "wechat") renderWechat();
  if (name === "competitors") renderCompetitors();
  if (name === "scripts") renderScripts();
}

async function loadAll() {
  const [leads, scripts, competitors, outreach, wechatTodos] = await Promise.all([
    api("/api/leads"),
    api("/api/scripts"),
    api("/api/competitors"),
    api("/api/outreach"),
    api("/api/wechat-todos"),
  ]);
  Object.assign(state, { leads, scripts, competitors, outreach, wechatTodos });
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
    <th>公司</th><th>联系人</th><th>电话</th><th>职位</th><th>状态</th><th>优先级</th><th>操作</th>
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
      <td class="col-actions">
        <button class="btn ghost small danger" type="button" data-delete-lead="${esc(l.id)}" title="删除该客户">删除</button>
      </td>
    </tr>`
    )
    .join("")}
  </tbody></table>`;
}

async function deleteLeadById(leadId) {
  const lead = state.leads.find((l) => l.id === leadId);
  const label = lead ? leadLabel(lead) : leadId;
  if (!confirm(`确认删除客户「${label}」？\n相关触达记录、微信待办也会一并删除。`)) return false;
  await api(`/api/leads/${encodeURIComponent(leadId)}`, { method: "DELETE" });
  state.leads = await api("/api/leads");
  state.outreach = await api("/api/outreach");
  state.wechatTodos = await api("/api/wechat-todos");
  if (state.currentLeadId === leadId) {
    state.currentLeadId = null;
    closeLeadModal();
  }
  return true;
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
  const display = [
    { n: 1, label: "上传名单", count: steps[1] || 0 },
    { n: 2, label: "客户触达", count: (steps[2] || 0) + (steps[3] || 0) + (steps[4] || 0) },
    { n: 3, label: "微信待办", count: steps[5] || 0 },
  ];
  const max = Math.max(1, ...display.map((d) => d.count));
  $("#stepBars").innerHTML = display
    .map(
      (d) => `<div class="tier-row"><span>${d.n}. ${d.label}</span><div class="bar"><i data-w="${((d.count / max) * 100).toFixed(1)}"></i></div><strong>${d.count}</strong></div>`
    )
    .join("");
  animateBars($("#stepBars"));

  $("#homeWechat").innerHTML = (dash.pending_wechat || []).length
    ? dash.pending_wechat
        .map((t) => {
          const due = String(t.due_at || "").replace("T", " ").slice(0, 16);
          return `<div class="list-item">
            <div class="li-main">
              <strong class="li-title" title="${esc(t.company || "")}">${esc(t.company || "")}</strong>
              <div class="muted li-sub">${esc(t.materials_to_send || "")}</div>
            </div>
            <span class="pill" title="${esc(due)}">${esc(due)}</span>
          </div>`;
        })
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
    tr.onclick = (e) => {
      if (e.target.closest("[data-delete-lead]")) return;
      state.currentLeadId = tr.getAttribute("data-lead");
      switchView("analyze");
      openAnalyzeLead(state.currentLeadId, true);
    };
  });
  $$("#importLeads [data-delete-lead]").forEach((btn) => {
    btn.onclick = async (e) => {
      e.preventDefault();
      e.stopPropagation();
      try {
        const ok = await deleteLeadById(btn.dataset.deleteLead);
        if (!ok) return;
        renderImportLeads();
        toast("客户已删除");
      } catch (err) {
        toast(err.message || "删除失败");
      }
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

function hasBeenCalled(leadId) {
  return (state.outreach || []).some((o) => o.lead_id === leadId);
}

function outreachForLead(leadId) {
  return (state.outreach || [])
    .filter((o) => o.lead_id === leadId)
    .sort(
      (a, b) =>
        leadDateTs(b, ["call_time", "created_at", "updated_at"]) -
        leadDateTs(a, ["call_time", "created_at", "updated_at"])
    );
}

function getAnalyzeFilters() {
  return {
    call: $("#analyzeFilterCall")?.value || "pending",
    tier: $("#analyzeFilterTier")?.value || "all",
    status: $("#analyzeFilterStatus")?.value || "all",
    sort: $("#analyzeSortBy")?.value || "priority",
    q: ($("#analyzeSearch")?.value || "").trim().toLowerCase(),
  };
}

function resetAnalyzePage() {
  state.analyzePage = 1;
}

function filterAndSortLeads(leads) {
  const { call, tier, status, sort, q } = getAnalyzeFilters();
  let rows = [...leads];

  if (call === "pending") {
    rows = rows.filter((l) => !hasBeenCalled(l.id));
  } else if (call === "called") {
    rows = rows.filter((l) => hasBeenCalled(l.id));
  }
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

function renderAnalyzePager(total) {
  const pager = $("#analyzePager");
  if (!pager) return;
  const pages = Math.max(1, Math.ceil(total / ANALYZE_PAGE_SIZE));
  if (state.analyzePage > pages) state.analyzePage = pages;
  if (total === 0) {
    pager.innerHTML = "";
    return;
  }
  pager.innerHTML = `
    <button class="btn ghost small" type="button" data-page-action="prev" ${state.analyzePage <= 1 ? "disabled" : ""}>上一页</button>
    <span class="pager-info">第 ${state.analyzePage} / ${pages} 页 · 每页 ${ANALYZE_PAGE_SIZE} 条</span>
    <button class="btn ghost small" type="button" data-page-action="next" ${state.analyzePage >= pages ? "disabled" : ""}>下一页</button>
  `;
  pager.querySelector('[data-page-action="prev"]')?.addEventListener("click", () => {
    if (state.analyzePage > 1) {
      state.analyzePage -= 1;
      renderAnalyzeTable();
    }
  });
  pager.querySelector('[data-page-action="next"]')?.addEventListener("click", () => {
    if (state.analyzePage < pages) {
      state.analyzePage += 1;
      renderAnalyzeTable();
    }
  });
}

function renderAnalyzeTable() {
  const all = state.leads;
  const rows = filterAndSortLeads(all);
  const countEl = $("#analyzeFilterCount");
  if (countEl) {
    countEl.textContent = rows.length === all.length ? `共 ${rows.length} 位客户` : `显示 ${rows.length} / ${all.length}`;
  }

  const pages = Math.max(1, Math.ceil(rows.length / ANALYZE_PAGE_SIZE));
  if (state.analyzePage > pages) state.analyzePage = pages;
  const start = (state.analyzePage - 1) * ANALYZE_PAGE_SIZE;
  const pageRows = rows.slice(start, start + ANALYZE_PAGE_SIZE);

  $("#analyzeTable").innerHTML = pageRows.length
    ? `<div class="analyze-list">${pageRows
        .map((l) => {
          const analyzed = Boolean(l.need_analysis);
          const called = hasBeenCalled(l.id);
          const when = formatShortDate(l);
          const callCount = outreachForLead(l.id).length;
          return `<article class="analyze-card clickable ${called ? "is-called" : ""}" data-lead="${esc(l.id)}">
            <div class="ac-left">
              <div class="ac-title">
                <strong>${esc(l.company)}</strong>
                <span class="pill ${tierClass(l.last_tier)}">${esc(l.last_tier || "未评分")}</span>
                <span class="pill ${called ? "called" : "pending-call"}">${called ? `已触达${callCount > 1 ? ` · ${callCount}次` : ""}` : "未触达"}</span>
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
              <div class="ac-action">打开触达 →</div>
            </div>
          </article>`;
        })
        .join("")}</div>`
    : `<p class="muted">${all.length ? "没有符合筛选条件的客户。" : "暂无客户。请先在「上传名单」导入 Excel。"}</p>`;

  renderAnalyzePager(rows.length);

  $$("#analyzeTable .analyze-card").forEach((card) => {
    card.onclick = () => openLeadModal(card.dataset.lead, true);
  });
}

function renderLeadModalContent(lead, extra = {}) {
  const hits = extra.rule_hits || [];
  const comps = extra.competitor_hits || [];
  const called = hasBeenCalled(lead.id);

  $("#leadModalCompany").textContent = lead.company || "客户详情";
  $("#leadModalMeta").innerHTML = `
    <span>联系人：<strong>${esc(lead.name || "-")}</strong></span>
    <span>职位：${esc(lead.title || "-")}</span>
    <span class="lead-phone">电话：<strong>${esc(lead.phone || "-")}</strong></span>
    <span class="pill ${tierClass(lead.last_tier)}">${esc(lead.last_tier || "未评分")}</span>
    ${lead.last_score != null ? `<span class="ac-score">${esc(lead.last_score)} 分</span>` : ""}
    <span class="pill ${called ? "called" : "pending-call"}">${called ? "已触达" : "未触达"}</span>
  `;

  const opener = lead.phone_opener || "暂无预生成开场白，可先补充信息后重新分析。";
  const wechat = lead.wechat_invite || "方便加一下微信吗？我把同行业案例发您看一下。";
  const qs = Array.isArray(lead.script_questions) ? lead.script_questions : [];
  $("#leadScriptBox").innerHTML = `
    <div class="script-highlight">
      <div class="sh-label">电话开场白</div>
      <p class="sh-body">${esc(opener)}</p>
    </div>
    <div class="script-highlight soft">
      <div class="sh-label">加微信话术</div>
      <p class="sh-body">${esc(wechat)}</p>
    </div>
    <div class="script-highlight soft">
      <div class="sh-label">探询问题</div>
      ${
        qs.length
          ? `<ol class="sh-questions">${qs.map((q) => `<li>${esc(q)}</li>`).join("")}</ol>`
          : `<p class="muted">暂无探询问题</p>`
      }
    </div>
  `;

  $("#leadAnalysisBox").innerHTML = `
    <div class="block">
      <h4>需求摘要</h4>
      <p>${esc(lead.need_analysis || "暂无，可补充信息后重新分析")}</p>
    </div>
    <div class="block">
      <h4>推荐产品和服务</h4>
      <div class="tag-row">${productTags(lead.recommended_products)}</div>
    </div>
    ${lead.talk_angle ? `<div class="block"><h4>切入角度</h4><p>${esc(lead.talk_angle)}</p></div>` : ""}
    ${lead.priority_reason ? `<div class="block"><h4>优先原因</h4><p class="muted">${esc(lead.priority_reason)}</p></div>` : ""}
    ${
      comps.length
        ? `<div class="block"><h4>客户现有方案 / 竞品参考</h4><ul>${comps
            .map((c) => `<li><strong>${esc(c.name)}</strong> — ${esc(c.strategy || "")}</li>`)
            .join("")}</ul></div>`
        : ""
    }
    ${
      hits.length
        ? `<div class="block"><h4>判断依据</h4><ul>${hits
            .slice(0, 5)
            .map((h) => `<li>${esc(h.need)} → ${esc(h.products)}</li>`)
            .join("")}</ul></div>`
        : ""
    }
  `;

  buildLeadOutreachForm(lead.id);
  renderLeadHistory(lead.id);
  $("#supplementText").value = lead.manual_supplement || "";
}

function buildLeadOutreachForm(leadId) {
  const scriptOpts = state.scripts
    .map((s) => `<option value="${esc(s.id)}">${esc(s.name)}</option>`)
    .join("");
  const materialOpts = MATERIAL_OPTIONS.map((m) => `<option value="${esc(m)}">${esc(m)}</option>`).join("");
  $("#leadOutreachForm").innerHTML = [
    `<input type="hidden" name="lead_id" value="${esc(leadId)}" />`,
    field("渠道", "channel", `<select name="channel"><option>电话</option><option>微信</option></select>`, "select"),
    field(
      "通话结果",
      "outcome",
      `<select name="outcome"><option>未接通</option><option>接通-忙线改约</option><option>接通-拒绝</option><option>接通-感兴趣</option><option>已加微</option></select>`,
      "select"
    ),
    field("通话时长(分钟)", "duration_min", ""),
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
    field("使用话术", "script_id", `<select name="script_id"><option value="">现场发挥</option>${scriptOpts}</select>`, "select"),
  ].join("");
}

function renderLeadHistory(leadId) {
  const rows = outreachForLead(leadId).slice(0, 8);
  const box = $("#leadHistoryBox");
  if (!rows.length) {
    box.innerHTML = `<p class="muted">暂无历史触达记录。</p>`;
    return;
  }
  box.innerHTML = `<table><thead><tr>
    <th>时间</th><th>渠道</th><th>结果</th><th>确认需求</th><th>异议</th><th>下一步</th><th>备注</th><th>加微</th>
  </tr></thead><tbody>
  ${rows
    .map(
      (o) => `<tr>
      <td>${esc((o.call_time || o.created_at || "").replace("T", " ").slice(0, 16))}</td>
      <td>${esc(o.channel || "-")}</td>
      <td>${esc(o.outcome || "-")}</td>
      <td>${esc(o.need_confirmed || "-")}</td>
      <td>${esc(o.objection || "-")}</td>
      <td>${esc(o.next_step || "-")}</td>
      <td>${esc(o.notes || "-")}</td>
      <td>${o.agree_wechat ? "是" : "否"}</td>
    </tr>`
    )
    .join("")}
  </tbody></table>`;
}

function closeLeadModal() {
  $("#leadModal")?.classList.add("hidden");
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
  if (!$("#leadModal").classList.contains("hidden") && state.currentLeadId === leadId) {
    renderLeadModalContent(lead, res);
  }
  return res;
}

async function openLeadModal(id, autoAnalyze = false) {
  state.currentLeadId = id;
  const lead = state.leads.find((l) => l.id === id);
  if (!lead) return;
  const modal = $("#leadModal");
  modal.classList.remove("hidden");
  renderLeadModalContent(lead, state.analysis?.lead?.id === id ? state.analysis : {});

  if (autoAnalyze && !lead.need_analysis) {
    try {
      await runAiAnalyze(id, lead.manual_supplement || "");
      toast("需求分析完成");
    } catch (e) {
      toast(e.message);
    }
  }
}

// 兼容旧调用名
async function openAnalyzeLead(id, autoAnalyze = false) {
  return openLeadModal(id, autoAnalyze);
}

function renderScriptView() {
  // 已合并进客户触达弹框
}

function buildOutreachForm() {
  // 已合并进客户触达弹框
}

function renderRecordView() {
  // 已合并进客户触达弹框
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
  $("#btnExportData").onclick = async () => {
    const btn = $("#btnExportData");
    try {
      showLoading("正在打包数据…", btn);
      const res = await fetch("/api/export/data.zip");
      if (!res.ok) {
        let msg = `导出失败（${res.status}）`;
        try {
          const body = await res.json();
          if (body.detail) msg = typeof body.detail === "string" ? body.detail : msg;
        } catch (_) {}
        throw new Error(msg);
      }
      const blob = await res.blob();
      const cd = res.headers.get("Content-Disposition") || "";
      const m = /filename="?([^"]+)"?/i.exec(cd);
      const filename = m ? m[1] : `knx-data-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.zip`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast("数据已导出");
    } catch (e) {
      toast(e.message || "导出失败");
    } finally {
      hideLoading();
    }
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

  $("#btnCloseLeadModal").onclick = () => {
    closeLeadModal();
    state.currentLeadId = null;
  };
  $("#leadModal").onclick = (e) => {
    if (e.target.id === "leadModal") {
      closeLeadModal();
      state.currentLeadId = null;
    }
  };

  ["analyzeFilterCall", "analyzeFilterTier", "analyzeFilterStatus", "analyzeSortBy"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.onchange = () => {
        resetAnalyzePage();
        renderAnalyzeTable();
      };
    }
  });
  const searchEl = $("#analyzeSearch");
  if (searchEl) {
    let t = null;
    searchEl.oninput = () => {
      clearTimeout(t);
      t = setTimeout(() => {
        resetAnalyzePage();
        renderAnalyzeTable();
      }, 180);
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
      resetAnalyzePage();
      renderAnalyzeTable();
      toast(`已完成 ${pending.length} 位客户分析`);
    } catch (e) {
      state.leads = await api("/api/leads");
      renderAnalyzeTable();
      toast(e.message);
    }
  };

  $("#btnSaveLeadOutreach").onclick = async () => {
    const form = $("#leadOutreachForm");
    if (!form) return;
    const obj = formToObject(form);
    obj.rule_ids = (state.analysis?.rule_hits || []).map((r) => r.rule_id).slice(0, 5);
    if (obj.duration_min === undefined) obj.duration_min = "";
    else obj.duration_min = String(obj.duration_min);
    try {
      await withLoading("正在保存触达记录…", () =>
        api("/api/outreach", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(obj),
        })
      );
      state.outreach = await api("/api/outreach");
      state.wechatTodos = await api("/api/wechat-todos");
      state.leads = await api("/api/leads");
      renderAnalyzeTable();
      const lead = state.leads.find((l) => l.id === obj.lead_id);
      if (lead) renderLeadModalContent(lead, state.analysis?.lead?.id === lead.id ? state.analysis : {});
      toast(obj.agree_wechat ? "已保存，并生成微信待办" : "触达记录已保存");
    } catch (e) {
      toast(e.message || "保存失败");
    }
  };

  // 兼容旧隐藏按钮，避免空引用
  if ($("#btnSaveOutreach")) {
    $("#btnSaveOutreach").onclick = () => $("#btnSaveLeadOutreach")?.click();
  }

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
