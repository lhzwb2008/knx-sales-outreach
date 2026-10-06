"""公海导入用的业务行业和成交对照。

已购展示仍用成交原文。这里只给分格、先导和并列建议。
旧的十条行业剧本留给没有这套行业编码的自有名单。
"""
from __future__ import annotations

import re
from typing import Any

from .playbooks import SHELF, STAGE_LABELS

INDUSTRIES: tuple[dict[str, Any], ...] = (
    {"code": "IND01", "name": "医药 / 医疗", "terms": ("医院", "医药", "医疗", "器械", "诊所", "药店")},
    {"code": "IND02", "name": "制造（含新能源、轻工）", "terms": ("制造", "工厂", "装备", "新能源", "汽车", "皮革", "电子", "半导体")},
    {"code": "IND03", "name": "国有企业 / 地方平台", "terms": ("城投", "平台", "国资", "农投")},
    {"code": "IND04", "name": "科技 / 互联网", "terms": ("科技", "软件", "网络", "信息", "智能", "互联网")},
    {"code": "IND05", "name": "银行 / 保险 / 持牌金融", "terms": ("银行", "保险", "保理", "证券", "信托", "消金", "财务公司")},
    {"code": "IND06", "name": "房地产 / 物业 / 经纪", "terms": ("有家", "房产", "地产", "置业", "商置", "小镇", "物业", "经纪")},
    {"code": "IND07", "name": "酒店 / 连锁住宿", "terms": ("酒店", "宾馆", "住宿", "度假")},
    {"code": "IND08", "name": "能源 / 石油 / 电力", "terms": ("石油", "石化", "电力", "核电", "能源", "燃气", "壳牌")},
    {"code": "IND09", "name": "快消 / 日化", "terms": ("日化", "食品", "饮料", "洗护", "蓝月亮")},
    {"code": "IND10", "name": "专业服务 / 企业管理 / 人力相关", "terms": ("企业管理", "管理咨询", "人力资源", "劳务", "外包", "商贸", "传媒", "咨询")},
    {"code": "IND00", "name": "主体例外", "terms": ()},
)

# 比通用关键词更具体的名称。中久大光虽带「科技」，本批按制造。
NAME_HINTS: tuple[tuple[str, str], ...] = (
    ("中久大光", "IND02"),
    ("东呈酒店", "IND07"),
    ("君臣逸", "IND07"),
    ("乐有家", "IND06"),
    ("招商商置", "IND06"),
    ("理想小镇", "IND06"),
    ("壳牌", "IND08"),
    ("十月知行", "IND10"),
    ("无限家", "IND04"),
    ("德信睿腾", "IND04"),
    ("沐易商贸", "IND10"),
)

SPEAKABLE = {
    "IND01": "集采和合规把利润压住之后，销售或医务辅助队伍的人岗是否匹配，需要能对内说明的依据。",
    "IND02": "产能外迁或技工不够时，外派能不能留下来、一线管理者够不够，是和招聘并列的下一件事。",
    "IND03": "任期和考核已经往下压，干部标准和薪酬穿透可以并列核对，不先讲战略课。",
    "IND04": "扩张放缓以后，先看管理者能不能带人，再看团队状态和学习方式。",
    "IND05": "监管和分行考核变硬之后，绩效可以往条线穿透，和已有的系统或充值账户并列看。",
    "IND06": "项目和中介队伍在收缩时，人效、关键岗位留人和绩效可以并列核对。",
    "IND07": "门店增减时，店长标准和一线能不能复制，比再讲一套战略课更近。",
    "IND08": "安全资质、外包和正式工、外派能不能落地，可以按岗位标准来核对。",
    "IND09": "渠道和终端人效变化时，一线销售的标准和状态可以并列看。",
    "IND10": "对方自己做人力或专业服务时，换一个问题：交付人效、培训和测评，而不是再推招聘。",
    "IND00": "这是工会、委员会等主体，先核对是不是经营主体，不按品牌公司的政策来开口。",
}

SHOCKS = {
    "IND01": ("集采", "合规整顿", "医保"),
    "IND02": ("出海", "建厂", "外派", "技工"),
    "IND03": ("三项制度", "任期制", "契约化", "世界一流"),
    "IND04": ("人效", "组织扁平", "裁员"),
    "IND05": ("薪酬递延", "消费者保护", "资本充足", "分行考核", "消保"),
    "IND06": ("保交楼", "融资收紧", "中介监管"),
    "IND07": ("关店", "加盟", "开店", "人工成本"),
    "IND08": ("安监", "国际化", "安全资质"),
    "IND09": ("渠道变革", "终端人效"),
    "IND10": ("预算收缩", "同业竞争"),
}

