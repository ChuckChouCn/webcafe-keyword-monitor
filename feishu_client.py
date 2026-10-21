import time
import requests
from typing import Dict, Any, List, Optional
from config import (
    FEISHU_APP_ID,
    FEISHU_APP_SECRET,
    FEISHU_BITABLE_APP_TOKEN,
    FEISHU_BITABLE_TABLE_ID,
    FEISHU_CHAT_ID
)

class FeishuClient:
    def __init__(self, app_id: str = FEISHU_APP_ID, app_secret: str = FEISHU_APP_SECRET):
        self.app_id = app_id
        self.app_secret = app_secret
        self.token = ""
        self.token_expire_time = 0

    def get_tenant_access_token(self) -> str:
        """获取并自动刷新 tenant_access_token"""
        if self.token and time.time() < self.token_expire_time - 300:
            return self.token

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={"app_id": self.app_id, "app_secret": self.app_secret}, timeout=10)
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取飞书 token 失败: {data}")

        self.token = data["tenant_access_token"]
        self.token_expire_time = time.time() + data.get("expire", 7200)
        return self.token

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.get_tenant_access_token()}",
            "Content-Type": "application/json"
        }

    def list_chats(self) -> List[Dict[str, Any]]:
        """获取机器人所在的群列表"""
        url = "https://open.feishu.cn/open-apis/im/v1/chats"
        resp = requests.get(url, headers=self._headers(), timeout=10)
        data = resp.json()
        if data.get("code") == 0:
            return data.get("data", {}).get("items", [])
        return []

    def send_card_message(self, receive_id: str, receive_id_type: str, card_content: Dict[str, Any]) -> bool:
        """发送交互式卡片消息"""
        url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}"
        payload = {
            "receive_id": receive_id,
            "msg_type": "interactive",
            "content": json_str(card_content)
        }
        resp = requests.post(url, headers=self._headers(), json=payload, timeout=10)
        data = resp.json()
        if data.get("code") == 0:
            return True
        print(f"[!] 飞书发消息失败: {data}")
        return False

    def add_bitable_record(self, item: Dict[str, Any], table_id: str = FEISHU_BITABLE_TABLE_ID) -> bool:
        """往飞书多维表格中新增一条商机记录"""
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_BITABLE_APP_TOKEN}/tables/{table_id}/records"
        is_new = item.get("kind") == "new"
        strategy = "⚡ 新词速攻·卖积分" if is_new else "💎 二次爆火·做长线订阅"

        brief = item.get("brief") or {}
        what = brief.get("what") or item.get("brief_what") or ""
        want = brief.get("want") or item.get("brief_want") or ""
        how = brief.get("how") or item.get("brief_how") or ""
        page_url = item.get("page_url", "")

        fields = {
            "关键词": item.get("keyword", ""),
            "推荐策略": strategy,
            "分类": item.get("category", "tool").upper(),
            "热度(GPTs倍数)": round(item.get("heat_ratio", 0), 2) if item.get("heat_ratio") else 0,
            "近期涨幅": f"+{item.get('growth_pct')}%" if item.get("growth_pct") else "平稳",
            "这是什么(What)": what[:500],
            "用户痛点(Want)": want[:500],
            "做工具/收费指南(How)": how[:500],
        }
        if page_url:
            fields["官方分析链接"] = {"text": "查看官方分析 ↗", "link": page_url}

        resp = requests.post(url, headers=self._headers(), json={"fields": fields}, timeout=10)
        return resp.json().get("code") == 0

def json_str(obj: Any) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)
