from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# 信号—需求—产品：第一优先被挡后，切相邻需求，而不是换个说法再问同一件事。
# 依据 ppt/out/肯耐珂萨销售陌拜系统方法论.pptx
# （L3 需求判断/优先级/话术角度；市场方案先判断对方在用什么再决定怎么说）

_FAMILIES: list[tuple[str, tuple[str, ...]]] = [
    ("talent_review", ("人才盘点", "继任", "梯队", "高潜", "九宫格")),
    ("assessment", ("测评", "胜任力", "领导力", "选人标准")),
    ("od", ("组织诊断", "组织变革", "架构", "权责", "OD")),
    ("payroll", ("考勤", "薪酬", "算薪", "假勤", "排班")),
    ("hcm", ("一体化", "HRIS", "HR系统", "人事系统")),
    ("learning", ("培训", "企业大学", "学习发展", "L&D", "培养")),
    ("search", ("猎头", "寻访", "补人", "招聘缺口")),
    ("perf", ("绩效", "OKR", "KPI", "目标管理")),
    ("efficiency", ("人效", "精简", "编制", "降本")),
    ("overseas", ("出海", "海外", "EOR", "跨境", "派驻")),
]

# 同一条需求链上的下一跳（第二优先）
_PIVOT: dict[str, tuple[str, str, str]] = {
    "talent_review": ("assessment", "关键岗位选人标准与中高管测评", "人才测评（中高管）"),
    "assessment": ("learning", "测完之后的管理者培养", "培训体系与企业大学"),
    "od": ("talent_review", "干部行不行、谁能接——中高管盘点", "人才盘点与继任"),
    "payroll": ("perf", "发薪之外，目标和人效能不能看清", "绩效管理升级"),
    "hcm": ("payroll", "每天都在出错的假勤算薪", "人事考勤薪酬 SaaS"),
    "learning": ("talent_review", "培训预算花在谁身上——先把人盘清楚", "人才盘点与继任"),
    "search": ("assessment", "先把岗位标准和用人风险立住", "人才测评（中高管）"),
    "perf": ("talent_review", "考核改不动时，先看关键岗谁能接", "人才盘点与继任"),
    "efficiency": ("talent_review", "精简之前先确认哪些人必须留", "人才盘点与继任"),
    "overseas": ("assessment", "派出或当地负责人能不能带住团队", "人才测评（中高管）"),
}

_FAMILY_PRIMARY_LABEL = {
    "talent_review": "核心岗位继任与人才盘点",
    "assessment": "关键岗位选人标准与中高管测评",
    "od": "组织协作与架构诊断",
    "payroll": "假勤算薪是否已经撑不住",
    "hcm": "人事系统一体化",
    "learning": "管理者培养与培训体系",
    "search": "关键岗位补人",
    "perf": "绩效与目标管理",
    "efficiency": "人效与编制优化",
    "overseas": "海外用工合规与落地速度",
}


@dataclass
class TalkPlan:
    greeting: str
    primary_need: str
    second_need: str
    second_products: str
    primary_family: str
    second_family: str
    competitor_branch: str  # complementary | replacement | blank
    observation: str
    opener: str
    wechat: str
    followups: list[dict[str, str]] = field(default_factory=list)
    pivot_reason: str = ""


SCRIPT_RULES = (
    "话术规则（必须遵守）："
    "1) phone_opener：45-60秒能说完，4-6句口语。把第一优先需求的1-2个具体探询嵌进开场"
    "（只问与第一优先相关的事，例如盘点问团队规模和核心岗谁能顶上，薪酬问几套规则/是否靠表对人），"
    "禁止只问「有没有挑战/方不方便聊」这类空泛是非题；禁止把别的需求的问题塞进开场。"
    "2) 只用线索里出现的姓名、职位、公司；禁止脑补部门职责"
    "（例如把创始人写成「负责研究与发展」）。英文名只称名字+您好，不要加「总」。"
    "3) rejection_followups 必须是「第一优先被拒绝后」才说的话，共3条："
    "第1-2条切到 second_need，不要换个说法再推同一需求；"
    "第3条做周旋（没时间就加微信发一页纸 / 已有强势方案走互补不要劝替换 / 找错人要到对接人）。"
    "4) 市场方案分支：对方已有强势方案时互补切入；自研、轻量工具或没有系统时可以提替换窗口。"
    "5) 首通不要求签约、报价或见高层。补充信息很少时用试探句式。被拒绝后的话术也不要硬推方案功能。"
    "6) 禁止出现：双循环、OLI、赋能、抓手、闭环、数字化转型、生态、方法论、顶层设计、战略协同。"
)

