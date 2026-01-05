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
# matplotlib.rcParams["font.family"] = ["Noto Sans CJK TC"] # 設定全域中文字型
import matplotlib.pyplot as plt
import cloudinary
import cloudinary.uploader

from google import genai
from serpapi import GoogleSearch

import json

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

    return 'OK'


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
        
        case "個股資訊":
            message = FlexSendMessage( alt_text="個股資訊", contents=stock_info ) 
            line_bot_api.reply_message(event.reply_token, message)

        case "stock":
            # line_bot_api.reply_message(
            #     event.reply_token,
            #     TextSendMessage(text=f"已收到查詢 {spilt_words[1]}，正在產生圖表，請稍候...")
            # )
            #繪製均線圖並回傳網址
            image_url, reply_text = plot_stock_chart(spilt_words)

            image_message = ImageSendMessage(
                original_content_url=image_url,
                preview_image_url=image_url
            )
            text_message = TextSendMessage(text=reply_text)

            line_bot_api.reply_message(
                event.reply_token,
                [image_message, text_message]
            )
            # line_bot_api.push_message(user_id, image_message)
            plt.close()
    

        case "gemini":
            response_txt = True
            text_input = spilt_words[1]
            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=text_input
            )
            response = response.text.replace("*","")

    if response_txt :
        reply = TextSendMessage(response.text)
        line_bot_api.reply_message(event.reply_token, reply)
        response_txt = False


# 處理加入群組事件
@handler.add(JoinEvent)
def handle_join(event):
    group_id = event.source.group_id
    # print("加入的群組 ID：", group_id)
    # 發送歡迎訊息
    line_bot_api.push_message(group_id, TextSendMessage(text='王老闆、侯老闆還有陳老闆大家好！！！'))


