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

session = None


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

    global session
    session = pdpyras.APISession(config["access_token"], auth_type="oauth2")


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
    for item in menu:
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
    team_lookup = {}
    service_lookup = {}

    team_incident_data = defaultdict(
        lambda: {
            "total": 0,
            "recent": 0,
            "services": defaultdict(lambda: {"total": 0, "recent": 0}),
        }
    )

    recent_threshold = datetime.datetime.utcnow() - datetime.timedelta(days=3)

    for incident in incidents:
        teams = incident["teams"]
        service = incident["service"]
        service_lookup[service["id"]] = service
        created_at = datetime.datetime.strptime(
            incident["created_at"], "%Y-%m-%dT%H:%M:%SZ"
        )

        for team in teams:
            team_lookup[team["id"]] = team
            team_incident_data[team["id"]]["total"] += 1
            team_incident_data[team["id"]]["services"][service["id"]]["total"] += 1
            if created_at > recent_threshold:
                team_incident_data[team["id"]]["recent"] += 1
                team_incident_data[team["id"]]["services"][service["id"]]["recent"] += 1

    def render_counts(team, service=None):
        entity = team_incident_data[team]
        if service:
            entity = entity["services"][service]
        return f"{entity["total"]} / {entity["recent"]}"

    for team_id in team_incident_data.keys():
        team = team_lookup[team_id]
        team_name = re.sub(r"\|", "¦", team["summary"])
        menu.append(
            f"---\n{team_name} ({render_counts(team_id)
                                 }) | href={team["html_url"]}\n---"
        )
        for service_id in team_incident_data[team_id]["services"].keys():
            service = service_lookup[service_id]
            menu.append(
                f"{service["summary"]} ({
                    render_counts(team_id, service_id)}) | href={service["html_url"]}"
            )

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
    menu.append(f'Logged in as: {user["name"]} | href={user["html_url"]}')

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

    output_menu(menu)


if __name__ == "__main__":
    main()
