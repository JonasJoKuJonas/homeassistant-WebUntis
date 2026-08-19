import json
import time
from typing import Any

import aiohttp
import requests
from webuntis import errors
from webuntis.utils import log  # pylint: disable=no-name-in-module
from webuntis.session import Session as WebUntisSession

from .qrLogin import QrData, async_qr_login, extract_login_result

QR_USER_AGENT = "UntisMobileAndroid"
QR_API_VERSION = "i3.2"


class ExtendedSession(WebUntisSession):
    """
    This class extends the original Session to include new functionality for
    fetching homeworks from the WebUntis API using a different endpoint.
    """

    @classmethod
    async def async_create_from_qr(
        cls,
        credentials: QrData,
        client_session: aiohttp.ClientSession,
    ) -> tuple["ExtendedSession", str]:
        """Create an authenticated ExtendedSession from QR credentials."""
        # 1. QR-Login über die ausgelagerte Funktion durchführen
        user_data, jsessionid = await async_qr_login(credentials, client_session)

        # 2. Session-Instanz aufbauen
        session = cls(
            server=f"https://{credentials.server}",
            school=credentials.school,
            username=credentials.user,
            password="",
            jsessionid=jsessionid,
            useragent="home-assistant",
        )

        # 3. Login-Ergebnis verarbeiten und zuweisen
        session.login_result = extract_login_result(user_data)
        return session, jsessionid

    def _request(self, method, params=None, use_login_repeat=None):
        try:
            return super()._request(
                method, params=params, use_login_repeat=use_login_repeat
            )
        except errors.RemoteError as err:
            # Catch the schoolyear not found error from untis
            if err.code == -8998 or ("schoolyear" in str(err) and "null" in str(err)):
                return []
            raise

    def _send_custom_request(self, endpoint, params):
        """
        A custom method for sending a request to a specific endpoint, different from the JSON-RPC method.

        :param endpoint: The API endpoint for the custom request (e.g., '/api/homeworks/lessons')
        :param params: The query parameters for the request
        :return: JSON response from the API
        """

        base_url = self.config["server"].replace("/WebUntis/jsonrpc.do", "")

        # Construct the URL
        url = f"{base_url}{endpoint}"

        # Prepare headers
        headers = {
            "User-Agent": self.config["useragent"],
            "Content-Type": "application/json",
        }

        # Ensure session is logged in
        if "jsessionid" in self.config:
            headers["Cookie"] = f"JSESSIONID={self.config['jsessionid']}"
        else:
            raise errors.NotLoggedInError("No JSESSIONID found. Please log in first.")

        # Log the request details
        log("debug", f"Making custom request to {url} with params: {params}")

        # Send the request using requests library
        response = requests.get(url, params=params, headers=headers)

        # Check if the response is valid JSON
        try:
            response_data = response.json()
            log("debug", f"Received valid JSON response: {str(response_data)[:100]}")
        except json.JSONDecodeError:
            raise errors.RemoteError("Invalid JSON response", response.text)

        return response_data

    def get_homeworks(self, start, end):
        """
        Fetch homeworks for lessons within a specific date range using the
        '/api/homeworks/lessons' endpoint.

        :param start_date: Start date in the format YYYYMMDD (e.g., 20240901)
        :param end_date: End date in the format YYYYMMDD (e.g., 20240930)
        :return: JSON response containing homework data
        """
        # Define the custom endpoint
        endpoint = "/WebUntis/api/homeworks/lessons"

        # Set query parameters
        params = {
            "startDate": start.strftime("%Y%m%d"),
            "endDate": end.strftime("%Y%m%d"),
        }

        # Send the request and return the response
        return self._send_custom_request(endpoint, params)

    def get_exams(self, start, end):
        """
        Fetch exams within a specific date range using the
        '/api/homeworks/exams' endpoint.

        :param start_date: Start date in the format YYYYMMDD (e.g., 20240901)
        :param end_date: End date in the format YYYYMMDD (e.g., 20240930)
        :return: JSON response containing exams data
        """
        # Define the custom endpoint
        endpoint = "/WebUntis/api/exams"

        # Set query parameters
        params = {
            "startDate": start.strftime("%Y%m%d"),
            "endDate": end.strftime("%Y%m%d"),
        }

        # Send the request and return the response
        return self._send_custom_request(endpoint, params)
