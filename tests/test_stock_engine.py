import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from backend.stock import engine, service, storage


AUTO = {
    "company": "华东某汽车精密冲压压铸系统股份公司",
    "industry": "汽车零部件",
    "purchased_scope": "关键岗位人才胜任力测评",
    "signals_text": "主机厂年度降本12%。泰国罗勇府海外压铸工厂奠基。密集招募精益生产经理、海外外派技术主管。车间一线流失率上升。",
    "phone": "13800000000",
    "source": "self_upload",
}

SOE = {
    "company": "某省属文化旅游投资集团有限公司",
    "industry": "地方国企",
    "purchased_scope": "人事考勤系统",
    "signals_text": "国企改革深化提升。省国资委三项制度改革穿透考核。近1个月招聘中层干部竞聘考核专员。新设市场化运营子公司。",
    "phone": "13800000001",
    "source": "admin_import",
}

LITHIUM = {
    "company": "某新能源材料公司",
    "industry": "锂电",
    "purchased_scope": "人事考勤软件",
    "signals_text": "受海外碳壁垒及行业反内卷政策影响，启动海外供应链建厂。近20天招聘越南工厂人力经理。",
    "phone": "13800000002",
    "source": "self_upload",
}

RETAIL_BLANK = {
    "company": "某区域餐饮连锁",
    "industry": "连锁餐饮",
    "purchased_scope": "",
    "signals_text": "宣布启动万店计划，大规模招聘区域督导主管。",
    "phone": "13800000003",
    "source": "self_upload",
}


def names(result: dict) -> set[str]:
    return {item["name"] for item in result["products"]}


class EngineTests(unittest.TestCase):
    def test_auto_keeps_stage_and_overseas_together(self):
        result = engine.analyze(AUTO)
        got = names(result)
        self.assertIn("一线管理者提升", got)
        self.assertIn("出海人才服务", got)
        self.assertGreaterEqual(len(got), 2)
        self.assertEqual(result["signal_level"], "confirm")
        self.assertEqual(result["maturity_stage"], 2)
        self.assertIn("泰国", result["pitch"])
        self.assertIn("一线管理者提升", result["lines"][4])
        self.assertGreater(len(result["pitch"]), 180)
        self.assertNotIn("禁语", json.dumps(result, ensure_ascii=False))

    def test_soe_pushes_both_products_without_replacing(self):
        result = engine.analyze(SOE)
        got = names(result)
        self.assertIn("人才测评", got)
        self.assertIn("绩效薪酬咨询", got)
        self.assertNotIn("组织能力杨三角建设", got)
        self.assertEqual(result["signal_level"], "confirm")

    def test_soe_independent_accounting_adds_without_dropping(self):
        record = dict(SOE)
        record["signals_text"] += "子公司独立核算。"
        result = engine.analyze(record)
        got = names(result)
        self.assertIn("人才测评", got)
        self.assertIn("绩效薪酬咨询", got)
        self.assertIn("组织能力杨三角建设", got)

    def test_lithium_understands_plant_hr_title(self):
        result = engine.analyze(LITHIUM)
        got = names(result)
        self.assertIn("人才测评", got)
        self.assertIn("出海人才服务", got)
        self.assertEqual(result["maturity_stage"], 1)
        self.assertEqual(result["signal_level"], "confirm")
        self.assertEqual(result["primary_industry"]["id"], "lithium")
        self.assertNotIn("禁语", json.dumps(result, ensure_ascii=False))

    def test_blank_purchase_skips_maturity_and_continues(self):
        result = engine.analyze(RETAIL_BLANK)
        self.assertIsNone(result["maturity_stage"])
        self.assertTrue(result["maturity_skipped"])
        self.assertEqual(result["signal_level"], "confirm")
        self.assertTrue(result["products"])
        self.assertIn("未判断成熟度", result["lines"][0])

    def test_grant_window_is_36_hours(self):
        start = datetime(2026, 9, 27, 9, 0, tzinfo=datetime.now().astimezone().tzinfo)
        expires = datetime.fromisoformat(engine.grant_expires_at(start))
        self.assertEqual(int((expires - start).total_seconds()), 36 * 3600)

    def test_incubation_phone_hidden_until_grant(self):
        record = {
            "phone": "13900001111",
            "source": "admin_assign",
            "status": "incubation",
            "owner": "stock-a",
            "grant_expires_at": "",
        }
        viewer = {"username": "stock-a", "stock_role": "frontline"}
        hidden = engine.phone_access(record, viewer)
        self.assertFalse(hidden["visible"])
        self.assertEqual(hidden["phone"], "")
        record["grant_expires_at"] = engine.grant_expires_at()
        shown = engine.phone_access(record, viewer)
        self.assertTrue(shown["visible"])
        self.assertEqual(shown["phone"], "13900001111")

    def test_self_upload_incubation_shows_own_number(self):
        record = {
            "phone": "13900002222",
            "source": "self_upload",
            "status": "incubation",
            "owner": "stock-a",
        }
        shown = engine.phone_access(record, {"username": "stock-a", "stock_role": "frontline"})
        self.assertTrue(shown["visible"])
        self.assertIn("本人上传", shown["note"])

    def test_same_company_is_stored_separately(self):
        original = storage.STOCK_DIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                storage.STOCK_DIR = Path(tmp)
                first = service.create_record(dict(AUTO), source="self_upload", owner="stock-a")
                second = service.create_record(
                    dict(AUTO, phone="13700003333"),
                    source="self_upload",
                    owner="stock-b",
                )
                rows = storage.list_items("records")
                self.assertEqual(len(rows), 2)
                self.assertNotEqual(first["id"], second["id"])
                self.assertEqual(first["company"], second["company"])
                self.assertFalse(first.get("lock_label"))
                self.assertFalse(second.get("lock_label"))
        finally:
            storage.STOCK_DIR = original

    def test_unconfirmed_signal_is_a_soft_hint(self):
        raw = (
            "顾问仅可在客户先行提及相应话题时，基于事实进行回应，"
            "严禁以任何形式暗示或引导客户进入上述产品的推销流程。"
            "此条内容仅用于内部知识准备，不能对外使用。"
            "确认信号未成立，不得作为开口依据。"
        )
        lines, pitch, supplement = engine.soften_copy([raw, raw], "", "零售转型还在推进，目前阶段不宜外呼。")
        blob = "\n".join(lines + [pitch, supplement])
        self.assertNotIn("严禁", blob)
        self.assertNotIn("不得作为开口依据", blob)
        self.assertNotIn("内部知识", blob)
        self.assertNotIn("不宜外呼", blob)
        self.assertEqual(lines.count(engine._SOFT_HINT), 1)
        self.assertIn("核对情况", blob)

    def test_login_does_not_split_modules(self):
        from backend import auth

        outreach = {"module": "outreach", "role": "user"}
        stock = {"module": "stock", "stock_role": "frontline"}
        readonly = {"module": "stock", "stock_role": "readonly"}
        legacy = {"role": "user"}
        for user in (outreach, stock, readonly, legacy):
            self.assertIsNone(auth.module_block(user, "/api/leads", "GET"))
            self.assertIsNone(auth.module_block(user, "/api/stock/reachable", "GET"))
            self.assertIsNone(auth.module_block(user, "/api/stock/calls", "POST"))


if __name__ == "__main__":
    unittest.main()
