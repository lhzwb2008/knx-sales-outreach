from __future__ import annotations

from typing import Any

from . import storage

PRODUCT = {
    "id": "P011",
    "name": "出海人力咨询",
    "category": "出海用工",
    "desc": "跨境用工合规、名义雇主 EOR、派驻签证与个税、全球薪酬代发；覆盖 160+ 国家/地区",
}

SCRIPTS = [
    {
        "id": "T012",
        "name": "出海·HRD合规开场",
        "signal": "出海/海外招聘/HRD",
        "channel": "电话",
        "body": "您好，请问是人力资源总监吗？我是肯耐珂萨出海组织这边的。很多企业从国内走到海外，HR会先碰到三件事：当地还没设公司人怎么合法雇、派驻过去签证和个税怎么处理、当地薪酬没有对标数据。想请教一下，贵司海外用工是已经有成熟供应商，还是还在摸当地政策？",
        "wechat": "方便加微信吗？我发一份《企业出海目标国用工合规避坑手册》，您先对照看，不着急。",
        "version": "A",
    },
    {
        "id": "T013",
        "name": "出海·业务负责人速度开场",
        "signal": "出海/海外事业部/总经理",
        "channel": "电话",
        "body": "您好，我是肯耐珂萨。不少团队出海前半年最怕为了几个人去当地注册公司，开户走半年、窗口被别人抢走。我们这边名义雇主大概 3 到 5 天能让人在当地合法上岗，试错成本大约是自建实体的十分之一。想请教您现在是先派人过去，还是已经在当地招人了？",
        "wechat": "加个微信，我把目标国 3 到 5 天上岗的路径发您，方便内部对齐速度和成本。",
        "version": "A",
    },
    {
        "id": "T014",
        "name": "出海·已有当地代理",
        "signal": "当地中介/海外代理",
        "channel": "电话",
        "body": "您好，当地代理帮忙办手续很常见。我们碰到的情况往往是总部管不透：绩效看不见、发薪是黑盒。肯耐珂萨按 160 多个国家帮总部把用工和算薪规则收成一套。方便问下，现在海外发薪和对账，总部能不能直接看清？",
        "wechat": "加微信发您一份《海外组织成熟度诊断清单》，20 分钟对一下总部能不能穿透当地。",
        "version": "A",
    },
]

RULES = [
    {
        "id": "R023",
        "signal_type": "招聘JD",
        "signal_keywords": "海外市场经理/印尼/越南/泰国/中东/东南亚/海外销售/国际业务/海外运营/海外仓",
        "signal_strength": 5,
        "need": "正在招海外岗位或建海外团队，用工合规与落地速度并行",
        "products": "出海人力咨询、猎头/高管寻访",
        "confidence": 80,
        "extra_condition": "同时有「出海」或「海外子公司」则置信度+12",
        "exception": "仅外贸跟单/跨境客服、人仍在国内办公，不等于当地雇佣",
        "script_id": "T012",
        "author": "出海初版",
        "validation_status": "验证中",
        "hit_count": 0,
        "deal_count": 0,
        "accuracy": 0,
        "enabled": True,
    },
    {
        "id": "R024",
        "signal_type": "招聘JD",
        "signal_keywords": "安装调试/驻场/外派/售后工程师/商务签/海外交付",
        "signal_strength": 5,
        "need": "派驻人员出境作业，签证与非法劳工风险",
        "products": "出海人力咨询、培训体系与企业大学",
        "confidence": 78,
        "extra_condition": "同时有装备/机械/新能源则置信度+10",
        "exception": "纯国内驻厂调试不做出海",
        "script_id": "T012",
        "author": "出海初版",
        "validation_status": "验证中",
        "hit_count": 0,
        "deal_count": 0,
        "accuracy": 0,
        "enabled": True,
    },
    {
        "id": "R025",
        "signal_type": "企业新闻",
        "signal_keywords": "跨境电商/独立站/海外仓/汉诺威/广交会出海/本地化运营",
        "signal_strength": 4,
        "need": "海外一线用工与多国发薪口径",
        "products": "出海人力咨询、人事考勤薪酬 SaaS",
        "confidence": 74,
        "extra_condition": "同时有旺季/蓝领/海外仓则置信度+10",
        "exception": "仅国内电商仓储",
        "script_id": "T013",
        "author": "出海初版",
        "validation_status": "未验证",
        "hit_count": 0,
        "deal_count": 0,
        "accuracy": 0,
        "enabled": True,
    },
]

