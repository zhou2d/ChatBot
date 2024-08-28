from flask import Flask, render_template, request, jsonify
from threading import Thread
import os
from mistune import markdown
from dashscope import Application
import time

app = Flask(__name__)

# Global variables
conversation_history = []
processing_requests = {}

MAX_INPUT_LENGTH = 5900  # Leave some buffer

@app.route("/")
def index():
    return render_template('chat.html')

@app.route("/get", methods=["POST"])
def get_bot_response():
    global conversation_history
    user_message = request.form["msg"]
    request_id = request.form["request_id"]
    
    print(f"Received request: ID={request_id}, Message={user_message}")
    
    conversation_history.append({"role": "user", "content": user_message})
    conversation_history = conversation_history[-10:]  # Keep only the last 10 messages
    
    processing_requests[request_id] = {"status": "processing", "message": "Processing request..."}
    
    thread = Thread(target=process_message, args=(user_message, conversation_history, request_id))
    thread.start()
    
    return jsonify({"status": "processing", "request_id": request_id})

def process_message(user_message, conversation_history, request_id):
    print(f"Processing message: ID={request_id}")
    
    prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history])
    
    # Truncate the prompt if it's too long
    if len(prompt) > MAX_INPUT_LENGTH:
        print(f"Prompt too long ({len(prompt)} chars), truncating...")
        prompt = summarize_conversation(conversation_history)
        #prompt = prompt[-MAX_INPUT_LENGTH:]
    
    try:
        # Load environment variables
        app_id = os.getenv('DASHSCOPE_APP_ID')
        api_key = os.getenv('DASHSCOPE_API_KEY')

        # Ensure the variables are set
        if not app_id or not api_key:
            raise ValueError("DASHSCOPE_APP_ID and DASHSCOPE_API_KEY must be set in the environment variables")
        
        print(f"Calling Bailian API: app_id={app_id}, prompt={prompt}")
        response = Application.call(
            app_id=app_id,
            prompt=prompt,
            api_key=api_key
        )
        print(f"API response received: ID={request_id}, Status={response.status_code if response else 'No response'}")
        
        if response and response.status_code == 200 and hasattr(response.output, 'text'):
            assistant_message = response.output.text
        else:
            print(f"Invalid response from API: ID={request_id}, Response={response}")
            assistant_message = "抱歉，我现在无法回答。请稍后再试。"

        # Update the conversation history in the global variable
        conversation_history.append({"role": "assistant", "content": assistant_message})
        
        processing_requests[request_id] = {
            "status": "complete",
            "message": markdown(assistant_message)
        }
        print(f"Processing complete: ID={request_id}")
    except Exception as e:
        print(f"Error processing message: ID={request_id}, Error={str(e)}")
        processing_requests[request_id] = {
            "status": "error",
            "message": "抱歉，处理您的请求时出现错误。请稍后再试。"
        }

@app.route("/status", methods=["GET"])
def get_status():
    request_id = request.args.get("request_id")
    print(f"Status check for request_id: {request_id}")
    
    if request_id in processing_requests:
        result = processing_requests[request_id]
        print(f"Status result: ID={request_id}, Status={result['status']}, Message={result['message'][:50]}...")
        
        if result['status'] == 'complete':
            # If the processing is complete, update the conversation history
            conversation_history = []
            conversation_history.append({"role": "assistant", "content": result['message']})
            # Remove the processed request from the dictionary
            del processing_requests[request_id]
            print(f"Request completed and removed from processing: ID={request_id}")
        return jsonify(result)
    else:
        print(f"Request not found: ID={request_id}")
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
    system_message = """You are an AI assistant responsible for summarizing conversations. 
        Please create a concise summary of the conversation below, ensuring that the last two messages 
        are kept EXACTLY as they are. Summarize the earlier messages, excluding any that are not relevant 
        to the final five messages. The summary should not exceed 5000 characters.

        The conversation to be summarized is as follows:: 
        """
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