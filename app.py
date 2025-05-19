from flask import Flask, request
import threading
import subprocess

app = Flask(__name__)

# Background task runner
def run_background_script():
    subprocess.Popen(['python', 'bot.py'])

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        threading.Thread(target=run_background_script).start()
        return '<p>Background script started! <a href="/">Go back</a></p>'
    
    return '''
        <form method="post">
            <button type="submit">Run Background Script</button>
        </form>
    '''

if __name__ == '__main__':
    app.run(debug=True)