INSIGHT_JSON_HINT = (
    "{need_analysis: string(2-4句中文，说清客户可能的HR需求与判断依据),"
    " recommended_products: string(推荐的产品/服务，用顿号或逗号分隔),"
    " priority_reason: string(为何值得现在打),"
    " talk_angle: string(一句话切入角度，含第一优先；可点出被拒后切第二优先),"
    " phone_opener: string(45-60秒开场，探询已嵌在开场里),"
    " wechat_invite: string,"
    " rejection_followups: [{trigger: string(对方拒绝时的原话/情境), say: string(你接着说的话)}]}"
)


def greeting(lead: dict[str, Any]) -> str:
    name = str(lead.get("name") or "").strip()
    if not name:
        return "您好"
    latin = name.replace(" ", "").replace("-", "").replace(".", "")
    if latin and all(ord(c) < 128 for c in latin):
        return f"{name.split()[0]}您好"
    return f"{name}您好"


def _blob(lead: dict[str, Any], extra: str = "") -> str:
    return " ".join(
        str(x or "")
        for x in (
            lead.get("company"),
            lead.get("industry"),
            lead.get("title"),
            lead.get("notes"),
            lead.get("manual_supplement"),
            lead.get("need_analysis"),
            lead.get("recommended_products"),
            extra,
        )
    )


def family_of(text: str) -> str | None:
    if not text:
        return None
    for fid, keys in _FAMILIES:
        if any(k in text for k in keys):
            return fid
    return None


def _distinct_families(rule_hits: list[dict], extra_text: str) -> list[tuple[str, dict]]:
    ordered: list[tuple[str, dict]] = []
    seen: set[str] = set()
    for hit in rule_hits or []:
        text = f"{hit.get('need') or ''} {hit.get('products') or ''}"
        fid = family_of(text)
        if not fid or fid in seen:
            continue
        seen.add(fid)
        ordered.append((fid, hit))
    if not ordered:
        fid = family_of(extra_text)
        if fid:
            ordered.append((fid, {"need": _FAMILY_PRIMARY_LABEL[fid], "products": ""}))
    return ordered


def competitor_branch(competitor_hits: list[dict]) -> str:
    if not competitor_hits:
        return "blank"
    if any(c.get("tier") == "strong" for c in competitor_hits):
        return "complementary"
    if any(c.get("tier") == "weak" for c in competitor_hits):
        return "replacement"
    return "complementary"


def _industry_default(lead: dict[str, Any]) -> tuple[str, str]:
    blob = _blob(lead).lower()
    if any(k in blob for k in ("consult", "咨询", "顾问机构", "顾问公司")):
        return "talent_review", "assessment"
    if any(k in blob for k in ("制造", "工厂", "生产", "蓝领")):
        return "payroll", "efficiency"
    if any(k in blob for k in ("互联", "软件", "科技", "saas")):
        return "talent_review", "learning"
    if any(k in blob for k in ("零售", "连锁", "门店")):
        return "payroll", "learning"
    return "talent_review", "assessment"


