#!/usr/bin/env python3
import os
import subprocess

from flask import Flask, redirect, render_template_string, url_for

app = Flask(__name__)

# The path to the debug log used in auto-ingest.sh
LOG_PATH = "/tmp/write_blocker_debug.log"
MOUNT_POINT = "/mnt/forensic_disk"

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Forensic Write Blocker</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; padding: 20px; background: #f4f7f6; color: #333; }
        .container { background: white; padding: 30px; border-radius: 12px; display: inline-block; text-align: left; box-shadow: 0 10px 25px rgba(0,0,0,0.1); width: 90%; max-width: 700px; }
        h2 { color: #2c3e50; border-bottom: 3px solid #e74c3c; padding-bottom: 10px; margin-top: 0; }
        .status-box { background: #ebf5fb; border-left: 5px solid #3498db; padding: 15px; margin: 20px 0; font-weight: bold; }
        .btn { background: #e74c3c; color: white; padding: 18px 30px; border: none; border-radius: 8px; cursor: pointer; width: 100%; font-size: 1.2em; font-weight: bold; transition: background 0.3s; }
        .btn:hover { background: #c0392b; }
        .btn:active { transform: translateY(2px); }
        pre { background: #2c3e50; color: #bdc3c7; padding: 20px; border-radius: 6px; overflow-x: auto; font-family: 'Courier New', Courier, monospace; line-height: 1.4; border: 1px solid #1a252f; }
        .footer-links { margin-top: 20px; text-align: center; }
        a { color: #3498db; text-decoration: none; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Forensic Ingest Station</h2>

        <div class="status-box">
            Target: <code>/dev/sd*</code> | Mode: <strong>Hardware Write-Block (RO)</strong>
        </div>

        <form action="/eject" method="post">
            <button type="submit" class="btn" onclick="return confirm('Confirm unmount and loopback detachment?')">
                UNMOUNT & EJECT DRIVE
            </button>
        </form>

        <h3>Device Activity Log:</h3>
        <pre>{{ log_content }}</pre>

        <div class="footer-links">
            <a href="/">Refresh Page</a>
        </div>
    </div>
</body>
</html>
"""


@app.route("/")
def index():
    content = "No active ingest detected. System ready for device..."
    if os.path.exists(LOG_PATH):
        try:
            with open(LOG_PATH, "r") as f:
                content = f.read()
        except Exception as e:
            content = f"Error reading log: {str(e)}"

    return render_template_string(HTML_PAGE, log_content=content)


@app.route("/eject", methods=["POST"])
def eject():
    try:
        # 1. Standard forensic prep
        subprocess.run(["/usr/bin/sync"], check=True)

        # 2. Kill any userspace processes (just in case)
        subprocess.run(["/usr/bin/fuser", "-k", "-m", MOUNT_POINT], capture_output=True)

        # 3. Aggressive Unmount
        # -l (lazy) detaches the mount point from the file tree immediately
        # -f (force) tells the kernel to stop waiting for the device
        subprocess.run(
            ["/usr/bin/umount", "-l", "-f", MOUNT_POINT], capture_output=True
        )

        # 4. Target the specific Loop Device
        # We look for the loop device associated with the forensic mount point
        # Based on 'losetup -a', we need to ensure loop1 is actually closed.

        # This command finds which loop device is currently holding your mount point
        find_loop = subprocess.run(
            ["/usr/bin/findmnt", "-n", "-o", "SOURCE", MOUNT_POINT],
            capture_output=True,
            text=True,
        )
        loop_to_del = find_loop.stdout.strip().split("p")[
            0
        ]  # Handles 'loop1p1' -> 'loop1'

        if loop_to_del and "/dev/loop" in loop_to_del:
            # Tell the kernel to forcefully detach the loop device
            subprocess.run(["/usr/sbin/losetup", "-d", loop_to_del], check=True)
        else:
            # Fallback: shotgun approach if the specific loop wasn't found
            subprocess.run(["/usr/sbin/losetup", "-D"], check=True)

        # 5. UI Cleanup
        if os.path.exists(LOG_PATH):
            os.remove(LOG_PATH)

        return "<h2>Eject Finalized</h2><p>Filesystem detached and loopback cleared.</p><br><a href='/'>Back</a>"

    except subprocess.CalledProcessError as e:
        # If the loop is already gone, losetup -d might return 1. We handle that here.
        return f"<h2>Eject Note</h2><p>System cleaned up with some warnings.</p><pre>{e.stderr}</pre><br><a href='/'>Back</a>"


if __name__ == "__main__":
    # Running on port 80 requires sudo/root permissions
    app.run(host="0.0.0.0", port=80, debug=False)
