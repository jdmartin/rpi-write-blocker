from flask import Flask, render_template_string
import subprocess
import os

app = Flask(__name__)

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Write Blocker Control Panel</title>
    <style>
        body { font-family: sans-serif; text-align: center; padding: 40px; background: #f0f2f5; }
        .container { background: white; padding: 30px; border-radius: 12px; display: inline-block; text-align: left; box-shadow: 0 4px 10px rgba(0,0,0,0.1); width: 80%; max-width: 600px; }
        .btn { background: #e74c3c; color: white; padding: 15px 30px; border: none; border-radius: 8px; cursor: pointer; width: 100%; font-size: 1.1em; }
        pre { background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 5px; overflow-x: auto; font-size: 0.85em; }
        h2 { border-bottom: 2px solid #eee; padding-bottom: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Forensic Station</h2>
        <form action="/eject" method="post">
            <button type="submit" class="btn">UNMOUNT & EJECT DRIVE</button>
        </form>

        <h3>Last Ingest Log:</h3>
        <pre>{{ log_content }}</pre>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    # If you added a log line to your auto-ingest script, we display it here
    log_path = "/tmp/write_blocker_debug.log"
    content = "No logs found. Plug in a device to start."
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            content = f.read()
    return render_template_string(HTML_PAGE, log_content=content)

@app.route('/eject', methods=['POST'])
def eject():
    subprocess.run(["/usr/bin/umount", "-l", "/mnt/forensic_disk"])
    subprocess.run(["/usr/sbin/losetup", "-D"])
    # Clear the log on eject so the next person starts fresh
    if os.path.exists("/tmp/write_blocker_debug.log"):
        os.remove("/tmp/write_blocker_debug.log")
    return "<h2>Drive Ejected.</h2><p>Safe to swap hardware.</p><br><a href='/'>Back</a>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
