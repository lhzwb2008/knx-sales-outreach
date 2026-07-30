# 肯耐珂萨 · 销售陌拜工作台

作者：**Ira** · 供肯耐珂萨销售同事日常陌拜使用。

目标：触达客户、挖掘需求、建立联系、促成交。主触达方式为电话；客户名单通过 Excel 导入。

## 五步流程

1. **上传名单** — 导入任意表头的 Excel，自动识别公司/电话等字段
2. **需求分析** — 结合已知信息判断需求与优先级（规则匹配 + 智能解读）
3. **话术触达** — 按需求预生成电话开场白后再外呼
4. **记录过程** — 人工填写通话细节与结果
5. **微信待办** — 对方同意加微后提醒跟进发资料

页面右上角「使用帮助」可查看流程图。

## 启动

```bash
cp .env.example .env   # 填入 DASHSCOPE_API_KEY 等配置
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

打开：http://127.0.0.1:8765

可选：预生成演示数据与话术

```bash
python scripts/prepare_demo_data.py
```

## 目录

- `backend/` API、规则引擎、智能助手客户端
- `frontend/` 工作台界面
- `data/` 本地 JSON 业务数据（演示数据已预置）
- `ppt/out/` 方法论 PPT / 优先级打分说明 PDF
- `scripts/` 演示数据准备脚本
- `.env.example` 配置模板（勿提交真实密钥）

## 说明

- 业务状态默认落在 `data/` 目录
- 本公司（肯耐珂萨）不出现在市场方案参考列表中
- 合规：请确保名单来源合法，遵守外呼时段与平台规范
