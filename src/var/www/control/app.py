#!/usr/bin/env python3
import os
import subprocess
from flask import Flask, redirect, render_template_string, url_for

app = Flask(__name__)

# Paths used by auto-ingest.sh and Thoth appliance
LOG_PATH = "/tmp/write_blocker_debug.log"
MOUNT_POINT = "/mnt/forensic_disk"
INFO_FILE = "/tmp/.current_mount.info"

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
    mount_info = {}
    
    # Try to load session data from the info file created by auto-ingest.sh
    if os.path.exists(INFO_FILE):
        try:
            with open(INFO_FILE, "r") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        mount_info[k] = v
        except Exception as e:
            print(f"Warning: Could not parse {INFO_FILE}: {e}")

    try:
        # 1. Standard forensic prep
        subprocess.run(["/usr/bin/sync"], check=True)

        # 2. Kill any userspace processes accessing the mount point
        subprocess.run(["/usr/bin/fuser", "-k", "-m", MOUNT_POINT], capture_output=True)

        # 3. Aggressive Unmount
        # -l (lazy) detaches the mount point immediately
        # -f (force) for network/stuck filesystems
        subprocess.run(["/usr/bin/umount", "-l", "-f", MOUNT_POINT], capture_output=True)

        # 4. Target the specific Loop Device
        loop_to_del = mount_info.get("LOOP_DEV")
        
        # Fallback: Find loop via findmnt if info file was missing
        if not loop_to_del:
            find_loop = subprocess.run(
                ["/usr/bin/findmnt", "-n", "-o", "SOURCE", MOUNT_POINT],
                capture_output=True, text=True
            )
            raw_source = find_loop.stdout.strip()
            if "loop" in raw_source:
                loop_to_del = raw_source.split("p")[0] # 'loop1p1' -> 'loop1'

        if loop_to_del and "/dev/loop" in loop_to_del:
            subprocess.run(["/usr/sbin/losetup", "-d", loop_to_del], check=True)
        else:
            # Final fallback: Shotgun approach
            subprocess.run(["/usr/sbin/losetup", "-D"], check=True)

        # 5. Physical Eject (Power Off)
        # This prevents udev from re-detecting the drive until physically swapped
        phys_dev = mount_info.get("PHYS_DEV")
        if phys_dev:
            subprocess.run(["/usr/bin/udisksctl", "power-off", "-b", phys_dev], capture_output=True)

        # 6. Cleanup
        if os.path.exists(LOG_PATH):
            os.remove(LOG_PATH)
        if os.path.exists(INFO_FILE):
            os.remove(INFO_FILE)

        return "<h2>Eject Finalized</h2><p>Filesystem detached, loopback cleared, and drive powered down.</p><br><a href='/'>Back</a>"

    except subprocess.CalledProcessError as e:
        return f"<h2>Eject Note</h2><p>System cleaned up with some warnings.</p><pre>{e.stderr}</pre><br><a href='/'>Back</a>"

if __name__ == "__main__":
    # Note: Running on port 80 requires sudo/root permissions
    app.run(host="0.0.0.0", port=80, debug=False)