def _observation(lead: dict[str, Any], primary_family: str) -> str:
    blob = _blob(lead)
    title = str(lead.get("title") or "")
    founder = any(k in title for k in ("创始", "老板", "CEO", "法人", "合伙人"))
    if any(k in blob.lower() for k in ("consult", "咨询", "顾问公司", "顾问机构")):
        if founder:
            return "咨询公司这个阶段常见会卡在两头：核心顾问能不能独立带项目，以及这几个人里有没有谁能往上接"
        return "咨询团队常见会先碰到：项目经理能不能独立交付，以及核心岗有没有人能接"
    mapping = {
        "talent_review": "扩张或交接时，核心岗位有没有人能顶上，往往比上系统更先痛",
        "assessment": "招人或提拔时如果没有一把统一的尺子，后面盘点和培养都会虚",
        "od": "组织一调整，协作和权责最容易卡壳",
        "payroll": "人一多、规则一复杂，假勤和算薪往往最先撑不住",
        "hcm": "多套工具并行时，管理层要的报表和员工体验会一起爆",
        "learning": "培训预算一紧，更需要先知道钱该花在谁身上",
        "search": "关键岗空着的成本，通常比一套盘点项目更具体",
        "perf": "目标和发薪对不上时，团队会觉得考核是走形式",
        "efficiency": "要控成本时，先分清哪些人能动、哪些人必须留",
        "overseas": "人还少的时候最容易为了两三个人去当地设公司，周期和风险都不划算",
    }
    return mapping.get(primary_family, "组织和人的问题通常会先从一两件具体的事上露出来")


def _probe_line(primary_family: str) -> str:
    probes = {
        "talent_review": "您现在团队大概多少人？核心岗位有没有明确能顶上的人？",
        "assessment": "您现在招人或提拔，主要看业绩，还是也会看带队和专业深度？",
        "od": "目前最想先解开的是结构、协作，还是干部能力？",
        "payroll": "现在算薪大概几套规则，还是主要靠表在对人？",
        "hcm": "您现在最头疼的是数据对不上、员工体验，还是管理层要报表？",
        "learning": "更优先的是新人能上手，还是中层能带队伍？",
        "search": "现在最急的是把人补上，还是先把这岗位的标准立住？",
        "perf": "考核结果现在能不能直接用到晋升和发薪上？",
        "efficiency": "您内部有没有在看哪些岗必须留、哪些编制可以动？",
        "overseas": "海外是已经有成熟供应商，还是还在摸当地怎么合法雇人？",
    }
    return probes.get(primary_family, "目前最想先解决的是选人、培养，还是把现有的人看清楚？")


def _wechat_hook(lead: dict[str, Any], primary_family: str, second_need: str) -> str:
    greet = greeting(lead)
    blob = _blob(lead).lower()
    if any(k in blob for k in ("consult", "咨询")):
        return (
            f"{greet}，方便加个微信吗？我发一页咨询同行「项目经理/合伙人」能力对照，"
            "您先留着看，不合适直接忽略。"
        )
    hooks = {
        "talent_review": "同行业轻量人才盘点案例和继任一页纸",
        "assessment": "关键岗位画像和测评维度对照",
        "od": "组织诊断轻量清单",
        "payroll": "「算薪容易出错的点」对照清单",
        "hcm": "招聘-假勤-薪酬-绩效路径图",
        "learning": "同行业管理者训练营大纲",
        "search": "关键岗位画像模板",
        "perf": "绩效校准一页纸",
        "efficiency": "人效诊断框架（仅内部讨论）",
        "overseas": "《企业出海目标国用工合规避坑手册》",
    }
    asset = hooks.get(primary_family, "同行业一页对照")
    return f"{greet}，方便加个微信吗？我发一份{asset}给您参考，您先看，不着急。"


