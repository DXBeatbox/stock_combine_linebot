import os
from dotenv import load_dotenv

load_dotenv()  # 讀取 .env 檔案

# 取得環境變數
line_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
line_secret = os.getenv("LINE_CHANNEL_SECRET")
ngrok_token = os.getenv("NGROK_AUTH_TOKEN")
gemini_key = os.getenv("GEMINI_API_KEY")
serpapi_api_key = os.getenv("SERPAPI_API_KEY")
cloudnary_cloud_name = os.getenv("CLOUDINARY_CLOUD_NMAE")
cloudnary_api_key = os.getenv("CLOUDINARY_API_KEY")
cloudnary_api_secret = os.getenv("CLOUDINARY_API_SERECT") 


from flask import Flask, request, abort
# line api
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, JoinEvent, ImageSendMessage, FlexSendMessage ,PostbackEvent
)

from pyngrok import ngrok
from pyngrok import conf
import requests #auto update Webhook URL

import numpy as np
import datetime
# import twstock
import yfinance as yf 
import matplotlib
matplotlib.use("Agg")  # 設定為非GUI backend
import matplotlib.pyplot as plt
import cloudinary
import cloudinary.uploader

from google import genai
from serpapi import GoogleSearch

import json
import math
import threading

from Check_usage_limit import (load_usage, check_and_update_usage, update_usage)

app = Flask(__name__)

# 設定 Gemini API 金鑰
# genai.configure(api_key=gemini_key)
client = genai.Client(api_key=gemini_key)

# 替換成你自己的 Channel Access Token 和 Channel Secret
line_bot_api = LineBotApi(line_token)
handler = WebhookHandler(line_secret)

with open("quickTourButton.json", "r", encoding="utf-8") as f:
    quickTourButton = json.load(f)

with open("stock_info.json", "r", encoding="utf-8") as f:
    stock_info = json.load(f)

# AI Model list
models = ["gemini-3-flash-preview", "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite-preview-09-2025", "gemini-2.5-flash-lite"]


# 函式：執行 Google 搜尋
def google_search(query):
    search_params = {
        "engine": "google",
        "q": query,
        "api_key": serpapi_api_key
    }
    search = GoogleSearch(search_params)
    results = search.get_dict()
    
    # 提取搜尋結果中的標題和連結
    if "organic_results" in results:
        organic_results = results["organic_results"]
        # 僅提取前3個結果以保持簡潔
        snippets = [f"標題: {res['title']}\n摘要: {res['snippet']}" for res in organic_results[:10]]
        return "\n\n".join(snippets)
    else:
        return "找不到相關搜尋結果。"
    

# Webhook 路徑
@app.route("/callback", methods=['POST'])
def callback():
    # 取得 LINE 傳來的簽名
    signature = request.headers['X-Line-Signature']

    # 取得請求內容
    body = request.get_data(as_text=True)
    # print("收到事件：", body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
        # 即使錯誤也回傳 200，避免 LINE 重送 
        # return 'OK', 200
    except Exception as e:
        print("Handler error:", e)  # 印 log 但不讓 Flask 回 500
    return 'OK', 200


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text_0 = event.message.text
    spilt_words = text_0.split(" ")
    response_txt = False
    
    line_bot_api = LineBotApi(line_token)

    

    match spilt_words[0]:
        case "快速導覽":
            message = FlexSendMessage( alt_text="股票快訊", contents=quickTourButton ) 
            line_bot_api.reply_message(event.reply_token, message)
            return 
        
        case "個股資訊":
            message = FlexSendMessage( alt_text="個股資訊", contents=stock_info ) 
            line_bot_api.reply_message(event.reply_token, message)
            return 

        case "stock":
            limit_check = check_and_update_usage(user_id)
            match limit_check:
                case "操作間隔必須大於 1 分鐘":
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text=limit_check)
                    )
                    return 
                case "這個月的使用次數已達上限30次":
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text=limit_check)
                    )
                    return 
                
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"已收到查詢 {spilt_words[1]}，正在產生圖表，請稍候...")
            )
            def process_stock_message(uid, words):
                image_url, reply_text = plot_stock_chart(words)
                image_message = ImageSendMessage(
                    original_content_url=image_url,
                    preview_image_url=image_url
                )
                line_bot_api.push_message(uid, [image_message, TextSendMessage(text=reply_text)])
                plt.close()
                update_usage(uid)
            threading.Thread(target=process_stock_message, args=(user_id, spilt_words)).start()
            return
            
    

        case "gemini":
            limit_check = check_and_update_usage(user_id)
            match limit_check:
                case "操作間隔必須大於 1 分鐘":
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text=limit_check)
                    )
                    return
                case "這個月的使用次數已達上限30次":
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text=limit_check)
                    )
                    return
                
            response_txt = True
            text_input = spilt_words[1]
            reply_text = None
            for model_name in models:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=text_input
                    )
                    reply_text = response.text.replace("*","")
                    break  # 成功就跳出迴圈
                except Exception as e:
                    continue  # 換下一個模型
            if not reply_text:
                reply_text = "目前所有模型都無法使用，請稍後再試或升級方案。"
            
            update_usage(user_id) # 更新紀錄

    if response_txt :
        reply = TextSendMessage(reply_text)
        # line_bot_api.reply_message(event.reply_token, reply)
        line_bot_api.push_message(user_id, reply)
        response_txt = False
        return


