"""
定时监控与 AI 门禁处理流水线 (Monitor Pipeline)
- 每 10 分钟自动增量拉取最新批次
- 代码初筛：排除游戏/内容，热度 >= 0.05 或涨幅 >= 200%
- AI 门禁：仅放行具备明确付费场景的工具/软件
- 消息触达：通过 cc-connect send 直接推送到你的飞书聊天
"""
import sys
import time
import argparse
import sqlite3
from datetime import datetime
from typing import List, Dict, Any

from config import DB_PATH
from service import KeywordMonitorService
from db import get_connection
from ai_gatekeeper import evaluate_keyword
from cc_connect_notifier import send_keyword_alert

svc = KeywordMonitorService()

def mark_all_historical_reviewed():
    """
    首次启动时，将历史老词打上已审核标记，避免启动瞬间对几千个旧词海量误推。
    """
    conn = get_connection()
    with conn:
        conn.execute("UPDATE keywords SET ai_reviewed = 1 WHERE ai_reviewed = 0;")
    print("[*] 历史旧词已初始化归档（新词将在产生时即时审核与推送）。")

def screen_unreviewed_keywords() -> List[Dict[str, Any]]:
    """
    对所有未审核（ai_reviewed = 0）的词进行初筛与 AI 深度门禁
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM keywords WHERE ai_reviewed = 0;")
    rows = [dict(r) for r in cur.fetchall()]
    
    if not rows:
        return []

    approved_list = []

    for item in rows:
        kw = item.get("keyword")
        cat = (item.get("category") or "").lower()
        verdict = item.get("verdict")
        heat = item.get("heat_ratio") or 0
        growth = item.get("growth_pct") or 0

        # 第 1 层：代码硬规则直接淘汰
        # 1. 淘汰游戏类
        if cat in ("game", "webgame"):
            with conn:
                conn.execute(
                    "UPDATE keywords SET ai_reviewed = 1, ai_verdict = 'drop_game' WHERE keyword = ?;",
                    (kw,)
                )
            continue

        # 2. 淘汰非 worth 词
        if verdict != "worth":
            with conn:
                conn.execute(
                    "UPDATE keywords SET ai_reviewed = 1, ai_verdict = 'drop_not_worth' WHERE keyword = ?;",
                    (kw,)
                )
            continue

        # 3. 淘汰无热度且无暴涨的冷门词 (heat < 0.05 且 growth < 200%)
        if heat < 0.05 and growth < 200:
            with conn:
                conn.execute(
                    "UPDATE keywords SET ai_reviewed = 1, ai_verdict = 'drop_low_heat' WHERE keyword = ?;",
                    (kw,)
                )
            continue

        # 通过第 1 层硬指标，进入第 2 层：AI 极简门禁审核
        print(f"[*] AI 门禁审核中: {kw} (热度: GPTs x{round(heat, 2)}, 涨幅: +{growth}%)...")
        ai_res = evaluate_keyword(item)

        is_paid = ai_res.get("is_paid_tool", False)
        proposal_text = f"[{ai_res.get('tool_category')}] 变现: {ai_res.get('monetization')} | 理由: {ai_res.get('reason')}"

        with conn:
            conn.execute(
                """
                UPDATE keywords 
                SET ai_reviewed = 1, 
                    ai_verdict = ?, 
                    ai_proposal = ?,
                    updated_at = CURRENT_TIMESTAMP 
                WHERE keyword = ?;
                """,
                ("paid_tool" if is_paid else "rejected", proposal_text, kw)
            )

        if is_paid:
            print(f"[✅ 审核通过] {kw} -> {ai_res.get('tool_category')}")
            send_keyword_alert(item, ai_res)
            approved_list.append(item)
        else:
            print(f"[❌ 审核淘汰] {kw} -> {ai_res.get('reason')}")

    return approved_list

def run_test_sample(sample_keyword: str = "seedance 2.5"):
    """
    测试模式：选取指定词跑一遍完整的「AI 审核 -> cc-connect 推送」流程
    """
    print(f"[*] 正在为测试词 [{sample_keyword}] 执行完整链路联调...")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM keywords WHERE keyword LIKE ? LIMIT 1;", (f"%{sample_keyword}%",))
    row = cur.fetchone()
    if not row:
        print(f"[!] 数据库中未找到测试词: {sample_keyword}")
        return

    item = dict(row)
    print(f"[*] 调用 AI 门禁审核 [{item['keyword']}]...")
    ai_res = evaluate_keyword(item)
    is_paid = ai_res.get("is_paid_tool", False)
    if is_paid:
        print("[*] 正在通过 cc-connect 推送飞书...")
        success = send_keyword_alert(item, ai_res)
        if success:
            print("[+] 联调成功！飞书已成功收到推送消息。")
        else:
            print("[!] 推送失败，请检查 cc-connect 会话状态。")
    else:
        print(f"[-] 门禁审核淘汰: {ai_res.get('reason')} (不推送到飞书)")

def start_daemon(interval: int = 600):
    """
    启动 10 分钟轮询守护进程
    """
    print(f"[*] 启动哥飞新词监控 & AI 门禁守护进程 (轮询间隔: {interval} 秒 / 10分钟)...")
    
    # 检查是否有未初始化的历史词
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM keywords WHERE ai_reviewed = 0;")
    unreviewed_count = cur.fetchone()[0]
    if unreviewed_count > 50:
        print(f"[*] 发现 {unreviewed_count} 个历史旧词，正在执行防刷屏归档...")
        mark_all_historical_reviewed()

    while True:
        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n[{now_str}] 正在检查 WebCafe 最新批次...")
            res = svc.sync(max_pages=1, force=False)
            fetched = res.get("batches_fetched", 0)
            new_kw = res.get("new_keywords", 0)

            if fetched > 0:
                print(f"[{now_str}] 抓取到 {fetched} 个新批次，入库新词 {new_kw} 个。开始执行门禁筛选...")
                approved = screen_unreviewed_keywords()
                print(f"[{now_str}] 本轮筛选完成，推送高价值付费工具: {len(approved)} 个")
            else:
                print(f"[{now_str}] 暂无新批次更新（已是最新数据）。")
                # 兜底扫描是否有残留未审词
                screen_unreviewed_keywords()

        except Exception as e:
            print(f"[!] 轮询过程发生异常: {e}")

        print(f"[*] 等待下一次轮询 ({interval} 秒后)...")
        time.sleep(interval)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebCafe 选词监控与 AI 门禁服务")
    parser.add_argument("--test", action="store_true", help="联调测试：选取样板词执行一次完整的 AI 审核与推送")
    parser.add_argument("--daemon", action="store_true", help="启动常驻 10 分钟轮询守护进程")
    parser.add_argument("--interval", type=int, default=600, help="轮询间隔（秒，默认 600 秒即 10 分钟）")
    parser.add_argument("--sample", type=str, default="seedance 2.5", help="测试时使用的关键词名")

    args = parser.parse_args()

    if args.test:
        run_test_sample(args.sample)
    elif args.daemon:
        start_daemon(args.interval)
    else:
        # 默认执行一次检查
        print("[*] 执行单次扫描检查...")
        res = svc.sync(max_pages=1, force=False)
        approved = screen_unreviewed_keywords()
        print(f"[*] 完成。通过并推送词数: {len(approved)}")