def _followups(plan_second: str, branch: str, lead: dict[str, Any], primary_family: str) -> list[dict[str, str]]:
    title = str(lead.get("title") or "")
    junior = any(k in title for k in ("专员", "助理", "主管")) and not any(
        k in title for k in ("总监", "创始", "老板", "CEO", "CHRO", "HRD")
    )
    first = {
        "talent_review": (
            "对方说盘点还不急 / 团队还小",
            "那我们先不谈盘点。人少的时候更怕用错能独立扛事的人。"
            f"更贴现在的是{plan_second}。您招人或往上推的时候，主要看业绩，还是也会看带队和专业深度？",
        ),
        "assessment": (
            "对方说测评不需要 / 已经有面试流程",
            "面试有流程很正常。差别通常在有没有一把统一的尺子。"
            f"尺子立住了，后面才接得上{plan_second}。您现在提拔或分项目，主要靠熟人和感觉，还是有内部标准？",
        ),
        "od": (
            "对方说组织不调整 / 没有变革项目",
            f"那就不碰架构。我们可以改看{plan_second}。"
            "您现在最费神的是协作，还是关键岗后继无人？",
        ),
        "payroll": (
            "对方说系统不换 / 还能用",
            f"系统可以先不动。不少团队真正疼的是{plan_second}。"
            "考核结果现在能不能直接用到发薪和晋升上？",
        ),
        "hcm": (
            "对方说一体化不急 / 上过系统了",
            f"大而全的可以后放。如果假勤算薪也不疼，我们可以看{plan_second}。"
            "您现在哪一块对账最费时间？",
        ),
        "learning": (
            "对方说培训没预算 / 不招培训",
            f"预算紧就更要先知道钱花在谁身上，也就是{plan_second}。"
            "您内部有没有已经默认的高潜或必须留住的人？",
        ),
        "search": (
            "对方说现在不招人",
            f"不招人也可以。下一次用人前，可以先做{plan_second}。"
            "您上次招关键岗，最不满意的是能力，还是文化合不来？",
        ),
        "perf": (
            "对方说绩效先不改",
            f"考核规则可以不动。我们可以改看{plan_second}。"
            "您现在有没有几个人是走了业务会空档的？",
        ),
        "efficiency": (
            "对方说编制不动 / 不谈精简",
            f"精简可以不谈。至少先确认哪些人必须留，也就是{plan_second}。"
            "您内部有没有已经点名要稳住的岗位？",
        ),
        "overseas": (
            "对方说海外人很少 / 暂时不需要",
            f"人少更要避免为两三个人去当地设公司。如果合规不急，我们改看{plan_second}。"
            "您现在是先派人，还是已经在当地招？",
        ),
    }
    trigger1, say1 = first.get(primary_family, first["talent_review"])

    if branch == "complementary":
        trigger2, say2 = (
            "对方说已经有供应商 / 自己在做",
            "明白，那就不替换您现在用的。我们更多是做互补：只补您缺的那一块，"
            f"比如{plan_second}，不用再上一个大项目。"
            "您觉得现在最费神的是选人、培养，还是把现有的人看清楚？",
        )
    elif branch == "replacement":
        trigger2, say2 = (
            "对方说现在有工具 / 但用得一般",
            "轻量工具能撑日常很常见。续约或规则变复杂前，其实是替换窗口。"
            f"我们先不谈换系统，只确认一件事：{plan_second}，您内部有没有人在盯？"
            "第一次沟通只做确认，不推销产品。",
        )
    else:
        trigger2, say2 = (
            "对方说已经有自己的做法 / 不需要外部",
            f"自己有做法很好。我们不插手日常，只在您缺尺子或缺对照时补一块——也就是{plan_second}。"
            "您更想先看选人标准，还是先看谁能接核心岗？",
        )

    if junior:
        trigger3, say3 = (
            "对方说我不负责这块 / 找错人了",
            "明白，不耽误您。方便告诉我实际负责组织和人才的同事怎么称呼、怎么联系吗？"
            "我只会转达一句具体的事，不会让您再传话。",
        )
    else:
        trigger3, say3 = (
            "对方说没时间 / 发资料就行",
            "不占用您通话。方便加个微信吗？我发一页对照您先留着，"
            "不合适直接忽略；合适的话您再看要不要回我。",
        )

    return [
        {"trigger": trigger1, "say": say1},
        {"trigger": trigger2, "say": say2},
        {"trigger": trigger3, "say": say3},
    ]


