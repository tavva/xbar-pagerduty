#!xbar-pagerduty/.venv/bin/python3

import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()


def log(message):
    if os.environ.get("DEBUG"):
        with open("/Users/Ben.Phillips/xbar-logging.txt", "a") as f:
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


def prompt_login():
    print("Login | color=red")
    print("---")
    app_script_path = os.path.join("xbar-pagerduty", "pagerduty.py")
    print(app_script_path)
    print(
        f'Login | shell="{
            app_script_path}" param1="loadapp" | color=red'
    )


prompt_login()

# Get all schedules for my teams
# Get all escalation policies for my schedules
# Get all oncalls for my escalation policies
