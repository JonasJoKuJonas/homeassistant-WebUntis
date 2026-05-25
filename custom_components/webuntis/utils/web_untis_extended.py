import requests
import json
from urllib.parse import urlparse, parse_qs
from webuntis import errors
from webuntis.utils import log  # pylint: disable=no-name-in-module
from webuntis.session import Session as WebUntisSession

import logging
import time
import pyotp

# logging.basicConfig(level=logging.DEBUG)


class ExtendedSession(WebUntisSession):
    """
    This class extends the original Session to include new functionality for
    fetching homeworks from the WebUntis API using a different endpoint.
    """

    def login_with_otp(self, otp_secret):
        """
        Authenticate using a TOTP secret (from QR code login).

        :param otp_secret: The TOTP secret key extracted from the QR code
        :returns: The session (for chaining)
        """
        try:
            username = self.config["username"]
            school = self.config["school"]
            useragent = self.config["useragent"]
        except KeyError as e:
            raise errors.BadCredentialsError("Missing config: " + str(e))

        server_url = self.config["server"]
        base_url = server_url.rstrip("/")

        token = pyotp.TOTP(otp_secret).now()
        client_time = int(time.time() * 1000)

        try:
            response = requests.post(
                f"{base_url}/WebUntis/jsonrpc_intern.do",
                params={
                    "m": "getUserData2017",
                    "school": school,
                    "v": "i2.2",
                },
                data=json.dumps({
                    "id": useragent,
                    "method": "getUserData2017",
                    "params": [
                        {
                            "auth": {
                                "clientTime": client_time,
                                "user": username,
                                "otp": int(token),
                            },
                        },
                    ],
                    "jsonrpc": "2.0",
                }),
                headers={
                    "User-Agent": useragent,
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
        except requests.RequestException as err:
            raise errors.AuthError(f"OTP login request failed: {err}") from err

        if response.status_code != 200:
            raise errors.AuthError(
                f"OTP login failed with status {response.status_code}"
            )

        response_data = response.json()
        if response_data.get("error"):
            raise errors.BadCredentialsError(
                response_data["error"].get("message", "OTP login failed")
            )

        cookies = response.headers.get("set-cookie", "")
        jsessionid = self._extract_jsessionid(cookies)

        if not jsessionid:
            raise errors.AuthError("No JSESSIONID received from OTP login")

        self.config["jsessionid"] = jsessionid
        log("debug", "Did get a jsessionid from OTP login: " + jsessionid)

        self.login_result = dict()
        self._fetch_person_info(base_url)

        return self

    @staticmethod
    def _extract_jsessionid(set_cookie_header):
        """Extract JSESSIONID from Set-Cookie header."""
        if not set_cookie_header:
            return None
        for cookie_part in set_cookie_header.split(";"):
            cookie_part = cookie_part.strip()
            if "=" in cookie_part:
                key, value = cookie_part.split("=", 1)
                if key.strip().upper() == "JSESSIONID":
                    return value.strip()
        return None

    def _fetch_person_info(self, base_url):
        """Fetch personId and personType from app config after OTP login."""
        headers = {
            "User-Agent": self.config["useragent"],
            "Cookie": f'JSESSIONID={self.config["jsessionid"]}',
        }

        config_resp = requests.get(
            f"{base_url}/WebUntis/api/app/config",
            headers=headers,
        )
        config_data = config_resp.json().get("data", {})
        login_config = config_data.get("loginServiceConfig", {})
        user_config = login_config.get("user", {})

        person_id = user_config.get("personId")
        if person_id is not None:
            self.login_result["personId"] = person_id

        person_type = None
        persons = user_config.get("persons", [])
        for person in persons:
            if person.get("id") == person_id:
                person_type = person.get("type")
                break
        if person_type is not None:
            self.login_result["personType"] = person_type

        try:
            day_config_resp = requests.get(
                f"{base_url}/WebUntis/api/daytimetable/config",
                headers=headers,
            )
            day_data = day_config_resp.json().get("data", {})
            klasse_id = day_data.get("klasseId")
            if klasse_id is not None:
                self.login_result["klasseId"] = klasse_id
        except Exception:
            pass

    @staticmethod
    def parse_qr_uri(qr_uri):
        """
        Parse a WebUntis QR code URI and extract connection parameters.

        QR URIs look like:
        untis://setschool?url=...&school=...&user=...&key=...&schoolNumber=...

        :param qr_uri: The raw QR code URI string
        :returns: dict with server, school, username, key
        """
        parsed = urlparse(qr_uri)
        params = parse_qs(parsed.query)

        result = {}
        for key in ("url", "school", "user", "key"):
            value = params.get(key, [None])[0]
            if value is None:
                raise ValueError(f"Missing required parameter '{key}' in QR URI")
            result[key] = value

        server = result["url"]
        if not server.lower().startswith(("http://", "https://")):
            server = "https://" + server
        result["url"] = server

        return {
            "server": result["url"],
            "school": result["school"],
            "username": result["user"],
            "key": result["key"],
        }

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
            headers["Cookie"] = f'JSESSIONID={self.config["jsessionid"]}'
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