def plan_talk(
    lead: dict[str, Any],
    rule_hits: list[dict] | None = None,
    competitor_hits: list[dict] | None = None,
    recommended_products: str = "",
) -> TalkPlan:
    extra = f"{recommended_products} {lead.get('need_analysis') or ''} {lead.get('talk_angle') or ''}"
    families = _distinct_families(rule_hits or [], _blob(lead, extra))
    if not families:
        primary_family, second_family = _industry_default(lead)
        primary_need = _FAMILY_PRIMARY_LABEL[primary_family]
        second_need, second_products = _PIVOT[primary_family][1], _PIVOT[primary_family][2]
        primary_hit: dict = {}
    else:
        primary_family, primary_hit = families[0]
        primary_need = str(primary_hit.get("need") or _FAMILY_PRIMARY_LABEL[primary_family])
        if len(families) >= 2:
            second_family, second_hit = families[1]
            second_need = str(second_hit.get("need") or _PIVOT.get(primary_family, ("", "", ""))[1])
            second_products = str(second_hit.get("products") or _PIVOT.get(primary_family, ("", "", ""))[2])
        else:
            second_family, second_need, second_products = _PIVOT.get(
                primary_family, ("assessment", "关键岗位选人标准与中高管测评", "人才测评（中高管）")
            )

    # 咨询创始人：盘点被拒后，第二优先几乎一定是「选人尺子/测评」
    blob = _blob(lead)
    if any(k in blob.lower() for k in ("consult", "咨询")) and primary_family == "talent_review":
        second_family, second_need, second_products = _PIVOT["talent_review"]

    branch = competitor_branch(competitor_hits or [])
    greet = greeting(lead)
    title = str(lead.get("title") or "").strip()
    company = str(lead.get("company") or "贵司").strip()
    role = f"您作为{company}的{title}" if title else f"您在{company}"
    observation = _observation(lead, primary_family)
    probe = _probe_line(primary_family)
    opener = (
        f"{greet}，我是肯耐珂萨的顾问。{role}，{observation}。"
        f"想先请教两件具体的事：{probe}"
    )
    wechat = _wechat_hook(lead, primary_family, second_need)
    followups = _followups(second_need, branch, lead, primary_family)
    pivot_reason = (
        f"规则命中第一优先是「{primary_need}」；被拒后切相邻需求「{second_need}」"
        + ("，对方已有方案时走互补。" if branch == "complementary" else "。")
    )
    return TalkPlan(
        greeting=greet,
        primary_need=primary_need,
        second_need=second_need,
        second_products=second_products,
        primary_family=primary_family,
        second_family=second_family,
        competitor_branch=branch,
        observation=observation,
        opener=opener,
        wechat=wechat,
        followups=followups,
        pivot_reason=pivot_reason,
    )


def facts_block(lead: dict[str, Any], plan: TalkPlan) -> str:
    return (
        f"已确认事实（禁止改写）：姓名={lead.get('name') or '未知'}，"
        f"职位={lead.get('title') or '未知'}，公司={lead.get('company') or '未知'}。\n"
        f"第一优先需求：{plan.primary_need}\n"
        f"第二优先需求（被拒绝后才用）：{plan.second_need} → 产品 {plan.second_products}\n"
        f"推演说明：{plan.pivot_reason}\n"
        f"市场方案分支：{plan.competitor_branch}（complementary=互补，replacement=替换窗口，blank=尚未判断）\n"
        f"开场必须点到的探询：{_probe_line(plan.primary_family)}"
    )


def opener_too_thin(text: str, lead: dict[str, Any] | None = None) -> bool:
    t = (text or "").strip()
    if len(t) < 80:
        return True
    if "有没有遇到" in t or "有没有什么挑战" in t:
        if t.count("？") + t.count("?") <= 1:
            return True
    title = str((lead or {}).get("title") or "")
    if title and "创始" in title and "研究与发展" in t:
        return True
    return False


def _as_followup(item: Any) -> dict[str, str] | None:
    if isinstance(item, dict):
        trigger = str(item.get("trigger") or item.get("when") or item.get("objection") or "").strip()
        say = str(item.get("say") or item.get("response") or item.get("text") or "").strip()
        if not say:
            return None
        return {"trigger": trigger, "say": say}
    if isinstance(item, str) and item.strip():
        raw = item.strip()
        for sep in ("】", "：", ":"):
            if sep in raw:
                left, right = raw.split(sep, 1)
                left = left.lstrip("【[").strip()
                right = right.strip()
                if left and right:
                    return {"trigger": left, "say": right}
        return {"trigger": "", "say": raw}
    return None


