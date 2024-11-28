#!xbar-pagerduty/.venv/bin/python3

import datetime
import json
import os
import pprint
import re
import sys
from collections import defaultdict

import pdpyras
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = None

session = pdpyras.APISession(ACCESS_TOKEN, auth_type="oauth2")


def log(message):
    # if os.environ.get("DEBUG"):
    with open("/tmp/xbar-logging.txt", "a") as f:
        f.write("in pagerduty.py")
        if len(sys.argv) > 1:
            f.write(" (loadapp)")
        f.write(": ")
        pprint.pprint(message, stream=f)
        f.write("\n")


def log_env():
    log("sys.argv: " + ", ".join(sys.argv))
    log(f"Python executable: {sys.executable}")
    log(f"Python version: {sys.version}")
    log(f"sys.path: {sys.path}")
    log(f"Environment variables:{os.environ}")
    log(f"cwd: {os.getcwd()}")


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


def output_menu(menu):
    print("☎")
    print("---")
    for item in menu[1]:
        print(item)


def get_user():
    response = session.get("/users/me").json()
    user = response["user"]
    log(user)

    return user


def get_teams(user):
    return [
        (x["id"], re.sub(r"\|", "¦", x["summary"]), x["html_url"])
        for x in user["teams"]
    ]


def get_services_and_incidents(teams):
    services = session.list_all("services", params={"team_ids": [x[0] for x in teams]})
    service_ids = [x["id"] for x in services]

    incidents = session.list_all("incidents", params={"service_ids": service_ids})
    log("incidents:")
    log(incidents)

    grouped_services = defaultdict(list)
    for service in services:
        for team in service["teams"]:
            grouped_services[team["id"]].append(service)

    return {"grouped_services": grouped_services, "incidents": incidents}


def process_incidents(incidents):
    menu = []

    team_incident_data = defaultdict(lambda: {"total": 0, "recent": 0})

    recent_threshold = datetime.datetime.utcnow() - datetime.timedelta(days=3)

    for incident in incidents:
        teams = incident["teams"]
        service = incident["service"]["summary"]
        created_at = datetime.datetime.strptime(
            incident["created_at"], "%Y-%m-%dT%H:%M:%SZ"
        )

        for team in teams:
            team_summary = team["summary"]
            team_incident_data[team_summary]["total"] += 1
            if created_at > recent_threshold:
                team_incident_data[team_summary]["recent"] += 1

    for team, data in team_incident_data.items():
        team = re.sub(r"\|", "¦", team)
        menu.append(f"---\n{team}\n---")
        menu.append(f"{service} ({data['total']}) ({data['recent']})")

    return menu


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "loadapp":
        log("we're in loadapp")
        from app import run_server

        run_server()
        sys.exit(0)

    check_login()

    menu = []

    user = get_user()
    menu.append(f'{user["name"]} | href={user["html_url"]}')

    teams = get_teams(user)
    log("teams:")
    log(teams)
    services_and_incidents = get_services_and_incidents(teams)
    services = services_and_incidents["grouped_services"]
    incidents = services_and_incidents["incidents"]
    log("services:")
    log(services)
    log("incidents:")
    log(incidents)

    menu.extend(process_incidents(incidents))

    output_menu()


# for team_id, team_summary, team_url in teams:
#     menu[1].append("---")
#     menu[1].append(f"{team_summary} | href={team_url}")
#     menu[1].append("---")
#     log("team_id: " + team_id)
#     for service in services[team_id]:
#         menu[1].append(
#             f'{service["name"]} | href={
#                 service["html_url"]} | size=10'
#         )


# Get all schedules for my teams
# Get all escalation policies for my schedules
# Get all oncalls for my escalation policies


if __name__ == "__main__":
    main()
