import os
import time
import pickle
import loguru
import requests
import pandas as pd
from seleniumwire import webdriver


class SberBankOperationsFilter:
    def __init__(self, operation_type: str, date_from: str, date_to: str, resource: list = None, result_format: any = None,
                 pagination_offset: int = 0, pagination_size: int = 50):
        self.type = operation_type
        self.date_from = date_from
        self.date_to = date_to
        self.resource = resource
        self.result_format = result_format \
            if result_format == dict or result_format == pd.DataFrame \
            else None  # Can be dict or pd.DataFrame
        self.pagination_offset = pagination_offset
        self.pagination_size = pagination_size
        self.logger = loguru.logger

        if result_format and not self.result_format:
            self.logger.warning(f"SberBankOperationsFilter don't support result format: {result_format}. "
                                f"result_format is set to None")

    def to_json(self):
        payload = {
            "filterName": self.type,
            "from": self.date_from,
            "to": self.date_to,
            "usedResource": self.resource,
            "paginationOffset": self.pagination_offset,
            "paginationSize": self.pagination_size,
        }
        # TODO: Remove None key value pairs from payload dictionary
        return payload


class SberBankApiClient:
    LOGIN_URL = "https://online.sberbank.ru/CSAFront/index.do"

    def __init__(self, path_to_cookies_file: str = None):
        self.path_to_cookies_file = path_to_cookies_file if path_to_cookies_file else "cookies.pkl"
        self.session = requests.Session()
        self.cookies = None
        self.headers = None
        self.logger = loguru.logger
        self.driver = webdriver.Chrome()

        if not path_to_cookies_file or not os.path.exists(self.path_to_cookies_file):
            self._login_and_save_session()
        elif not self._load_session() or self._session_expired():
            self._login_and_save_session()
        else:
            if not self._validate_session():
                self._login_and_save_session()
            else:
                self.logger.info("Session is valid. You're in!")

    def __initialize_sberbank_public_api_endpoints(
        self,
        sberbank_web_node: str = None,
        sberbank_api_web_node: str = None
    ):
        if sberbank_web_node:
            self.SBERBANK_WEB_NODE = sberbank_web_node
        if sberbank_api_web_node:
            self.SBERBANK_API_WEB_NODE = sberbank_api_web_node

        self.MAIN_URL = f"https://{self.SBERBANK_WEB_NODE}.online.sberbank.ru/main"
        self.WARMUP_URL = f"https://{self.SBERBANK_WEB_NODE}.online.sberbank.ru/api/warmUpSession"
        self.LOG_REPORT_URL = f"https://{self.SBERBANK_WEB_NODE}.online.sberbank.ru/api/log/report"
        self.OPERATIONS_URL = f"https://web-node1.online.sberbank.ru/uoh-bh/v1/operations/list"

    def _load_session(self):
        # Load cookies and headers from a pickle file if it exists.
        if os.path.exists(self.path_to_cookies_file):
            with open(self.path_to_cookies_file, "rb") as f:
                data = pickle.load(f)
                self.cookies = data.get("cookies")
                self.headers = data.get("headers")
                # Set loaded cookies in the requests session.
                if self.cookies:
                    for domen_cookies in self.cookies:
                        self.session.cookies.update(domen_cookies)
            return True
        return False

    def _session_expired(self):
        # Dummy check: implement your own expiration logic if needed.
        # For instance, check timestamp saved with cookies.
        return False

    def _validate_session(self):
        # Validate the session by making a POST request to warmUpSession.
        try:
            response = self.session.post(self.WARMUP_URL)
            if response.status_code == 200 and response.json().get("code") == 0:
                return True
        except Exception as e:
            self.logger.info("Session validation failed:", e)
        return False

    def _login_and_save_session(self):
        # Use Selenium to perform login.
        self.logger.info("No valid session found. Initiating login process...")

        self.driver.get(self.LOGIN_URL)

        # Wait for the user to log in manually.
        # Sberbank redirects user to https://{web_node_name}.online.sberbank.ru/main after
        # That's why we use this expression to figure out if user logged in or not.
        while self.driver.current_url.split(".")[1::] != ['online', 'sberbank', 'ru/main']:
            time.sleep(1)

        # Extracting web_node_name from https://{web_node_name}.online.sberbank.ru/main
        self.SBERBANK_WEB_NODE = self.driver.current_url.split(".")[:1:][0].split("https://")[1]

        # Extracting api_web_node_name from
        # https://{api_web_node_name}.online.sberbank.ru/main-screen/rest/v2/m1/web/section/meta
        for request in self.driver.requests:
            endpoint_parts = request.url.split(".")
            if endpoint_parts[1::] == ['online', 'sberbank', 'ru/main-screen/rest/v2/m1/web/section/meta']:
                self.SBERBANK_API_WEB_NODE = endpoint_parts[:1:][0].split("https://")[1]
                self.SBERBANK_API_WEB_NODE_HEADERS = request.headers

        self.__initialize_sberbank_public_api_endpoints(self.SBERBANK_WEB_NODE, self.SBERBANK_API_WEB_NODE)

        self.logger.info("Login successful. Retrieving session data...")

        # Retrieve cookies from Selenium.
        selenium_cookies = self.driver.get_cookies()
        self.cookies = {cookie["name"]: cookie["value"] for cookie in selenium_cookies}
        self.session.cookies.update(self.cookies)

        # Mimic retrieval of headers by watching network requests.
        # This part requires custom logic or a proxy tool.
        # For now, assume headers are hardcoded or manually set.
        self.headers = {
            "User-Agent": self.driver.execute_script("return navigator.userAgent;")
            # Add any additional headers as required.
        }
        self.headers.update(self.SBERBANK_API_WEB_NODE_HEADERS)

        # Save cookies and headers to file.
        with open(self.path_to_cookies_file, "wb") as f:
            pickle.dump({"cookies": self.cookies, "headers": self.headers}, f)

        self.driver.quit()
        self.logger.info("Session data saved. You're in!")

    def warm_up_session(self):
        # Send a POST request to prolong the session.
        try:
            response = self.session.post(self.WARMUP_URL, headers=self.headers)
            if response.status_code == 200 and response.json().get("code") == 0:
                self.logger.info("Session prolonged successfully.")
            else:
                self.logger.info("Failed to prolong session.")
        except Exception as e:
            self.logger.info("Error during session warm-up:", e)

    def get_operations(self, _filter: SberBankOperationsFilter):
        payload = _filter.to_json()

        try:
            response = self.session.post(self.OPERATIONS_URL, json=payload, headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                if _filter.result_format == pd.DataFrame:
                    return pd.DataFrame(data.get("body", {}).get("operations", []))
                else:
                    return data
            else:
                self.logger.info("Failed to get operations. Status code:", response.status_code)
        except Exception as e:
            self.logger.info("Error retrieving operations:", e)
        return None