CONFIRM = ("竞聘", "奠基", "投产", "开业", "持证上岗", "万店", "督导")

_YEAR_SPAN = re.compile(r"\d{4}\s*[-~/年至]+\s*\d{1,4}")
_YEAR_MONTH = re.compile(r"\d{4}\s*[-~/年]\s*\d{1,2}")
_YEAR_HEAD = re.compile(r"^\d{4}")
_EDITION = re.compile(r"(集团版|精英版)")


def industry_options() -> list[dict[str, str]]:
    return [{"code": item["code"], "name": item["name"]} for item in INDUSTRIES]


def industry_by_code(code: str) -> dict[str, Any] | None:
    for item in INDUSTRIES:
        if item["code"] == code:
            return item
    return None


def classify_company(name: str) -> dict[str, Any]:
    text = str(name or "").strip()
    tags: list[str] = []
    if "工会" in text:
        return _classified("IND00", ["工会"], pending=False, exception=True)
    for hint, code in NAME_HINTS:
        if hint in text:
            tags.extend(_name_tags(text))
            return _classified(code, tags, pending=False, exception=False)
    for item in INDUSTRIES:
        if item["code"] in {"IND00", "IND03"}:
            continue
        if any(term in text for term in item["terms"]):
            tags.extend(_name_tags(text))
            return _classified(item["code"], tags, pending=False, exception=False)
    if any(term in text for term in ("城投", "国资", "农投")):
        tags.extend(_name_tags(text))
        return _classified("IND03", tags, pending=False, exception=False)
    return _classified("", tags, pending=True, exception=False)


def _name_tags(text: str) -> list[str]:
    tags: list[str] = []
    if "分行" in text:
        tags.append("分行")
    if "分公司" in text:
        tags.append("分公司")
    if "办事处" in text:
        tags.append("办事处")
    if any(term in text for term in ("国资", "中广核", "诚通")):
        tags.append("国资背景")
    return tags


def _classified(code: str, tags: list[str], *, pending: bool, exception: bool) -> dict[str, Any]:
    found = industry_by_code(code) if code else None
    uniq: list[str] = []
    for tag in tags:
        if tag not in uniq:
            uniq.append(tag)
    return {
        "industry_code": code,
        "industry_name": found["name"] if found else "",
        "industry_tags": uniq,
        "industry_status": "pending" if pending else "suggested",
        "entity_exception": exception or code == "IND00",
    }


def _core(segment: str) -> str:
    text = str(segment or "").strip()
    text = _YEAR_SPAN.sub("", text)
    text = _YEAR_MONTH.sub("", text)
    text = _YEAR_HEAD.sub("", text)
    text = _EDITION.sub("", text)
    return text.strip(" -—~～")


def translate_deals(raw_items: list[str], extra_rules: list[dict] | None = None) -> dict[str, Any]:
    """把成交原文翻译成经营范围。展示用的原文不在这里改写。"""
    scopes: list[str] = []
    stages: list[int] = []
    unrecognized: list[str] = []
    kmi = False
    consult = False
    for raw in raw_items:
        original = str(raw or "").strip()
        if not original:
            continue
        core = _core(original) or original
        folded = core.casefold()
        hit = _match_rule(original, core, folded, extra_rules or [])
        if hit == "kmi":
            kmi = True
            continue
        if hit == "consult":
            consult = True
            continue
        if isinstance(hit, tuple):
            name, stage = hit
            if name not in scopes:
                scopes.append(name)
            stages.append(stage)
            continue
        if original not in unrecognized:
            unrecognized.append(original)
    return {
        "scopes": scopes,
        "stages": stages,
        "kmi_account": kmi,
        "consult_unspecified": consult,
        "unrecognized": unrecognized,
    }


def _match_rule(original: str, core: str, folded: str, extra_rules: list[dict]) -> str | tuple[str, int] | None:
    blob = f"{original}\n{core}"
    for rule in extra_rules:
        keyword = str(rule.get("keyword") or "").strip()
        if keyword and keyword.casefold() in blob.casefold():
            kind = rule.get("kind") or "scope"
            if kind == "kmi":
                return "kmi"
            if kind == "consult":
                return "consult"
            scope = str(rule.get("scope") or "")
            if scope in SHELF:
                return scope, _stage_of(scope)
    if "k米" in folded or "kmi" in folded:
        return "kmi"
    if "传统hro" in folded or "传统ＨＲＯ" in original:
        return "招聘软件和服务", 1
    if "人事管理云" in core or "人事管理云" in original:
        return "人事考勤软件", 1
    if "绩效云" in core or "绩效云" in original:
        return "绩效薪酬软件和咨询服务", 1
    if "内训" in core or "内训" in original:
        return "人才培训", 3
    if re.search(r"LM", original, re.I) or re.search(r"LM", core, re.I):
        return "人才培训", 3
    if "咨询服务" in core or "咨询服务" in original:
        return "consult"
    return None


