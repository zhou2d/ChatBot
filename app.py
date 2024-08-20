from flask import Flask, render_template, request, jsonify, session
from http import HTTPStatus
import markdown, os
from dashscope import Application  # 确保导入 Application 类

app = Flask(__name__)
app.secret_key = 'super_secret_key_92873abd8'  # 为了使用 session，需要 secret_key

@app.route("/")
def index():
    return render_template('chat.html')


@app.route("/get", methods=["GET", "POST"])
def get_Chat_response():
    app_id = os.getenv('DASHSCOPE_APP_ID')
    api_key = os.getenv('DASHSCOPE_API_KEY')
    
    if not app_id or not api_key:
        return jsonify({
            'error': 'Missing DASHSCOPE_APP_ID or DASHSCOPE_API_KEY'
        }), HTTPStatus.INTERNAL_SERVER_ERROR
    
    user_message = request.form["msg"]
    
    # 获取上下文（对话历史）
    conversation_history = session.get('conversation_history', [])

    # 将用户的新消息添加到上下文中
    conversation_history.append({"role": "user", "content": user_message})
    
    # 检查上下文长度，如果超过一定限制则进行摘要
    if len(conversation_history) > 10:  # 设定限制为10条对话
        conversation_summary = summarize_conversation(conversation_history)
        conversation_history = [{"role": "system", "content": conversation_summary}]
    
    # 将对话历史拼接为 prompt
    prompt = ""
    for message in conversation_history:
        prompt += f"{message['role']}: {message['content']}\n"
    
    # 调用 Dashscope API
    try:
        response = Application.call(
            app_id=app_id,
            prompt=prompt,  # 使用拼接后的对话历史作为 prompt
            api_key=api_key
        )

        # 检查响应状态
        if response.status_code != HTTPStatus.OK:
            return jsonify({
                'request_id': response.request_id,
                'error': response.message,
                'status_code': response.status_code
            }), response.status_code

        
        # 解析助手的回复并存储
        assistant_message = response.output.text
        conversation_history.append({"role": "assistant", "content": assistant_message})
        session['conversation_history'] = conversation_history  # 更新 session

        return markdown.markdown(assistant_message)
    
    except Exception as e:
        return jsonify({'error': str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR


def summarize_conversation(history):
    """使用摘要模型对对话历史进行摘要"""
    app_id = os.getenv('DASHSCOPE_SUMMARY_APP_ID')
    api_key = os.getenv('DASHSCOPE_SUMMARY_API_KEY')
    
    # 提取所有的对话文本
    conversation_text = "\n".join([msg["content"] for msg in history])

    # 调用摘要模型（伪代码，替换为实际的摘要模型调用）
    try:
        summary_response = Application.call(
            app_id=app_id,
            prompt=conversation_text,  # 使用对话文本作为 prompt
            api_key=api_key
        )

        if summary_response.status_code == HTTPStatus.OK:
            return summary_response.output.text
        else:
            return "对话摘要生成失败"

    except Exception as e:
        return "摘要模型调用失败: " + str(e)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081, debug=True)
