from flask import Flask, request
import time
import requests
from urllib.parse import quote

app = Flask(__name__)

cookie=''                       # 115 网盘的 cookie
uid = ''                        # 自己的 uid
wp_path_id = ''                 # 离线路径的 id
sign_refresh_interval = 1200    # 设置sign的刷新间隔（假设为20分钟）
bot_token = ''                  # Telegram bot 的 token
PER_PAGE = 10                   # 每页显示的任务数量  


res = requests.session()

h = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_16_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.61 Safari/537.36 115Browser/24.1.0.13',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
    'Cookie': cookie,
}




# 获取签名
last_sign_time = 0  # 上次获取 sign 的时间



# 定义一个全局变量来存储sign  
current_sign = ''  
  
def getsign():  
    global last_sign_time, current_sign  
    current_time = time.time()  
      
    # 如果距离上次获取sign的时间超过刷新间隔，或者last_sign_time为0（第一次获取sign），则获取新的sign  
    if current_time - last_sign_time >= sign_refresh_interval or last_sign_time == 0:  
        ts = str(int(current_time * 1000))  
        url = 'https://115.com/?ct=offline&ac=space&_=' + ts  
        current_sign = res.get(url, headers=h).json()['sign']  
        last_sign_time = current_time  # 更新上次获取sign的时间  
    return current_sign  


# 列出离线任务
def lixianlist():
    sign = getsign()  # 更新sign
    ts = str(int(time.time()))
    url = 'https://115.com/web/lixian/?ct=lixian&ac=task_lists'
    d = 'page=1&page_row=100&uid=' + uid + '&sign=' + sign + '&time=' + ts
    s = res.post(url, d, headers=h).json()['tasks']
    try:
        dic = {}
        for i in s:
            name = i['name']
            has = i['info_hash']
            dic.update({name: has})
        return dic
    except:
        return {}

# 删除离线任务
def deltask(hash):
    sign = getsign()  # 更新sign
    ts = str(int(time.time()))
    d = 'hash%5B0%5D=' + hash + '&uid=' + uid + '&sign=' + sign + '&time=' + ts
    url = 'https://115.com/web/lixian/?ct=lixian&ac=task_del'
    s = res.post(url, d, headers=h).json()
    return s

# 添加离线任务
def lixian(path):
    sign = getsign()  # 更新sign
    ts = str(int(time.time()))
    url = 'https://115.com/web/lixian/?ct=lixian&ac=add_task_url'
    mag = quote(path)
    d = 'url=' + mag + '&savepath=&wp_path_id=' + wp_path_id + '&uid=' + uid + '&sign=' + sign + '&time=' + ts
    s = res.post(url, d, headers=h).json()
    return s

# 接收Webhook请求并处理


def send_message(chat_id, text, reply_markup=None):
    url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    if reply_markup==None:
        data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}
    else:
        data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown', 'reply_markup': reply_markup}
    response = requests.post(url, json=data)
    return response


last_tasks=None


@app.route('/webhook', methods=['POST'])
def webhook():
    global last_tasks
    data = request.json
    if 'callback_query' in data:
        query_data = data['callback_query']['data']
        chat_id = data['callback_query']['message']['chat']['id']
        message_id = data['callback_query']['message']['message_id']  # 获取消息ID
        page = int(query_data.split('_')[1])
        tasks = lixianlist()
        tasks_items = list(tasks.items())
        total_pages = len(tasks_items) // PER_PAGE + (1 if len(tasks_items) % PER_PAGE != 0 else 0)  # 计算总页数
        task_list = "\n\n".join([f"*{name[:70]}*:\n`{hash}`" for name, hash in tasks_items[page*PER_PAGE:(page+1)*PER_PAGE]])
        reply_markup = {"inline_keyboard": [[]]}
        if page > 0:  # 如果不是第一页，显示"Previous page"按钮
            reply_markup["inline_keyboard"][0].append({"text": "Previous page", "callback_data": f"list_{page-1}"})
        if page < total_pages - 1:  # 如果不是最后一页，显示"Next page"按钮
            reply_markup["inline_keyboard"][0].append({"text": "Next page", "callback_data": f"list_{page+1}"})

        url = f'https://api.telegram.org/bot{bot_token}/editMessageText'  # 使用editMessageText方法
        data = {'chat_id': chat_id, 'message_id': message_id, 'text': f"Here are your tasks:\n{task_list}", 'parse_mode': 'Markdown', 'reply_markup': reply_markup}
        response = requests.post(url, json=data)
        return '', 200
    else:
        message_text = data['message']['text']
        chat_id = data['message']['chat']['id']  # 获取chat id
        if message_text == '/list':  
            tasks = lixianlist()  
            last_tasks = tasks
            if tasks:  
                tasks_items = list(tasks.items())  
                total_pages = len(tasks_items) // PER_PAGE + (1 if len(tasks_items) % PER_PAGE != 0 else 0)  # 计算总页数  
                task_list = "\n\n".join([f"*{name[:70]}*:\n`{hash}`" for name, hash in tasks_items[:PER_PAGE]])  
                reply_markup = {"inline_keyboard": [[]]}  
                if total_pages > 1:  # 如果总页数大于1，显示"Next page"按钮  
                    reply_markup["inline_keyboard"][0].append({"text": "Next page", "callback_data": f"list_1"})  
                send_message(chat_id, f"Here are your tasks:\n{task_list}", reply_markup)  # 将任务列表发送给telegram bot  
            else:  
                send_message(chat_id, "You have no tasks.")  # 如果任务列表为空，发送一条消息通知用户  
          
            return '', 200  
        
        elif message_text.startswith('/add'):  
            url = message_text.split(' ')[1]  
            result = lixian(url) 
            if result['state']:  
                send_message(chat_id, f"Task has been added successfully. Info hash: {result['info_hash']}")  # 将结果发送给telegram bot  
            else:  
                send_message(chat_id, f"Failed to add task. Error: {result['errtype']}")  # 如果添加任务失败，发送错误消息给telegram bot  
            return '', 200  

        elif message_text.startswith('/delete'):
            hash = message_text.split(' ')[1]
            result = deltask(hash)
            if result['state']:
                send_message(chat_id, f"Task with hash '{hash}' has been deleted successfully.")  # 将结果发送给telegram bot
            else:
                send_message(chat_id, f"Failed to delete task. Error: {result['errtype']}")  # 如果删除任务失败，发送错误消息给telegram bot
            return '', 200

        else:
            send_message(chat_id, "Invalid command")  # 如果命令无效，发送错误消息给telegram bot
            return '', 200



if __name__ == '__main__':
    app.run(debug=True)