def _stage_of(scope: str) -> int:
    if scope in {"人事考勤软件", "招聘软件和服务", "绩效薪酬软件和咨询服务", "海外人事合规与落地用工底座"}:
        return 1
    if scope in {"人才测评", "人才盘点", "关键岗位人才保留", "绩效薪酬咨询"}:
        return 2
    if scope in {"人才培训", "员工敬业度满意度调研", "企业文化建设", "AI 学习平台", "领导力发展", "一线管理者提升", "中层管理提升"}:
        return 3
    return 4


def business_signals(industry_code: str, text: str) -> tuple[str, list[str], list[str]]:
    """行业本身不是信号。只有材料里出现冲击或动作才算。"""
    shocks = SHOCKS.get(industry_code) or ()
    leading = [term for term in shocks if term and term in text]
    confirm = [term for term in CONFIRM if term in text]
    if confirm:
        return "confirm", leading, confirm
    if leading:
        return "leading", leading, confirm
    return "none", leading, confirm


def business_products(
    industry_code: str,
    scopes: list[str],
    *,
    kmi: bool,
    consult: bool,
    text: str,
    company: str,
    exception: bool,
) -> list[dict[str, str]]:
    if exception or industry_code in {"", "IND00"}:
        return []
    bought = set(scopes)
    names = _policy_names(industry_code, bought, kmi=kmi, consult=consult, text=text, company=company)
    if industry_code == "IND10":
        names = [name for name in names if name != "招聘软件和服务"]
    if industry_code in {"IND02", "IND08"} and any(term in text for term in ("出海", "海外", "外派", "建厂")):
        names.append("出海人才服务")
    ordered: list[dict[str, str]] = []
    seen: set[str] = set()
    for name in names:
        if name not in SHELF or name in bought or name in seen:
            continue
        if name in {"组织能力杨三角建设", "AI 大师课", "中高层管理提升"}:
            continue
        seen.add(name)
        ordered.append({"name": name, "basis": "下一阶段并列"})
    return ordered


def _policy_names(
    industry_code: str,
    bought: set[str],
    *,
    kmi: bool,
    consult: bool,
    text: str,
    company: str,
) -> list[str]:
    del consult
    if industry_code == "IND01":
        return ["人才测评", "人才盘点"]
    if industry_code == "IND02":
        names = ["人才测评"]
        if any(term in text for term in ("组织发展", "OD", "培训体系")):
            names.append("人才培训")
        return names
    if industry_code == "IND03":
        return ["人才测评", "绩效薪酬咨询", "绩效薪酬软件和咨询服务"]
    if industry_code == "IND04":
        return ["员工敬业度满意度调研", "中层管理提升", "AI 学习平台"]
    if industry_code == "IND05":
        if "人才培训" in bought and not kmi and "人事考勤软件" not in bought:
            return ["员工敬业度满意度调研", "中层管理提升"]
        return ["绩效薪酬咨询", "人才测评"]
    if industry_code == "IND06":
        return ["人才盘点", "绩效薪酬咨询", "关键岗位人才保留"]
    if industry_code == "IND07":
        if "人才培训" in bought:
            return ["一线管理者提升"]
        return ["人才测评", "人才盘点", "人才培训"]
    if industry_code == "IND08":
        names = ["人才测评", "人才培训"]
        if "三项制度" in text and "壳牌" not in company:
            names.append("绩效薪酬咨询")
        return names
    if industry_code == "IND09":
        return ["人才测评", "人才培训", "员工敬业度满意度调研"]
    if industry_code == "IND10":
        return ["人事考勤软件", "绩效薪酬软件和咨询服务", "人才培训", "人才测评", "AI 学习平台"]
    return []


def maturity_from_translation(translated: dict[str, Any]) -> dict[str, Any]:
    if translated["scopes"]:
        stage = max(translated["stages"] or [1])
        return {"stage": stage, "skipped": False, "reason": "", "label": STAGE_LABELS.get(stage, "")}
    if translated["kmi_account"]:
        return {"stage": None, "skipped": True, "reason": "kmi", "label": "未判断成熟度"}
    if translated["consult_unspecified"]:
        return {"stage": None, "skipped": True, "reason": "consult", "label": "未判断成熟度"}
    if translated["unrecognized"]:
        return {"stage": None, "skipped": True, "reason": "unmapped", "label": "未判断成熟度"}
    return {"stage": None, "skipped": True, "reason": "empty", "label": "未判断成熟度"}
