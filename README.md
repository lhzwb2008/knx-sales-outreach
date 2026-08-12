# KNX 智拓 · 销售智能触达工作台

作者：**Ira** · 供肯耐珂萨销售同事日常陌拜使用。

目标：触达客户、挖掘需求、建立联系、促成交。主触达方式为电话；客户名单通过 Excel 导入。

## 服务地址

**https://knx-zituo.101.201.237.149.sslip.io/**

> 服务器 `101.201.237.149`，由 Caddy + sslip.io 提供 HTTPS；HTTP 直连：`http://101.201.237.149:8877/`

## 五步流程

1. **上传名单** — 导入任意表头的 Excel，自动识别公司/电话等字段
2. **客户触达** — 在列表点击客户，弹框内完成需求分析、话术查看、外呼记录
3. **微信待办** — 对方同意加微后提醒跟进发资料

侧栏「使用帮助」可查看流程图；「导出数据」可下载全部业务 JSON（zip）。

> 工作流已从原先的「分析 / 话术 / 记录」三栏合并为统一的客户触达弹框。

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
- `data/` 业务 JSON（本地/服务器私有，**不入库**；首次启动可自动 seed 演示数据）
- `scripts/` 部署、本地备份、演示数据脚本
- `.env.example` 配置模板（勿提交真实密钥）

## 说明

- 业务状态落在服务器 `/opt/knx-outreach/data`；每小时备份到本机 `/var/backups/knx-outreach`（不推 Git）
- 需要拷贝数据时，用网站侧栏「导出数据」下载 zip
- 部署不会覆盖远端 `data/` 与 `.env`
- 本公司（肯耐珂萨）不出现在市场方案参考列表中
- 合规：请确保名单来源合法，遵守外呼时段与平台规范
