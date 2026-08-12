from __future__ import annotations

import io
import zipfile
from datetime import datetime, timedelta
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, engine, excel_import, image_gen, llm, storage
from .seed_data import reset_and_seed, seed_all

app = FastAPI(title="肯耐珂萨销售陌拜工作台", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    storage.ensure_data_dir()
    seed_all()
    if not storage.list_items("wechat_todos") and not (config.DATA_DIR / "wechat_todos.json").exists():
        storage.write_collection("wechat_todos", [])
    # 帮助图可异步缺失，首次打开帮助时再生成
    config.ASSETS_DIR.mkdir(parents=True, exist_ok=True)


class LeadIn(BaseModel):
    name: str = "客户"
    phone: str = ""
    company: str
    title: str = ""
    industry: str = ""
    company_size: str = ""
    source: str = "手工录入"
    notes: str = ""
    status: str = "待分析"
    workflow_step: int = 1
    owner: str = ""


class ProfileIn(BaseModel):
    lead_id: str
    company: str = ""
    industry: str = ""
    company_size: str = ""
    stage: str = ""
    financing: str = ""
    summary: str = ""
    jobs: list[dict] = Field(default_factory=list)
    recruiting_text: str = ""
    news_text: str = ""
    review_text: str = ""
    website_text: str = ""
    contact_title: str = ""
    contact_notes: str = ""
    recent_change: bool = False
    research_notes: str = ""


class RuleIn(BaseModel):
    id: str | None = None
    signal_type: str
    signal_keywords: str
    signal_strength: int = 3
    need: str = ""
    products: str = ""
    confidence: float = 60
    extra_condition: str = ""
    exception: str = ""
    script_id: str = ""
    author: str = "Ira"
    validation_status: str = "未验证"
    enabled: bool = True


class ScriptIn(BaseModel):
    id: str | None = None
    name: str
    signal: str = ""
    channel: str = "电话"
    body: str
    wechat: str = ""
    version: str = "A"


class CompetitorIn(BaseModel):
    id: str | None = None
    name: str
    aliases: str = ""
    keywords: str = ""
    tier: str = "medium"
    category: str = ""
    strategy: str = ""
    enabled: bool = True


class OutreachIn(BaseModel):
    lead_id: str
    channel: str = "电话"
    script_id: str = ""
    script_version: str = "A"
    call_time: str = ""
    duration_min: str = ""
    outcome: str = "未接通"
    need_confirmed: str = ""
    objection: str = ""
    next_step: str = ""
    notes: str = ""
    agree_wechat: bool = False
    wechat_id_hint: str = ""
    materials_to_send: str = ""
    assignee: str = ""
    rule_ids: list[str] = Field(default_factory=list)
    deal_stage: str = ""


class WechatTodoIn(BaseModel):
    lead_id: str
    assignee: str = ""
    wechat_id_hint: str = ""
    materials_to_send: str = "案例资料 / 白皮书"
    notes: str = ""
    due_at: str = ""


class AIProfileIn(BaseModel):
    lead_id: str
    extra_context: str = ""


class AIAnalyzeIn(BaseModel):
    lead_id: str
    supplement: str = ""


class AIScriptIn(BaseModel):
    lead_id: str
    signal: str = ""
    tone: str = "专业克制，代表肯耐珂萨，首通不硬推销"


class AIRuleIn(BaseModel):
    experience: str


def _lead_or_404(lead_id: str) -> dict:
    lead = storage.get_item("leads", lead_id)
    if not lead:
        raise HTTPException(404, "线索不存在")
    return lead


def _set_step(lead: dict, step: int, status: str | None = None) -> dict:
    lead["workflow_step"] = max(int(lead.get("workflow_step") or 1), step)
    if status:
        lead["status"] = status
    return storage.upsert_item("leads", lead)


@app.get("/api/health")
def health() -> dict:
    # 对前端只暴露业务就绪状态，不暴露模型名与实现细节
    return {
        "ok": True,
        "assistant_ready": llm.available(),
        "time": storage.now_iso(),
    }


@app.get("/api/dashboard")
def dashboard() -> dict:
    leads = storage.list_items("leads")
    outreach = storage.list_items("outreach")
    wechat_todos = storage.list_items("wechat_todos")
    pending_wechat = [t for t in wechat_todos if t.get("status") != "done"]
    tiers: dict[str, int] = {}
    steps = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for lead in leads:
        t = lead.get("last_tier") or "未评分"
        tiers[t] = tiers.get(t, 0) + 1
        step = int(lead.get("workflow_step") or 1)
        steps[step] = steps.get(step, 0) + 1
    return {
        "counts": {
            "leads": len(leads),
            "analyzed": sum(1 for l in leads if l.get("last_score") is not None),
            "called": len(outreach),
            "wechat_pending": len(pending_wechat),
            "rules": len(storage.list_items("rules")),
        },
        "steps": steps,
        "tiers": tiers,
        "recent_leads": sorted(leads, key=lambda x: x.get("updated_at", ""), reverse=True)[:8],
        "pending_wechat": pending_wechat[:10],
        "settings": storage.read_object("settings", {}),
    }


@app.post("/api/seed/reset")
def api_reset_seed() -> dict:
    result = reset_and_seed()
    storage.write_collection("wechat_todos", [])
    return result


@app.get("/api/export/data.zip")
def export_data_zip() -> StreamingResponse:
    """打包 data/*.json 供本地下载；不写入 Git。"""
    storage.ensure_data_dir()
    buf = io.BytesIO()
    written = 0
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in storage.COLLECTIONS:
            path = config.DATA_DIR / f"{name}.json"
            if not path.exists():
                continue
            zf.write(path, arcname=f"{name}.json")
            written += 1
        for path in sorted(config.DATA_DIR.glob("*.json")):
            if path.stem in storage.COLLECTIONS:
                continue
            if path.name.startswith("_") or path.name.startswith("._"):
                continue
            zf.write(path, arcname=path.name)
            written += 1
    if written == 0:
        raise HTTPException(404, "暂无可导出的数据文件")
    buf.seek(0)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"knx-data-{stamp}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/help")
