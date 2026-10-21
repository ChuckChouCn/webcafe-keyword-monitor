import json
import sqlite3
import threading
import time
from typing import Dict, Any, Optional
import lark_oapi as lark
from config import (
    FEISHU_APP_ID,
    FEISHU_APP_SECRET,
    FEISHU_CHAT_ID,
    FEISHU_BITABLE_APP_TOKEN,
    DB_PATH
)
from feishu_client import FeishuClient
from service import KeywordMonitorService

fc = FeishuClient()
svc = KeywordMonitorService()

def query_keyword_detail(kw_name: str) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM keywords WHERE keyword LIKE ? ORDER BY heat_ratio DESC LIMIT 1", (f"%{kw_name}%",))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["verdict_reasons"] = json.loads(d["verdict_reasons"]) if d.get("verdict_reasons") else []
    return d

def query_top_keywords(kind: Optional[str] = None, category: Optional[str] = None, limit: int = 5):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    conditions = ["verdict = 'worth'", "category IN ('ai', 'tool')"]
    params = []
    if kind:
        conditions.append("kind = ?")
        params.append(kind)
    if category:
        conditions.append("category = ?")
        params.append(category)

    sql = f"""
        SELECT * FROM keywords
        WHERE {' AND '.join(conditions)}
        ORDER BY heat_ratio DESC
        LIMIT ?
    """
    params.append(limit)
    cur.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def handle_user_command(user_text: str) -> Dict[str, Any]:
    text = user_text.strip().lower()

    # 1. 帮助与菜单
    if text in ("帮助", "help", "菜单", "?", "？", "hi", "hello"):
        return {
            "type": "card",
            "title": "🤖 agy AI 商业分析助手 · 使用指令",
            "template": "blue",
            "content": """**你可以直接在飞书里给我发送以下指令：**

• **查关键词**：输入 `查 minimax` 或 `搜 photocraft`，立即查看该词的完整商业立项分析与做站指南。
• **看新词**：输入 `新词`，查看最新爆发、适合快速卖积分的 Top 5 AI/工具词。
• **看长线词**：输入 `二次爆火` 或 `订阅`，查看适合做长期 SaaS 订阅的 Top 5 标的。
• **查看库统计**：输入 `统计`，查看当前库内收录总数与值得做占比。
• **多维表格**：输入 `表格`，获取 38 个精选商机库直达链接。"""
        }

    # 2. 查多维表格
    if "表格" in text or "看板" in text or "bitable" in text:
        return {
            "type": "card",
            "title": "📊 飞书多维表格 · AI与工具商机总库",
            "template": "indigo",
            "content": f"你的专属多维表格已在线同步，包含 38 个精选 AI & 工具付费商机：\n\n👉 [点击直接打开多维表格总库](https://qcnik9bast8t.feishu.cn/base/{FEISHU_BITABLE_APP_TOKEN})"
        }

    # 3. 统计指令
    if "统计" in text or "数据" in text:
        stats = svc.get_statistics()
        return {
            "type": "card",
            "title": "📊 词库当前监控统计",
            "template": "watchet",
            "content": f"""• **收录总批次**: {stats['total_batches']} 个
• **入库独立新词**: {stats['total_keywords']} 个
• **AI 与 工具【值得做】精选**: 38 个
• **最新同步批次**: `{stats['latest_batch']['id'] if stats['latest_batch'] else '无'}`"""
        }

    # 4. 新词推荐
    if "新词" in text or "积分" in text:
        items = query_top_keywords(kind="new", limit=5)
        lines = []
        for idx, it in enumerate(items, 1):
            lines.append(f"**{idx}. [{it['category'].upper()}] {it['keyword']}** (GPTs ×{round(it['heat_ratio'], 2)})\n• 方案: {it['brief_how'][:80]}...\n")
        return {
            "type": "card",
            "title": "⚡【新词速攻 · 卖积分】Top 5 精选标的",
            "template": "turquoise",
            "content": "\n".join(lines)
        }

    # 5. 二次爆火推荐
    if "二次爆火" in text or "订阅" in text or "长期" in text:
        items = query_top_keywords(kind="resurgence", limit=5)
        lines = []
        for idx, it in enumerate(items, 1):
            lines.append(f"**{idx}. [{it['category'].upper()}] {it['keyword']}** (GPTs ×{round(it['heat_ratio'], 2)})\n• 方案: {it['brief_how'][:80]}...\n")
        return {
            "type": "card",
            "title": "💎【二次爆火 · 做长线订阅】Top 5 精选标的",
            "template": "carmine",
            "content": "\n".join(lines)
        }

    # 6. 查指定词
    search_term = text
    for prefix in ("查", "搜", "分析", "看", "search ", "find "):
        if search_term.startswith(prefix):
            search_term = search_term[len(prefix):].strip()
            break

    detail = query_keyword_detail(search_term)
    if detail:
        is_new = detail.get("kind") == "new"
        badge = "⚡ 新词速攻·卖积分" if is_new else "💎 二次爆火·做长线订阅"
        color = "turquoise" if is_new else "carmine"
        return {
            "type": "card",
            "title": f"{badge}: {detail['keyword']}",
            "template": color,
            "content": f"""**【基本面指标】**
• 分类: `{detail['category'].upper()}` | 热度: `GPTs ×{round(detail['heat_ratio'], 2)}` | 涨幅: `+{detail['growth_pct']}%` | 走势: `{detail['trend_now']}`

**【这是什么 (What)】**
{detail['brief_what'] or '暂无说明'}

**【用户痛点 (Want)】**
{detail['brief_want'] or '暂无说明'}

**【建议怎么做工具/收积分 (How)】**
{detail['brief_how'] or '暂无说明'}"""
        }

    # 7. 未识别指令
    return {
        "type": "text",
        "content": f"未找到与「{user_text}」相关的 AI/工具 黄金词。你可以输入「新词」、「二次爆火」、「统计」或「查 <词名>」查看商机！"
    }

def on_message_received(data: lark.im.v1.P2ImMessageReceiveV1):
    try:
        event = data.event
        msg = event.message
        chat_id = msg.chat_id
        msg_type = msg.message_type

        # 仅处理文本消息
        if msg_type != "text":
            return

        content_dict = json.loads(msg.content)
        user_text = content_dict.get("text", "").strip()

        # 去除 @机器人的标识
        if "@_user" in user_text:
            import re
            user_text = re.sub(r"@_user_\d+", "", user_text).strip()

        print(f"[*] 收到飞书消息: [{user_text}] 来自会话: {chat_id}")

        reply_data = handle_user_command(user_text)

        if reply_data["type"] == "card":
            card = {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": reply_data["title"]},
                    "template": reply_data["template"]
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {"tag": "lark_md", "content": reply_data["content"]}
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
        else:
            # 发普通文本
            url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
            payload = {
                "receive_id": chat_id,
                "msg_type": "text",
                "content": json.dumps({"text": reply_data["content"]}, ensure_ascii=False)
            }
            import requests
            requests.post(url, headers=fc._headers(), json=payload, timeout=10)

    except Exception as e:
        print(f"[!] 处理飞书消息异常: {e}")

def start_ws_bot():
    print("=" * 60)
    print("🚀 启动飞书官方 WebSocket 长连接服务 (双向互动机器人)...")
    print("=" * 60)
    event_handler = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_im_message_receive_v1(on_message_received) \
        .build()

    client = lark.ws.Client(
        FEISHU_APP_ID,
        FEISHU_APP_SECRET,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO
    )
    client.start()

if __name__ == "__main__":
    start_ws_bot()
