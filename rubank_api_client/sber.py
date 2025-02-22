import os
import time
import random
import loguru
import pickle
import requests
import pandas as pd

from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.common import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class SberBankOperationsFilter:
    def __init__(self, operation_type: str, date_from: str, date_to: str, resource: list = None,
                 result_format: any = None,
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
        payload = {key: value for key, value in payload.items() if value is not None}
        return payload


class SberBankApiClient:
    LOGIN_URL = "https://online.sberbank.ru/CSAFront/index.do"

    def __init__(self, path_to_cookies_file: str = None):
        self.path_to_cookies_file = path_to_cookies_file if path_to_cookies_file else "cookies.pkl"
        self.session = requests.Session()
        self.request_cookies = None
        self.selenium_driver_cookies = None
        self.headers = None
        self.logger = loguru.logger
        self.driver = webdriver.Chrome()

        if self._load_session():
            self.logger.info("Conserved session is valid. You're in!")
        else:
            self._login_and_save_session()
            self.logger.info("New session is created. You're in!")

    def __initialize_sberbank_public_api_endpoints(
            self,
            sberbank_frontend_web_node_id: str = None,
            sberbank_backend_api_web_node_id: str = None
    ):
        if sberbank_frontend_web_node_id:
            self.SBERBANK_FRONTEND_WEB_NODE_ID = sberbank_frontend_web_node_id
        if sberbank_backend_api_web_node_id:
            self.SBERBANK_BACKEND_API_WEB_NODE_ID = sberbank_backend_api_web_node_id

        self.MAIN_URL = f"https://{self.SBERBANK_FRONTEND_WEB_NODE_ID}.online.sberbank.ru/main"
        self.WARMUP_URL = f"https://{self.SBERBANK_FRONTEND_WEB_NODE_ID}.online.sberbank.ru/api/warmUpSession"
        self.LOG_REPORT_URL = f"https://{self.SBERBANK_FRONTEND_WEB_NODE_ID}.online.sberbank.ru/api/log/report"
        self.OPERATIONS_URL = f"https://{self.SBERBANK_BACKEND_API_WEB_NODE_ID}.online.sberbank.ru/uoh-bh/v1/operations/list"

    def _load_session(self):
        if not os.path.exists(self.path_to_cookies_file):
            return False

        # Open sber web app, to load cookies and local_storage to right domain
        self.driver.get(self.LOGIN_URL)
        self.driver.delete_all_cookies()

        # Load cookies, local storage items and headers from a pickle file if it exists.
        with open(self.path_to_cookies_file, "rb") as f:
            data = pickle.load(f)
            self.request_cookies = data.get("cookies")
            self.selenium_driver_cookies = data.get("selenium_driver_cookies")
            self.headers = data.get("headers")
            self.local_storage = data.get("local_storage")

            self.SBERBANK_FRONTEND_WEB_NODE_ID = data.get("sberbank_frontend_web_node_id")
            self.SBERBANK_BACKEND_API_WEB_NODE_ID = data.get("sberbank_backend_api_web_node_id")

            # Set loaded cookies in the requests session.
            if self.request_cookies:
                self.session.cookies.update(self.request_cookies)

            if self.local_storage:
                self.__load_local_storage(self.local_storage)

            # Set loaded cookies in selenium driver
            if self.selenium_driver_cookies:
                for cookie_obj in self.selenium_driver_cookies:
                    if cookie_obj['domain'][0] != ".":
                        self.driver.get("https://" + cookie_obj['domain'])
                    else:
                        pass
                    self.driver.add_cookie(cookie_obj)
                    time.sleep(random.uniform(3, 6))

        if not self.SBERBANK_BACKEND_API_WEB_NODE_ID or not self.SBERBANK_FRONTEND_WEB_NODE_ID:
            return False

        self.driver.get(self.LOGIN_URL)
        return True
        # # Wait for the PIN entry element to appear.
        # try:
        #     # Wait for an element that exists only on the PIN page.
        #     # For example, we look for an element with the unique data attribute:
        #     WebDriverWait(self.driver, 10).until(
        #         EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="input-pin-indicator"]'))
        #     )
        #     # If found, assume session is restored and PIN code prompt is displayed.
        #     self.pin_code = "13378"
        #
        #     for digit in self.pin_code:
        #         btn = WebDriverWait(self.driver, 5).until(
        #             EC.element_to_be_clickable((By.XPATH, f'//button[.//div[contains(text(), "{digit}")]]'))
        #         )
        #         btn.click()
        #         # Short delay between clicks (adjust if necessary)
        #         time.sleep(random.uniform(0.01, 0.5))
        #
        #     return True
        # except TimeoutException:
        #     # If the element does not appear within the timeout, then the session did not load properly.
        #     return True # TODO: Replace True with False
        #     # Temporarily return True, because we fall back on user to enter pincode

    def __load_local_storage(self, local_storage):
        for key, value in local_storage.items():
            self.driver.execute_script(
                "window.localStorage.setItem(arguments[0], arguments[1]);", key, value
            )

    def _login_and_save_session(self):
        try:
            self.logger.info("No valid session found. Initiating login process...")
            self.driver.get(self.LOGIN_URL)
            self.logger.info("Wait for the user to log in manually...")

            self.SBERBANK_FRONTEND_WEB_NODE_ID = self.__get_sber_frontend_web_node_id()
            self.logger.info(f"SBERBANK_FRONTEND_WEB_NODE_ID prefix: {self.SBERBANK_FRONTEND_WEB_NODE_ID}")

            self.SBERBANK_BACKEND_API_WEB_NODE_ID = self.__get_sber_backend_api_web_node_id()
            self.logger.info(f"SBERBANK_BACKEND_API_WEB_NODE_ID prefix: {self.SBERBANK_BACKEND_API_WEB_NODE_ID}")

            if self.SBERBANK_FRONTEND_WEB_NODE_ID and self.SBERBANK_BACKEND_API_WEB_NODE_ID:
                self.__initialize_sberbank_public_api_endpoints(
                    self.SBERBANK_FRONTEND_WEB_NODE_ID,
                    self.SBERBANK_BACKEND_API_WEB_NODE_ID
                )
            else:
                raise Exception(f"Missing self.SBERBANK_FRONTEND_WEB_NODE_ID ({self.SBERBANK_FRONTEND_WEB_NODE_ID}) or "
                                f"self.SBERBANK_BACKEND_API_WEB_NODE_ID ({self.SBERBANK_BACKEND_API_WEB_NODE_ID}).")
        except TimeoutException:
            self.logger.error("Failed to wait for request to find out "
                              "SBERBANK_BACKEND_API_WEB_NODE_ID or SBERBANK_FRONTEND_WEB_NODE_ID value...")
        except Exception as e:
            self.logger.error(e)

        self.logger.info("Login successful. Retrieving session data...")

        self.__conserve_session()

        self.logger.info("Session data saved. You're in!")

    def __get_sber_frontend_web_node_id(self):
        # Sberbank redirects user to https://{web_node_name}.online.sberbank.ru/main after
        # That's why we use this expression to figure out if user logged in or not.
        # Extracting web_node_name from https://{web_node_name}.online.sberbank.ru/main

        self.logger.info("Waiting for request to find out SBERBANK_FRONTEND_WEB_NODE_ID value...")
        request = self.driver.wait_for_request('/main', timeout=100)  # Long timeout to allow user not to hurry

        return request.url.split(".")[:1:][0].split("https://")[1]

    def __get_sber_backend_api_web_node_id(self):
        # Extracting api_web_node_name from
        # https://{api_web_node_name}.online.sberbank.ru/main-screen/rest/v2/m1/web/section/meta

        self.logger.info("Waiting for request to find out SBERBANK_BACKEND_API_WEB_NODE_ID value...")
        request = self.driver.wait_for_request('/main-screen/rest/v2/m1/web/section/meta', timeout=20)
        self.SBERBANK_BACKEND_API_WEB_NODE_HEADERS = request.headers

        endpoint_parts = request.url.split(".")
        return endpoint_parts[:1:][0].split("https://")[1]

    def __conserve_session(self):
        self.request_cookies = {cookie["name"]: cookie["value"] for cookie in self.driver.get_cookies()}
        self.selenium_driver_cookies = self.driver.get_cookies()
        self.session.cookies.update(self.request_cookies)

        self.headers = {
            "User-Agent": self.driver.execute_script("return navigator.userAgent;")
        }
        self.headers.update(self.SBERBANK_BACKEND_API_WEB_NODE_HEADERS)

        # Save cookies, headers, and local storage to file.
        session_data = {
            "cookies": self.request_cookies,
            "selenium_driver_cookies": self.selenium_driver_cookies,
            "headers": self.headers,
            "local_storage": self.get_local_storage(),
            "sberbank_frontend_web_node_id": self.SBERBANK_FRONTEND_WEB_NODE_ID,
            "sberbank_backend_api_web_node_id": self.SBERBANK_BACKEND_API_WEB_NODE_ID
        }
        with open(self.path_to_cookies_file, "wb") as f:
            pickle.dump(session_data, f)

    def get_local_storage(self):
        return self.driver.execute_script("""
            var ls = {};
            for (var i = 0; i < localStorage.length; i++) {
                var key = localStorage.key(i);
                ls[key] = localStorage.getItem(key);
            }
            return ls;
        """)

    def _validate_session(self):
        # TODO: Consider removing or rewriting this method
        # Validate the session by making a POST request to warmUpSession.
        try:
            response = self.session.post(self.WARMUP_URL)
            self.logger.info(f"POST {self.WARMUP_URL}: {response.json()}")
            if response.status_code == 200 and response.json().get("code") == 0:
                return True
        except Exception as e:
            self.logger.info("Session validation failed:", e)
        return False

    def warm_up_session(self):
        # TODO: Consider removing or rewriting this method
        # Send a POST request to prolong the session.
        try:
            response = self.session.post(self.WARMUP_URL, headers=self.headers)
            if response.status_code == 200 and response.json().get("code") == 0:
                self.logger.info("Session prolonged successfully.")
            else:
                self.logger.info("Failed to prolong session.")
        except Exception as e:
            self.logger.info("Error during session warm-up:", e)

    @staticmethod
    def __parse_operations_json_response(data: dict) -> list[dict]:
        return data['body']['operations']

    def get_operations(self, _filter: SberBankOperationsFilter):
        payload = _filter.to_json()

        try:
            response = self.session.post(self.OPERATIONS_URL, json=payload, headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                if _filter.result_format == pd.DataFrame:
                    return pd.DataFrame(self.__parse_operations_json_response(data))
                else:
                    return self.__parse_operations_json_response(data)
            else:
                self.logger.info("Failed to get operations. Status code:", response.status_code)
        except Exception as e:
            self.logger.info("Error retrieving operations:", e)
        return None
