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

const state = { me: null, view: "", accounts: [], detail: null, industries: null, preview: null, poolIndustry: "" };

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
  if (name === "pool") {
    const industry = state.poolIndustry || "";
    return api(`/api/stock/admin/pool${industry ? `?industry=${encodeURIComponent(industry)}` : ""}`);
  }
  if (name === "base") return api("/api/stock/admin/base");
  const path = name === "trial" ? "trials" : name;
  return api(`/api/stock/${path}`);
}

async function ensureIndustries() {
  if (state.industries) return state.industries;
  state.industries = await api("/api/stock/admin/industries");
  return state.industries;
}

function csvCell(value) {
  const text = String(value ?? "");
  if (/[",\n]/.test(text)) return `"${text.replaceAll('"', '""')}"`;
  return text;
}

function downloadCsv(filename, header, rows) {
  const lines = [header.join(","), ...rows.map((row) => row.map(csvCell).join(","))];
  const blob = new Blob([`\ufeff${lines.join("\n")}`], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}

async function renderList(name) {
  const titles = {
    reachable: ["可触达", "确认信号已经成立的客户都在这里，不按张数截断。建议产品并列，没有优先级。"],
    incubation: ["孵化期", "只有先导信号。系统不建议外呼。这里的联系人号码都不展示，获准后 36 小时内才可见。"],
    trial: ["试分析", "还没有形成先导信号。只留在本账号，不进公共池。"],
    base: ["公海底表", "已导入、还没有确认信号、也还没分给部门的客户。公海成交表要先预览再确认。"],
    pool: ["公共池", "只有确认信号、尚未分配的客户。先导信号在孵化期。可按业务行业筛选。"],
  };
  const [title, desc] = titles[name];
  let rows = [];
  try {
    rows = await loadRows(name);
  } catch (err) {
    page(title, desc, `<div class="panel"><p>${esc(err.message)}</p></div>`);
    return;
  }
  if (name === "pool" && !state.accounts.length) {
    state.accounts = await api("/api/stock/admin/accounts");
  }
  if (name === "pool" || name === "base") {
    try {
      await ensureIndustries();
    } catch (err) {
      state.industries = state.industries || [];
    }
  }
  const body = rows
    .map((row) => {
      const extra = row.extra_contact_count ? `，还有 ${row.extra_contact_count} 人` : "";
      const phone = row.phone_visible ? `${esc(row.phone || "—")}${esc(extra)}` : "未显示";
      const assign =
        name === "pool" && true
          ? `<button class="btn small" data-assign="${esc(row.id)}" type="button">分配</button>`
          : "";
      return `<tr data-id="${esc(row.id)}"><td>${esc(row.company)}</td><td>${esc(row.source_label)}</td><td>${esc(STATUS[row.status] || row.status)}</td><td>${phone}</td><td>${esc(productsOf(row))}</td><td><button class="btn small" data-open="${esc(row.id)}" type="button">查看</button>${assign}</td></tr>`;
    })
    .join("");
  const industryFilter =
    name === "pool"
      ? `<form id="poolFilter" class="panel"><label>业务行业<select name="industry"><option value="">全部</option>${(state.industries || [])
          .map((item) => `<option value="${esc(item.code)}"${state.poolIndustry === item.code ? " selected" : ""}>${esc(item.name)}</option>`)
          .join("")}</select></label></form>`
      : "";
  const importer =
    name === "base"
      ? `<form id="importForm" class="panel"><div class="panel-h"><h2>导入公海成交表</h2></div><p>按客户编码收成公司，不按 Excel 行。预览确认前不落库，也不生成打单卡。</p><input id="importFile" type="file" name="file" accept=".xlsx" required /><div class="row-actions"><button class="btn" type="submit">生成预览</button></div><div id="importPreview"></div></form>`
      : "";
  page(
    title,
    desc,
    `${industryFilter}${importer}<div class="panel"><div class="table-wrap"><table><thead><tr><th>公司</th><th>来源</th><th>状态</th><th>号码</th><th>并列建议</th><th></th></tr></thead><tbody>${body || `<tr><td colspan="6">暂无客户</td></tr>`}</tbody></table></div></div><div id="detail"></div>`,
  );
  const poolFilter = $("#poolFilter");
  if (poolFilter) {
    poolFilter.onsubmit = (e) => e.preventDefault();
    poolFilter.onchange = () => {
      state.poolIndustry = new FormData(poolFilter).get("industry") || "";
      openView("pool");
    };
  }
  const importForm = $("#importForm");
  if (importForm) {
    importForm.onsubmit = async (e) => {
      e.preventDefault();
      const file = $("#importFile").files[0];
      if (!file) return;
      const body = new FormData();
      body.append("file", file);
      try {
        state.industries = state.industries || (await ensureIndustries());
        state.preview = await api("/api/stock/admin/imports/preview", { method: "POST", body });
        if (!state.accounts.length) state.accounts = await api("/api/stock/admin/accounts");
        paintPreview();
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

function paintPreview() {
  const data = state.preview;
  const box = $("#importPreview");
  if (!data || !box) return;
  const summary = data.summary || {};
  const issues = (items, title) =>
    items.length
      ? `<h3>${title}</h3><ul class="issue-list">${items.map((item) => `<li>${esc(item.code)} ${esc(item.message)}</li>`).join("")}</ul>`
      : "";
  const options = (selected) =>
    [`<option value="">待确认</option>`]
      .concat(
        (state.industries || []).map(
          (item) => `<option value="${esc(item.code)}"${item.code === selected ? " selected" : ""}>${esc(item.name)}</option>`,
        ),
      )
      .join("");
  const cards = (data.companies || [])
    .map((company) => {
      const people = (company.contacts || [])
        .map((contact, index) => {
          const channels = (contact.channels || [])
            .map((channel) => `${channel.kind === "landline" ? "座机" : "手机"} ${channel.number}${channel.switchboard ? "（疑似总机）" : ""}`)
            .join(" / ");
          return `<li>${index + 1}. ${esc(contact.name || "未填姓名")} / ${esc(contact.role || "无职务")}${contact.preferred ? "（建议首选）" : ""} / ${esc(channels)}</li>`;
        })
        .join("");
      const analysis = company.kmi_account
        ? "分析层：有 K米账户，四格不因此填实。"
        : company.consult_unspecified
          ? "分析层：有咨询成交，产品线未细分。"
          : `分析层：${esc((company.scopes || []).join("、") || "未翻译到经营范围")}`;
      const related = (company.related || []).length ? `<p>关联建议：${esc(company.related.map((item) => item.company).join("、"))}</p>` : "";
      return `<div class="preview-block"><p><strong>${esc(company.company)}</strong> · ${esc(company.customer_code)}</p>
        <p>已购（展示，原文）：${esc(company.purchased_display || "—")}</p>
        <p>${analysis}</p>
        <label>主行业<select data-industry="${esc(company.customer_code)}">${options(company.industry_code)}</select></label>
        <p>标签：${esc((company.industry_tags || []).join("、") || "—")}</p>
        <ol>${people}</ol>${related}</div>`;
    })
    .join("");
  const owners = state.accounts
    .map((user) => `<option value="${esc(user.username)}">${esc(user.department)}（${esc(user.username)}）</option>`)
    .join("");
  box.innerHTML = `<div class="preview-block">
      <p>将生成 ${summary.companies || 0} 家客户、${summary.contacts || 0} 位联系人。Excel ${summary.excel_rows || 0} 行，其中 ${summary.multi_contact_companies || 0} 家有多位联系人。</p>
      <p>阻断 ${summary.blockers || 0} · 警告 ${summary.warnings || 0} · 提示 ${summary.hints || 0}</p>
      ${issues(data.blockers || [], "阻断，处理后才能导入")}
      ${issues(data.warnings || [], "警告")}
      ${issues(data.hints || [], "提示")}
      ${cards}
      <div class="row-actions">
        <button class="btn secondary" id="btnIssues" type="button">下载问题明细</button>
        <button class="btn secondary" id="btnUnknown" type="button">下载未识别成交原文</button>
      </div>
      <div class="form-grid">
        <label class="check"><input id="ackWarnings" type="checkbox" />已知晓警告</label>
        <label>去向<select id="importDestination"><option value="base">仅进公海底表</option><option value="pool">有信号的进公共池</option><option value="assign">指定部门账号当日名单</option></select></label>
        <label>部门账号<select id="importOwner">${owners || `<option value="">还没有一线账号</option>`}</select></label>
      </div>
      <div class="row-actions"><button class="btn" id="btnConfirmImport" type="button" ${data.can_confirm ? "" : "disabled"}>确认导入</button></div>
      <p>确认后按去向落库。这里不生成打单卡，也不开始拨打。</p>
    </div>`;
  $("#btnIssues").onclick = () => {
    const rows = [...(data.blockers || []), ...(data.warnings || []), ...(data.hints || [])].map((item) => [
      item.excel_row,
      item.customer_code,
      item.code,
      item.message,
    ]);
    downloadCsv("问题明细.csv", ["行号", "编码", "类型", "原文"], rows);
  };
  $("#btnUnknown").onclick = () => {
    const rows = [];
    (data.companies || []).forEach((company) => {
      (company.unrecognized || []).forEach((text) => rows.push([company.customer_code, company.company, text]));
    });
    downloadCsv("未识别成交原文.csv", ["编码", "客户", "原文"], rows);
  };
  $("#btnConfirmImport").onclick = async () => {
    if (!data.can_confirm) return;
    if ((data.warnings || []).length && !$("#ackWarnings").checked) {
      toast("请先勾选已知晓警告");
      return;
    }
    const destination = $("#importDestination").value;
    const owner = $("#importOwner").value;
    const companies = (data.companies || []).map((company) => {
      const select = document.querySelector(`[data-industry="${CSS.escape(company.customer_code)}"]`);
      const industry_code = select ? select.value : company.industry_code;
      const found = (state.industries || []).find((item) => item.code === industry_code);
      return {
        ...company,
        industry_code,
        industry_name: found ? found.name : "",
        entity_exception: industry_code === "IND00",
        industry_status: industry_code ? "confirmed" : "pending",
      };
    });
    try {
      const saved = await api("/api/stock/admin/imports/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          destination,
          owner,
          acknowledge: true,
          warning_count: (data.warnings || []).length,
          companies,
        }),
      });
      toast(`已导入 ${saved.count} 家`);
      state.preview = null;
      openView(destination === "pool" ? "pool" : "base");
    } catch (err) {
      toast(err.message);
    }
  };
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
  const contacts = record.contacts || [];
  const preferred = contacts.find((item) => item.preferred) || contacts[0];
  const others = contacts.filter((item) => item !== preferred);
  const channelText = (contact) =>
    (contact?.channels || [])
      .map((channel) => {
        const label = channel.kind === "landline" ? "座机" : "手机";
        const number = record.phone_visible ? channel.number || "—" : "号码不可见";
        const flags = `${channel.switchboard ? "，疑似总机" : ""}${channel.invalid ? "，已失效" : ""}`;
        return `${label} ${number}${flags}`;
      })
      .join(" / ") || (record.phone_visible ? "—" : "号码不可见");
  const more = others.length
    ? `<details><summary>还有 ${others.length} 人</summary><ul>${others
        .map((contact) => `<li>${esc(contact.name || "未填姓名")} ${esc(contact.role || "")} · ${esc(channelText(contact))}</li>`)
        .join("")}</ul></details>`
    : "";
  const phoneLine = preferred
    ? `${esc(preferred.name || "—")} ${esc(preferred.role || "")} · ${esc(channelText(preferred))}`
    : record.phone_visible
      ? esc(record.phone || "—")
      : "号码不可见";
  const canCall =
    record.status === "reachable" ||
    record.status === "trial" ||
    (record.status === "incubation" && record.phone_visible);
  const ask =
    record.status === "incubation" && record.source !== "self_upload" && !record.phone_visible
      ? `<button class="btn secondary" id="btnAsk" type="button">申请外呼</button>`
      : "";
  const channelOptions = contacts
    .flatMap((contact) =>
      (contact.channels || [])
        .filter((channel) => channel.number && !channel.invalid)
        .map(
          (channel) =>
            `<option value="${esc(contact.id)}|${esc(channel.number)}">${esc(contact.name || "联系人")} ${channel.kind === "landline" ? "座机" : "手机"} ${esc(channel.number)}</option>`,
        ),
    )
    .join("");
  const painFields = record.pain_recorded
    ? `<p>公司痛点已记录：${esc(record.pain_match || "")} ${esc(record.pain_note || "")}。打下一位联系人不用重填。</p>`
    : `<label>痛点<select name="pain_match"><option>属实</option><option>偏差</option></select></label>
        <label class="full">真实痛点或偏差<input name="pain_note" /></label>`;
  const call = canCall
    ? `<form id="callForm" class="form-grid">
        <label>本次号码<select name="channel">${channelOptions || `<option value="">暂无可用号码</option>`}</select></label>
        <label>意向<select name="intention"><option>有明确兴趣</option><option>暂无需求</option><option>需发资料</option><option>号码失效</option></select></label>
        ${painFields}
        <label>操作人备注或分机<input name="operator_note" /></label>
        <label>分机号<input name="extension" /></label>
        <div class="row-actions"><button class="btn" type="submit">保存回写</button></div>
      </form>`
    : "";
  const narrate = `<button class="btn ghost small" id="btnNarrate" type="button">润色五线</button>`;
  const box = $("#detail") || host();
  const html = `${notice}<div class="panel">
      <div class="panel-h"><h2>${esc(record.company)}</h2><span class="pill">${esc(record.source_label || "")}</span></div>
      <p>基本面：${phoneLine}${record.phone_note ? `（${esc(record.phone_note)}）` : ""} · ${esc(record.industry || "行业未填")}${(record.industry_tags || []).length ? ` · ${esc(record.industry_tags.join("、"))}` : ""}</p>
      ${more}
      <p>已购：${esc(record.purchased_display || record.purchased_scope || "已购未填")} · 截止 ${esc(record.service_end || "—")} · 客单价 ${esc(record.unit_price || "—")}</p>
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
    const channel = String(payload.channel || "");
    const splitAt = channel.indexOf("|");
    payload.contact_id = splitAt >= 0 ? channel.slice(0, splitAt) : "";
    payload.channel_number = splitAt >= 0 ? channel.slice(splitAt + 1) : "";
    delete payload.channel;
    if (payload.intention === "号码失效") payload.invalidate = true;
    if (record.pain_recorded && !payload.pain_match) payload.pain_match = record.pain_match || "";
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
    await ensureIndustries();
    rows = await api("/api/stock/admin/align");
  } catch (err) {
    toast(err.message);
  }
  const body = rows
    .map(
      (row) =>
        `<tr><td>${esc(row.company)}</td><td>${esc(row.industry || (row.industry_status === "pending" ? "行业待确认" : "—"))}</td><td>${esc(row.source_label)}</td><td>${
          row.industry_status === "pending"
            ? `<form data-industry-set="${esc(row.id)}" class="row"><select name="industry_code">${(state.industries || [])
                .map((item) => `<option value="${esc(item.code)}">${esc(item.name)}</option>`)
                .join("")}</select><button class="btn small" type="submit">确认行业</button></form>`
            : `<form data-align="${esc(row.id)}" class="row"><input name="crm_id" placeholder="CRM 主键" /><button class="btn small" type="submit">确认主体</button></form>`
        }</td></tr>`,
    )
    .join("");
  page(
    "主体待确认",
    "公司名对不齐、或业务行业还没确认的客户在这里。确认行业不会合并其他部门的名单。",
    `<div class="panel"><div class="table-wrap"><table><thead><tr><th>公司</th><th>行业</th><th>来源</th><th></th></tr></thead><tbody>${body || `<tr><td colspan="4">没有待确认主体</td></tr>`}</tbody></table></div></div>`,
  );
  host().querySelectorAll("[data-industry-set]").forEach((form) => {
    form.onsubmit = async (e) => {
      e.preventDefault();
      const industry_code = new FormData(form).get("industry_code");
      try {
        await api(`/api/stock/admin/industry/${form.dataset.industrySet}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ industry_code }),
        });
        toast("已确认行业");
        renderAlign();
      } catch (err) {
        toast(err.message);
      }
    };
  });
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
  let dealRows = [];
  try {
    dealRows = await api("/api/stock/admin/deal-map");
  } catch (err) {
    dealRows = [];
  }
  const dealBody = dealRows
    .map((row) => `<tr><td>${esc(row.keyword)}</td><td>${esc(row.kind === "kmi" ? "K米账户" : row.kind === "consult" ? "咨询未细分" : row.scope)}</td></tr>`)
    .join("");
  page(
    "行业条目",
    "上面十条是自有名单的参照。公海导入用另一套业务行业。成交对照只翻译给引擎，不改卡片上的已购原文。",
    `<div class="panel"><div class="table-wrap"><table><thead><tr><th>行业</th><th>状态</th><th></th></tr></thead><tbody>${body}</tbody></table></div></div>
     <form id="dealForm" class="panel"><div class="panel-h"><h2>成交原文对照</h2></div>
       <div class="form-grid">
         <label>原文关键词<input name="keyword" placeholder="例如 咨询服务" required /></label>
         <label>分析层<select name="scope"><option value="consult">咨询未细分，不占格</option><option value="kmi">K米账户，不占格</option><option>人才测评</option><option>人才盘点</option><option>绩效薪酬咨询</option><option>人才培训</option><option>人事考勤软件</option><option>招聘软件和服务</option><option>绩效薪酬软件和咨询服务</option><option>员工敬业度满意度调研</option><option>一线管理者提升</option><option>中层管理提升</option><option>AI 学习平台</option></select></label>
       </div>
       <div class="row-actions"><button class="btn" type="submit">加入对照</button></div>
       <div class="table-wrap"><table><thead><tr><th>关键词</th><th>分析层</th></tr></thead><tbody>${dealBody || `<tr><td colspan="2">还没有额外对照，内置的 HRO、云、内训、K米 已能识别</td></tr>`}</tbody></table></div>
     </form>`,
  );
  const dealForm = $("#dealForm");
  if (dealForm) {
    dealForm.onsubmit = async (e) => {
      e.preventDefault();
      const payload = Object.fromEntries(new FormData(dealForm).entries());
      try {
        await api("/api/stock/admin/deal-map", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        toast("已加入对照");
        renderPlaybooks();
      } catch (err) {
        toast(err.message);
      }
    };
  }
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
