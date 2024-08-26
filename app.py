from flask import Flask, render_template, request, jsonify, session
from http import HTTPStatus
import markdown, os
from dashscope import Application  # 确保导入 Application 类
import threading
import logging



app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')  # 为了使用 session，需要 secret_key

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add a file handler to write logs to a file
file_handler = logging.FileHandler(r'd:/python_debug/公文小助手serverside.log')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger('').addHandler(file_handler)

# 用于存储正在处理的请求状态
processing_requests = {}

@app.route("/")
def index():
    return render_template('chat.html')

@app.route("/get", methods=["POST"])
def get_Chat_response():
    user_message = request.form["msg"]
    conversation_history = session.get('conversation_history', [])
    request_id = request.form.get("request_id")
    
    logging.info(f"Received request: ID={request_id}, Message={user_message}")
    
    # Store the request_id in the session
    session['current_request_id'] = request_id
    
    # Start a new thread to process the request
    thread = threading.Thread(target=process_message, args=(user_message, conversation_history, request_id))
    thread.start()
    
    return jsonify({"status": "processing", "message": "AI正在思考中，请稍候...", "request_id": request_id})

def process_message(user_message, conversation_history, request_id):
    app.logger.info(f"Processing message: ID={request_id}")
    conversation_history.append({"role": "user", "content": user_message})
    prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history])
    
    try:
        # Load environment variables
        app_id = os.getenv('DASHSCOPE_APP_ID')
        api_key = os.getenv('DASHSCOPE_API_KEY')

        # Ensure the variables are set
        if not app_id or not api_key:
            raise ValueError("DASHSCOPE_APP_ID and DASHSCOPE_API_KEY must be set in the environment variables")
        
        app.logger.info(f"Calling Bailian API: app_id={app_id}")
        response = Application.call(
            app_id=app_id,
            prompt=prompt,
            api_key=api_key
        )
        app.logger.info(f"API response received: ID={request_id}, Status={response.status_code}")
        
        assistant_message = response.output.text
        conversation_history.append({"role": "assistant", "content": assistant_message})
        
        processing_requests[request_id] = {
            "status": "complete",
            "message": markdown.markdown(assistant_message)
        }
        app.logger.info(f"Processing complete: ID={request_id}")
    except Exception as e:
        app.logger.error(f"Error processing message: ID={request_id}, Error={str(e)}")
        processing_requests[request_id] = {
            "status": "error",
            "message": "An error occurred while processing your request."
        }

@app.route("/status", methods=["GET"])
def get_status():
    request_id = request.args.get("request_id") or session.get('current_request_id')
    app.logger.info(f"Status check for request_id: {request_id}")  # Add this line
    logging.info(f"Status check for request: ID={request_id}")
    
    if request_id in processing_requests:
        result = processing_requests[request_id]
        logging.info(f"Status result: ID={request_id}, Status={result['status']}, Message={result['message'][:50]}...")
        
        if result['status'] == 'complete':
            # If the processing is complete, update the conversation history in the session
            conversation_history = session.get('conversation_history', [])
            conversation_history.append({"role": "assistant", "content": result['message']})
            session['conversation_history'] = conversation_history
            # Remove the processed request from the dictionary
            del processing_requests[request_id]
            logging.info(f"Request completed and removed from processing: ID={request_id}")
        return jsonify(result)
    else:
        logging.warning(f"Request not found: ID={request_id}")
        return jsonify({"status": "not_found", "message": "Request not found"})

def summarize_conversation(history):
    """使用Cloudflare Worker AI的llama-3.1-8b-instruct模型对对话历史进行摘要"""
    account_id = os.getenv('CLOUDFLARE_ACCOUNT_ID')
    api_token = os.getenv('CLOUDFLARE_API_TOKEN')
    
    if not account_id or not api_token:
        return "对话摘要生成失败: Missing Cloudflare API credentials"
    
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/meta/llama-3.1-8b-instruct"
    
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    
    # 构建摘要请求的消息
    system_message = "You are an AI assistant tasked with summarizing conversations. Please provide a concise summary of the following conversation."
    user_message = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
    
    data = {
        "stream": False,  # 我们不需要流式响应
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": f"Please summarize this conversation:\n\n{user_message}"}
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()  # 如果请求失败，这将引发异常
        
        result = response.json()
        
        if result.get('success'):
            summary = result['result']['response']
            return summary
        else:
            return "对话摘要生成失败: " + str(result.get('errors', ['Unknown error']))

    except requests.exceptions.RequestException as e:
        return f"摘要模型调用失败: {str(e)}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8082, debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true')