def normalize_followups(insights: dict[str, Any]) -> list[dict[str, str]]:
    raw = insights.get("rejection_followups")
    if not isinstance(raw, list) or not raw:
        raw = insights.get("questions") or []
    out: list[dict[str, str]] = []
    for item in raw:
        row = _as_followup(item)
        if row:
            out.append(row)
    return out[:4]


def followups_ok(followups: list[dict[str, str]], plan: TalkPlan) -> bool:
    if len(followups) < 2:
        return False
    blob = " ".join(f.get("say", "") + f.get("trigger", "") for f in followups)
    markers = ("不急", "还小", "已经有", "供应商", "没时间", "找错", "不负责", "发资料", "互补")
    if not any(m in blob for m in markers):
        return False
    # 至少有一条不再重复第一优先话术
    second_keys = [k for fid, keys in _FAMILIES if fid == plan.second_family for k in keys]
    if second_keys and not any(k in blob for k in second_keys + [plan.second_need[:4]]):
        # 允许周旋话术不含产品词，但第1条应碰到第二优先
        first_say = followups[0].get("say", "")
        if plan.second_need[:4] not in first_say and not any(k in first_say for k in second_keys):
            return False
    return True


def questions_from_followups(followups: list[dict[str, str]]) -> list[str]:
    rows: list[str] = []
    for item in followups:
        trigger, say = item.get("trigger") or "", item.get("say") or ""
        rows.append(f"【{trigger}】{say}" if trigger else say)
    return rows


def _strip_latin_zong(text: str, lead: dict[str, Any]) -> str:
    first = str(lead.get("name") or "").split()[0]
    if not first or not all(ord(c) < 128 for c in first):
        return text
    return (
        text.replace(f"{first}总您好", f"{first}您好")
        .replace(f"{first}总，", f"{first}您好，")
        .replace(f"{first}总", first)
    )


def fallback_insights(lead: dict[str, Any], plan: TalkPlan, rule_hits: list[dict] | None = None) -> dict[str, Any]:
    hits = rule_hits or []
    products = "、".join(
        dict.fromkeys(
            x
            for h in hits[:3]
            for x in str(h.get("products") or "").replace("，", "、").split("、")
            if x
        )
    ) or plan.second_products
    return {
        "need_analysis": "；".join(h.get("need", "") for h in hits[:3])
        or f"公开信息有限，先按{plan.primary_need}试探，被拒后切{plan.second_need}。",
        "recommended_products": products,
        "priority_reason": "",
        "talk_angle": f"开场确认{plan.primary_need}；被拒后切{plan.second_need}",
        "phone_opener": plan.opener,
        "wechat_invite": plan.wechat,
        "rejection_followups": plan.followups,
        "questions": questions_from_followups(plan.followups),
    }


def apply_to_lead(lead: dict[str, Any], insights: dict[str, Any], plan: TalkPlan) -> dict[str, Any]:
    opener = str(insights.get("phone_opener") or "").strip()
    if opener_too_thin(opener, lead):
        opener = plan.opener
    opener = _strip_latin_zong(opener, lead)
    wechat = _strip_latin_zong(str(insights.get("wechat_invite") or "").strip() or plan.wechat, lead)
    followups = normalize_followups(insights)
    if not followups_ok(followups, plan):
        followups = plan.followups
    lead["phone_opener"] = opener
    lead["wechat_invite"] = wechat
    lead["script_followups"] = followups
    lead["script_questions"] = questions_from_followups(followups)
    lead["primary_need"] = plan.primary_need
    lead["second_need"] = plan.second_need
    if insights.get("talk_angle"):
        lead["talk_angle"] = str(insights.get("talk_angle")).strip()
    else:
        lead["talk_angle"] = f"开场确认{plan.primary_need}；被拒后切{plan.second_need}"
    return lead