def help_meta() -> dict:
    exists = config.HELP_IMAGE_PATH.exists() and config.HELP_IMAGE_PATH.stat().st_size > 1000
    return {
        "title": "KNX 智拓 · 使用说明",
        "steps": [
            {"n": 1, "title": "上传名单", "desc": "导入 Excel 客户表，系统自动识别姓名、电话、公司等字段"},
            {"n": 2, "title": "客户触达", "desc": "在列表点击客户，弹框内查看需求分析与话术，外呼并直接保存通话记录"},
            {"n": 3, "title": "微信待办", "desc": "对方同意加微后，提醒同事添加微信并发送资料"},
        ],
        "image_ready": exists,
        "image_url": "/assets/help-workflow.png" if exists else None,
        "author": "Ira",
        "org": "KNX 智拓 · 肯耐珂萨",
    }


@app.post("/api/help/generate-image")
def help_generate_image(force: bool = False) -> dict:
    try:
        path = image_gen.ensure_help_image(force=force)
    except image_gen.ImageError as e:
        raise HTTPException(502, f"流程图生成失败，请稍后重试") from e
    return {"ok": True, "image_url": "/assets/help-workflow.png", "bytes": path.stat().st_size}


@app.post("/api/import/excel")
async def import_excel(file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm", ".xltx")):
        raise HTTPException(400, "请上传 Excel 文件（.xlsx）")
    content = await file.read()
    if not content:
        raise HTTPException(400, "文件为空")
    try:
        result = excel_import.parse_leads_with_llm(content, file.filename)
    except llm.LLMError as e:
        raise HTTPException(502, "名单解析失败，请检查表格内容后重试") from e
    except Exception as e:
        raise HTTPException(400, f"无法读取 Excel：{e}") from e
    return result


@app.get("/api/leads")
def list_leads() -> list:
    return sorted(storage.list_items("leads"), key=lambda x: x.get("updated_at", ""), reverse=True)


@app.post("/api/leads")
def create_lead(body: LeadIn) -> dict:
    item = body.model_dump()
    item["id"] = storage.new_id("L")
    item["workflow_step"] = 1
    return storage.upsert_item("leads", item)


@app.put("/api/leads/{lead_id}")
def update_lead(lead_id: str, body: LeadIn) -> dict:
    existing = _lead_or_404(lead_id)
    item = {**existing, **body.model_dump(), "id": lead_id}
    return storage.upsert_item("leads", item)


@app.delete("/api/leads/{lead_id}")
def delete_lead(lead_id: str) -> dict:
    if not storage.delete_item("leads", lead_id):
        raise HTTPException(404, "线索不存在")
    storage.write_collection(
        "profiles", [p for p in storage.list_items("profiles") if p.get("lead_id") != lead_id]
    )
    return {"ok": True}


@app.post("/api/leads/{lead_id}/analyze")
def analyze(lead_id: str) -> dict:
    try:
        result = engine.analyze_lead(lead_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    lead = _lead_or_404(lead_id)
    _set_step(lead, 2, "已分析")
    result["lead"] = storage.get_item("leads", lead_id)
    return result


@app.post("/api/ai/analyze-need")
def ai_analyze_need(body: AIAnalyzeIn) -> dict:
    """AI 全自动需求分析：规则匹配 + 模型解读，结果写回线索。"""
    lead = _lead_or_404(body.lead_id)
    if body.supplement.strip():
        lead["manual_supplement"] = body.supplement.strip()
        storage.upsert_item("leads", lead)
        # 同步进画像备注，供规则引擎文本匹配
        profile = None
        for p in storage.list_items("profiles"):
            if p.get("lead_id") == body.lead_id:
                profile = p
                break
        if not profile:
            profile = {
                "id": storage.new_id("PF"),
                "lead_id": body.lead_id,
                "company": lead.get("company"),
            }
        note = body.supplement.strip()
        profile["research_notes"] = note
        profile["recruiting_text"] = ((profile.get("recruiting_text") or "") + "\n" + note).strip()
        profile["summary"] = note if not profile.get("summary") else profile.get("summary")
        storage.upsert_item("profiles", profile)

    try:
        result = engine.analyze_lead(body.lead_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e

    products_catalog = storage.list_items("products")
    system = (
        "你是肯耐珂萨销售需求分析助手。根据线索与规则命中结果，输出面向销售可读的 JSON："
        "{need_analysis: string(2-4句中文，说清客户可能的HR需求与判断依据),"
        " recommended_products: string(推荐的产品/服务，用顿号或逗号分隔),"
        " priority_reason: string(为何值得现在打),"
        " talk_angle: string(一句话切入角度),"
        " phone_opener: string(30秒首通开场，代表肯耐珂萨，不硬推销),"
        " wechat_invite: string,"
        " questions: string[]}。"
        "语气务实，不要提模型或技术实现。"
    )
    user = (
        f"线索：{lead}\n人工补充：{body.supplement or lead.get('manual_supplement') or ''}\n"
        f"规则命中：{result.get('rule_hits', [])[:5]}\n"
        f"市场方案：{result.get('competitor_hits', [])}\n"
        f"优先级：{result.get('priority')}\n"
        f"可推荐产品目录：{[p.get('name') for p in products_catalog]}\n请输出 JSON。"
    )
    try:
        insights = llm.chat_json(system=system, user=user, temperature=0.3, max_tokens=1800)
    except llm.LLMError as e:
        # 模型不可用时降级为规则汇总
        hits = result.get("rule_hits") or []
        insights = {
            "need_analysis": "；".join(h.get("need", "") for h in hits[:3]) or "信息不足，建议补充招聘/新闻后再分析",
            "recommended_products": "、".join(
                dict.fromkeys(x for h in hits[:3] for x in str(h.get("products") or "").replace("，", "、").split("、") if x)
            )
            or "待定",
            "priority_reason": (result.get("priority") or {}).get("tier", ""),
            "talk_angle": "先确认对方当前最紧迫的人事管理问题",
            "phone_opener": "您好，我是肯耐珂萨，想跟您确认下贵司目前在组织与人才管理上最想先解决的是哪一块。",
            "wechat_invite": "方便加微信吗？我把同行业轻量案例发您先看。",
            "questions": ["目前最紧迫的是系统、组织还是干部能力？"],
        }

    lead = _lead_or_404(body.lead_id)
    lead["need_analysis"] = str(insights.get("need_analysis") or "").strip()
    lead["recommended_products"] = str(insights.get("recommended_products") or "").strip()
    lead["priority_reason"] = str(insights.get("priority_reason") or "").strip()
    lead["talk_angle"] = str(insights.get("talk_angle") or "").strip()
    lead["phone_opener"] = str(insights.get("phone_opener") or "").strip()
    lead["wechat_invite"] = str(insights.get("wechat_invite") or "").strip()
    lead["script_questions"] = insights.get("questions") or []
    lead["last_analyzed_at"] = storage.now_iso()
    if body.supplement.strip():
        lead["manual_supplement"] = body.supplement.strip()
    _set_step(lead, 3, "已分析")
    lead = storage.get_item("leads", body.lead_id) or lead

    return {
        "lead": lead,
        "insights": insights,
        "rule_hits": result.get("rule_hits", []),
        "competitor_hits": result.get("competitor_hits", []),
        "priority": result.get("priority"),
        "scripts": result.get("scripts", []),
    }


@app.get("/api/profiles")
def list_profiles() -> list:
    return storage.list_items("profiles")


@app.get("/api/profiles/by-lead/{lead_id}")
def profile_by_lead(lead_id: str) -> dict:
    for p in storage.list_items("profiles"):
        if p.get("lead_id") == lead_id:
            return p
    raise HTTPException(404, "画像不存在")


@app.post("/api/profiles")
def save_profile(body: ProfileIn) -> dict:
    existing = None
    for p in storage.list_items("profiles"):
        if p.get("lead_id") == body.lead_id:
            existing = p
            break
    item = body.model_dump()
    item["id"] = (existing or {}).get("id") or storage.new_id("PF")
    if existing:
        item = {**existing, **item}
    saved = storage.upsert_item("profiles", item)
    lead = storage.get_item("leads", body.lead_id)
    if lead:
        _set_step(lead, 2)
    return saved


def _crud_save(name: str, payload: dict, prefix: str) -> dict:
    if not payload.get("id"):
        payload["id"] = storage.new_id(prefix)
    return storage.upsert_item(name, payload)


@app.get("/api/rules")
def list_rules() -> list:
    return storage.list_items("rules")


@app.post("/api/rules")
def save_rule(body: RuleIn) -> dict:
    item = body.model_dump()
    item.setdefault("hit_count", 0)
    item.setdefault("deal_count", 0)
    item.setdefault("accuracy", 0)
    return _crud_save("rules", item, "R")


@app.delete("/api/rules/{item_id}")
def delete_rule(item_id: str) -> dict:
    if not storage.delete_item("rules", item_id):
        raise HTTPException(404)
    return {"ok": True}


@app.get("/api/scripts")
def list_scripts() -> list:
    return storage.list_items("scripts")


@app.post("/api/scripts")
def save_script(body: ScriptIn) -> dict:
    return _crud_save("scripts", body.model_dump(), "T")


@app.delete("/api/scripts/{item_id}")
def delete_script(item_id: str) -> dict:
    if not storage.delete_item("scripts", item_id):
        raise HTTPException(404)
    return {"ok": True}


@app.get("/api/competitors")
def list_competitors() -> list:
    # 永不返回本公司
    return [
        c
        for c in storage.list_items("competitors")
        if "肯耐" not in (c.get("name") or "") and "Kenexa" not in (c.get("name") or "")
    ]


@app.post("/api/competitors")
def save_competitor(body: CompetitorIn) -> dict:
    if "肯耐" in body.name or "Kenexa" in body.name or "knx" in body.name.lower():
        raise HTTPException(400, "本公司无需录入竞品词典")
    return _crud_save("competitors", body.model_dump(), "C")


@app.delete("/api/competitors/{item_id}")
def delete_competitor(item_id: str) -> dict:
    if not storage.delete_item("competitors", item_id):
        raise HTTPException(404)
    return {"ok": True}


@app.get("/api/products")
def list_products() -> list:
    return storage.list_items("products")


@app.get("/api/scoring")
def get_scoring() -> dict:
    return storage.read_object("scoring", {})


@app.put("/api/scoring")
def put_scoring(body: dict[str, Any]) -> dict:
    current = storage.read_object("scoring", {})
    current.update(body)
    return storage.write_object("scoring", current)


@app.get("/api/outreach")
def list_outreach() -> list:
    return sorted(storage.list_items("outreach"), key=lambda x: x.get("created_at", ""), reverse=True)


@app.post("/api/outreach")
def create_outreach(body: OutreachIn) -> dict:
    _lead_or_404(body.lead_id)
    item = body.model_dump()
    item["id"] = storage.new_id("O")
    item["created_at"] = storage.now_iso()
    if not item.get("call_time"):
        item["call_time"] = storage.now_iso()
    saved = storage.upsert_item("outreach", item)

    if body.deal_stage in ("方案", "成交"):
        for rid in body.rule_ids:
            rule = storage.get_item("rules", rid)
            if rule:
                rule["deal_count"] = int(rule.get("deal_count") or 0) + 1
                hc = int(rule.get("hit_count") or 0)
                rule["accuracy"] = round(rule["deal_count"] / hc * 100, 1) if hc else 0
                storage.upsert_item("rules", rule)

    lead = storage.get_item("leads", body.lead_id)
    status = body.deal_stage or body.outcome
    _set_step(lead, 4, status)

    if body.agree_wechat:
        todo = {
            "id": storage.new_id("W"),
            "lead_id": body.lead_id,
            "company": lead.get("company"),
            "contact_name": lead.get("name"),
            "phone": lead.get("phone"),
            "assignee": body.assignee or lead.get("owner") or "",
            "wechat_id_hint": body.wechat_id_hint,
            "materials_to_send": body.materials_to_send or "案例资料 / 白皮书",
            "notes": body.notes,
            "due_at": (datetime.now() + timedelta(hours=4)).strftime("%Y-%m-%d %H:%M"),
            "status": "pending",
            "created_at": storage.now_iso(),
            "updated_at": storage.now_iso(),
        }
        storage.upsert_item("wechat_todos", todo)
        _set_step(lead, 5, "待加微信")

    return saved


@app.get("/api/wechat-todos")
def list_wechat_todos() -> list:
    return sorted(storage.list_items("wechat_todos"), key=lambda x: x.get("due_at", ""))


@app.post("/api/wechat-todos")
def create_wechat_todo(body: WechatTodoIn) -> dict:
    lead = _lead_or_404(body.lead_id)
    item = body.model_dump()
    item["id"] = storage.new_id("W")
    item["company"] = lead.get("company")
    item["contact_name"] = lead.get("name")
    item["phone"] = lead.get("phone")
    item["status"] = "pending"
    if not item.get("due_at"):
        item["due_at"] = (datetime.now() + timedelta(hours=4)).strftime("%Y-%m-%d %H:%M")
    saved = storage.upsert_item("wechat_todos", item)
    _set_step(lead, 5, "待加微信")
    return saved


@app.post("/api/wechat-todos/{tid}/done")
def complete_wechat_todo(tid: str) -> dict:
    item = storage.get_item("wechat_todos", tid)
    if not item:
        raise HTTPException(404)
    item["status"] = "done"
    item["done_at"] = storage.now_iso()
    return storage.upsert_item("wechat_todos", item)


@app.get("/api/followups")
def list_followups() -> list:
    return sorted(storage.list_items("followups"), key=lambda x: x.get("due_at", ""))


@app.post("/api/followups/{fid}/done")
def complete_followup(fid: str) -> dict:
    item = storage.get_item("followups", fid)
    if not item:
        raise HTTPException(404)
    item["status"] = "done"
    item["done_at"] = storage.now_iso()
    return storage.upsert_item("followups", item)


@app.post("/api/ai/enrich-profile")
def ai_enrich_profile(body: AIProfileIn) -> dict:
    lead = _lead_or_404(body.lead_id)
    profile = None
    for p in storage.list_items("profiles"):
        if p.get("lead_id") == body.lead_id:
            profile = p
            break
    system = (
        "你是肯耐珂萨资深销售研究员，帮助销售在打电话前做有的放矢的需求分析。"
        "根据有限线索输出企业画像 JSON。不确定处标注「待核实」并给出调研方向。"
        "字段：summary, industry, company_size, stage, financing, jobs(array of {title,desc}), "
        "recruiting_text, news_text, review_text, website_text, contact_title, contact_notes, "
        "recent_change(boolean), hypothesized_needs(array), research_checklist(array), "
        "recommended_angle(string)。"
    )
    user = f"线索：{lead}\n现有画像：{profile or '{}'}\n补充：{body.extra_context}\n请输出 JSON。"
    try:
        data = llm.chat_json(system=system, user=user, temperature=0.3, max_tokens=2500)
    except llm.LLMError as e:
        raise HTTPException(502, "智能分析暂时不可用，请稍后重试") from e
    merged = {
        "id": (profile or {}).get("id") or storage.new_id("PF"),
        "lead_id": body.lead_id,
        "company": lead.get("company"),
        **(profile or {}),
        **{k: v for k, v in data.items() if k != "id"},
    }
    saved = storage.upsert_item("profiles", merged)
    _set_step(lead, 2, "需求分析中")
    return {"profile": saved, "insights": data}


@app.post("/api/ai/generate-script")
def ai_generate_script(body: AIScriptIn) -> dict:
    lead = _lead_or_404(body.lead_id)
    try:
        analysis = engine.analyze_lead(body.lead_id)
    except Exception:
        analysis = None
    system = (
        "你是肯耐珂萨电话销售教练。生成首通开场白：代表肯耐珂萨，不硬推销，"
        "只做需求确认+建立信任；30秒内说完；口语化中文。"
        "输出 JSON：phone_opener, wechat_invite, questions(array), taboo(array), signal_used。"
    )
    user = (
        f"线索：{lead}\n信号：{body.signal}\n语气：{body.tone}\n"
        f"命中需求：{(analysis or {}).get('rule_hits', [])[:3]}\n"
        f"市场方案：{(analysis or {}).get('competitor_hits', [])}\n请输出 JSON。"
    )
    try:
        data = llm.chat_json(system=system, user=user, temperature=0.5, max_tokens=1500)
    except llm.LLMError as e:
        raise HTTPException(502, "话术生成暂时不可用，请稍后重试") from e
    _set_step(lead, 3, "待触达")
    # 可选落库一条临时话术
    return data


@app.post("/api/ai/experience-to-rule")
def ai_experience_to_rule(body: AIRuleIn) -> dict:
    system = (
        "把肯耐珂萨销售的陌拜经验转成规则表一行。输出 JSON："
        "signal_type, signal_keywords(用/分隔), signal_strength(1-5), need, products, "
        "confidence(0-100), extra_condition, exception, suggested_script_name, notes。"
    )
    try:
        return llm.chat_json(
            system=system,
            user=f"经验描述：{body.experience}\n请输出 JSON。",
            temperature=0.2,
            max_tokens=1200,
        )
    except llm.LLMError as e:
        raise HTTPException(502, "规则整理暂时不可用，请稍后重试") from e


# 静态资源：帮助图等
config.ASSETS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/assets", StaticFiles(directory=str(config.ASSETS_DIR)), name="assets")
app.mount("/static", StaticFiles(directory=str(config.FRONTEND_DIR)), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(config.FRONTEND_DIR / "index.html")


@app.get("/css/{path:path}")
def css(path: str) -> FileResponse:
    return FileResponse(config.FRONTEND_DIR / "css" / path)


@app.get("/js/{path:path}")
def js(path: str) -> FileResponse:
    return FileResponse(config.FRONTEND_DIR / "js" / path)
