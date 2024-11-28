#!xbar-pagerduty/.venv/bin/python3

import json
import os
import sys
from collections import defaultdict

import pdpyras
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = None


def log(message):
    # if os.environ.get("DEBUG"):
    with open("/tmp/xbar-logging.txt", "a") as f:
        f.write("in pagerduty.py")
        if len(sys.argv) > 1:
            f.write(" (loadapp)")
        f.write(": ")
        f.write(str(message))
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


def get_user(session):
    response = session.get("/users/me").json()
    user = response["user"]
    log(user)

    return user


def get_teams(user):
    import re

    return [
        (x["id"], re.sub(r"\|", "¦", x["summary"]), x["html_url"])
        for x in user["teams"]
    ]


def get_services(teams):
    services = session.list_all("services", params={"team_ids": [x[0] for x in teams]})
    grouped_services = defaultdict(list)
    for service in services:
        for team in service["teams"]:
            grouped_services[team["id"]].append(service)

    return grouped_services


session = pdpyras.APISession(ACCESS_TOKEN, auth_type="oauth2")
user = get_user(session)
menu[1].append(f'{user["name"]} | href={user["html_url"]}')

teams = get_teams(user)
log(teams)
services = get_services(teams)
log(services)

for team_id, team_summary, team_url in teams:
    menu[1].append("---")
    menu[1].append(f"{team_summary} | href={team_url}")
    menu[1].append("---")
    for service in services[team_id]:
        menu[1].append(
            f'{service["name"]} | href={
                service["html_url"]} | size=10'
        )


# Get all schedules for my teams
# Get all escalation policies for my schedules
# Get all oncalls for my escalation policies

output_menu()
