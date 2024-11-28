#!xbar-pagerduty/.venv/bin/python3

import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = None


def log(message):
    if os.environ.get("DEBUG"):
        with open("/tmp/xbar-logging.txt", "a") as f:
            f.write("in pagerduty.py")
            if len(sys.argv) > 1:
                f.write(" (loadapp)")
            f.write(": ")
            f.write(message)
            f.write("\n")


log("sys.argv: " + ", ".join(sys.argv))
log(f"Python executable: {sys.executable}")
log(f"Python version: {sys.version}")
log(f"sys.path: {sys.path}")
log(f"Environment variables:{os.environ}")
log(f"cwd: {os.getcwd()}")


if len(sys.argv) > 1 and sys.argv[1] == "loadapp":
    log("we're in loadapp")
    from app import run_server

    run_server()
    sys.exit(0)


def load_config():
    try:
        with open("xbar-pagerduty.json") as config_file:
            config = json.load(config_file)
            return config
    except FileNotFoundError:
        return {}


def check_login():
    config = load_config()
    if not config.get("access_token"):
        prompt_login()
    global ACCESS_TOKEN
    ACCESS_TOKEN = config["access_token"]


def prompt_login():
    print("⚠️ | color=red")
    print("---")
    app_script_path = os.path.join("xbar-pagerduty", "pagerduty.py")
    print(
        f'Login | shell="{
            app_script_path}" param1="loadapp" | color=red'
    )
    sys.exit(0)


def output_menu():
    print(menu[0])
    print("---")
    for item in menu[1]:
        print(item)


check_login()

menu = ("☎", [])


# Get all schedules for my teams
# Get all escalation policies for my schedules
# Get all oncalls for my escalation policies
