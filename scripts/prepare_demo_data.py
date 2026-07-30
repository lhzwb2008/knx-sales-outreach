#!/usr/bin/env python3
"""预生成演示数据：充实线索/画像/分析结果/定制话术。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import engine, llm, storage
from backend.seed_data import seed_all


DEMO_LEADS = [
    {
        "id": "L001",
        "name": "王",
        "phone": "13816782101",
        "company": "星澜智造科技",
        "title": "人力资源总监",
        "industry": "智能制造",
        "company_size": "800人 / 多工厂",
        "source": "工博会名片",
        "notes": "华南新建工厂，在招薪酬绩效与HRIS",
        "owner": "Ira",
    },
    {
        "id": "L002",
        "name": "李",
        "phone": "13921563428",
        "company": "果味零售集团",
        "title": "HRBP负责人",
        "industry": "连锁零售",
        "company_size": "2000人 / 180+门店",
        "source": "脉脉",
        "notes": "新任三个月，门店排班投诉多，在招OD与培训经理",
        "owner": "Ira",
    },
    {
        "id": "L003",
        "name": "陈",
        "phone": "13701889056",
        "company": "云启软件",
        "title": "CHO",
        "industry": "企业服务 / SaaS",
        "company_size": "350人",
        "source": "融资新闻跟进",
        "notes": "刚完成B轮，大规模招中高层与企业大学负责人",
        "owner": "Ira",
    },
    {
        "id": "L004",
        "name": "赵",
        "phone": "18602114567",
        "company": "晖泽医药",
        "title": "人力资源副总裁",
        "industry": "医药研发",
        "company_size": "1200人",
        "source": "行业峰会",
        "notes": "并购整合期，公开招标人事系统，高管变动频繁",
        "owner": "Ira",
    },
    {
        "id": "L005",
        "name": "周",
        "phone": "13564781230",
        "company": "北岸新能源",
        "title": "组织发展总监",
        "industry": "新能源 / 制造",
        "company_size": "4500人",
        "source": "客户转介绍",
        "notes": "多基地扩张，蓝领排班复杂，在招劳动力管理与绩效经理",
        "owner": "Ira",
    },
    {
        "id": "L006",
        "name": "吴",
        "phone": "15800336791",
        "company": "青禾消费",
        "title": "HRD",
        "industry": "消费品牌",
        "company_size": "600人",
        "source": "Excel导入",
        "notes": "新上任HRD，员工吐槽算薪错误，现用钉钉+Excel",
        "owner": "Ira",
    },
    {
        "id": "L007",
        "name": "郑",
        "phone": "13671665402",
        "company": "瀚海教育科技",
        "title": "人才发展负责人",
        "industry": "在线教育",
        "company_size": "280人",
        "source": "官网留资",
        "notes": "要建管理者训练营与企业大学，在招培训经理",
        "owner": "Ira",
    },
    {
        "id": "L008",
        "name": "孙",
        "phone": "18721660983",
        "company": "城际出行",
        "title": "共享服务中心负责人",
        "industry": "出行服务",
        "company_size": "3000人",
        "source": "招标信息",
        "notes": "人事共享中心建设，多地发薪与考勤统一，JD要求熟悉红海/用友",
        "owner": "Ira",
    },
]

DEMO_PROFILES = {
    "L001": {
        "industry": "智能制造",
        "company_size": "800人",
        "stage": "多工厂扩张",
        "financing": "A轮后稳健经营",
        "summary": "华东制造企业，新建华南工厂，在招薪酬绩效专员与HRIS专员，JD提到熟悉北森更好；员工评价有算薪错误、打卡难用。",
        "jobs": [
            {"title": "薪酬绩效专员", "desc": "多工厂算薪规则，Excel算薪，熟悉北森优先"},
            {"title": "HRIS专员", "desc": "维护人事系统，对接钉钉打卡，推进数字化"},
            {"title": "生产总监", "desc": "新建工厂管理层"},
        ],
        "recruiting_text": "在招薪酬绩效专员、HRIS专员、生产总监；要求熟悉北森、Excel算薪、对接钉钉。",
        "news_text": "去年新建华南工厂，空降生产副总裁。",
        "review_text": "打卡系统难用；工资算错过；请假麻烦。",
        "website_text": "数字化转型与智慧工厂。",
        "contact_title": "人力资源总监",
        "recent_change": True,
    },
    "L002": {
        "industry": "连锁零售",
        "company_size": "2000人",
        "stage": "门店扩张",
        "financing": "未披露",
        "summary": "连锁社区零售，新上任HRBP负责人，门店排班与蓝领考勤压力大，在招组织发展经理与培训经理。",
        "jobs": [
            {"title": "组织发展经理", "desc": "门店组织效能、OD"},
            {"title": "培训经理", "desc": "门店培训体系、学习发展"},
            {"title": "排班专员", "desc": "门店人力排班、劳动力管理"},
        ],
        "recruiting_text": "招聘组织发展经理、培训经理、排班专员，强调门店人力与蓝领考勤。",
        "news_text": "今年计划新开80家社区店。",
        "review_text": "排班混乱；加班打卡坑；HR不作为。",
        "website_text": "组织能力升级。",
        "contact_title": "HRBP负责人",
        "contact_notes": "新上任到任三个月",
        "recent_change": True,
    },
    "L003": {
        "industry": "企业服务 / SaaS",
        "company_size": "350人",
        "stage": "B轮扩张",
        "financing": "B轮",
        "summary": "SaaS公司刚完成B轮，大规模招聘中高层与HRBP，公开要建人才梯队和企业大学。",
        "jobs": [
            {"title": "研发总监", "desc": "中层管理，带30人团队"},
            {"title": "HRBP", "desc": "业务伙伴，组织发展"},
            {"title": "企业大学负责人", "desc": "培训体系与人才培养"},
        ],
        "recruiting_text": "大规模招聘中高层：研发总监、销售总监；同时招HRBP、企业大学负责人、培训经理。",
        "news_text": "完成B轮融资，宣布组织规模化与人才战略。",
        "review_text": "节奏快；晋升不透明。",
        "website_text": "人才战略、组织能力升级。",
        "contact_title": "CHO",
        "recent_change": True,
    },
    "L004": {
        "industry": "医药研发",
        "company_size": "1200人",
        "stage": "并购整合",
        "financing": "上市公司子公司",
        "summary": "并购后组织并表，公开招标人力资源系统采购，高管变动频繁，需要组织诊断与一体化人事。",
        "jobs": [
            {"title": "SSC负责人", "desc": "人事共享、多地分子公司"},
            {"title": "薪酬经理", "desc": "复杂算薪与并购后薪酬并轨"},
        ],
        "recruiting_text": "招聘SSC负责人、薪酬经理；人力资源系统采购招标进行中。",
        "news_text": "完成并购重组并表；管理层调整，空降COO。",
        "review_text": "绩效不透明；系统卡。",
        "website_text": "数字化转型、智慧人力。",
        "contact_title": "人力资源副总裁",
        "recent_change": True,
    },
    "L005": {
        "industry": "新能源制造",
        "company_size": "4500人",
        "stage": "多基地扩张",
        "financing": "战略融资",
        "summary": "新能源多基地，蓝领排班与工时复杂，在招劳动力/排班与绩效经理，部分工厂已用盖雅。",
        "jobs": [
            {"title": "劳动力管理专员", "desc": "排班、蓝领考勤、门店人力"},
            {"title": "绩效经理", "desc": "绩效考核、OKR、目标管理"},
            {"title": "储备干部", "desc": "中层管理管培"},
        ],
        "recruiting_text": "招聘排班/劳动力管理、绩效经理、储备干部；熟悉盖雅优先。",
        "news_text": "新基地投产，编制激增。",
        "review_text": "排班不合理；加班多。",
        "website_text": "组织能力升级。",
        "contact_title": "组织发展总监",
        "recent_change": True,
    },
    "L006": {
        "industry": "消费品牌",
        "company_size": "600人",
        "stage": "品牌扩张",
        "financing": "战略投资",
        "summary": "新任HRD三个月，现用钉钉打卡+Excel算薪，员工吐槽算薪错误与请假麻烦，有明确替换窗口。",
        "jobs": [
            {"title": "薪酬专员", "desc": "手工考勤、多套工资规则、Excel算薪"},
            {"title": "HRIS专员", "desc": "对接钉钉，推进人事系统"},
        ],
        "recruiting_text": "薪酬专员、HRIS专员；Excel算薪、对接钉钉、多套工资规则。",
        "news_text": "新任人力资源总监到任三个月，推动管理升级。",
        "review_text": "算薪错误；打卡系统难用；请假麻烦。",
        "website_text": "数字化转型。",
        "contact_title": "HRD",
        "contact_notes": "新上任HRD",
        "recent_change": True,
    },
    "L007": {
        "industry": "在线教育",
        "company_size": "280人",
        "stage": "组织能力建设",
        "financing": "C轮后",
        "summary": "教育科技公司要建管理者训练营与企业大学，在招培训经理与学习发展，关注干部带教。",
        "jobs": [
            {"title": "培训经理", "desc": "企业大学、学习发展、管理者培养"},
            {"title": "L&D专家", "desc": "培训体系、人才培养"},
        ],
        "recruiting_text": "培训经理、企业大学、学习发展、管理者培养。",
        "news_text": "发布人才战略，强调干部梯队。",
        "review_text": "晋升通道不清晰。",
        "website_text": "人才战略。",
        "contact_title": "人才发展负责人",
        "recent_change": False,
    },
    "L008": {
        "industry": "出行服务",
        "company_size": "3000人",
        "stage": "共享服务建设",
        "financing": "未披露",
        "summary": "建设HRSSC，多地考勤发薪统一，公开招标与JD要求熟悉红海/用友，偏集团化人事底座。",
        "jobs": [
            {"title": "SSC运营经理", "desc": "人事共享、员工关系、多地分子公司"},
            {"title": "薪酬共享专员", "desc": "多地发薪、熟悉用友HCM"},
        ],
        "recruiting_text": "SSC、人事共享、熟悉红海/用友；人力资源系统采购立项。",
        "news_text": "集团推进共享服务中心与数字化。",
        "review_text": "流程慢；系统体验一般。",
        "website_text": "智慧人力。",
        "contact_title": "共享服务中心负责人",
        "recent_change": True,
    },
}


def upsert_demo_base() -> None:
    seed_all()
    now = storage.now_iso()
    leads = []
    for raw in DEMO_LEADS:
        item = {
            **raw,
            "status": "待分析",
            "workflow_step": 1,
            "created_at": now,
            "updated_at": now,
        }
        leads.append(item)
    storage.write_collection("leads", leads)

    profiles = []
    for lead in leads:
        pf = DEMO_PROFILES.get(lead["id"], {})
        profiles.append(
            {
                "id": f"PF{lead['id'][1:]}",
                "lead_id": lead["id"],
                "company": lead["company"],
                **pf,
                "created_at": now,
                "updated_at": now,
            }
        )
    storage.write_collection("profiles", profiles)


def generate_analyses_and_scripts() -> dict:
    scripts_out = []
    for lead in storage.list_items("leads"):
        print(f"分析 {lead['company']} ...")
        # rule engine + AI insight
        result = engine.analyze_lead(lead["id"])
        products = [p.get("name") for p in storage.list_items("products")]
        system = (
            "你是肯耐珂萨销售需求分析助手。输出 JSON："
            "{need_analysis, recommended_products, priority_reason, talk_angle,"
            " phone_opener, wechat_invite, questions:[] }。"
            "phone_opener 为30秒首通开场，代表肯耐珂萨，不硬推销；中文务实。"
        )
        user = (
            f"线索：{lead}\n规则命中：{result.get('rule_hits', [])[:4]}\n"
            f"市场方案：{result.get('competitor_hits', [])}\n优先级：{result.get('priority')}\n"
            f"产品目录：{products}\n请输出 JSON。"
        )
        try:
            insights = llm.chat_json(system=system, user=user, temperature=0.35, max_tokens=1800)
        except Exception as e:
            print("  LLM失败，用规则降级:", e)
            hits = result.get("rule_hits") or []
            insights = {
                "need_analysis": "；".join(h.get("need", "") for h in hits[:3]) or "待补充",
                "recommended_products": "、".join(h.get("products", "") for h in hits[:2]) or "综合HR解决方案",
                "priority_reason": (result.get("priority") or {}).get("tier", ""),
                "talk_angle": "先确认当前最紧迫的人事管理问题",
                "phone_opener": f"您好，我是肯耐珂萨，看到贵司近期在组织与人才方面有一些动作，想跟您简单确认下目前最想先解决的是哪一块。",
                "wechat_invite": "方便加一下微信吗？我把同行业轻量案例发您先看。",
                "questions": ["目前最紧迫的是系统、组织还是干部能力？", "决策大概会在哪个时间窗口？"],
            }

        lead = storage.get_item("leads", lead["id"])
        lead["need_analysis"] = insights.get("need_analysis", "")
        lead["recommended_products"] = insights.get("recommended_products", "")
        lead["priority_reason"] = insights.get("priority_reason", "")
        lead["talk_angle"] = insights.get("talk_angle", "")
        lead["phone_opener"] = insights.get("phone_opener", "")
        lead["wechat_invite"] = insights.get("wechat_invite", "")
        lead["script_questions"] = insights.get("questions") or []
        lead["status"] = "已分析"
        lead["workflow_step"] = 3
        lead["last_score"] = (result.get("priority") or {}).get("total")
        lead["last_tier"] = (result.get("priority") or {}).get("tier")
        lead["last_analyzed_at"] = storage.now_iso()
        storage.upsert_item("leads", lead)

        scripts_out.append(
            {
                "id": f"TS{lead['id'][1:]}",
                "lead_id": lead["id"],
                "company": lead["company"],
                "name": f"{lead['company']} · 定制开场",
                "signal": lead.get("need_analysis", "")[:40],
                "channel": "电话",
                "body": lead.get("phone_opener", ""),
                "wechat": lead.get("wechat_invite", ""),
                "questions": lead.get("script_questions") or [],
                "products": lead.get("recommended_products", ""),
                "version": "定制",
                "pregenerated": True,
                "created_at": storage.now_iso(),
                "updated_at": storage.now_iso(),
            }
        )
        print(f"  -> {lead.get('last_tier')} | {lead.get('recommended_products')[:40]}")

    # merge with library scripts
    lib = [s for s in storage.list_items("scripts") if not s.get("pregenerated")]
    # keep library templates + per-lead scripts
    storage.write_collection("scripts", lib + scripts_out)

    # sample outreach + wechat
    now = storage.now_iso()
    outreach = [
        {
            "id": "ODEMO01",
            "lead_id": "L001",
            "channel": "电话",
            "outcome": "接通-感兴趣",
            "need_confirmed": "多工厂算薪与考勤统一，有替换窗口",
            "objection": "担心迁移成本",
            "next_step": "加微信发迁移清单",
            "notes": "HRD认可痛点，同意加微",
            "agree_wechat": True,
            "materials_to_send": "案例资料",
            "assignee": "Ira",
            "deal_stage": "需求确认",
            "call_time": now,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "ODEMO02",
            "lead_id": "L003",
            "channel": "电话",
            "outcome": "接通-感兴趣",
            "need_confirmed": "B轮后干部梯队与企业大学",
            "objection": "预算要过董事会",
            "next_step": "发送人才盘点白皮书",
            "notes": "CHO时间紧，约下周深聊",
            "agree_wechat": True,
            "materials_to_send": "白皮书",
            "assignee": "Ira",
            "deal_stage": "需求确认",
            "call_time": now,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "ODEMO03",
            "lead_id": "L006",
            "channel": "电话",
            "outcome": "接通-忙线改约",
            "need_confirmed": "",
            "objection": "",
            "next_step": "周四再打",
            "notes": "在开会，改约",
            "agree_wechat": False,
            "materials_to_send": "案例资料",
            "assignee": "Ira",
            "deal_stage": "",
            "call_time": now,
            "created_at": now,
            "updated_at": now,
        },
    ]
    storage.write_collection("outreach", outreach)
    storage.write_collection(
        "wechat_todos",
        [
            {
                "id": "WDEMO01",
                "lead_id": "L001",
                "company": "星澜智造科技",
                "contact_name": "王",
                "phone": "13816782101",
                "assignee": "Ira",
                "materials_to_send": "案例资料",
                "notes": "发送多工厂算薪迁移案例",
                "due_at": "2026-07-30 18:00",
                "status": "pending",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "WDEMO02",
                "lead_id": "L003",
                "company": "云启软件",
                "contact_name": "陈",
                "phone": "13701889056",
                "assignee": "Ira",
                "materials_to_send": "白皮书",
                "notes": "人才盘点与企业大学路径白皮书",
                "due_at": "2026-07-30 20:00",
                "status": "pending",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "WDEMO03",
                "lead_id": "L002",
                "company": "果味零售集团",
                "contact_name": "李",
                "phone": "13921563428",
                "assignee": "Ira",
                "materials_to_send": "近期市场活动介绍",
                "notes": "邀请参加零售门店人效沙龙",
                "due_at": "2026-07-31 12:00",
                "status": "pending",
                "created_at": now,
                "updated_at": now,
            },
        ],
    )
    return {"leads": len(storage.list_items("leads")), "scripts": len(scripts_out)}


if __name__ == "__main__":
    upsert_demo_base()
    print(generate_analyses_and_scripts())
