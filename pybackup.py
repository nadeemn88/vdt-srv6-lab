# Backup Cisco XR config (overwrite xrd-config files)

import paramiko
import subprocess
import sys
import json
import os

user = 'cisco'
secret = 'cisco123'
port = 22

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

# ---------- Colors ----------
class Color:
    RED = "\033[91m"
    YELLOW = "\033[93m"
    GREEN = "\033[92m"
    RESET = "\033[0m"


def color_text(text, color):
    return f"{color}{text}{Color.RESET}"


def confirm_device_list(max_attempts=5):
    for attempt in range(1, max_attempts + 1):
        answer = input(
            color_text("Have you updated the device list file? (y/n): ", Color.RED)
        ).strip().lower()

        if answer == "y":
            print(color_text("Proceeding with backup...\n", Color.GREEN))
            return True
        if answer == "n":
            print(color_text("Backup aborted by user.", Color.RED))
            return False

        if attempt < max_attempts:
            print(color_text(
                f"Invalid input. Please enter 'y' or 'n' "
                f"({max_attempts - attempt} attempts left).",
                Color.YELLOW
            ))
        else:
            print(color_text("Maximum attempts reached. Backup aborted.", Color.RED))

    return False


if not confirm_device_list():
    sys.exit(1)


def git_push(message):
    try:
        print("--- Starting Git Sync ---")
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", message], check=True)
        subprocess.run(["git", "push"], check=True)
        print("--- Git Sync Successful ---")
    except subprocess.CalledProcessError as e:
        print(f"Git error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during Git sync: {e}")


device_json_path = "/home/admin/MPLS_to_SRv6_stitching/MPLS_to_SRv6_stitching-master/device-list.json"
output_dir = "/home/admin/MPLS_to_SRv6_stitching/MPLS_to_SRv6_stitching-master/xrd-config"

# Ensure output directory exists
os.makedirs(output_dir, exist_ok=True)

# Load devices
try:
    with open(device_json_path, "r") as f:
        devices = json.load(f)
except FileNotFoundError:
    print(color_text(f"Device list JSON not found: {device_json_path}", Color.RED))
    sys.exit(1)
except json.JSONDecodeError as e:
    print(color_text(f"Invalid JSON in {device_json_path}: {e}", Color.RED))
    sys.exit(1)

if not isinstance(devices, list) or not devices:
    print(color_text(f"No devices found in {device_json_path}", Color.RED))
    sys.exit(1)

# Backup each device (overwrite files)
for dev in devices:
    if not isinstance(dev, dict):
        print(color_text(f"Skipping invalid entry (not an object): {dev}", Color.YELLOW))
        continue

    hostname = (dev.get("hostname") or "").strip()
    ipaddr = (dev.get("mngt_ip") or "").strip()

    if not ipaddr:
        print(color_text(f"Skipping entry missing mngt_ip: {dev}", Color.YELLOW))
        continue

    base_name = hostname if hostname else ipaddr
    out_file = os.path.join(output_dir, f"{base_name}.cfg")

    try:
        ssh.connect(hostname=ipaddr, username=user, password=secret, port=port, timeout=15)
        stdin, stdout, stderr = ssh.exec_command("show run")

        output = stdout.read().decode(errors="ignore")
        err = stderr.read().decode(errors="ignore").strip()

        if err:
            print(color_text(f"{base_name} ({ipaddr}) stderr: {err}", Color.YELLOW))

        # Write/overwrite
        with open(out_file, "w") as f:
            f.write(output)

        print(color_text(f"Updated: {out_file}  <--  {ipaddr}", Color.GREEN))

    except Exception as e:
        print(color_text(f"Failed: {base_name} ({ipaddr}): {e}", Color.RED))
    finally:
        try:
            ssh.close()
        except Exception:
            pass

# Git sync (message without timestamped dir)
git_push("Automated config refresh (overwrite xrd-config)")
