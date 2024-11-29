#!xbar-pagerduty/.venv/bin/python3

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Tuple

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
