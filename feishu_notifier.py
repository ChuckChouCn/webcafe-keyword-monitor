import json
import requests
from typing import Dict, Any, Optional

def send_feishu_webhook(webhook_url: str, keyword_item: Dict[str, Any]) -> bool:
    """
    发送结构化飞书卡片消息到自定义机器人 Webhook
    """
    if not webhook_url:
        return False

    is_new = keyword_item.get("kind") == "new"
    category = keyword_item.get("category", "tool").upper()
    keyword = keyword_item.get("keyword", "")
    heat_ratio = keyword_item.get("heat_ratio", 0)
    growth_pct = keyword_item.get("growth_pct")
    growth_str = f"+{growth_pct}%" if growth_pct else "平稳"

    if is_new:
        strategy_badge = "⚡【新词速攻 · 卖积分模式】"
        strategy_desc = "适合：24小时快速上线单页/Playground套壳，集成 API 免费试用1次，购买额度包/积分充值"
        header_color = "turquoise"
    else:
        strategy_badge = "💎【二次爆火 · 做长线订阅】"
        strategy_desc = "适合：沉淀为长期垂直在线工具/SaaS，提供云端免安装能力，做 $9.9~$19/月 会员订阅"
        header_color = "carmine"

    brief = keyword_item.get("brief") or {}
    what_text = brief.get("what") or keyword_item.get("brief_what") or "暂无说明"
    want_text = brief.get("want") or keyword_item.get("brief_want") or "暂无说明"
    how_text = brief.get("how") or keyword_item.get("brief_how") or "暂无说明"
    page_url = keyword_item.get("page_url", "")

    # 构造飞书交互卡片 JSON
    card_payload = {
        "msg_type": "interactive",
        "card": {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"{strategy_badge} {keyword}"
                },
                "template": header_color
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**赛道方向:** {category}"
                            }
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**热度倍数:** GPTs ×{round(heat_ratio, 2) if heat_ratio else '-'}"
                            }
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**近期涨幅:** {growth_str}"
                            }
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**走势状态:** {keyword_item.get('trend_now') or '稳定'}"
                            }
                        }
                    ]
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**💡 商业策略定位:**\n{strategy_desc}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**🛠️ 这是什么 (What):**\n{what_text}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**🎯 搜索痛点 (Want):**\n{want_text}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**🚀 建议怎么建站/做工具 (How):**\n{how_text}"
                    }
                }
            ]
        }
    }

    if page_url:
        card_payload["card"]["elements"].append({
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {
                        "tag": "plain_text",
                        "content": "查看官方 SEO 竞争分析 ↗"
                    },
                    "type": "primary",
                    "url": page_url
                }
            ]
        })

    try:
        resp = requests.post(webhook_url, json=card_payload, timeout=10)
        res_json = resp.json()
        return res_json.get("code") == 0 or res_json.get("StatusCode") == 0
    except Exception as e:
        print(f"[!] 飞书推送失败: {e}")
        return False
