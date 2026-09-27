(() => {
const $ = (s) => document.querySelector(s);

const STATUS = {
  reachable: "可触达",
  incubation: "孵化期",
  trial: "试分析",
  base: "公海底表",
  pool: "公共池",
};

const ITEMS = [
  ["upload", "上传名单"],
  ["reachable", "可触达"],
  ["incubation", "孵化期"],
  ["trial", "试分析"],
  ["base", "公海底表"],
  ["pool", "公共池"],
  ["grants", "外呼审批"],
  ["align", "主体待确认"],
  ["playbooks", "行业条目"],
  ["settings", "分成"],
];

const state = { me: null, view: "", accounts: [], detail: null };

function esc(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.add("hidden"), 3200);
}

async function api(path, options = {}) {
  const res = await fetch(path, { ...options, credentials: "same-origin" });
  const text = await res.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { detail: text };
  }
  if (!res.ok) {
    const msg = data.detail || res.statusText;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

function host() {
  return document.querySelector("#view-stock") || document.querySelector("#view");
}

function navHost() {
  return document.querySelector("#navStock") || document.querySelector("#nav");
}

function renderNav() {
  const items = ITEMS;
  navHost().innerHTML = `<div class="side-group"><div class="side-label">存量</div>${items
    .map(
      ([id, label], index) =>
        `<button class="side-item${state.view === id ? " active" : ""}" data-view="${id}" type="button"><span class="side-num">${index + 1}</span><span>${label}</span></button>`,
    )
    .join("")}</div>`;
  navHost().querySelectorAll("[data-view]").forEach((btn) => {
    btn.onclick = () => openView(btn.dataset.view);
  });
}

function page(title, desc, body) {
  host().innerHTML = `<div class="page-head"><div><h1>${esc(title)}</h1><p>${esc(desc)}</p></div></div>${body}`;
}

function productsOf(record) {
  return ((record.analysis || {}).products || []).map((item) => item.name).join("、") || "—";
}

async function openView(name) {
  state.view = name;
  state.detail = null;
  renderNav();
  if (name === "upload") return renderUpload();
  if (name === "grants") return renderGrants();
  if (name === "align") return renderAlign();
  if (name === "playbooks") return renderPlaybooks();
  if (name === "settings") return renderSettings();
  if (name === "chain") return renderChain();
  return renderList(name);
}

function renderUpload() {
  page(
    "上传名单",
    "导入自己手上的客户表。系统按存量规则分析，结果只留在本账号下。",
    `<form id="uploadForm" class="panel"><div class="panel-h"><h2>Excel</h2></div>
      <p>需要公司全称。电话、联系人、行业、已购经营范围、公开信号、备注有则填写，表头可以不完全一致。</p>
      <input id="uploadFile" type="file" accept=".xlsx" required />
      <div class="row-actions"><button class="btn" id="uploadSubmit" type="submit">开始分析</button></div>
      <div id="uploadResult"></div>
    </form>`,
  );
  $("#uploadForm").onsubmit = async (e) => {
    e.preventDefault();
    const file = $("#uploadFile").files[0];
    if (!file) return;
    const body = new FormData();
    body.append("file", file);
    const submit = $("#uploadSubmit");
    if (submit) {
      submit.disabled = true;
      submit.textContent = "模型分析中…";
    }
    try {
      const data = await api("/api/stock/uploads", { method: "POST", body });
      const rows = (data.records || [])
        .map(
          (row) =>
            `<tr><td>${esc(row.company)}</td><td>${esc(STATUS[row.status] || row.status)}</td><td>${esc(productsOf(row))}</td><td>${esc(row.source_label)}</td></tr>`,
        )
        .join("");
      $("#uploadResult").innerHTML = `<p>已分析 ${data.count} 家，同一公司不会并到其他部门。</p><div class="table-wrap"><table><thead><tr><th>公司</th><th>去向</th><th>并列建议</th><th>来源</th></tr></thead><tbody>${rows}</tbody></table></div>`;
      toast("分析完成");
    } catch (err) {
      toast(err.message);
    } finally {
      if (submit) {
        submit.disabled = false;
        submit.textContent = "开始分析";
      }
    }
  };
}

async function loadRows(name) {
  if (name === "base" || name === "pool") return api(`/api/stock/admin/${name}`);
  const path = name === "trial" ? "trials" : name;
  return api(`/api/stock/${path}`);
}

async function renderList(name) {
  const titles = {
    reachable: ["可触达", "确认信号已经成立的客户都在这里，不按张数截断。建议产品并列，没有优先级。"],
    incubation: ["孵化期", "只有先导信号。系统不建议外呼。管理员分配的号码在批准前不可见。"],
    trial: ["试分析", "还没有形成先导信号。只留在本账号，不进公共池。"],
    base: ["公海底表", "已导入、还没有信号、也还没分给部门的客户。"],
    pool: ["公共池", "已有先导或确认信号、尚未分配。确认信号优先排在前面。"],
  };
  const [title, desc] = titles[name];
  let rows = [];
  try {
    rows = await loadRows(name);
  } catch (err) {
    page(title, desc, `<div class="panel"><p>${esc(err.message)}</p></div>`);
    return;
  }
  if (name === "pool" && true && !state.accounts.length) {
    state.accounts = await api("/api/stock/admin/accounts");
  }
  const body = rows
    .map((row) => {
      const phone = row.phone_visible ? esc(row.phone || "—") : "未显示";
      const assign =
        name === "pool" && true
          ? `<button class="btn small" data-assign="${esc(row.id)}" type="button">分配</button>`
          : "";
      return `<tr data-id="${esc(row.id)}"><td>${esc(row.company)}</td><td>${esc(row.source_label)}</td><td>${esc(STATUS[row.status] || row.status)}</td><td>${phone}</td><td>${esc(productsOf(row))}</td><td><button class="btn small" data-open="${esc(row.id)}" type="button">查看</button>${assign}</td></tr>`;
    })
    .join("");
  const importer =
    name === "base" && true
      ? `<form id="importForm" class="panel"><div class="panel-h"><h2>导入存量底表</h2></div><p>填写公司全称、已购经营范围、服务截止、客单价和 CRM 主键。没有信号的留在底表，有信号的进公共池。</p><input type="file" name="file" accept=".xlsx" required /><div class="row-actions"><button class="btn" type="submit">导入</button></div></form>`
      : "";
  page(
    title,
    desc,
    `${importer}<div class="panel"><div class="table-wrap"><table><thead><tr><th>公司</th><th>来源</th><th>状态</th><th>号码</th><th>并列建议</th><th></th></tr></thead><tbody>${body || `<tr><td colspan="6">暂无客户</td></tr>`}</tbody></table></div></div><div id="detail"></div>`,
  );
  const importForm = $("#importForm");
  if (importForm) {
    importForm.onsubmit = async (e) => {
      e.preventDefault();
      const body = new FormData(importForm);
      try {
        const data = await api("/api/stock/admin/imports", { method: "POST", body });
        toast(`已导入 ${data.count} 家`);
        openView("base");
      } catch (err) {
        toast(err.message);
      }
    };
  }
  host().querySelectorAll("[data-open]").forEach((btn) => {
    btn.onclick = () => openCard(btn.dataset.open);
  });
  host().querySelectorAll("[data-assign]").forEach((btn) => {
    btn.onclick = () => openAssign(btn.dataset.assign, rows.find((row) => row.id === btn.dataset.assign));
  });
}

async function renderChain() {
  try {
    const groups = await Promise.all([
      api("/api/stock/reachable"),
      api("/api/stock/incubation"),
      api("/api/stock/trials"),
    ]);
    const rows = groups.flat();
    const body = rows
      .map(
        (row) =>
          `<tr><td>${esc(row.company)}</td><td>${esc(row.owner || "—")}</td><td>${esc(STATUS[row.status] || row.status)}</td><td>${esc(row.source_label)}</td><td>${esc(productsOf(row))}</td><td><button class="btn small" data-open="${esc(row.id)}" type="button">查看</button></td></tr>`,
      )
      .join("");
    page(
      "全链路",
      "查看分配、信号和来源。这里不能外呼，也不能改库。",
      `<div class="panel"><div class="table-wrap"><table><thead><tr><th>公司</th><th>账号</th><th>状态</th><th>来源</th><th>并列建议</th></tr></thead><tbody>${body || `<tr><td colspan="5">暂无客户</td></tr>`}</tbody></table></div></div><div id="detail"></div>`,
    );
    host().querySelectorAll("[data-open]").forEach((btn) => {
      btn.onclick = () => openCard(btn.dataset.id || btn.dataset.open);
    });
  } catch (err) {
    toast(err.message);
  }
}

function openAssign(id, row) {
  const options = state.accounts
    .map((user) => `<option value="${esc(user.username)}">${esc(user.department)}（${esc(user.username)}）</option>`)
    .join("");
  $("#detail").innerHTML = `<form id="assignForm" class="panel"><div class="panel-h"><h2>分配 ${esc(row?.company || "")}</h2></div>
    <div class="form-grid">
      <label>部门账号<select name="owner" required>${options || `<option value="">还没有一线账号</option>`}</select></label>
      <label>可打号码<input name="phone" value="${esc(row?.phone || "")}" /></label>
      <label>默认角色<input name="role_name" value="${esc(row?.role_name || "")}" /></label>
      <label>CRM 主键<input name="crm_id" value="${esc(row?.crm_id || "")}" /></label>
      <label>生效日<input name="effective_on" type="date" /></label>
    </div>
    <div class="row-actions"><button class="btn" type="submit">确认分配</button></div>
  </form>`;
  $("#assignForm").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = Object.fromEntries(fd.entries());
    try {
      await api(`/api/stock/admin/assign/${id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      toast("已分配");
      openView("pool");
    } catch (err) {
      toast(err.message);
    }
  };
}

function startStockWait(title) {
  const started = Date.now();
  const box = $("#detail");
  if (box) {
    box.innerHTML = `<div class="panel stock-wait">
      <div class="spinner" aria-hidden="true"></div>
      <p>${esc(title)}</p>
      <p class="stock-wait-sub" id="stockWaitSub">已等待 0 秒。思考已压到最低，通常十几秒到半分钟，页面不会自己跳走。</p>
    </div>`;
  }
  const timer = setInterval(() => {
    const sub = document.querySelector("#stockWaitSub");
    if (!sub) {
      clearInterval(timer);
      return;
    }
    const elapsed = Math.floor((Date.now() - started) / 1000);
    sub.textContent = `已等待 ${elapsed} 秒。思考已压到最低，通常十几秒到半分钟，页面不会自己跳走。`;
  }, 1000);
  return () => clearInterval(timer);
}

async function openCard(id) {
  const stopWait = startStockWait("正在用模型写五线和话术");
  let data;
  try {
    data = await api(`/api/stock/cards/${id}`);
  } catch (err) {
    stopWait();
    const box = $("#detail");
    if (box) {
      box.innerHTML = `<div class="panel"><p>这次没有写完：${esc(err.message)}</p><div class="row-actions"><button class="btn" id="btnRetryCard" type="button">重试</button></div></div>`;
      $("#btnRetryCard").onclick = () => openCard(id);
    }
    toast(err.message);
    return;
  }
  stopWait();
  state.detail = data;
  const record = data.record;
  const analysis = record.analysis || {};
  const lines = (data.lines || []).map((line, i) => `<p class="stock-copy"><strong>${esc(["一", "二", "三", "四", "五"][i] || i + 1)}、</strong>${esc(line)}</p>`).join("");
  const products = (data.products || [])
    .map((item) => `<li>${esc(item.name)} <span class="pill">${esc(item.basis)}</span></li>`)
    .join("");
  const notice = data.incubation_notice ? `<div class="panel"><h2>孵化期，系统不建议外呼</h2></div>` : "";
  const phone = record.phone_visible ? esc(record.phone || "—") : "号码不可见";
  const canCall =
    record.status === "reachable" ||
    record.status === "trial" ||
    (record.status === "incubation" && record.phone_visible);
  const ask =
    record.status === "incubation" && record.source === "admin_assign" && !record.phone_visible
      ? `<button class="btn secondary" id="btnAsk" type="button">申请外呼</button>`
      : "";
  const call = canCall
    ? `<form id="callForm" class="form-grid">
        <label>意向<select name="intention"><option>有明确兴趣</option><option>暂无需求</option><option>需发资料</option><option>号码失效</option></select></label>
        <label>痛点<select name="pain_match"><option>属实</option><option>偏差</option></select></label>
        <label class="full">真实痛点或偏差<input name="pain_note" /></label>
        <label>操作人备注或分机<input name="operator_note" /></label>
        <label>分机号<input name="extension" /></label>
        <div class="row-actions"><button class="btn" type="submit">保存回写</button></div>
      </form>`
    : "";
  const narrate = `<button class="btn ghost small" id="btnNarrate" type="button">润色五线</button>`;
  const box = $("#detail") || host();
  const html = `${notice}<div class="panel">
      <div class="panel-h"><h2>${esc(record.company)}</h2><span class="pill">${esc(record.source_label || "")}</span></div>
      <p>基本面：${esc(record.contact || "—")} ${esc(record.role_name || "")} · ${esc(record.industry || "行业未填")} · ${phone}${record.phone_note ? `（${esc(record.phone_note)}）` : ""}</p>
      <p>存量历史：${esc(record.purchased_scope || "已购未填")} · 截止 ${esc(record.service_end || "—")} · 客单价 ${esc(record.unit_price || "—")}</p>
      <p>触达时点：${esc((analysis.confirm_hits || []).join("、") || "确认信号未成立")}</p>
      ${record.signals_text ? `<p>公开材料</p><p class="stock-copy">${esc(record.signals_text)}</p>` : ""}
      <p>一句说明：${esc(analysis.speakable || "")}</p>
      <p>并列建议</p><ul>${products || "<li>暂无</li>"}</ul>
      ${data.pitch ? `<p>话术</p><p id="pitchText" class="stock-copy">${esc(data.pitch)}</p><button class="btn small" id="btnCopy" type="button">复制话术</button>` : ""}
      ${data.supplement ? `<p>补充观察</p><p class="stock-copy">${esc(data.supplement)}</p>` : ""}
      <div class="stock-lines">${lines}</div>
      <p>${esc((analysis.gaps || []).join("；"))}</p>
      <div class="row-actions">${ask}${narrate}</div>
      ${call}
    </div>`;
  if ($("#detail")) $("#detail").innerHTML = html;
  else box.insertAdjacentHTML("beforeend", `<div id="detail">${html}</div>`);
  $("#btnCopy") && ($("#btnCopy").onclick = async () => {
    await navigator.clipboard.writeText(data.pitch || "");
    toast("话术已复制");
  });
  $("#btnAsk") && ($("#btnAsk").onclick = async () => {
    try {
      await api(`/api/stock/incubation/${id}/call-requests`, { method: "POST" });
      toast("已提交申请");
    } catch (err) {
      toast(err.message);
    }
  });
  $("#btnNarrate") && ($("#btnNarrate").onclick = async () => {
    try {
      await api(`/api/stock/cards/${id}/narrate`, { method: "POST" });
      toast("已按规则润色");
      openCard(id);
    } catch (err) {
      toast(err.message);
    }
  });
  $("#callForm") && ($("#callForm").onsubmit = async (e) => {
    e.preventDefault();
    const payload = Object.fromEntries(new FormData(e.target).entries());
    payload.record_id = id;
    try {
      await api("/api/stock/calls", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      toast("回写已保存");
    } catch (err) {
      toast(err.message);
    }
  });
}

async function renderGrants() {
  let rows = [];
  try {
    rows = await api("/api/stock/admin/grants");
  } catch (err) {
    toast(err.message);
  }
  const body = rows
    .map(
      (row) =>
        `<tr><td>${esc(row.company)}</td><td>${esc(row.owner)}</td><td>${true ? `<button class="btn small" data-grant="${esc(row.id)}" type="button">批准 36 小时</button>` : "待审批"}</td></tr>`,
    )
    .join("");
  page(
    "外呼审批",
    "批准后号码可见 36 小时。打完要回写。获准外呼不会升成可触达。",
    `<div class="panel"><div class="table-wrap"><table><thead><tr><th>公司</th><th>申请账号</th><th></th></tr></thead><tbody>${body || `<tr><td colspan="3">没有待审批申请</td></tr>`}</tbody></table></div></div>`,
  );
  host().querySelectorAll("[data-grant]").forEach((btn) => {
    btn.onclick = async () => {
      try {
        await api(`/api/stock/admin/grants/${btn.dataset.grant}?approved=true`, { method: "POST" });
        toast("已批准，36 小时内可见号码");
        renderGrants();
      } catch (err) {
        toast(err.message);
      }
    };
  });
}

async function renderAlign() {
  let rows = [];
  try {
    rows = await api("/api/stock/admin/align");
  } catch (err) {
    toast(err.message);
  }
  const body = rows
    .map(
      (row) =>
        `<tr><td>${esc(row.company)}</td><td>${esc(row.source_label)}</td><td>${esc(row.owner || "—")}</td><td>${
          true
            ? `<form data-align="${esc(row.id)}" class="row"><input name="crm_id" placeholder="CRM 主键" /><button class="btn small" type="submit">确认主体</button></form>`
            : "待确认"
        }</td></tr>`,
    )
    .join("");
  page(
    "主体待确认",
    "公司名对不齐时各自保留，不会把子公司信号锁到别的号码上。",
    `<div class="panel"><div class="table-wrap"><table><thead><tr><th>公司</th><th>来源</th><th>账号</th><th>CRM</th></tr></thead><tbody>${body || `<tr><td colspan="4">没有待确认主体</td></tr>`}</tbody></table></div></div>`,
  );
  host().querySelectorAll("[data-align]").forEach((form) => {
    form.onsubmit = async (e) => {
      e.preventDefault();
      const crm_id = new FormData(form).get("crm_id");
      try {
        await api(`/api/stock/admin/align/${form.dataset.align}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ crm_id }),
        });
        toast("已记录主体，没有合并其他部门的名单");
        renderAlign();
      } catch (err) {
        toast(err.message);
      }
    };
  });
}

