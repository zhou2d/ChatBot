from flask import Flask, render_template, request, jsonify
from http import HTTPStatus
import markdown, os
from dashscope import Application


app = Flask(__name__)

@app.route("/")
def index():
    return render_template('chat.html')


@app.route("/get", methods=["GET", "POST"])
def get_Chat_response():
    print('1')
    app_id = os.getenv('DASHSCOPE_APP_ID')
    api_key = os.getenv('DASHSCOPE_API_KEY')
    print('2')
    print(app_id)
    print('3')
    print(request.form["msg"])
    print('4')
    print(api_key)
    if not app_id or not api_key:
        return jsonify({
            'error':
            'Missing DASHSCOPE_APP_ID or DASHSCOPE_API_KEY'
        })
            
    response = Application.call(app_id=app_id,
                                prompt=request.form["msg"],
                                api_key=api_key,
                                )

    print (markdown.markdown(response.output.text))                               

    if response.status_code != HTTPStatus.OK:
        return 'request_id=%s, code=%s, message=%s\n' % (response.request_id, response.status_code, response.message)
    else:
        return markdown.markdown(response.output.text)


if __name__ == '__main__':
    app.run()
