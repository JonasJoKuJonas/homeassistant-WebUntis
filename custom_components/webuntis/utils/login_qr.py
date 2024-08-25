import pyotp
import datetime
import requests

# pylint: disable=maybe-no-member
import webuntis

from .errors import BadCredentials


def login_qr(url: str, school: str, user: str, key: str):
    # Create a TOTP instance with a time window of 30 seconds
    totp = pyotp.TOTP(key, interval=30)

    # Generate the OTP based on the current timestamp
    secret = totp.now()

    time = int(datetime.datetime.now().timestamp() * 1000)

    url = url + "/WebUntis/jsonrpc_intern.do"
    headers = {"Content-Type": "application/json"}
    data = {
        "id": "Awesome",
        "method": "getUserData2017",
        "params": [
            {
                "auth": {
                    "clientTime": time,
                    "user": user,
                    "otp": secret,
                },
            },
        ],
        "jsonrpc": "2.0",
    }
    params = {
        "m": "getUserData2017",
        "school": school,
        "v": "i2.2",
    }

    response = requests.post(url, json=data, headers=headers, params=params, timeout=30)

    if "error" in response.json():
        if response.json()["error"]["message"] == "bad credentials":
            raise BadCredentials(response.json()["error"])
        else:
            raise Exception(response.json()["error"]["message"])

    # print(response)
    # print(response.json())

    s = webuntis.Session()

    s.login_result = dict()

    result = response.json()["result"]
    if "elemType" in result["userData"]:
        s.login_result["personType"] = {
            "KLASSE": 1,
            "TEACHER": 2,
            "SUBJECT": 3,
            "ROOM": 4,
            "STUDENT": 5,
        }[result["userData"]["elemType"]]
        s.login_result["personId"] = result["userData"]["elemId"]

    if "set-cookie" in response.headers:
        cookie_parts = response.headers["set-cookie"].split("; ")
        jsessionid = ""
        for part in cookie_parts:
            if part.startswith("JSESSIONID="):
                jsessionid = part[len("JSESSIONID=") :]
                s.config["jsessionid"] = jsessionid
                s.config["username"] = user
                s.config["school"] = school
                s.config["server"] = url
                s.config["useragent"] = "WebUntis Test"
                break
    return s
