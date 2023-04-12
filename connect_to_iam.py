import numpy as np
import requests
import json

class BearerAuth(requests.auth.AuthBase):
    def __init__(self, token) -> None:
        self.token = token

    def __call__(self, r):
        r.headers["authorization"] = "Bearer " + self.token
        return r

class IAMLogin(object):
    """Service logs in to IAM backend"""

    def __init__(self) -> None:
        """Instance initialization"""

        # IAM backend
        self.url_base = "https://iam-backend.alamedaproject.eu"

        # API endpoint to log in
        self.request_url = "/api/v1/auth/login"

    def login(self):
        """Service logs in against IAM backend"""

        with open("unic_iam_credentials.json", "r") as file:
            data = json.load(file)
            
        response = requests.post(self.url_base + self.request_url, json=data)

        if response.status_code == 200:
            print("Service successfully logged in to IAM component")
            data = json.loads(response.text)

            return response.status_code, data["access_token"], data["refresh_token"]
        elif response.status_code == 401:
            print("****Service failed to log in against IAM****")
            return response.status_code, data["access_token"], data["refresh_token"]

class VerifyAuthentication(object):
    """Verify token received from WM"""

    def __init__(self) -> None:
        """Instance Initialization"""

        # IAM backend
        self.url_base = "https://iam-backend.alamedaproject.eu"

        # API endpoint to verify received token
        self.request_url = "/api/v1/auth/verify"

    def verification(self, access_token):
        """Verification"""

        response = requests.get(self.url_base + self.request_url, auth=BearerAuth(access_token))

        if response.status_code == 200:
            print("****User access token verification succeeded****")
            return response.status_code
        elif response.status_code == 401:
            print("****User access token verification FAILED****")

class RefreshAccessToken(object):
    """
    To refresh generated access token.
    """

    def __init__(self) -> None:
        """
        Instance initialization
        """

        # IAM backend
        self.url_base = "https://iam-backend.alamedaproject.eu"

        # API endpoint to verify received token
        self.request_url = "/api/v1/auth/refresh-token"

    def refresh_token(self, ca_access_token, ca_refresh_token):
        """
        Refresh token
        """

        payload = {
            "access_token":ca_access_token,
            "refresh_token":ca_refresh_token
        }

        response = requests.post(
            url=self.url_base+self.request_url,
            json=payload
        )
        print(response.json())

        if response.status_code == 200:
            print("****Token successfully refreshed****")
            data = json.loads(response.text)
            return response.status_code, data["access_token"], data["refresh_token"]
        else:
            print(f"****Failed to refresh token with code {response.status_code}****")