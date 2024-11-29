#!xbar-pagerduty/.venv/bin/python3

import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

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
class Team:
    id: str
    name: str
    url: str

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "Team":
        return cls(id=data["id"], name=data["summary"], url=data["html_url"])


@dataclass
class Service:
    id: str
    name: str
    url: str
    team_ids: List[str]

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "Service":
        return cls(
            id=data["id"],
            name=data["name"],
            url=data["html_url"],
            team_ids=[team["id"] for team in data["teams"]],
        )


@dataclass
class Incident:
    id: str
    title: str
    url: str
    status: str
    created_at: datetime
    service_id: str
    team_ids: List[str]

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "Incident":
        return cls(
            id=data["id"],
            title=data["title"],
            url=data["html_url"],
            status=data["status"],
            created_at=datetime.fromisoformat(
                data["created_at"].replace("Z", "+00:00")
            ),
            service_id=data["service"]["id"],
            team_ids=[team["id"] for team in data.get("teams", [])],
        )


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

    def get_teams(self, user: Dict[str, Any]) -> List[Team]:
        try:
            teams = [Team.from_api_response(team) for team in user.get("teams", [])]
            logger.debug("Successfully retrieved teams data")
            return teams
        except KeyError as e:
            logger.error("Malformed team data: %s", e)
            raise PagerDutyError(f"Invalid team data structure: {e}")

    def get_services_and_incidents(
        self, team_ids: List[str]
    ) -> Dict[str, List[Union[Service, Incident]]]:
        try:
            logger.debug("Fetching services for team_ids: %s", team_ids)
            raw_services = self.session.list_all(
                "services", params={"team_ids": team_ids}
            )
            services = [Service.from_api_response(s) for s in raw_services]

            service_ids = [service.id for service in services]
            logger.debug("Fetching incidents for service_ids: %s", service_ids)
            raw_incidents = self.session.list_all(
                "incidents", params={"service_ids": service_ids}
            )
            incidents = [Incident.from_api_response(i) for i in raw_incidents]

            grouped_services = defaultdict(list)
            for service in services:
                for team_id in service.team_ids:
                    grouped_services[team_id].append(service)

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
        team_ids = [team.id for team in teams]

        data = client.get_services_and_incidents(team_ids)
        incidents = data["incidents"]

        active_incidents = [i for i in incidents if i.status != "resolved"]

        # Header - normal phone icon for functioning state
        print("☎️")
        print("---")

        print(
            format_menu_item(
                f'Logged in as: {user["name"]}',
                href=user["html_url"],
            )
        )

        if active_incidents:
            print(
                format_menu_item(
                    f"🔴 {len(active_incidents)} active incidents", color="red"
                )
            )
        else:
            print(format_menu_item("✅ No active incidents"))

        print("---")

        for incident in active_incidents:
            print(format_menu_item(incident.title, href=incident.url))

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