@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    text_0 = event.postback.data # 例如 "stock=2330"
    # text_0 = event.message.text
    spilt_words = text_0.split(" ")
    
    line_bot_api = LineBotApi(line_token)

    match spilt_words[0]:
        case "Dr_willy_said":
            image_message = ImageSendMessage(
                original_content_url=Dr_willy_said_url,
                preview_image_url=Dr_willy_said_url
            )
            # line_bot_api.push_message(user_id, image_message)
            line_bot_api.reply_message(
                event.reply_token,
                image_message
            )

        case "stock":
            # line_bot_api.reply_message(
            #     event.reply_token,
            #     TextSendMessage(text=f"已收到查詢 {spilt_words[1]}，正在產生圖表，請稍候...")
            # )
            #繪製均線圖並回傳網址與AI建議
            image_url, reply_text = plot_stock_chart(spilt_words)

            image_message = ImageSendMessage(
                original_content_url=image_url,
                preview_image_url=image_url
            )

            text_message = TextSendMessage(text=reply_text)
            # line_bot_api.push_message(user_id, image_message)
            line_bot_api.reply_message(
                event.reply_token,
                [image_message, text_message]
            )
            plt.close()

        case "gemini":
            # line_bot_api.reply_message(
            #     event.reply_token,
            #     TextSendMessage(text=f"請稍後喔~ 小幫手還在打字中，{spilt_words[1]} 資訊好多，麻煩耐心等候 :D")
            # )
            text_buf = spilt_words[1]
            stock_area = classify_stock_symbol(spilt_words[1])

            
            if stock_area=="TWstock":
                search_text = "台股代號 " + text_buf + " 做什麼的"
                search_results = google_search(search_text)
                # 建立一個包含搜尋結果的提示（Prompt）
                full_prompt = (
                    f"以下是關於 '{search_text}' 的最新搜尋結果：\n\n"
                    f"{search_results}\n\n"
                    f"請根據你自己的內部資訊以及搜尋的這些資訊介紹"
                )

            if stock_area=="TWstock":
                text_input =  full_prompt + "台股代號 " + text_buf + "請先一句話告訴我這間公司適不適合繼續投資，並說明這間公司在做什麼、主要產品、核心技術與市場定位。/n我要放上Line回復的，幫我回復成適合在Line上閱讀的形式，也不要有下面這種文字出現/n這是一份為您整理好、適合在 Line 上直接轉傳的 IonQ 公司介紹，已避開所有星號（*）並使用易讀的符號與表情："
            elif stock_area=="USstock":
                text_input =  "請使用 Google 搜尋最新資料，介紹美股 " + text_buf + "請先一句話告訴我這間公司適不適合繼續投資，並說明這間公司在做什麼、主要產品、核心技術與市場定位。/n我要放上Line回復的，幫我回復成適合在Line上閱讀的形式，也不要有下面這種文字出現/n這是一份為您整理好、適合在 Line 上直接轉傳的 IonQ 公司介紹，已避開所有星號（*）並使用易讀的符號與表情："

            
            reply_text = None
            for model_name in models:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents="你是冷靜果決的股票分析師，現在在當LINE的回覆小助理，回覆時請考慮LINE視窗大小。\n" + text_input
                    )
                    reply_text = response.text.replace("*","")
                    break  # 成功就跳出迴圈
                except Exception as e:
                    continue  # 換下一個模型
            if not reply_text:
                reply_text = "目前所有模型都無法使用，請稍後再試或升級方案。"

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=reply_text)
            )
            # line_bot_api.push_message( to=user_id,messages=[TextSendMessage(text=reply_text)] )


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

    date_110_days_ago = today - datetime.timedelta(days=110)
    tomorrow = today + datetime.timedelta(days=1)
    stock_area = classify_stock_symbol(spilt_words[1])

    if stock_area=="TWstock":
        data = yf.download(spilt_words[1]+".TW", start=date_110_days_ago, end=tomorrow)
    elif stock_area=="USstock":
        data = yf.download(spilt_words[1], start=date_110_days_ago, end=tomorrow)

    # 建立兩個子圖，共用X軸
    fig, (ax1, ax2) = plt.subplots(2, 1, gridspec_kw={'height_ratios': [3, 1]}, sharex=True)        

    # 繪製收盤價折線圖
    ma1 = data["Close"].iloc[20:].values.flatten()
    ax1.plot(ma1, color='blue', label='Closing price')

    if len(spilt_words)==3 and spilt_words[2]=="ma":       
        # 計算均線資料
        data["MA5"] = data["Close"].rolling(window=5).mean()
        data["MA10"] = data["Close"].rolling(window=10).mean()
        data["MA20"] = data["Close"].rolling(window=20).mean()

        # 三條移動平均線陣列
        ma5 = data["MA5"].iloc[20:].values.flatten()
        ma10 = data["MA10"].iloc[20:].values.flatten()
        ma20 = data["MA20"].iloc[20:].values.flatten()

        # 計算布林通道 
        data["STD20"] = data["Close"].rolling(window=20).std() 
        data["Upper"] = data["MA20"] + (2 * data["STD20"]) 
        data["Lower"] = data["MA20"] - (2 * data["STD20"])
        Bollinger_Bands_Upper = data["Upper"].iloc[20:].values.flatten()
        Bollinger_Bands_Lower = data["Lower"].iloc[20:].values.flatten()

        # 畫均線圖&布林通道 為了排列所以打亂順序        
        ax1.plot(ma20, color='m', label='MA20' ,linewidth = 1, alpha=0.5) # 20日線
        ax1.plot(ma5, color='c', label='MA5' ,linewidth = 1, alpha=0.5) # 5日線
        ax1.plot(Bollinger_Bands_Upper, label="Upper Band", color="black",linewidth = 1, alpha=0.2) # Upper
        ax1.plot(ma10, color='y', label='MA10' ,linewidth = 1, alpha=0.5) # 10日線
        ax1.plot(Bollinger_Bands_Lower, label="Lower Band", color="black",linewidth = 1, alpha=0.2) # Lower


    # ax1.set_ylabel('收盤價 (Close)', color='blue')
    ax1.tick_params(axis='y', labelcolor='blue')
    ax1.grid(True)
    ax1.set_xlim(0, len(ma1)-1)
    # 把圖例放在圖外上方 
    ax1.legend(loc='upper right', bbox_to_anchor=(1.03, 1.2), ncol=3, frameon=False,fontsize="small")

    # 繪製成交量柱狀圖
    ax2.bar(list(range(len(data["Volume"].iloc[20:].values.flatten()))), data["Volume"].iloc[20:].values.flatten(), color='gray',width=0.7)
    ax2.set_ylabel('Volume', color='gray')
    ax2.tick_params(axis='y', labelcolor='gray')
    ax2.get_xaxis().set_visible(False)

    # 調整子圖間距和整體標題
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    fig.suptitle(spilt_words[1]+' Chart of Stock Prices and Trading Volumes', fontsize=16)

    savefig_name = './pic/' + spilt_words[1] + '.png'
    plt.savefig(savefig_name) # 將圖存成 png 檔
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
