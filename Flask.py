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
matplotlib.rcParams["font.family"] = ["Arial Unicode MS"] # 設定全域中文字型
import matplotlib.pyplot as plt
import cloudinary
import cloudinary.uploader

import google.generativeai as genai
from serpapi import GoogleSearch

import json

app = Flask(__name__)

# 設定 Gemini API 金鑰
genai.configure(api_key=gemini_key)


# 替換成你自己的 Channel Access Token 和 Channel Secret
line_bot_api = LineBotApi(line_token)
handler = WebhookHandler(line_secret)

with open("quickTourButton.json", "r", encoding="utf-8") as f:
    quickTourButton = json.load(f)

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

        case "stock":
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"已收到查詢 {spilt_words[1]}，正在產生圖表，請稍候...")
            )
            #繪製均線圖並回傳網址
            image_url = plot_stock_chart(spilt_words)

            image_message = ImageSendMessage(
                original_content_url=image_url,
                preview_image_url=image_url
            )
            line_bot_api.push_message(user_id, image_message)
            plt.close()

        case "gemini":
            response_txt = True
            model = genai.GenerativeModel('gemini-2.5-flash')
            text_input = spilt_words[1]
            if any(keyword in text_input for keyword in ["附上來源"]):
                # print("偵測到需要搜尋的關鍵字，正在上網查詢...")
                search_results = google_search(text_input)
                
                # 建立一個包含搜尋結果的提示（Prompt）
                full_prompt = (
                    f"以下是一些關於 '{text_input}' 的最新搜尋結果：\n\n"
                    f"{search_results}\n\n"
                    f"請根據這些資訊，回答我的問題。"
                )
            else:
                full_prompt = text_input
            response = model.generate_content(full_prompt+"，字數請幫我濃縮到300字左右，謝謝~")

    
        case "gemini-l":
            response_txt = True
            model = genai.GenerativeModel('gemini-2.5-flash')
            text_input = spilt_words[1]
            if any(keyword in text_input for keyword in ["即時", "今年", "這半年", "附上來源"]):
                # print("偵測到需要搜尋的關鍵字，正在上網查詢...")
                search_results = google_search(text_input)
                
                # 建立一個包含搜尋結果的提示（Prompt）
                full_prompt = (
                    f"以下是一些關於 '{text_input}' 的最新搜尋結果：\n\n"
                    f"{search_results}\n\n"
                    f"請根據這些資訊，回答我的問題。"
                )
            else:
                full_prompt = text_input
            response = model.generate_content(full_prompt)
    
        case "gemini-pro":
            response_txt = True
            model = genai.GenerativeModel('gemini-2.5-pro')
            chat = model.start_chat(history=[])
            response = chat.send_message(spilt_words[1]+"，並附上來源，謝謝~")

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
            line_bot_api.push_message(user_id, image_message)
        case "stock":
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"已收到查詢 {spilt_words[1]}，正在產生圖表，請稍候...")
            )
            #繪製均線圖並回傳網址
            image_url = plot_stock_chart(spilt_words)

            image_message = ImageSendMessage(
                original_content_url=image_url,
                preview_image_url=image_url
            )
            line_bot_api.push_message(user_id, image_message)
            plt.close()


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
    response = cloudinary.uploader.upload("Dr_willy_said.png")
    # 取得公開網址
    return response['secure_url']

def plot_stock_chart(spilt_words):
    # Get current timing
    today = datetime.date.today()

    # plt.rcParams["font.family"]=["Microsoft JhengHei"]   # 中文字型
    # plt.title(spilt_words[1] + ' 近 31 日股價')


    date_80_days_ago = today - datetime.timedelta(days=110)
    data = yf.download(spilt_words[1]+".TW", start=date_80_days_ago, end=today)

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
    fig.suptitle(spilt_words[1]+'股票價格與成交量對照圖', fontsize=16)

    savefig_name = spilt_words[1] + '.png'
    plt.savefig(savefig_name) # 將圖存成 png 檔
    plt.close()

    # 初始化 Cloudinary
    cloudinary.config(
        cloud_name = cloudnary_cloud_name,
        api_key = cloudnary_api_key,
        api_secret = cloudnary_api_secret
    ) 

    # 上傳圖片
    response = cloudinary.uploader.upload(savefig_name)
    # 取得公開網址
    return response['secure_url']
    

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
