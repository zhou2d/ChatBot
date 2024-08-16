from flask import Flask, render_template, request
from http import HTTPStatus
import markdown
from dashscope import Application


app = Flask(__name__)

@app.route("/")
def index():
    return render_template('chat.html')


@app.route("/get", methods=["GET", "POST"])
def get_Chat_response():
    response = Application.call(app_id='9193d7ac66de4b79bd7f5d78db494f95',
                                prompt=request.form["msg"],
                                api_key='sk-ca86b34dfd6242a3abd028a47e08dc2b',
                                )

    #print (markdown.markdown(response.output.text))                               

    if response.status_code != HTTPStatus.OK:
        return 'request_id=%s, code=%s, message=%s\n' % (response.request_id, response.status_code, response.message)
    else:
        return markdown.markdown(response.output.text)


if __name__ == '__main__':
    app.run()
