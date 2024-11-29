#!xbar-pagerduty/.venv/bin/python3

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import pdpyras

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


@dataclass
class PagerDutyError(Exception):
    message: str
    status_code: Optional[int] = None
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
