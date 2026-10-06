import io
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from backend.stock import catalog, engine, preview, service, storage


def workbook(rows: list[list]) -> bytes:
    book = Workbook()
    sheet = book.active
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


HEADER = ["客户编码", "客户名称", "联系人", "手机", "职务", "历史成交产品", "销售", "公开信号"]


class PreviewTests(unittest.TestCase):
    def test_groups_people_and_keeps_purchase_text(self):
        content = workbook(
            [
                HEADER,
                ["A1", "望城泰平企业管理有限公司", "李胜", "13973116522", "", "", "公海", ""],
                ["A1", "望城泰平企业管理有限公司", "李胜", "13973116522", "", "", "公海", ""],
                ["A1", "望城泰平企业管理有限公司", "李胜", "13973116522", "", "", "公海", ""],
                ["B1", "长沙银行股份有限公司", "邓一", "0731-84307242", "培训中心主任", "2022-7K米", "公海", "分行考核"],
                ["B1", "长沙银行股份有限公司", "邓一", "18711100461", "培训经理", "", "公海", ""],
                ["C1", "长沙十月知行文化传媒有限公司", "郑茜", "13142183330", "经理", "2026-7传统HRO", "公海", ""],
                ["D1", "长沙无限家科技有限公司", "郑茜", "13142183330", "HR", "", "公海", ""],
                ["E1", "北京壳牌石油有限公司", "齐敏", "010-65810058", "", "2017-2018咨询服务", "公海", ""],
                ["F1", "日照银行股份有限公司", "李凯", "13800001111", "", "2025-5内训", "公海", "竞聘"],
                ["G1", "蓝月亮(中国)有限公司工会委员会", "王敏", "13800002222", "老师", "", "公海", ""],
                ["H1", "长沙市强晟企业管理有限公司", "赵六", "13800003333", "HRD", "2024-4传统HRO", "公海", ""],
                ["I1", "某未知行业公司", "钱七", "13800004444", "", "神秘课程包", "公海", "竞聘"],
            ]
        )
        data = preview.build_preview(content)
        self.assertTrue(data["can_confirm"])
        self.assertEqual(data["summary"]["excel_rows"], 12)
        self.assertEqual(data["summary"]["companies"], 9)
        codes = {item["customer_code"]: item for item in data["companies"]}
        taiping = codes["A1"]
        self.assertEqual(len(taiping["contacts"]), 1)
        self.assertTrue(any(item["code"] == "W1" for item in data["warnings"]))
        bank = codes["B1"]
        self.assertEqual(bank["purchased_display"], "2022-7K米")
        self.assertEqual(bank["scopes"], [])
        self.assertTrue(bank["kmi_account"])
        self.assertEqual(bank["industry_code"], "IND05")
        person = bank["contacts"][0]
        self.assertEqual(person["name"], "邓一")
        self.assertEqual(person["role"], "培训中心主任")
        kinds = {channel["kind"] for channel in person["channels"]}
        self.assertEqual(kinds, {"mobile", "landline"})
        self.assertTrue(any(channel["switchboard"] for channel in person["channels"]))
        self.assertEqual(bank["signal_level"], "leading")
        self.assertTrue(any(item["code"] == "W3" for item in data["warnings"]))
        self.assertTrue(any(item["code"] == "W4" for item in data["warnings"]))
        self.assertTrue(any(item["code"] == "W6" for item in data["warnings"]))
        self.assertTrue(codes["C1"]["related"])
        self.assertEqual(codes["C1"]["scopes"], ["招聘软件和服务"])
        self.assertEqual(codes["D1"]["industry_code"], "IND04")
        self.assertTrue(codes["E1"]["consult_unspecified"])
        self.assertEqual(codes["E1"]["scopes"], [])
        self.assertEqual(codes["F1"]["scopes"], ["人才培训"])
        self.assertEqual(codes["F1"]["signal_level"], "confirm")
        self.assertTrue(codes["G1"]["entity_exception"])
        self.assertEqual(codes["G1"]["industry_code"], "IND00")
        self.assertIn("神秘课程包", codes["I1"]["unrecognized"])
        self.assertTrue(any("传统HRO" not in item["message"] or item["code"] != "W5" for item in data["warnings"]))
        self.assertFalse(any(item["code"] == "W5" and "K米" in item["message"] for item in data["warnings"]))
        self.assertFalse(any(item["code"] == "W5" and "传统HRO" in item["message"] for item in data["warnings"]))

    def test_missing_code_blocks_the_batch(self):
        content = workbook([HEADER, ["", "没有编码的公司", "张三", "13800005555", "", "", "公海", ""]])
        data = preview.build_preview(content)
        self.assertFalse(data["can_confirm"])
        self.assertEqual(data["blockers"][0]["code"], "B1")

    def test_wrong_template_is_blocked(self):
        content = workbook([["公司全称", "电话"], ["某公司", "13800006666"]])
        data = preview.build_preview(content)
        self.assertEqual(data["blockers"][0]["code"], "B5")

    def test_business_rules_and_placement(self):
        bank = engine.analyze(
            {
                "import_profile": "business",
                "company": "长沙银行股份有限公司",
                "industry_code": "IND05",
                "purchased_display": "2022-7K米",
                "scopes": [],
                "kmi_account": True,
                "signals_text": "",
            }
        )
        names = {item["name"] for item in bank["products"]}
        self.assertEqual(names, {"绩效薪酬咨询", "人才测评"})
        self.assertNotIn("组织能力杨三角建设", names)
        self.assertIn("2022-7K米", bank["lines"][0])
        self.assertIn("充值账户", bank["lines"][0])
        self.assertEqual(bank["maturity_reason"], "kmi")

        trained = engine.analyze(
            {
                "import_profile": "business",
                "company": "日照银行股份有限公司",
                "industry_code": "IND05",
                "purchased_display": "2025-5内训",
                "scopes": ["人才培训"],
                "signals_text": "竞聘",
            }
        )
        trained_names = {item["name"] for item in trained["products"]}
        self.assertIn("员工敬业度满意度调研", trained_names)
        self.assertNotIn("组织能力杨三角建设", trained_names)
        self.assertEqual(trained["signal_level"], "confirm")

        agency = engine.analyze(
            {
                "import_profile": "business",
                "company": "长沙市强晟企业管理有限公司",
                "industry_code": "IND10",
                "purchased_display": "2024-4传统HRO",
                "scopes": ["招聘软件和服务"],
            }
        )
        agency_names = {item["name"] for item in agency["products"]}
        self.assertNotIn("招聘软件和服务", agency_names)
        self.assertIn("人才测评", agency_names)

        shell = engine.analyze(
            {
                "import_profile": "business",
                "company": "北京壳牌石油有限公司",
                "industry_code": "IND08",
                "purchased_display": "2017-2018咨询服务",
                "consult_unspecified": True,
                "scopes": [],
            }
        )
        self.assertEqual(shell["maturity_reason"], "consult")
        self.assertNotIn("组织能力杨三角建设", {item["name"] for item in shell["products"]})

        self.assertEqual(preview.place_company("none", "pool", False), "base")
        self.assertEqual(preview.place_company("leading", "pool", False), "incubation")
        self.assertEqual(preview.place_company("confirm", "pool", False), "pool")
        self.assertEqual(preview.place_company("confirm", "assign", True), "base")
        self.assertEqual(preview.place_company("confirm", "base", False), "base")

    def test_confirm_import_keeps_companies_and_hides_incubation_numbers(self):
        content = workbook(
            [
                HEADER,
                ["B1", "长沙银行股份有限公司", "邓一", "18711100461", "培训中心主任", "2022-7K米", "公海", "分行考核"],
                ["F1", "日照银行股份有限公司", "李凯", "13800001111", "", "2025-5内训", "公海", "竞聘"],
            ]
        )
        data = preview.build_preview(content)
        original = storage.STOCK_DIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                storage.STOCK_DIR = Path(tmp)
                created = service.import_companies(
                    data["companies"],
                    destination="pool",
                    owner="",
                    assigned_by="admin",
                    acknowledge=True,
                    warning_count=len(data["warnings"]),
                )
                by_name = {item["company"]: item for item in created}
                self.assertEqual(by_name["长沙银行股份有限公司"]["status"], "incubation")
                self.assertEqual(by_name["日照银行股份有限公司"]["status"], "pool")
                self.assertEqual(by_name["长沙银行股份有限公司"]["analysis"]["copy_source"], "pending")
                shown = service.present(by_name["长沙银行股份有限公司"], {"username": "a"})
                self.assertFalse(shown["phone_visible"])
                self.assertEqual(shown["phone"], "")
                self.assertEqual(shown["purchased_display"], "2022-7K米")
                self.assertTrue(shown["contacts"])
                self.assertEqual(shown["contacts"][0]["channels"][0]["number"], "")
                self.assertEqual(len(storage.list_items("records")), 2)
        finally:
            storage.STOCK_DIR = original

    def test_le_you_jia_and_union_classification(self):
        home = catalog.classify_company("长沙乐有家企业管理有限公司")
        self.assertEqual(home["industry_code"], "IND06")
        branch = catalog.classify_company("交通银行股份有限公司上海分行")
        self.assertEqual(branch["industry_code"], "IND05")
        self.assertIn("分行", branch["industry_tags"])
        plant = catalog.classify_company("四川中久大光科技有限公司")
        self.assertEqual(plant["industry_code"], "IND02")


if __name__ == "__main__":
    unittest.main()
