import os
import json
import base64
import urllib.request
import urllib.error

# Repo details
OWNER = "hacrav00"
REPO = "picampro"
BRANCH = "main"

FILES_TO_UPLOAD = [
    "core/camera_manager.py",
    "gui/control_panel.py",
    "gui/app_window.py",
    "gui/preview_canvas.py",
    "assets/icon.png",
    "upload_to_github.py",
]

def get_sha(path, token):
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{path}?ref={BRANCH}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            return data.get("sha")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None  # File is new, no SHA
        print(f"Error checking SHA for {path}: {e.read().decode()}")
        raise e

def upload_file(path, token):
    if not os.path.exists(path):
        print(f"Skipping {path} (local file not found)")
        return

    # Read and encode file
    with open(path, "rb") as f:
        content_bytes = f.read()
    content_b64 = base64.b64encode(content_bytes).decode("utf-8")

    sha = get_sha(path, token)

    url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{path}"
    payload = {
        "message": "Fix resolution parsing, add autofocus controls, and optimize preview FPS",
        "content": content_b64,
        "branch": BRANCH,
    }
    if sha:
        payload["sha"] = sha

    req = urllib.request.Request(url, method="PUT")
    req.add_header("Authorization", f"token {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/vnd.github.v3+json")

    data = json.dumps(payload).encode("utf-8")

    try:
        with urllib.request.urlopen(req, data=data) as response:
            print(f"Successfully uploaded: {path}")
    except urllib.error.HTTPError as e:
        print(f"Failed to upload {path}: {e.code} - {e.read().decode()}")

def main():
    print("==========================================================")
    print("      PiCamPro GitHub Direct Uploader (No Git Required)   ")
    print("==========================================================")
    print(f"Target Repository: https://github.com/{OWNER}/{REPO}\n")
    print("To upload, you need a GitHub Personal Access Token (PAT).")
    print("Generate one at: https://github.com/settings/tokens")
    print("Make sure the token has 'repo' scopes enabled.\n")
    
    token = input("Enter your GitHub Personal Access Token (PAT): ").strip()
    if not token:
        print("Token cannot be empty.")
        return

    for path in FILES_TO_UPLOAD:
        print(f"Uploading {path}...")
        try:
            upload_file(path, token)
        except Exception as e:
            print(f"Error uploading {path}: {e}")

if __name__ == "__main__":
    main()
