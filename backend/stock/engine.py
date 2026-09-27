"""存量分析流水线。

行业、信号和产品由规则决定。建议产品并列保留，不互相替换。
已购为空或对不上货架时不判断成熟度，继续做信号和命题。
不生成禁语。
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from .playbooks import OVERSEAS_TERMS, PLAYBOOKS, PROPOSITIONS, PURCHASED_TOKENS, SHELF, STAGE_LABELS

GRANT_HOURS = 36
LOCK_DAYS = 60

STAGE_MARKERS: tuple[tuple[int, tuple[str, ...]], ...] = (
    (4, ("杨三角", "中高层", "大师课", "企业参访", "出海人才")),
    (3, ("敬业度", "满意度调研", "企业文化建设", "文化建设", "学习平台", "AI 学习", "AI学习", "领导力", "一线管理者", "中层管理", "人才培训")),
    (2, ("人才测评", "胜任力", "测评", "人才盘点", "盘点", "人才保留", "绩效薪酬咨询", "薪酬咨询")),
    (1, ("考勤", "招聘软件", "招聘服务", "薪酬软件", "绩效软件", "EOR", "名义雇主", "人事软件", "人事系统")),
)


def grant_expires_at(now: datetime | None = None) -> str:
    moment = now or datetime.now().astimezone()
    return (moment + timedelta(hours=GRANT_HOURS)).isoformat(timespec="seconds")


def lock_until(first_touch: datetime) -> str:
    return (first_touch + timedelta(days=LOCK_DAYS)).isoformat(timespec="seconds")


def _text(*parts: Any) -> str:
    return "\n".join(str(part or "") for part in parts)


def _hits(text: str, terms: tuple[str, ...] | list[str]) -> list[str]:
    return [term for term in terms if term and term in text]


def _signal_hit(text: str, signal: dict) -> bool:
    if not _hits(text, signal.get("any") or ()):
        return False
    context = signal.get("context") or ()
    if context and not _hits(text, context):
        return False
    return True


def maturity_of(purchased_scope: str) -> dict[str, Any]:
    text = (purchased_scope or "").strip()
    if not text:
        return {
            "stage": None,
            "skipped": True,
            "reason": "empty",
            "label": "未判断成熟度",
        }
    found = [stage for stage, markers in STAGE_MARKERS if _hits(text, markers)]
    if not found:
        return {
            "stage": None,
            "skipped": True,
            "reason": "unmapped",
            "label": "未判断成熟度",
        }
    stage = max(found)
    return {
        "stage": stage,
        "skipped": False,
        "reason": "",
        "label": STAGE_LABELS[stage],
    }


def _already_bought(name: str, purchased_scope: str) -> bool:
    text = purchased_scope or ""
    if not text.strip():
        return False
    if name and name in text:
        return True
    for token in PURCHASED_TOKENS.get(name, ()):
        if token in text:
            return True
    return False


def _score_playbook(playbook: dict, record: dict[str, Any]) -> int:
    industry = str(record.get("industry") or "")
    company = str(record.get("company") or "")
    scope = _text(record.get("purchased_scope"), record.get("business_scope"))
    rest = _text(record.get("signals_text"), record.get("notes"))
    score = 0
    for term in playbook["match"]:
        if term in industry:
            score += 3 * len(term)
        elif term in company or term in scope:
            score += 2 * len(term)
        elif term in rest:
            score += len(term)
    return score


def match_industries(record: dict[str, Any], disabled: set[str] | None = None) -> list[dict]:
    blocked = disabled or set()
    ranked = []
    for playbook in PLAYBOOKS:
        if playbook["id"] in blocked:
            continue
        score = _score_playbook(playbook, record)
        if score > 0:
            ranked.append((score, playbook))
    ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
    return [playbook for _, playbook in ranked]


def match_propositions(text: str) -> list[dict]:
    return [item for item in PROPOSITIONS if _hits(text, item["terms"])]


def _add_product(ordered: list[dict[str, str]], seen: set[str], name: str, basis: str, purchased: str) -> None:
    if name not in SHELF or _already_bought(name, purchased):
        return
    if name in seen:
        for item in ordered:
            if item["name"] == name and basis not in item["basis"]:
                item["basis"] = f"{item['basis']}；{basis}"
        return
    seen.add(name)
    ordered.append({"name": name, "basis": basis})


def recommend_products(
    playbook: dict | None,
    record: dict[str, Any],
    maturity: dict[str, Any],
    propositions: list[dict],
    text: str,
) -> list[dict[str, str]]:
    purchased = str(record.get("purchased_scope") or "")
    ordered: list[dict[str, str]] = []
    seen: set[str] = set()
    stage = maturity["stage"]

    if playbook and stage is not None:
        for name in playbook["stages"].get(stage) or ():
            _add_product(ordered, seen, name, "按当前成熟度", purchased)
        for cross in playbook.get("cross") or ():
            if _hits(text, cross["when"]):
                for name in cross["products"]:
                    _add_product(ordered, seen, name, "与其他建议并行", purchased)
    elif propositions:
        for prop in propositions:
            for name in prop["products"]:
                _add_product(ordered, seen, name, "未判断成熟度，按经营命题", purchased)
        if playbook:
            for cross in playbook.get("cross") or ():
                if _hits(text, cross["when"]):
                    for name in cross["products"]:
                        _add_product(ordered, seen, name, "与其他建议并行", purchased)
    elif playbook:
        for name in playbook.get("opening") or ():
            _add_product(ordered, seen, name, "未判断成熟度，按行业参考并列", purchased)

    if _hits(text, OVERSEAS_TERMS):
        _add_product(ordered, seen, "出海人才服务", "出海信号与其他建议并行", purchased)
    return ordered


def _matched_labels(text: str, signals: tuple[dict, ...]) -> list[str]:
    return [signal["label"] for signal in signals if _signal_hit(text, signal)]


def signal_level_of(playbook: dict | None, text: str) -> tuple[str, list[str], list[str]]:
    if playbook:
        leading = _matched_labels(text, playbook["leading"])
        confirm = _matched_labels(text, playbook["confirm"])
    else:
        leading = [item["label"] for item in match_propositions(text)]
        confirm = [term for term in ("竞聘上岗", "正式奠基", "万店计划", "流片", "颁证", "License-out", "III 期") if term in text]
    if confirm:
        return "confirm", leading, confirm
    if leading:
        return "leading", leading, confirm
    return "none", leading, confirm


def place_status(signal_level: str, source: str, owner: str) -> str:
    owned = bool((owner or "").strip())
    if source == "self_upload":
        if signal_level == "confirm":
            return "reachable"
        if signal_level == "leading":
            return "incubation"
        return "trial"
    if not owned:
        if signal_level == "none":
            return "base"
        return "pool"
    if signal_level == "confirm":
        return "reachable"
    if signal_level == "leading":
        return "incubation"
    return "trial"


def _clip(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _clean(text: str) -> str:
    return " ".join((text or "").split())


PRODUCT_WHY = {
    "人事考勤软件": "人事事务里考勤底座还没买齐时，和招聘、薪酬并列补，不跨去讲战略。",
    "招聘软件和服务": "门店、产线或灵活用工要批量到面时，和测评、保留放在同一次对话里。",
    "绩效薪酬软件和咨询服务": "薪酬还停在记录层时，软件和咨询可以并列看考核怎么落下去。",
    "海外人事合规与落地用工底座": "人已经要派到海外、当地用工还没底座时，和出海人才服务并列。",
    "人才测评": "选拔、竞聘或外派适岗缺一套能对内说明的依据时，用测评把人看清楚，不替换别的项目。",
    "人才盘点": "看现有干部和关键岗位断在哪、谁能派出去，和测评、出海服务并列。",
    "关键岗位人才保留": "骨干被挖或即将外派时，先把留下谁说清楚，和测评并列。",
    "绩效薪酬咨询": "考核、契约化或分成已经出现时，和测评、盘点并列看激励怎么落地。",
    "人才培训": "新岗位、海外员工或合规协作要变成可上课的内容时，和管理者提升并列。",
    "员工敬业度满意度调研": "用来核对一线、店员或骨干为什么留不住，和管理者提升放在同一次对话里。",
    "企业文化建设": "加盟、重组或跨背景团队要把做法对齐时，和调研并列，不单独当成开口。",
    "AI 学习平台": "总部标准要传到门店或一线时，用短训把动作拆开，和管理者提升并列。",
    "领导力发展": "管理者要换一种带人方式时，和中层、中高层项目并列。",
    "一线管理者提升": "下一阶段补的是班组、店长或外派主管怎么带人，不重复讲公司战略。",
    "中层管理提升": "中层要从行政命令转到目标管理时，和测评之后的项目并列。",
    "组织能力杨三角建设": "只有材料写明高阶段或独立核算时才并列出现，不替换测评和咨询。",
    "中高层管理提升": "高管层要把新业务或新考核对齐时，和一线、中层项目并列。",
    "AI 大师课": "高管要看清技术和业务怎么配合时并列提及，不作为唯一开口。",
    "企业参访和出海人才服务": "要看成熟出海企业怎么搭组织时，和出海人才服务并列。",
    "出海人才服务": "海外工厂、海外门店或外派已经出现，属地用工和外派与国内项目并列，不互相替换。",
}


def _product_lines(result: dict[str, Any]) -> str:
    rows = []
    for item in result.get("products") or []:
        why = PRODUCT_WHY.get(item["name"], "与其他建议放在同一次沟通里，由客户决定先做哪件。")
        rows.append(f"· {item['name']}：{why}")
    return "\n".join(rows) or "· 暂无可锁定的货架产品。"


def build_lines(result: dict[str, Any]) -> list[str]:
    purchased = result.get("purchased_scope") or "未填写"
    maturity = result["maturity_label"]
    history = []
    if result.get("service_end"):
        history.append(f"服务截止 {result['service_end']}")
    if result.get("unit_price"):
        history.append(f"客单价 {result['unit_price']}")
    history_text = f"（{'，'.join(history)}）" if history else ""
    if result["maturity_skipped"]:
        reason = "为空" if result["maturity_reason"] == "empty" else "对不上四阶段货架"
        line1 = (
            f"已购经营范围{reason}，未判断成熟度，所以不假装知道他们停在哪一格。"
            f"下面仍按公开材料和经营命题把能并列的产品写出来，等补上已购后再收窄。"
        )
    else:
        line1 = (
            f"已购「{purchased}」{history_text}，目前落在{maturity}。"
            "这一格只说明已经买过的部分，同阶段没买的和下一阶段要补的都还空着。"
            "这次不是换掉已购，而是把没买的项和下一阶段并列拿出来，由客户选先做哪件。"
        )
    facts = _clean(result.get("signals_text") or "")
    props = "、".join(result["propositions"]) or "尚未识别明确经营命题"
    if result["leading_hits"]:
        leading = "、".join(result["leading_hits"])
    elif result["signal_level"] == "confirm":
        leading = "这些事实已经足以支撑确认信号，不另找一句空泛先导"
    else:
        leading = "材料里还没有形成先导信号"
    fact_sentence = f"材料原话是：{_clip(facts, 420)}。" if facts else "上传材料里没有写公开信号。"
    line2 = f"{fact_sentence}\n对应的经营命题是：{props}。先导判断：{leading}。"
    speakable = result.get("speakable") or "人的问题仍缺可对外说明的事实。"
    line3 = (
        f"电话里可以这样说人的问题：{speakable}"
        "这句只用来开口，不评价对方组织好不好。具体工厂、门店、毛利、招聘岗位，以材料原话为准，不要再加一层形容词。"
    )
    if result["signal_level"] == "confirm":
        line4 = (
            "确认信号已成立，可以进入触达。触发原因是："
            + "、".join(result["confirm_hits"])
            + "。开口时请点出材料里的时间、地点和数字，例如工厂是否投产、门店规模、招聘岗位或考核动作，不要只说“有新闻”。"
        )
    else:
        line4 = (
            "确认信号还不够齐。电话里可以先核对材料里已经写明的事实，产品先放一放。"
            "还缺能说明组织已经在动的事实，例如竞聘、海外工厂投产、万店或督导体系、核心岗位招聘。"
        )
    if result["signal_level"] == "confirm":
        line5 = "并列建议，没有优先级。已购项不重复卖，下面每一项都保留，电话里问客户先做哪件：\n" + _product_lines(result)
    else:
        line5 = (
            "下面是可以先记着的并列产品，等事实更清楚再谈，没有先后：\n"
            + _product_lines(result)
        )
    return [line1, line2, line3, line4, line5]


def build_pitch(result: dict[str, Any]) -> str:
    if result["signal_level"] != "confirm" or not result["products"]:
        return ""
    company = result.get("company") or "贵司"
    contact = (result.get("contact") or "").strip()
    role = (result.get("role_name") or "").strip()
    if role and contact:
        who = f"{role}{contact}"
    else:
        who = contact or role or "负责人"
    purchased = result.get("purchased_scope") or "已有的人事项目"
    facts = _clip(_clean(result.get("signals_text") or ""), 280).rstrip("。")
    product_talk = "\n".join(
        f"{item['name']}：{PRODUCT_WHY.get(item['name'], '和前面几项并列').rstrip('。')}。"
        for item in result["products"]
    )
    return (
        f"您好，我是肯耐珂萨的，想找{who}核对一件事，大概两分钟。\n"
        f"我们看到{company}的公开材料里写着：{facts or '有一些和组织、用人有关的进展'}。\n"
        f"贵司已经买过「{purchased}」，这次不重复讲这个。想并列核对的是：\n{product_talk}\n"
        "这几件没有先后，您看哪一件最先能帮上忙？如果时机不对，我也可以只把材料留下来，不占用今天的会。"
    )


def build_supplement(result: dict[str, Any], text: str) -> str:
    notes = []
    if "市场化" in text and "子公司" in text and "独立核算" not in text:
        notes.append("材料写到市场化子公司，但没有写独立核算。绩效薪酬咨询因此和原阶段建议并列保留，不单独升成唯一推荐。")
    if result["reference_industries"]:
        names = "、".join(item["name"] for item in result["reference_industries"][:2])
        notes.append(f"材料同时沾到{names}。主行业仍用证据更强的一条，参考行业不删已有建议。")
    if result["maturity_skipped"]:
        notes.append("已购没形成成熟度，产品是按经营命题并列写的，补上已购后应再收窄。")
    if not notes and result.get("signals_text"):
        notes.append("话术里的工厂、门店、人数和百分比都来自上传的公开材料。对外只复述这些原话，不把“同比减少不到1个点”说成大幅下滑。")
    return _clip("".join(notes), 320)


def analyze(record: dict[str, Any], disabled: set[str] | None = None) -> dict[str, Any]:
    text = _text(
        record.get("industry"),
        record.get("company"),
        record.get("purchased_scope"),
        record.get("signals_text"),
        record.get("notes"),
        record.get("business_scope"),
    )
    matched = match_industries(record, disabled)
    playbook = matched[0] if matched else None
    maturity = maturity_of(str(record.get("purchased_scope") or ""))
    propositions = match_propositions(text)
    level, leading, confirm = signal_level_of(playbook, text)
    products = recommend_products(playbook, record, maturity, propositions, text)
    gaps: list[str] = []
    if maturity["reason"] == "empty":
        gaps.append("已购经营范围为空，未判断成熟度")
    elif maturity["reason"] == "unmapped":
        gaps.append("已购经营范围未能对应四阶段货架，未判断成熟度")
    if not playbook:
        gaps.append("未命中行业模板，主建议来自经营命题")
    if level == "none":
        gaps.append("尚未形成先导或确认信号")
    if not (record.get("phone") or "").strip():
        gaps.append("缺少电话")
    if not (record.get("crm_id") or "").strip() and record.get("source") == "self_upload":
        gaps.append("未对齐 CRM")

    result = {
        "company": record.get("company") or "",
        "purchased_scope": record.get("purchased_scope") or "",
        "primary_industry": {"id": playbook["id"], "name": playbook["name"]} if playbook else None,
        "reference_industries": [{"id": item["id"], "name": item["name"]} for item in matched[1:3]],
        "unmatched_template": playbook is None,
        "maturity_stage": maturity["stage"],
        "maturity_label": maturity["label"],
        "maturity_skipped": maturity["skipped"],
        "maturity_reason": maturity["reason"],
        "propositions": [item["label"] for item in propositions],
        "leading_hits": leading,
        "confirm_hits": confirm,
        "signal_level": level,
        "speakable": playbook["speakable"] if playbook else "公开信息还不足以对上一句人的问题，建议先把行业和已发生的事实补全。",
        "tension_tags": list(playbook["tension_tags"]) if playbook else [],
        "products": products,
        "gaps": gaps,
        "signals_text": record.get("signals_text") or "",
        "contact": record.get("contact") or "",
        "role_name": record.get("role_name") or record.get("role") or "",
        "service_end": record.get("service_end") or "",
        "unit_price": record.get("unit_price") or "",
    }
    result["lines"] = build_lines(result)
    result["pitch"] = build_pitch(result)
    result["supplement"] = build_supplement(result, text)
    return result


_DROP_SENTENCE = re.compile(
    r"严禁|不得|禁止|不能对外|仅用于内部|内部知识|硬性约束|"
    r"违反客户意愿|任何主动触达|必须在客户明确"
)
_TRAILING_HINT = re.compile(r"不宜外呼|不能据此|不能当本次")
_SOFT_HINT = "这几项事实还不够齐，电话里可以先核对情况，产品先放一放。"
_BAN_LEAD = re.compile(
    r"[，,](?:但|并且|同时|另外)?[^，,。！？\n]*(?:主动提出|目前阶段|客户意愿|不宜)[^，,。！？\n]*$"
)


def soften_text(text: str) -> tuple[str, bool]:
    """禁令整句删掉。事实写在前面、句尾才是提醒时，留下事实。"""
    if not text or not (_DROP_SENTENCE.search(text) or _TRAILING_HINT.search(text)):
        return text or "", False
    kept: list[str] = []
    for piece in re.split(r"(?<=[。！？\n])", text):
        if not piece:
            continue
        if _DROP_SENTENCE.search(piece):
            continue
        mark = _TRAILING_HINT.search(piece)
        if not mark:
            kept.append(piece)
            continue
        prefix = piece[: mark.start()]
        while True:
            nxt = _BAN_LEAD.sub("", prefix)
            if nxt == prefix:
                break
            prefix = nxt
        prefix = prefix.rstrip("，,；;、 \n")
        if len(prefix) >= 12:
            if not prefix.endswith(("。", "！", "？", "\n")):
                prefix += "。"
            kept.append(prefix)
    return "".join(kept).strip(), True


def soften_copy(lines: list[Any], pitch: str, supplement: str) -> tuple[list[str], str, str]:
    """禁令整句删掉。若因此没剩下可用文字，只留一句委婉提醒，不重复展开。"""
    softened: list[str] = []
    hinted = False
    for line in lines or []:
        cleaned, dropped = soften_text(str(line))
        if cleaned:
            softened.append(cleaned)
            continue
        if dropped and not hinted:
            softened.append(_SOFT_HINT)
            hinted = True

    def _tail(text: str) -> str:
        nonlocal hinted
        cleaned, dropped = soften_text(text or "")
        if cleaned:
            return cleaned
        if dropped and not hinted:
            hinted = True
            return _SOFT_HINT
        return ""

    return softened, _tail(pitch), _tail(supplement)


def public_analysis(analysis: dict[str, Any], *, include_tension: bool) -> dict[str, Any]:
    data = dict(analysis)
    if not include_tension:
        data.pop("tension_tags", None)
    return data


def phone_access(record: dict[str, Any], viewer: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """管理员分配的孵化期号码默认不可见；获准后 36 小时内可见。自有名单号码回显。"""
    del viewer
    phone = str(record.get("phone") or "")
    source = record.get("source") or ""
    status = record.get("status") or ""
    if source == "self_upload":
        return {"visible": True, "phone": phone, "note": "号码来自本人上传"}
    if status != "incubation":
        return {"visible": True, "phone": phone, "note": ""}
    expires = str(record.get("grant_expires_at") or "")
    moment = now or datetime.now().astimezone()
    if status == "incubation" and expires:
        try:
            exp = datetime.fromisoformat(expires)
        except ValueError:
            exp = None
        if exp is not None:
            if exp.tzinfo is None:
                exp = exp.astimezone()
            if exp > moment:
                return {"visible": True, "phone": phone, "note": f"外呼授权至 {expires}"}
    return {"visible": False, "phone": "", "note": ""}
