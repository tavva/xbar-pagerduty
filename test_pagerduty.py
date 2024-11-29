import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pdpyras

from pagerduty import (
    IncidentCounts,
    PagerDutyClient,
    PagerDutyError,
    TeamIncidentData,
    format_menu_item,
    process_incidents,
)


class TestIncidentCounts(unittest.TestCase):
    def test_incident_counts_initialization(self):
        counts = IncidentCounts()
        self.assertEqual(counts.total, 0)
        self.assertEqual(counts.recent, 0)

    def test_incident_counts_with_values(self):
        counts = IncidentCounts(total=5, recent=2)
        self.assertEqual(counts.total, 5)
        self.assertEqual(counts.recent, 2)


class TestPagerDutyClient(unittest.TestCase):
    def setUp(self):
        self.client = PagerDutyClient("fake-token")

    @patch("pdpyras.APISession.get")
    def test_get_user(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {"user": {"name": "Jim Bob"}}
        mock_get.return_value = mock_response

        user = self.client.get_user()
        self.assertEqual(user["name"], "Jim Bob")

    @patch("pdpyras.APISession.get")
    def test_get_user_error(self, mock_get):
        mock_get.side_effect = pdpyras.PDClientError("API Error")

        with self.assertRaises(PagerDutyError):
            self.client.get_user()

    def test_clean_team_name(self):
        self.assertEqual(PagerDutyClient._clean_team_name("Team|Name"), "Team¦Name")


class TestIncidentProcessing(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(UTC)
        self.recent_incident = {
            "id": "1",
            "title": "Recent Incident",
            "created_at": (self.now - timedelta(days=1)).strftime(
                "%Y-%m-%dT%H:%M:%S+00:00"
            ),
            "status": "triggered",
            "html_url": "http://example.com/1",
            "service": {
                "id": "S1",
                "summary": "Service 1",
                "html_url": "http://example.com/s1",
            },
            "teams": [
                {"id": "T1", "summary": "Team 1", "html_url": "http://example.com/t1"}
            ],
        }
        self.old_incident = {
            "id": "2",
            "title": "Old Incident",
            "created_at": (self.now - timedelta(days=5)).strftime(
                "%Y-%m-%dT%H:%M:%S+00:00"
            ),
            "status": "resolved",
            "html_url": "http://example.com/2",
            "service": {
                "id": "S1",
                "summary": "Service 1",
                "html_url": "http://example.com/s1",
            },
            "teams": [
                {"id": "T1", "summary": "Team 1", "html_url": "http://example.com/t1"}
            ],
        }

    def test_process_incidents(self):
        incidents = [self.recent_incident, self.old_incident]
        teams = [("T1", "Team 1", "http://example.com/t1")]
        services = {
            "grouped_services": {
                "T1": [
                    {
                        "id": "S1",
                        "summary": "Service 1",
                        "html_url": "http://example.com/s1",
                    }
                ]
            }
        }

        menu_items = process_incidents(incidents, teams, services)

        self.assertTrue(any("Team 1 (2 / 1)" in item for item in menu_items))
        self.assertTrue(any("Service 1 (2 / 1)" in item for item in menu_items))

    def test_process_incidents_empty(self):
        menu_items = process_incidents([], [], {"grouped_services": {}})
        self.assertEqual(menu_items, [])


class TestMenuFormatting(unittest.TestCase):
    def test_format_menu_item(self):
        self.assertEqual(format_menu_item("Test"), "Test")

        self.assertEqual(
            format_menu_item("Test", color="red", href="http://example.com"),
            "Test | color=red | href=http://example.com",
        )

        self.assertEqual(
            format_menu_item("Test", color="red", href=None), "Test | color=red"
        )


class TestTeamIncidentData(unittest.TestCase):
    def test_team_incident_data_initialization(self):
        data = TeamIncidentData()
        self.assertEqual(data.total, 0)
        self.assertEqual(data.recent, 0)
        self.assertIsNotNone(data.services)

        service_counts = data.services["new-service"]
        self.assertTrue(isinstance(service_counts, IncidentCounts))
        self.assertEqual(service_counts.total, 0)
        self.assertEqual(service_counts.recent, 0)

    def test_team_incident_data_with_services(self):
        data = TeamIncidentData(total=10, recent=5)
        data.services["test-service"].total = 3
        data.services["test-service"].recent = 2

        self.assertEqual(data.total, 10)
        self.assertEqual(data.recent, 5)
        self.assertEqual(data.services["test-service"].total, 3)
        self.assertEqual(data.services["test-service"].recent, 2)


if __name__ == "__main__":
    unittest.main()
