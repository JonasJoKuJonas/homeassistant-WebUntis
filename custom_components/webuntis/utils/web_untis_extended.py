import json
import time
from typing import Any

import aiohttp
import pyotp
import requests
from webuntis import errors
from webuntis.utils import log  # pylint: disable=no-name-in-module
from webuntis.session import Session as WebUntisSession

from qrLogin import QrData

QR_USER_AGENT = "UntisMobileAndroid"
QR_API_VERSION = "i3.2"


class ExtendedSession(WebUntisSession):
    """
    This class extends the original Session to include new functionality for
    fetching homeworks from the WebUntis API using a different endpoint.
    """

    @staticmethod
    def _extract_login_result(data: dict[str, Any]) -> dict[str, Any]:
        """Extract fields expected by webuntis.Session.login_result."""
        keys = ("personType", "personId", "klasseId")
        login_result = {key: data[key] for key in keys if key in data}

        result = data.get("result")
        if isinstance(result, dict):
            for key in keys:
                if key in result and key not in login_result:
                    login_result[key] = result[key]

        return login_result

    @staticmethod
    def _qr_endpoint(credentials: QrData, method: str) -> str:
        return (
            f"https://{credentials.server}/WebUntis/jsonrpc_intern.do"
            f"?m={method}&school={credentials.school}&v={QR_API_VERSION}"
        )

    @staticmethod
    def _qr_auth_block(credentials: QrData) -> dict[str, Any]:
        """Generate auth block for QR login."""
        return {
            "user": credentials.user,
            "otp": pyotp.TOTP(credentials.key).now(),
            "clientTime": int(time.time() * 1000),
        }

    @classmethod
    async def async_qr_login(
        cls,
        credentials: QrData,
        client_session: aiohttp.ClientSession,
    ) -> tuple[dict[str, Any], str]:
        """Authenticate via QR credentials and return user payload and JSESSIONID."""
        method = "getUserData2017"
        body = {
            "id": "ha-webuntis-qr",
            "method": method,
            "params": [
                {
                    "auth": cls._qr_auth_block(credentials),
                    "deviceOs": "AND",
                    "deviceOsVersion": "13",
                }
            ],
            "jsonrpc": "2.0",
        }
        headers = {
            "Content-Type": "application/json",
            "User-Agent": QR_USER_AGENT,
        }

        async with client_session.post(
            cls._qr_endpoint(credentials, method),
            json=body,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as response:
            response.raise_for_status()
            data = await response.json(content_type=None)

            error = data.get("error")
            if error:
                message = (
                    error.get("message", error) if isinstance(error, dict) else error
                )
                raise errors.NotLoggedInError(f"WebUntis error: {message}")

            jsessionid = response.cookies.get("JSESSIONID")
            if jsessionid is None:
                raise errors.NotLoggedInError(
                    "Could not find JSESSIONID in QR login response"
                )

            result = data.get("result")
            user_data = result if isinstance(result, dict) else {}
            return user_data, jsessionid.value

    @classmethod
    async def async_create_from_qr(
        cls,
        credentials: QrData,
        client_session: aiohttp.ClientSession,
    ) -> tuple["ExtendedSession", str]:
        """Create an authenticated ExtendedSession from QR credentials."""
        user_data, jsessionid = await cls.async_qr_login(credentials, client_session)
        session = cls(
            server=f"https://{credentials.server}",
            school=credentials.school,
            username=credentials.user,
            password="",
            jsessionid=jsessionid,
            useragent="home-assistant",
        )
        session.login_result = cls._extract_login_result(user_data)
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
