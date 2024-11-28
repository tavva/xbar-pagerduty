#!xbar-pagerduty/.venv/bin/python3

import os
import sys


def log(message):
    if os.environ.get("DEBUG"):
        with open("/Users/Ben.Phillips/xbar-logging.txt", "a") as f:
            f.write("in app.py: ")
            f.write(message)
            f.write("\n")


log(f"Python executable: {sys.executable}")
log(f"Python version: {sys.version}")
log(f"sys.path: {sys.path}")
log(f"Environment variables:{os.environ}")

log(os.getcwd())
log(os.getlogin())


import json
import os
import threading
import urllib
import webbrowser

import requests
from dotenv import load_dotenv
from flask import Flask, redirect, request
from requests.exceptions import HTTPError

load_dotenv()
app = Flask(__name__)

BASE_OAUTH_URL = "https://identity.pagerduty.com/oauth"
CALLBACK_URI = "http://localhost:5000/callback"

auth_params = {
    "response_type": "code",
    "client_id": os.environ["PAGERDUTY_CLIENT_ID"],
    "redirect_uri": CALLBACK_URI,
}

AUTH_URL = "{url}/authorize?{query_string}".format(
    url=BASE_OAUTH_URL, query_string=urllib.parse.urlencode(auth_params)
)
print("auth url", AUTH_URL)


@app.route("/")
def index():
    print("redirecting to auth url", AUTH_URL)
    return redirect(AUTH_URL)


@app.route("/callback")
def callback():
    token_params = {
        "client_id": os.environ["PAGERDUTY_CLIENT_ID"],
        "client_secret": os.environ["PAGERDUTY_CLIENT_SECRET"],
        "redirect_uri": CALLBACK_URI,
        "grant_type": "authorization_code",
        "code": request.args.get("code"),
    }

    try:
        # Retrieve code and request access token
        url = f"{BASE_OAUTH_URL}/token"
        print("url", url)
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        token_res = requests.post(url, data=token_params, headers=headers)

        token_res.raise_for_status()
        body = token_res.json()
        api_token = body["access_token"]

        with open("xbar-pagerduty.json", "w") as json_file:
            json.dump({"api_token": api_token}, json_file)

        html = "You are logged in, you can close this now."
        shutdown_server()

    except HTTPError as e:
        print(e)
        html = "<p>{error}</p>".format(error=e)

    return html


def shutdown_server():
    threading.Timer(1.0, lambda: os._exit(0)).start()


def open_browser():
    threading.Timer(
        1.0, lambda: webbrowser.open_new_tab("http://127.0.0.1:5000")
    ).start()


def run_server():
    open_browser()
    app.run(host="0.0.0.0", port=5000, debug=True)


if __name__ == "__main__":
    run_server()