# 處理加入群組事件
@handler.add(JoinEvent)
def handle_join(event):
    group_id = event.source.group_id
    # print("加入的群組 ID：", group_id)
    # 發送歡迎訊息
    line_bot_api.push_message(group_id, TextSendMessage(text='王老闆、侯老闆還有陳老闆大家好！！！'))
    return


@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    text_0 = event.postback.data # 例如 "stock=2330"
    # text_0 = event.message.text
    response_txt = False
    spilt_words = text_0.split(" ")
    
    line_bot_api = LineBotApi(line_token)

    match spilt_words[0]:
        case "Dr_willy_said":
            image_message = ImageSendMessage(
                original_content_url=Dr_willy_said_url,
                preview_image_url=Dr_willy_said_url
            )
            line_bot_api.push_message(user_id, image_message)
            return
            # line_bot_api.reply_message(
            #     event.reply_token,
            #     image_message
            # )

        case "stock":
            limit_check = check_and_update_usage(user_id)
            match limit_check:
                case "操作間隔必須大於 1 分鐘":
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text=limit_check)
                    )
                    return
                case "這個月的使用次數已達上限30次":
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text=limit_check)
                    )
                    return
                
            line_bot_api.push_message(
                user_id,
                TextSendMessage(text=f"已收到查詢 {spilt_words[1]}，正在產生圖表，請稍候...")
            )
            def process_stock_postback(uid, words):
                image_url, reply_text = plot_stock_chart(words)
                image_message = ImageSendMessage(
                    original_content_url=image_url,
                    preview_image_url=image_url
                )
                line_bot_api.push_message(uid, [image_message, TextSendMessage(text=reply_text)])
                plt.close()
                update_usage(uid)
            threading.Thread(target=process_stock_postback, args=(user_id, spilt_words)).start()
            return
            

        case "gemini":
            limit_check = check_and_update_usage(user_id)
            match limit_check:
                case "操作間隔必須大於 1 分鐘":
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text=limit_check)
                    )
                    return
                case "這個月的使用次數已達上限30次":
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text=limit_check)
                    )
                    return
                
            line_bot_api.push_message(
                user_id,
                TextSendMessage(text=f"請稍後喔~ 小幫手還在打字中，{spilt_words[1]} 資訊好多，麻煩耐心等候 :D")
            )
            def process_gemini_postback(uid, words):
                text_buf = words[1]
                stock_area = classify_stock_symbol(text_buf)
                if stock_area=="TWstock":
                    search_text = "台股代號 " + text_buf + " 做什麼的"
                    search_results = google_search(search_text)
                    full_prompt = (
                        f"以下是關於 '{search_text}' 的最新搜尋結果：\n\n"
                        f"{search_results}\n\n"
                        f"請根據你自己的內部資訊以及搜尋的這些資訊介紹"
                    )
                    text_input = full_prompt + "台股代號 " + text_buf + "請先一句話告訴我這間公司適不適合繼續投資，並說明這間公司在做什麼、主要產品、核心技術與市場定位。/n我要放上Line回復的，幫我回復成適合在Line上閱讀的形式，也不要有下面這種文字出現/n這是一份為您整理好、適合在 Line 上直接轉傳的 IonQ 公司介紹，已避開所有星號（*）並使用易讀的符號與表情："
                elif stock_area=="USstock":
                    text_input = "請使用 Google 搜尋最新資料，介紹美股 " + text_buf + "請先一句話告訴我這間公司適不適合繼續投資，並說明這間公司在做什麼、主要產品、核心技術與市場定位。/n我要放上Line回復的，幫我回復成適合在Line上閱讀的形式，也不要有下面這種文字出現/n這是一份為您整理好、適合在 Line 上直接轉傳的 IonQ 公司介紹，已避開所有星號（*）並使用易讀的符號與表情："
                else:
                    return
                reply_text = None
                for model_name in models:
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                            contents="你是冷靜果決的股票分析師，現在在當LINE的回覆小助理，回覆時請考慮LINE視窗大小。\n" + text_input
                        )
                        reply_text = response.text.replace("*","")
                        break
                    except Exception as e:
                        continue
                if not reply_text:
                    reply_text = "目前所有模型都無法使用，請稍後再試或升級方案。"
                line_bot_api.push_message(to=uid, messages=[TextSendMessage(text=reply_text)])
                update_usage(uid)
            threading.Thread(target=process_gemini_postback, args=(user_id, spilt_words)).start()
            return


