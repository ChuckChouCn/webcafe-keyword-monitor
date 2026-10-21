import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from service import KeywordMonitorService
from config import REPORTS_DIR

def format_table(rows, headers):
    if not rows:
        return "（无数据）"
    col_widths = [len(h) for h in headers]
    for row in rows:
        for idx, val in enumerate(row):
            str_val = str(val or "")
            # estimate display width (CJK characters take roughly 2 chars)
            val_len = sum(2 if ord(c) > 127 else 1 for c in str_val)
            if val_len > col_widths[idx]:
                col_widths[idx] = min(val_len, 40)

    header_line = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    sep_line = "-+-".join("-" * col_widths[i] for i in range(len(headers)))
    data_lines = []
    for row in rows:
        line_parts = []
        for i, val in enumerate(row):
            s = str(val or "")
            if len(s) > col_widths[i]:
                s = s[:col_widths[i]-3] + "..."
            line_parts.append(s.ljust(col_widths[i]))
        data_lines.append(" | ".join(line_parts))

    return "\n".join([header_line, sep_line] + data_lines)

def main():
    parser = argparse.ArgumentParser(description="哥飞 SEO 新词拉取与监控服务")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # sync
    p_sync = subparsers.add_parser("sync", help="同步新词批次数据")
    p_sync.add_argument("--pages", type=int, default=1, help="拉取批次列表页数（每页30个批次，默认1）")
    p_sync.add_argument("--force", action="store_true", help="强制重新拉取已存在的批次")

    # list
    p_list = subparsers.add_parser("list", help="查看已抓取关键词列表")
    p_list.add_argument("--verdict", type=str, default="worth", help="评级筛选: worth / maybe / skip / all（默认 worth）")
    p_list.add_argument("--category", type=str, help="分类筛选（如 game, ai, tool 等）")
    p_list.add_argument("--min-growth", type=int, help="最低涨幅百分比（如 500 表示 +500%%）")
    p_list.add_argument("--query", type=str, help="关键词搜索")
    p_list.add_argument("--limit", type=int, default=25, help="返回条数（默认 25）")

    # show
    p_show = subparsers.add_parser("show", help="查看指定关键词的建站指导与深度分析")
    p_show.add_argument("keyword", type=str, help="关键词名称")

    # report
    p_report = subparsers.add_parser("report", help="导出/生成高价值词发现简报 (Markdown)")
    p_report.add_argument("--hours", type=int, default=72, help="统计范围（小时，默认 72）")
    p_report.add_argument("--limit", type=int, default=30, help="最多收录词数（默认 30）")
    p_report.add_argument("--out", type=str, help="输出文件路径（默认保存到 data/reports/）")

    # stats
    p_stats = subparsers.add_parser("stats", help="查看本地数据库统计")

    # ai-tools
    p_aitools = subparsers.add_parser("ai-tools", help="只查看 AI 与 工具类付费站商机（区分新词卖积分与二次爆火做订阅）")
    p_aitools.add_argument("--strategy", choices=["all", "new", "resurgence"], default="all", help="筛选策略：new (新词卖积分) / resurgence (二次爆火做订阅)")

    # test-feishu
    p_test_feishu = subparsers.add_parser("test-feishu", help="测试飞书机器人 Webhook 推送")
    p_test_feishu.add_argument("--webhook", type=str, help="飞书机器人 Webhook 地址")

    # daemon
    p_daemon = subparsers.add_parser("daemon", help="启动常驻监控守护服务并推送到飞书")
    p_daemon.add_argument("--interval", type=int, default=1800, help="轮询间隔（秒，默认 1800 即 30 分钟）")
    p_daemon.add_argument("--webhook", type=str, help="飞书机器人 Webhook 地址（如果不传则读取 config.py 中的配置）")

    # ui / dashboard
    p_ui = subparsers.add_parser("ui", help="生成并打开哥飞 1:1 对标看板网页 (dashboard.html)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    svc = KeywordMonitorService()

    if args.command == "sync":
        print(f"[*] 正在拉取批次 (页数: {args.pages}, 强制刷新: {args.force})...")
        res = svc.sync(max_pages=args.pages, force=args.force)
        print(f"[+] 同步完成！")
        print(f"    - 新拉取批次: {res['batches_fetched']} 个")
        print(f"    - 跳过已缓存批次: {res['batches_skipped']} 个")
        print(f"    - 新增关键词: {res['new_keywords']} 个")
        print(f"    - 更新关键词: {res['updated_keywords']} 个")
        print(f"    - 本次发现高价值词 (worth): {len(res['new_worth_keywords'])} 个")

        # 自动刷新 CSV 表格与 HTML 可视化看板
        try:
            from export import export_all
            from generate_ui import generate_dashboard
            export_all()
            generate_dashboard()
            print("[+] 已自动更新 Excel 表格与可视化网页看板！")
        except Exception as e:
            print(f"[!] 自动导出报表失败: {e}")

        if res['new_worth_keywords']:
            print("\n🌟 本次发现的重点值得做 (Worth) 词:")
            for item in res['new_worth_keywords']:
                growth = f"+{item.get('growth_pct')}%" if item.get('growth_pct') else "平稳"
                print(f"    • [{item.get('category')}] {item.get('keyword')} (涨幅: {growth}, 走势: {item.get('trend_now')})")

    elif args.command == "list":
        verdict = None if args.verdict == "all" else args.verdict
        kws = svc.list_keywords(
            verdict=verdict,
            category=args.category,
            min_growth=args.min_growth,
            query=args.query,
            limit=args.limit
        )
        print(f"[*] 查询结果 (共 {len(kws)} 条):")
        headers = ["关键词", "评级", "分类", "涨幅", "走势", "建议形态", "首次发现", "爆发日期"]
        rows = []
        for k in kws:
            growth = f"+{k['growth_pct']}%" if k.get("growth_pct") else "-"
            rows.append([
                k["keyword"],
                k["verdict"],
                k["category"],
                growth,
                k["trend_now"] or "-",
                k["verdict_suggestion"] or "-",
                k["appear_date"] or "-",
                k["burst_date"] or "-"
            ])
        print(format_table(rows, headers))

    elif args.command == "show":
        kw = svc.get_keyword(args.keyword)
        if not kw:
            print(f"[-] 未找到关键词: {args.keyword}")
            return

        print("=" * 60)
        print(f"🔍 关键词深度分析: {kw['keyword']}")
        print("=" * 60)
        print(f"评级: {kw['verdict']} | 分类: {kw['category']} | 建议形态: {kw['verdict_suggestion']}")
        print(f"热度比: {kw['heat_ratio']} | 涨幅: +{kw['growth_pct']}% | 走势: {kw['trend_now']}")
        print(f"首次出现: {kw['appear_date']} | 爆发日期: {kw['burst_date']} | 推送日期: {kw['pushed_on']}")
        print(f"收录页数: {kw['page_count']} | 定向收录: {kw['targeted_count']}")
        print(f"数据来源: {', '.join(kw['sources'])}")
        print(f"详情页面: {kw['page_url']}")
        
        if kw['verdict_reasons']:
            print("\n💡 评判理由:")
            for r in kw['verdict_reasons']:
                print(f"  • {r}")

        print("\n🛠️ 建站行动指南:")
        print(f"  [这是什么] {kw['brief_what'] or '暂无'}")
        print(f"  [用户需求] {kw['brief_want'] or '暂无'}")
        print(f"  [如何做站] {kw['brief_how'] or '暂无'}")

        if kw.get("history"):
            print(f"\n📈 历史抓取轨迹 ({len(kw['history'])} 次):")
            for h in kw['history'][:5]:
                print(f"  • 批次 {h['batch_id']}: 评级={h['verdict']}, 涨幅={h['growth_pct']}%, 走势={h['trend_now']} ({h['recorded_at']})")
        print("=" * 60)

    elif args.command == "report":
        md = svc.generate_markdown_report(hours=args.hours, limit=args.limit)
        if args.out:
            out_file = Path(args.out)
        else:
            filename = f"keyword_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            out_file = REPORTS_DIR / filename
        
        out_file.write_text(md, encoding="utf-8")
        print(f"[+] 简报生成成功: {out_file.resolve()}")
        print("\n--- 简报预览 ---\n")
        print("\n".join(md.split("\n")[:30]))
        print("...")

    elif args.command == "stats":
        stats = svc.get_statistics()
        print("=" * 40)
        print("📊 哥飞新词库统计")
        print("=" * 40)
        print(f"已收录批次总数: {stats['total_batches']}")
        print(f"入库独立关键词: {stats['total_keywords']}")
        print("\n评级分布 (Verdicts):")
        for v, cnt in stats["verdicts"].items():
            print(f"  • {v or 'unrated'}: {cnt}")
        print("\n热门分类 (Top Categories):")
        for cat, cnt in stats["top_categories"].items():
            print(f"  • {cat or 'other'}: {cnt}")
        if stats["latest_batch"]:
            print(f"\n最新批次: {stats['latest_batch']['id']} (完成于 {stats['latest_batch']['finished_at']}, 包含 {stats['latest_batch']['keyword_count']} 词)")
        print("=" * 40)

    elif args.command == "ai-tools":
        conn = svc.client.session # placeholder or get db
        from db import get_connection
        conn = get_connection()
        cur = conn.cursor()

        print("=" * 70)
        print("🤖 AI 与 🛠️ 工具付费站商机（已彻底过滤游戏与泛资讯）")
        print("=" * 70)

        # 1. 新词（速攻卖积分）
        if args.strategy in ("all", "new"):
            print("\n【⚡ 策略 A：新词速攻 · 卖积分模式】(适合：24小时内上线单页/套壳，卖积分包)")
            print("-" * 70)
            cur.execute("""
                SELECT keyword, category, heat_ratio, growth_pct, trend_now, brief_what, brief_how, page_url
                FROM keywords
                WHERE category IN ('ai', 'tool') AND kind = 'new' AND verdict = 'worth'
                ORDER BY heat_ratio DESC
                LIMIT 10
            """)
            rows = cur.fetchall()
            for idx, r in enumerate(rows, 1):
                growth_str = f"+{r['growth_pct']}%" if r['growth_pct'] else "平稳"
                print(f"{idx}. [{r['category'].upper()}] {r['keyword']} | GPTs ×{round(r['heat_ratio'], 2) if r['heat_ratio'] else '-'} | 涨幅: {growth_str} | 走势: {r['trend_now']}")
                print(f"   • 是什么: {r['brief_what'] or '暂无'}")
                print(f"   • 怎么做工具收积分: {r['brief_how'] or '暂无'}")
                print(f"   • 详情: {r['page_url']}\n")

        # 2. 二次爆火（做长线订阅）
        if args.strategy in ("all", "resurgence"):
            print("\n【💎 策略 B：二次爆火 · 做长线订阅】(适合：做长期垂直在线工具/SaaS，收月费订阅)")
            print("-" * 70)
            cur.execute("""
                SELECT keyword, category, heat_ratio, growth_pct, trend_now, brief_what, brief_how, page_url
                FROM keywords
                WHERE category IN ('ai', 'tool') AND kind = 'resurgence' AND verdict = 'worth'
                ORDER BY heat_ratio DESC
                LIMIT 10
            """)
            rows = cur.fetchall()
            for idx, r in enumerate(rows, 1):
                growth_str = f"+{r['growth_pct']}%" if r['growth_pct'] else "平稳"
                print(f"{idx}. [{r['category'].upper()}] {r['keyword']} | GPTs ×{round(r['heat_ratio'], 2) if r['heat_ratio'] else '-'} | 涨幅: {growth_str} | 走势: {r['trend_now']}")
                print(f"   • 是什么: {r['brief_what'] or '暂无'}")
                print(f"   • 怎么做长期SaaS订阅: {r['brief_how'] or '暂无'}")
                print(f"   • 详情: {r['page_url']}\n")
        conn.close()

    elif args.command == "test-feishu":
        from config import FEISHU_WEBHOOK_URL
        from feishu_notifier import send_feishu_webhook
        webhook = args.webhook or FEISHU_WEBHOOK_URL
        if not webhook:
            print("[-] 未检测到飞书 Webhook 地址！请使用 --webhook <url> 或在 config.py 中配置。")
            return

        print(f"[*] 正在向飞书发送测试商机卡片...")
        sample_item = {
            "keyword": "minimax h3",
            "category": "ai",
            "kind": "new",
            "heat_ratio": 4.02,
            "growth_pct": 120,
            "trend_now": "高位",
            "brief_what": "MiniMax 推出的开源多模态视频生成模型 H3，支持文/图生成 2K 视频。",
            "brief_want": "搜的人想找在线免排队体验入口，或找现成可用的 API Playground。",
            "brief_how": "做新站首页，接入 Replicate API 提供在线生成，免费试用1次，购买 50 积分包或 $9.9 充值解锁高清导出。",
            "page_url": "https://new.web.cafe/keywords/minimax-h3"
        }
        ok = send_feishu_webhook(webhook, sample_item)
        if ok:
            print("[+] 测试卡片推送成功！请在飞书群中查看效果。")
        else:
            print("[-] 推送失败，请检查 Webhook 地址是否正确。")

    elif args.command == "daemon":
        from config import FEISHU_CHAT_ID, FEISHU_BITABLE_APP_TOKEN
        from feishu_client import FeishuClient
        fc = FeishuClient()
        chat_id = args.webhook or FEISHU_CHAT_ID

        print(f"[*] 启动 AI与工具 商机守护服务... 轮询间隔: {args.interval} 秒")
        if chat_id:
            print(f"[+] 已连接飞书群聊推送: {chat_id}")
        if FEISHU_BITABLE_APP_TOKEN:
            print(f"[+] 已连接飞书多维表格: {FEISHU_BITABLE_APP_TOKEN}")

        while True:
            try:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{now_str}] 正在检查最新批次...")
                res = svc.sync(max_pages=1, force=False)
                if res["batches_fetched"] > 0:
                    worth_ai_tools = [
                        k for k in res["new_worth_keywords"] 
                        if k.get("category") in ("ai", "tool")
                    ]
                    print(f"[{now_str}] 批次已抓取。其中 AI与工具【值得做】新商机: {len(worth_ai_tools)} 个")

                    for item in worth_ai_tools:
                        kind_str = "⚡ 新词速攻·卖积分" if item.get("kind") == "new" else "💎 二次爆火·做长线订阅"
                        print(f"    🔔 【{kind_str}】[{item.get('category').upper()}] {item.get('keyword')} (GPTs x{item.get('heat_ratio')})")
                        
                        # 1. 自动写入飞书多维表格
                        try:
                            fc.add_bitable_record(item)
                        except Exception as e:
                            print(f"[!] 写入多维表格异常: {e}")

                        # 2. 自动发送飞书群卡片
                        if chat_id:
                            try:
                                is_new = item.get("kind") == "new"
                                card = {
                                    "config": {"wide_screen_mode": True},
                                    "header": {
                                        "title": {"tag": "plain_text", "content": f"{'⚡【新词速攻·卖积分】' if is_new else '💎【二次爆火·做订阅】'} {item.get('keyword')}"},
                                        "template": "turquoise" if is_new else "carmine"
                                    },
                                    "elements": [
                                        {
                                            "tag": "div",
                                            "fields": [
                                                {"is_short": True, "text": {"tag": "lark_md", "content": f"**赛道方向:** {item.get('category', '').upper()}"}},
                                                {"is_short": True, "text": {"tag": "lark_md", "content": f"**热度倍数:** GPTs ×{round(item.get('heat_ratio', 0), 2)}"}},
                                                {"is_short": True, "text": {"tag": "lark_md", "content": f"**近期涨幅:** +{item.get('growth_pct')}%"}},
                                                {"is_short": True, "text": {"tag": "lark_md", "content": f"**走势状态:** {item.get('trend_now') or '高位'}"}}
                                            ]
                                        },
                                        {"tag": "hr"},
                                        {
                                            "tag": "div",
                                            "text": {
                                                "tag": "lark_md",
                                                "content": f"**💡 商业策略指南 (How):**\n{item.get('brief_how') or item.get('brief_what') or '暂无'}"
                                            }
                                        },
                                        {
                                            "tag": "action",
                                            "actions": [
                                                {
                                                    "tag": "button",
                                                    "text": {"tag": "plain_text", "content": "📊 打开多维表格看板 ↗"},
                                                    "type": "primary",
                                                    "url": f"https://qcnik9bast8t.feishu.cn/base/{FEISHU_BITABLE_APP_TOKEN}"
                                                }
                                            ]
                                        }
                                    ]
                                }
                                fc.send_card_message(chat_id, "chat_id", card)
                            except Exception as e:
                                print(f"[!] 发送卡片异常: {e}")
                else:
                    print(f"[{now_str}] 暂无新批次更新。")
            except Exception as e:
                print(f"[!] 监控轮询出错: {e}")

            time.sleep(args.interval)

    elif args.command == "ui":
        from generate_ui import generate_dashboard
        html_file = generate_dashboard()
        print("\n[+] 哥飞 1:1 对标看板网页已生成！")
        print("    - 本地文件路径: /home/chuck/projects/agy/data/dashboard.html")
        print("    - Windows 访问路径: \\\\wsl.localhost\\Ubuntu\\home\\chuck\\projects\\agy\\data\\dashboard.html")
        try:
            import subprocess
            subprocess.run(["explorer.exe", "\\\\wsl.localhost\\Ubuntu\\home\\chuck\\projects\\agy\\data\\dashboard.html"], stderr=subprocess.DEVNULL)
            print("    - [✓] 已通过 explorer.exe 唤起 Windows 默认浏览器打开看板！")
        except Exception:
            pass

if __name__ == "__main__":
    main()
