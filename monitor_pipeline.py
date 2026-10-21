"""
定时监控与 AI 门禁处理流水线 (Monitor Pipeline)
- 定时自动增量拉取最新批次
- 第 1 层代码硬规则门禁：
  1. 淘汰游戏与纯娱乐
  2. 淘汰非 worth 词
  3. 走势一票否决：回落、下降、负增长坚决不推，必须为上升走势
  4. 严格时效与爆发校验：新词必须在近 30 天内出现；老词仅当在近 14 天内二次爆发且暴涨时才作为二次爆火放行
  5. 淘汰微弱信号词 (heat < 0.05 且 growth < 100)
- 第 2 层 AI 深度门禁：
  综合考量功能交互、变现能力、以及当前是否处于风口红利期，严拒过气与下行词
- 消息触达：
  通过 cc-connect send 直接推送到你的飞书聊天，并自动同步当前焦点词上下文
"""
import sys
import time
import argparse
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from config import DB_PATH
from service import KeywordMonitorService
from db import get_connection
from ai_gatekeeper import evaluate_keyword
from cc_connect_notifier import send_keyword_alert

svc = KeywordMonitorService()

def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip()[:10], "%Y-%m-%d")
    except Exception:
        return None

def check_keyword_suitability(item: Dict[str, Any]) -> Tuple[bool, str, str]:
    """
    第一层代码硬规则初筛与定位：
    返回: (is_qualified: bool, drop_reason_or_ok: str, kind_tag: str)
    """
    kw = item.get("keyword", "")
    cat = (item.get("category") or "").lower()
    verdict = item.get("verdict")
    heat = item.get("heat_ratio") or 0.0
    growth = item.get("growth_pct")
    trend_str = (item.get("trend_now") or "").strip()
    appear_d = parse_date(item.get("appear_date"))
    burst_d = parse_date(item.get("burst_date"))
    now = datetime.now()

    # 1. 淘汰游戏与纯娱乐
    if cat in ("game", "webgame"):
        return False, "drop_game", ""

    # 2. 淘汰非 worth 词 (必须为哥飞建议做的 worth 词)
    if verdict != "worth":
        return False, "drop_not_worth", ""

    # 3. 走势一票否决：回落、下降、跌、负增长坚决不推
    if any(k in trend_str for k in ("回落", "下降", "跌", "衰退")):
        return False, "drop_declining_trend", ""
    if growth is not None and growth < 0:
        return False, "drop_negative_growth", ""
    if "上升" not in trend_str and trend_str != "":
        # 如果不是明确上升，且无暴涨数据，予以淘汰
        if growth is None or growth < 100:
            return False, "drop_not_rising", ""

    # 4. 淘汰无热度信号词 (heat < 0.05 且 growth < 100)
    if heat < 0.05 and (growth is None or growth < 100):
        return False, "drop_low_heat", ""

    # 5. 时效性与红利期严格校验 (杜绝数月前旧词冒充新词)
    appear_days = (now - appear_d).days if appear_d else None
    burst_days = (now - burst_d).days if burst_d else None

    # 分类判定:
    # A. 真正的新词 (新词速攻): 出现时间在近 30 天内
    if appear_days is not None and appear_days <= 30:
        return True, "ok", "new"
    
    # B. 老词但近期二次爆发 (二次爆火):
    # 出现时间较早，但爆发日期在近 14 天内，且有显著暴涨 (growth >= 100% 或 heat >= 0.2)
    if burst_days is not None and burst_days <= 14:
        if (growth is not None and growth >= 100) or heat >= 0.2:
            return True, "ok", "resurgence"
        else:
            return False, "drop_resurgence_insufficient_growth", ""

    # C. 如果两者都没有有效日期，但有极高暴涨 (growth >= 200%)
    if appear_days is None and burst_days is None:
        if growth is not None and growth >= 200:
            return True, "ok", "new"
        return False, "drop_no_date_low_surge", ""

    # D. 既不是新词 (appear > 30 天)，又不是近期爆发 (burst > 14 天或无近期爆发) -> 陈年老词淘汰
    return False, "drop_stale_old_word", ""

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
        heat = item.get("heat_ratio") or 0
        growth = item.get("growth_pct")
        trend = item.get("trend_now", "未知")

        # 第 1 层：代码硬规则门禁审核
        is_ok, drop_code, kind_tag = check_keyword_suitability(item)
        if not is_ok:
            with conn:
                conn.execute(
                    "UPDATE keywords SET ai_reviewed = 1, ai_verdict = ? WHERE keyword = ?;",
                    (drop_code, kw)
                )
            continue

        # 校准类型标签 (杜绝盲信上游数据)
        item["kind"] = kind_tag

        # 通过第 1 层硬指标，进入第 2 层：AI 深度门禁审核 (把关付费场景与时机红利)
        print(f"[*] AI 门禁审核中: {kw} (走势: {trend}, 涨幅: {growth}%, 热度: GPTs x{round(heat, 2)})...")
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
                    kind = ?,
                    updated_at = CURRENT_TIMESTAMP 
                WHERE keyword = ?;
                """,
                ("paid_tool" if is_paid else "rejected", proposal_text, kind_tag, kw)
            )

        if is_paid:
            print(f"[✅ 审核通过] {kw} -> {ai_res.get('tool_category')}")
            send_keyword_alert(item, ai_res)
            approved_list.append(item)
        else:
            print(f"[❌ 审核淘汰] {kw} -> {ai_res.get('reason')}")

    return approved_list

def run_test_sample(sample_keyword: str = "reverse engineer anything github"):
    """
    测试模式：选取指定词跑一遍完整的「硬规则初筛 -> AI 审核 -> cc-connect 推送」流程
    """
    print(f"[*] 正在为测试词 [{sample_keyword}] 执行完整链路联调...")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM keywords WHERE keyword = ? OR keyword LIKE ? ORDER BY CASE WHEN keyword = ? THEN 1 ELSE 2 END, heat_ratio DESC LIMIT 1;",
        (sample_keyword, f"%{sample_keyword}%", sample_keyword)
    )
    row = cur.fetchone()
    if not row:
        print(f"[!] 数据库中未找到测试词: {sample_keyword}")
        return

    item = dict(row)
    print(f"[*] 执行第 1 层硬规则初筛...")
    is_ok, drop_code, kind_tag = check_keyword_suitability(item)
    if not is_ok:
        print(f"[-] 硬规则初筛淘汰: 原因代码 = {drop_code}")
        return

    item["kind"] = kind_tag
    print(f"[+] 第 1 层通过！定位为: {'⚡新词速攻' if kind_tag == 'new' else '💎二次爆火'}")

    print(f"[*] 执行第 2 层 AI 门禁审核 [{item['keyword']}]...")
    ai_res = evaluate_keyword(item)
    is_paid = ai_res.get("is_paid_tool", False)
    if is_paid:
        print(f"[+] AI 审核通过: {ai_res.get('reason')}")
        print("[*] 正在通过 cc-connect 推送飞书...")
        success = send_keyword_alert(item, ai_res)
        if success:
            print("[+] 联调成功！飞书已成功收到推送消息。")
        else:
            print("[!] 推送失败，请检查 cc-connect 会话状态。")
    else:
        print(f"[-] AI 门禁审核淘汰: {ai_res.get('reason')} (不推送到飞书)")

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
    parser.add_argument("--sample", type=str, default="grok bot", help="测试时使用的关键词名")

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