async function renderPlaybooks() {
  let rows = [];
  try {
    rows = await api("/api/stock/admin/playbooks");
  } catch (err) {
    toast(err.message);
  }
  const body = rows
    .map((row) => {
      const action =
        true
          ? `<button class="btn small" data-book="${esc(row.id)}" data-enabled="${row.enabled ? "0" : "1"}" type="button">${row.enabled ? "停用" : "启用"}</button>`
          : "";
      return `<tr><td>${esc(row.name)}</td><td>${row.enabled ? "启用" : "停用"}</td><td>${action}</td></tr>`;
    })
    .join("");
  page(
    "行业条目",
    "十条行业是参照。停用后，新的分析不再用该条目做主行业。",
    `<div class="panel"><div class="table-wrap"><table><thead><tr><th>行业</th><th>状态</th><th></th></tr></thead><tbody>${body}</tbody></table></div></div>`,
  );
  host().querySelectorAll("[data-book]").forEach((btn) => {
    btn.onclick = async () => {
      try {
        await api(`/api/stock/admin/playbooks/${btn.dataset.book}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: btn.dataset.enabled === "1" }),
        });
        renderPlaybooks();
      } catch (err) {
        toast(err.message);
      }
    };
  });
}

async function renderSettings() {
  let current = { commission_rate: 8 };
  try {
    current = await api("/api/stock/admin/settings");
  } catch (err) {
    toast(err.message);
  }
  const form =
    true
      ? `<form id="settingsForm" class="row"><label>分成比例 %<input name="commission_rate" type="number" min="5" max="10" step="0.5" value="${esc(current.commission_rate)}" /></label><button class="btn" type="submit">保存</button></form>`
      : `<p>当前分成 ${esc(current.commission_rate)}%</p>`;
  page("分成", "跨部门成交时按合同额计。孵化期外呼授权固定 36 小时。", `<div class="panel">${form}<p>可触达锁定按单条记录计算 60 天，不锁定整家公司。</p></div>`);
  const settings = $("#settingsForm");
  if (settings) {
    settings.onsubmit = async (e) => {
      e.preventDefault();
      const commission_rate = Number(new FormData(settings).get("commission_rate"));
      try {
        await api("/api/stock/admin/settings", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ commission_rate }),
        });
        toast("已保存");
      } catch (err) {
        toast(err.message);
      }
    };
  }
}

window.StockApp = {
  show(view) {
    openView(view || state.view || "upload");
  },
};
})();