def auto_update_WebhookURL(url_add_Callback):
    # 自動更新 LINE Webhook URL
    webhook_update_url = "https://api.line.me/v2/bot/channel/webhook/endpoint"
    headers = {
        "Authorization": f"Bearer {line_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "endpoint": url_add_Callback
    }
    response = requests.put(webhook_update_url, headers=headers, json=payload)
    if response.status_code == 200:
        print("✅ LINE Webhook 已更新網址.")
    else:
        print("❌ LINE Webhook 更新失敗：", response.text)

def initial_upload_pic():
    # 初始化 Cloudinary
    cloudinary.config(
        cloud_name = cloudnary_cloud_name,
        api_key = cloudnary_api_key,
        api_secret = cloudnary_api_secret
    ) 
    # 上傳圖片
    response = cloudinary.uploader.upload("./pic/Dr_willy_said.png")
    # 取得公開網址
    return response['secure_url']


def classify_stock_symbol(symbol: str) -> str: 
    if symbol.isdigit(): return "TWstock" 
    elif symbol.isalpha(): return "USstock" 
    else: return "Unknow"



def plot_stock_chart(spilt_words):
    # Get current timing
    today = datetime.date.today()
    # total_days = 220
    total_days = 300
    date_110_days_ago = today - datetime.timedelta(days=total_days)
    tomorrow = today + datetime.timedelta(days=1)
    stock_area = classify_stock_symbol(spilt_words[1])

    if stock_area=="TWstock":
        data = yf.download(spilt_words[1]+".TW", start=date_110_days_ago, end=tomorrow)
        if data.empty: 
            data = yf.download(spilt_words[1] + ".TWO", start=date_110_days_ago, end=tomorrow)
    elif stock_area=="USstock":
        data = yf.download(spilt_words[1], start=date_110_days_ago, end=tomorrow)


    has_ma = len(spilt_words)==3 and spilt_words[2]=="ma"

    # 建立子圖，ma 模式多一個斜率子圖
    if has_ma:
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, gridspec_kw={'height_ratios': [3, 1, 1]}, sharex=True)
        ax_vol = ax3
    else:
        fig, (ax1, ax2) = plt.subplots(2, 1, gridspec_kw={'height_ratios': [3, 1]}, sharex=True)
        ax_vol = ax2

    # 繪製收盤價折線圖
    ma1 = data["Close"].iloc[20:].values.flatten()
    ax1.plot(ma1, color='blue', label='Closing price')

    if has_ma:
        # 計算均線資料
        data["MA5"] = data["Close"].rolling(window=5).mean()
        data["MA10"] = data["Close"].rolling(window=10).mean()
        data["MA20"] = data["Close"].rolling(window=20).mean()

        ma5 = data["MA5"].iloc[20:].values.flatten()
        ma10 = data["MA10"].iloc[20:].values.flatten()
        ma20 = data["MA20"].iloc[20:].values.flatten()

        # 計算布林通道
        data["STD20"] = data["Close"].rolling(window=20).std()
        data["Upper"] = data["MA20"] + (2 * data["STD20"])
        data["Lower"] = data["MA20"] - (2 * data["STD20"])
        Bollinger_Bands_Upper = data["Upper"].iloc[20:].values.flatten()
        Bollinger_Bands_Lower = data["Lower"].iloc[20:].values.flatten()

        # 畫均線圖&布林通道
        ax1.plot(ma20, color='m', label='MA20', linewidth=1, alpha=0.5)
        ax1.plot(ma5, color='c', label='MA5', linewidth=1, alpha=0.5)
        ax1.plot(Bollinger_Bands_Upper, label="Upper Band", color="black", linewidth=1, alpha=0.2)
        ax1.plot(ma10, color='y', label='MA10', linewidth=1, alpha=0.5)
        ax1.plot(Bollinger_Bands_Lower, label="Lower Band", color="black", linewidth=1, alpha=0.2)

        # 計算 MA5 斜率，畫在 ax2
        ma5_slope = np.concatenate([[0], np.diff(ma5)])
        colors_slope = ['red' if v > 0 else 'green' for v in ma5_slope]
        ax2.bar(range(len(ma5_slope)), ma5_slope, color=colors_slope, width=0.7, alpha=0.6, linewidth=0)
        ax2.axhline(0, color='gray', linewidth=0.5, linestyle='--')
        ax2.set_ylabel('MA5 Slope', color='gray', size='small')
        ax2.tick_params(axis='y', labelcolor='gray')

    ax1.tick_params(axis='y', labelcolor='blue')
    ax1.grid(True)
    ax1.set_xlim(-0.5, len(ma1)-0.5)
    ax1.legend(loc='upper right', bbox_to_anchor=(1.03, 1.2), ncol=3, frameon=False, fontsize="small")

    # 取得成交量
    raw_volume = data["Volume"].iloc[20:].values.flatten()

    # 找出Exponent
    max_vol = raw_volume.max()
    if max_vol > 0:
        exponent = int(math.log10(max_vol))
    else:
        exponent = 0

    # 成交量柱狀圖
    ax_vol.bar(list(range(len(raw_volume))), raw_volume, color='gray', width=0.7, linewidth=0)

    if has_ma:
        data["VMA5"] = data["Volume"].rolling(window=5).mean()
        data["VMA10"] = data["Volume"].rolling(window=10).mean()
        vma5 = data["VMA5"].iloc[20:].values.flatten()
        vma10 = data["VMA10"].iloc[20:].values.flatten()
        ax_vol.plot(vma5, color='c', linewidth=1, alpha=0.8, label='Vol MA5')
        ax_vol.plot(vma10, color='y', linewidth=1, alpha=0.8, label='Vol MA10')
        ax_vol.legend(loc='upper right', fontsize='small', frameon=False)

    ax_vol.set_ylabel(f'Volume ($10^{{{exponent}}}$)', color='gray', size="small")
    ax_vol.yaxis.get_offset_text().set_visible(False)
    ax_vol.tick_params(axis='y', labelcolor='gray')

    # 調整子圖間距和整體標題
    fig.suptitle(spilt_words[1]+' Chart of Stock Prices and Trading Volumes', fontsize=16, y=0.9)
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    fig.subplots_adjust(hspace=0.05)

    savefig_name = './pic/' + spilt_words[1] + '.png'
    plt.savefig(savefig_name, dpi=180) # 將圖存成 png 檔
    plt.close()

    reply_text = ""
    for model_name in models:
        try:
            # 呼叫模型，傳入文字 + 圖片
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    {"role": "user", "parts": [
                        {"text": "你是冷靜果決的股票分析師，現在在當LINE的回覆小助理，回覆時請考慮LINE視窗大小。\n請幫我分析這張股票走勢圖\n，淺灰色的是布林通道，下面是交易量，其餘你自己看圖標"},
                        {"inline_data": {
                            "mime_type": "image/png",
                            "data": open(savefig_name, "rb").read()
                        }}
                    ]}
                ]
            )
            reply_text = response.text.replace("*","")
            break  # 成功就跳出迴圈
        except Exception as e:
            continue  # 換下一個模型

    if reply_text=="":
        reply_text = "AI 助理額度已用完"

    # 初始化 Cloudinary
    cloudinary.config(
        cloud_name = cloudnary_cloud_name,
        api_key = cloudnary_api_key,
        api_secret = cloudnary_api_secret
    ) 

    # 上傳圖片
    response = cloudinary.uploader.upload(savefig_name)
    # 回傳公開網址和AI建議文字
    return response['secure_url'], reply_text
    

# 啟動 Flask Server
if __name__ == "__main__":
    port_value = 5000

    # 讀取使用限制表
    load_usage()

    conf.get_default().auth_token = ngrok_token
    # 啟動 ngrok 隧道，綁定到 Flask 的 port
    public_url = ngrok.connect(port_value)
    # print("ngrok 公開網址：", public_url)
    url_add_Callback = str(public_url).split('"')[1] + "/callback"
    # print(url_add_Callback)
    auto_update_WebhookURL(url_add_Callback)
    # 處理侯老闆箴言
    Dr_willy_said_url = initial_upload_pic()
    app.run(host='0.0.0.0', port=port_value)
