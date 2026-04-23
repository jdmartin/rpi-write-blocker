#!/usr/bin/env python3
import os
import subprocess
from flask import Flask, render_template_string

app = Flask(__name__)

# --- Configurations ---
LOG_PATH = "/tmp/write_blocker_debug.log"
MOUNT_POINT = "/mnt/forensic_disk"
INFO_FILE = "/tmp/.current_mount.info"

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Thoth | Forensic Write Blocker</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; padding: 20px; background: #f4f7f6; color: #333; }
        .container { background: white; padding: 30px; border-radius: 12px; display: inline-block; text-align: left; box-shadow: 0 10px 25px rgba(0,0,0,0.1); width: 90%; max-width: 700px; }
        h2 { color: #2c3e50; border-bottom: 3px solid #e74c3c; padding-bottom: 10px; margin-top: 0; }
        .status-box { background: #ebf5fb; border-left: 5px solid #3498db; padding: 15px; margin: 20px 0; font-weight: bold; line-height: 1.6; }
        .btn { background: #e74c3c; color: white; padding: 18px 30px; border: none; border-radius: 8px; cursor: pointer; width: 100%; font-size: 1.2em; font-weight: bold; transition: background 0.3s; }
        .btn:hover { background: #c0392b; }
        .btn:active { transform: translateY(2px); }
        .btn:disabled { background: #95a5a6; cursor: not-allowed; }
        pre { background: #2c3e50; color: #bdc3c7; padding: 20px; border-radius: 6px; overflow-x: auto; font-family: 'Courier New', Courier, monospace; line-height: 1.4; border: 1px solid #1a252f; }
        .footer-links { margin-top: 20px; text-align: center; }
        a { color: #3498db; text-decoration: none; }
        .warning { color: #e67e22; font-size: 0.9em; margin-top: 5px; display: block; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Forensic Ingest Station</h2>

        <div class="status-box">
            {% if details.phys != "None" %}
                <span style="color: #27ae60;">● ACTIVE INGEST DETECTED</span><br>
                Physical Source: <code>{{ details.phys }}</code><br>
                Virtual Bridge: <code>{{ details.loop }}</code>
                {% if not details.is_safe %}
                    <span class="warning">⚠️ SYSTEM DEVICE DETECTED - EJECT DISABLED</span>
                {% endif %}
            {% else %}
                <span style="color: #7f8c8d;">○ STANDBY</span><br>
                Waiting for forensic media...
            {% endif %}
        </div>

        <form action="/eject" method="post">
            <button type="submit" class="btn" 
                {% if details.phys == "None" or not details.is_safe %} disabled {% endif %}
                onclick="return confirm('Confirm unmount of {{ details.phys }}?')">
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
    content = "System ready. Connect a device to begin ingest."
    mount_details = {"phys": "None", "loop": "None", "is_safe": True}
    
    # 1. Read the activity log
    if os.path.exists(LOG_PATH):
        try:
            with open(LOG_PATH, "r") as f:
                content = f.read()
        except Exception as e:
            content = f"Error reading log: {str(e)}"

    # 2. Parse active mount information
    if os.path.exists(INFO_FILE):
        try:
            with open(INFO_FILE, "r") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        if k == "PHYS_DEV": 
                            mount_details["phys"] = v
                            # Protection: Don't allow ejecting the internal SD card
                            if "mmcblk0" in v:
                                mount_details["is_safe"] = False
                        if k == "LOOP_DEV": 
                            mount_details["loop"] = v
        except Exception:
            pass

    return render_template_string(HTML_PAGE, log_content=content, details=mount_details)

@app.route("/eject", methods=["POST"])
def eject():
    mount_info = {}
    
    # Read session data to know exactly what to kill
    if os.path.exists(INFO_FILE):
        try:
            with open(INFO_FILE, "r") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        mount_info[k] = v
        except Exception as e:
            print(f"Metadata read error: {e}")

    # Safety: Refuse to eject if it's the system SD card
    if "mmcblk0" in mount_info.get("PHYS_DEV", ""):
        return "<h2>Operation Blocked</h2><p>Cannot eject system storage.</p><br><a href='/'>Back</a>"

    try:
        # 1. Forensic Prep
        subprocess.run(["/usr/bin/sync"], check=True)

        # 2. Kill processes accessing the mount
        subprocess.run(["/usr/bin/fuser", "-k", "-m", MOUNT_POINT], capture_output=True)

        # 3. Unmount
        subprocess.run(["/usr/bin/umount", "-l", "-f", MOUNT_POINT], capture_output=True)

        # 4. Detach Loop Device
        loop_to_del = mount_info.get("LOOP_DEV")
        if not loop_to_del:
            # Fallback check
            find_loop = subprocess.run(["/usr/bin/findmnt", "-n", "-o", "SOURCE", MOUNT_POINT], capture_output=True, text=True)
            loop_to_del = find_loop.stdout.strip().split("p")[0]

        if loop_to_del and "/dev/loop" in loop_to_del:
            subprocess.run(["/usr/sbin/losetup", "-d", loop_to_del], check=True)
        else:
            subprocess.run(["/usr/sbin/losetup", "-D"], check=True)

        # 5. Physical Disconnect
        phys_dev = mount_info.get("PHYS_DEV")
        if phys_dev:
            subprocess.run(["/usr/bin/udisksctl", "power-off", "-b", phys_dev], capture_output=True)

        # 6. Cleanup session files
        if os.path.exists(LOG_PATH): os.remove(LOG_PATH)
        if os.path.exists(INFO_FILE): os.remove(INFO_FILE)

        return "<h2>Eject Finalized</h2><p>Hardware powered down safely.</p><br><a href='/'>Back</a>"

    except Exception as e:
        return f"<h2>Eject Warning</h2><p>Cleanup finished with errors: {str(e)}</p><br><a href='/'>Back</a>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=False)
