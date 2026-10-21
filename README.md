# 哥飞 SEO 新词挖掘与飞书自动推送系统 (WebCafe Keyword Monitor)

基于 **哥飞 SEO 工具箱 (seo.web.cafe)** 的新词发现接口开发的自动化监控、AI 门禁过滤与实时推送到飞书的端到端系统。

通过定时增量拉取最新批次词库，配合 AI 大模型智能筛选出具备**高商业价值、可在线交互、有明确付费场景（卖积分/月度订阅）**的工具类出海商机词，并即时推送到你的飞书对话或飞书群。

---

## 🌟 核心特性

- **0 积分差量拉取**：针对新词批次接口（完全免积分），通过 SQLite WAL 本地缓存避免重复拉取。
- **双层门禁过滤**：
  1. **硬指标初筛**：排除游戏/纯娱乐/百科攻略词，筛选高热度（GPTs 热度倍数）与高暴涨（涨幅百分比）的词。
  2. **AI 智能门禁**：调用 DeepSeek 等大模型，二元判定关键词是否为【可在线交互、具备明确付费场景的工具/微型 SaaS】，并自动归纳做站策略与变现方案。
- **全方位飞书触达**：
  - **`cc-connect` 智能体会话管道**：直接将商机卡片推送到个人飞书会话，并在飞书回复“帮我做这个词”时由 Antigravity 继承上下文直接生成 MVP 代码！
  - **飞书 Webhook 交互卡片**：支持直接推送格式美观的高亮卡片到飞书工作群。
  - **飞书长连接 WebSocket Bot**：支持在飞书聊天中直接指令检索词库。
- **选词数据导出与看板**：
  - 自动生成结构化选词简报（Markdown）。
  - 一键导出 Excel 友好（UTF-8-SIG）的商业精选词表与全量词库 CSV。
  - 生成单页交互式数据可视化看板（`dashboard.html`）。

---

## 🚀 快速上手

### 1. 环境准备
推荐使用 Python 3.10+ 环境。

```bash
# 克隆仓库
git clone https://github.com/ChuckChouCn/webcafe-keyword-monitor.git
cd webcafe-keyword-monitor

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量
复制环境配置模板并填入你的 API 密钥：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入核心配置项：
```ini
# 1. 哥飞 SEO 工具箱 Token (在 https://seo.web.cafe 个人中心获取)
WEBCAFE_TOKEN="wc_mcp_xxxxxxxxxxxx"

# 2. AI 门禁大模型 Key (用于判断是否为付费工具，推荐 DeepSeek)
DEEPSEEK_API_KEY="sk-xxxxxxxxxxxx"

# 3. 飞书配置 (若使用 cc-connect 会话推送，此项可由本地 session 自动发现或指定)
CC_CONNECT_SESSION_KEY="feishu:oc_xxx:ou_xxx"

# 4. 可选：飞书自建应用配置 (若使用独立飞书 Bot 或 Webhook)
FEISHU_APP_ID="cli_xxx"
FEISHU_APP_SECRET="xxx"
```

### 3. 初始化并同步首批数据
执行一次同步，拉取最新批次并自动初始化本地 SQLite 数据库：

```bash
python cli.py sync --pages 1
```

查看当前本地词库的统计分布：
```bash
python cli.py stats
```

---

## 🛠️ 常用 CLI 指令

### 1. 检索与筛选词库
```bash
# 查看所有被标记为 "值得做 (worth)" 的词
python cli.py list --verdict worth

# 筛选 AI 分类、涨幅超过 200% 的词
python cli.py list --category ai --min-growth 200

# 搜索特定关键词
python cli.py list --query pdf --limit 10
```

### 2. 查看单个关键词的深度建站建议
```bash
python cli.py show "qwen 3.8"
```
包含：
- **这是什么**：模型/产品介绍
- **用户需求**：搜索用户的痛点、试用/部署/API 查询意图
- **如何做站**：哥飞推荐抢位策略（新站首页/对比页/工具箱）

### 3. 导出精选词库与生成看板
```bash
# 导出 UTF-8-SIG CSV 表格到 data/ 目录
python export.py

# 生成近 24 小时选词 Markdown 简报
python cli.py report --hours 24
```

---

## 🔄 运行与后台守护服务

### 方式 A：前台单次扫描 / 联调测试
```bash
# 执行单次抓取与门禁审核
python monitor_pipeline.py

# 选取样板词联调一次完整的 AI 审核与推送飞书流程
python monitor_pipeline.py --test --sample "seedance 2.5"
```

### 方式 B：CLI 常驻轮询 (默认每 10 分钟轮询一次)
```bash
python monitor_pipeline.py --daemon --interval 600
```

### 方式 C：使用 systemd 用户服务常驻守护 (推荐生产部署)
本项目提供了现成的 systemd 配置文件模板：

1. 复制模板并配置当前路径：
   ```bash
   mkdir -p ~/.config/systemd/user
   cp systemd/gefei-monitor.service.example ~/.config/systemd/user/gefei-monitor.service
   ```
2. 编辑 `~/.config/systemd/user/gefei-monitor.service`，将其中的 `WorkingDirectory` 和 `ExecStart` 路径替换为你的实际绝对路径。
3. 启用并启动服务：
   ```bash
   systemctl --user daemon-reload
   systemctl --user enable gefei-monitor.service
   systemctl --user start gefei-monitor.service
   ```
4. 管理与日志查看：
   ```bash
   # 查看运行状态
   systemctl --user status gefei-monitor.service

   # 实时跟踪推送日志
   journalctl --user -u gefei-monitor.service -f
   ```

---

## 📂 项目目录结构

```text
webcafe-keyword-monitor/
├── .env.example              # 环境变量配置模板
├── .gitignore                # Git 忽略配置 (保护数据与密钥不泄露)
├── requirements.txt          # Python 依赖清单
├── README.md                 # 完整系统文档
├── config.py                 # 全局配置与原生 .env 加载器
├── db.py                     # SQLite WAL 模式数据库层与自动建表
├── api_client.py             # WebCafe API 客户端 (自动重试/鉴权)
├── service.py                # 业务核心服务 (增量批次同步/查询/报告)
├── ai_gatekeeper.py          # AI 门禁大模型评估 (判定在线交互付费工具)
├── cc_connect_notifier.py    # cc-connect 管道飞书推送与上下文更新
├── feishu_client.py          # 飞书开放平台 Client
├── feishu_notifier.py        # 飞书 Webhook 交互卡片发送器
├── feishu_ws_bot.py          # 飞书 WebSocket 长连接交互机器人
├── cli.py                    # 命令行交互工具集
├── export.py                 # 词库导出与 CSV 处理 (支持零依赖兜底)
├── generate_ui.py            # 数据可视化看板构建器
├── systemd/
│   └── gefei-monitor.service.example  # systemd 用户守护服务模板
└── data/                     # 数据与输出目录 (已做 gitkeep 保障)
    └── reports/              # 导出的选词简报存放目录
```

---

## 🤝 搭配 Antigravity (飞书联动工作流)

当系统推送到你的飞书聊天窗口后：
1. 本地会自动在项目根目录维护焦点词状态文件 [`CURRENT_MONITOR_KEYWORD.md`](CURRENT_MONITOR_KEYWORD.md)。
2. 你只需在飞书回复：
   > *“帮我做这个词”* 或 *“帮我为第 1 个词生成全套 MVP 落地页与项目脚手架”*
3. Antigravity 智能体将直接识别上下文，围绕该词启动原型设计与自动化代码开发！