R022_PATCH = {
    "signal_keywords": "出海/海外分公司/国际化/新加坡主体/海外子公司/当地主体",
    "need": "多地雇佣合规与统一人事，可同时看出海用工和国内一体化",
    "products": "出海人力咨询、HR一体化 SaaS",
    "confidence": 72,
    "extra_condition": "多国发薪则置信度+15",
    "exception": "仅贸易出口无本地雇佣",
    "script_id": "T012",
    "validation_status": "验证中",
}

OBJECTIONS = [
    {
        "trigger": "我们暂时不需要 / 海外人很少",
        "response": "起步这几个人最容易踩坑。为两三个人去当地设公司，注册开户往往要几个月。私下发薪又有资金和劳资风险。名义雇主就是为起步期设计的，人少也能 3 到 5 天合法上岗。",
    },
    {
        "trigger": "我们已经有当地代理/中介在做",
        "response": "当地代理办手续没问题。差别通常在总部能不能看清：绩效是否可控、发薪是不是黑盒。我们是按 160 多个国家帮总部把算薪和激励规则收成一套，不是再找一个代办。",
    },
    {
        "trigger": "发资料到邮箱吧 / 你把方案发我",
        "response": "可以发。为了对上版本，想请教两个具体信息：大概是哪个国家、当地大概几个人。我按这个发，并约一个回访时间，避免资料不对口。",
    },
    {
        "trigger": "我不负责这块",
        "response": "明白，不耽误您。方便告诉我实际负责海外用工或薪酬的同事姓名和联系方式吗？我只会转达一句：不设当地公司也能 3 到 5 天让人合法上岗。",
    },
]

DEFAULT_QUESTIONS = [
    "贵司海外用工，是已经有成熟供应商，还是还在摸当地政策？",
    "现在是先派人出去，还是已经在当地招人？",
    "海外发薪和对账，总部能不能直接看清？",
]

HOOK_ASSET = "企业出海目标国用工合规避坑手册"


def ensure_catalog() -> None:
    """线上已有数据时也能补上出海产品、话术、规则，不覆盖销售改过的同 ID 记录。"""
    storage.ensure_data_dir()
    now = storage.now_iso()

    if not storage.get_item("products", PRODUCT["id"]):
        storage.upsert_item("products", {**PRODUCT, "created_at": now})

    for script in SCRIPTS:
        if not storage.get_item("scripts", script["id"]):
            storage.upsert_item("scripts", {**script, "created_at": now})

    existing_r022 = storage.get_item("rules", "R022")
    if existing_r022:
        products = str(existing_r022.get("products") or "")
        if "出海人力咨询" not in products:
            patched = {**existing_r022, **R022_PATCH, "id": "R022"}
            storage.upsert_item("rules", patched)

    for rule in RULES:
        if not storage.get_item("rules", rule["id"]):
            storage.upsert_item("rules", {**rule, "created_at": now})


def is_overseas_context(lead: dict[str, Any], rule_hits: list[dict], insights: dict[str, Any] | None = None) -> bool:
    chunks = [
        lead.get("company") or "",
        lead.get("title") or "",
        lead.get("notes") or "",
        lead.get("manual_supplement") or "",
        lead.get("need_analysis") or "",
        lead.get("recommended_products") or "",
        (insights or {}).get("recommended_products") or "",
        (insights or {}).get("need_analysis") or "",
    ]
    for hit in rule_hits or []:
        chunks.append(str(hit.get("products") or ""))
        chunks.append(str(hit.get("need") or ""))
        chunks.append(" ".join(hit.get("matched_keywords") or []))
    blob = "\n".join(chunks)
    keys = ("出海", "海外", "EOR", "名义雇主", "海外仓", "跨境", "国际化", "派驻", "外派")
    return any(k in blob for k in keys)


def merge_products(*parts: str) -> str:
    names: list[str] = []
    for part in parts:
        for token in str(part or "").replace("，", "、").replace(",", "、").split("、"):
            name = token.strip()
            if name and name not in names:
                names.append(name)
    return "、".join(names)


def attach_playbook(lead: dict[str, Any], *, overseas: bool) -> dict[str, Any]:
    if overseas:
        lead["script_objections"] = OBJECTIONS
        lead["hook_asset"] = HOOK_ASSET
    else:
        lead.pop("script_objections", None)
        lead.pop("hook_asset", None)
    return lead
