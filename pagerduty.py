#!xbar-pagerduty/.venv/bin/python3

import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pdpyras

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


@dataclass
class PagerDutyError(Exception):
    message: str
    status_code: int = None
    response: Any = None


@dataclass
class IncidentCounts:
    total: int = 0
    recent: int = 0


@dataclass
class TeamIncidentData:
    total: int = 0
    recent: int = 0
    services: Dict[str, IncidentCounts] = None

    def __post_init__(self):
        if self.services is None:
            self.services = defaultdict(lambda: IncidentCounts())


class PagerDutyClient:
    def __init__(self, access_token: str):
        if not access_token:
            logger.error("No access token provided")
            raise ValueError("Access token is required")

        self.session = pdpyras.APISession(
            access_token, auth_type="oauth2", default_from=datetime.utcnow().isoformat()
        )
        logger.debug("PagerDuty client initialized")

    def get_user(self) -> Dict[str, Any]:
        try:
            response = self.session.get("/users/me")
            logger.debug("Successfully retrieved user information")
            return response.json()["user"]
        except pdpyras.PDClientError as e:
            logger.error("Failed to get user info: %s", e)
            raise PagerDutyError(
                message="Failed to get user information",
                status_code=e.response.status_code if e.response else None,
                response=e.response,
            )

    def get_teams(self, user: Dict[str, Any]) -> List[Tuple[str, str, str]]:
        try:
            teams = [
                (team["id"], self._clean_team_name(team["summary"]), team["html_url"])
                for team in user.get("teams", [])
            ]
            logger.debug("Successfully retrieved teams data")
            return teams
        except KeyError as e:
            logger.error("Malformed team data: %s", e)
            raise PagerDutyError(f"Invalid team data structure: {e}")

    def get_services_and_incidents(self, team_ids: List[str]) -> Dict[str, Any]:
        try:
            logger.debug("Fetching services for team_ids: %s", team_ids)
            services = self.session.list_all("services", params={"team_ids": team_ids})

            service_ids = [service["id"] for service in services]
            logger.debug("Fetching incidents for service_ids: %s", service_ids)
            incidents = self.session.list_all(
                "incidents", params={"service_ids": service_ids}
            )

            grouped_services = defaultdict(list)
            for service in services:
                for team in service["teams"]:
                    grouped_services[team["id"]].append(service)

            logger.debug("Successfully retrieved services and incidents")
            return {"grouped_services": dict(grouped_services), "incidents": incidents}

        except pdpyras.PDClientError as e:
            logger.error("Failed to fetch services and incidents: %s", e)
            raise PagerDutyError(
                message="Failed to fetch services and incidents",
                status_code=e.response.status_code if e.response else None,
                response=e.response,
            )

    @staticmethod
    def _clean_team_name(name: str) -> str:
        return name.replace("|", "¦")


def format_menu_item(text: str, **kwargs) -> str:
    params = " ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    return f"{text} | {params}" if params else text


def load_config() -> Optional[str]:
    """Load PagerDuty token from OAuth config file"""
    try:
        config_path = Path("xbar-pagerduty.json")
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
                return config.get("access_token")
    except Exception as e:
        logger.error("Error reading config file: %s", e)
    return None


def process_incidents(
    incidents: List[Dict], teams: List[Tuple[str, str, str]], services: Dict[str, Any]
) -> List[str]:
    menu = []
    team_lookup = {}
    service_lookup = {}

    team_incident_data = defaultdict(TeamIncidentData)

    recent_threshold = datetime.utcnow() - timedelta(days=3)

    # Process incidents
    for incident in incidents:
        teams_data = incident["teams"]
        service = incident["service"]
        service_lookup[service["id"]] = service
        created_at = datetime.strptime(incident["created_at"], "%Y-%m-%dT%H:%M:%SZ")

        for team in teams_data:
            team_lookup[team["id"]] = team
            team_incident_data[team["id"]].total += 1
            team_incident_data[team["id"]].services[service["id"]].total += 1
            if created_at > recent_threshold:
                team_incident_data[team["id"]].recent += 1
                team_incident_data[team["id"]].services[service["id"]].recent += 1

    def render_counts(team_id: str, service_id: Optional[str] = None) -> str:
        data = team_incident_data[team_id]
        if service_id:
            counts = data.services[service_id]
        else:
            counts = data
        return f"{counts.total} / {counts.recent}"

    # Generate menu items
    for team_id, team_name, team_url in teams:
        if team_id in team_incident_data:
            menu.append(
                f"---\n{team_name} ({render_counts(team_id)}) | href={team_url}\n---"
            )

            # Add services for this team
            team_services = services.get("grouped_services", {}).get(team_id, [])
            for service in team_services:
                if service["id"] in team_incident_data[team_id].services:
                    menu.append(
                        format_menu_item(
                            f"{service['summary']} ({render_counts(team_id, service['id'])})",
                            href=service["html_url"],
                        )
                    )

    return menu


def main():
    try:
        access_token = load_config()
        if not access_token:
            print("☎️ | color=red")
            print("---")
            print("Click here to login | bash='./app.py'")
            return

        client = PagerDutyClient(access_token)

        user = client.get_user()
        teams = client.get_teams(user)
        team_ids = [team[0] for team in teams]

        data = client.get_services_and_incidents(team_ids)

        print("☎️")
        print("---")

        print(format_menu_item(f'Logged in as: {user["name"]}', href=user["html_url"]))

        menu_items = process_incidents(data["incidents"], teams, data)
        print("\n".join(menu_items))

    except PagerDutyError as e:
        logger.error("PagerDuty error: %s", e.message)
        print("☎️ | color=red")
        print("---")
        print(format_menu_item("PagerDuty Error", color="red"))
        print(e.message)
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        print("☎️ | color=red")
        print("---")
        print(format_menu_item("Error", color="red"))
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()
