import json
import os
import datetime
from dotenv import load_dotenv

load_dotenv()  # 讀取 .env 檔案
DEVELOPER_ID = os.getenv("DEVELOPER_ID")  # 開發者 ID

USAGE_FILE = "./user_usage.txt"
MAX_USAGE = 3

# 初始化檔案（如果不存在就自動生成）
def init_usage_file():
    if not os.path.exists(USAGE_FILE):
        usage_data = {"month": datetime.date.today().month, "usage": {}}
        with open(USAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(usage_data, f, indent=2, ensure_ascii=False)

# 讀取使用紀錄
def load_usage():
    init_usage_file()  # 確保檔案存在
    with open(USAGE_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {"month": datetime.date.today().month, "usage": {}}

# 寫入使用紀錄
def save_usage(usage_dict):
    with open(USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(usage_dict, f, indent=2, ensure_ascii=False)

# 檢查並更新使用次數
def check_and_update_usage(user_id):
    today = datetime.date.today()
    usage_data = load_usage()

    # 後門使用者 → 無限制
    if user_id == DEVELOPER_ID:
        return "開發者"

    # 如果跨月 → 自動重置
    if usage_data.get("month") != today.month:
        usage_data = {"month": today.month, "usage": {}}

    usage_dict = usage_data["usage"]
    user_info = usage_dict.get(user_id, {"count": 0, "last_time": None})

    # 檢查操作間隔
    now = datetime.datetime.now()
    if user_info["last_time"] is not None:
        last_time = datetime.datetime.fromisoformat(user_info["last_time"])
        if (now - last_time).total_seconds() < 60:
            return "操作間隔必須大於 1 分鐘"

    # 檢查次數限制
    if user_info["count"] >= MAX_USAGE:
        return "這個月的使用次數已達上限30次"

    return "OK"

def update_usage(user_id):  # 更新紀錄
    today = datetime.date.today() 
    usage_data = load_usage() 
    usage_dict = usage_data["usage"] 
    user_info = usage_dict.get(user_id, {"count": 0, "last_time": None}) 
    user_info["count"] += 1 
    user_info["last_time"] = datetime.datetime.now().isoformat() 
    usage_dict[user_id] = user_info 
    usage_data["usage"] = usage_dict 
    usage_data["month"] = today.month 
    save_usage(usage_data) 
    return f"目前已使用 {user_info['count']} 次"


