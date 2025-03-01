import time
import random
import pickle
import loguru
import datetime
import requests
import threading
import pandas as pd

from seleniumwire import webdriver
from selenium.common import TimeoutException


class SberBankOperationsFilter:
    def __init__(
        self,
        operation_type: str = None,
        date_from: str = None,
        date_to: str = None,
        resource: list = None,
        result_format: any = None,
        pagination_offset: int = 0,
        pagination_size: int = 51,
        show_hidden=False
    ):
        self.type = operation_type
        self.date_from = date_from
        self.date_to = date_to
        self.resource = resource
        self.result_format = result_format if result_format == dict or result_format == pd.DataFrame else None
        self.pagination_offset = pagination_offset
        self.pagination_size = pagination_size
        self.show_hidden = show_hidden if isinstance(show_hidden, bool) else False
        self.logger = loguru.logger

        if result_format and not self.result_format:
            self.logger.warning(f"SberBankOperationsFilter doesn't support result format: {result_format}. "
                                f"result_format is set to None")

    def to_json(self):
        payload = {
            "filterName": self.type,
            "from": self.date_from,
            "to": self.date_to,
            "usedResource": self.resource,
            "paginationOffset": self.pagination_offset,
            "paginationSize": self.pagination_size,
            "showHidden": self.show_hidden
        }
        # Remove keys with None values
        return {key: value for key, value in payload.items() if value is not None}


class SberBankApiClient:
    LOGIN_URL = "https://online.sberbank.ru/CSAFront/index.do"

    def __init__(self, path_to_cookies_file: str = None):
        self.path_to_cookies_file = path_to_cookies_file if path_to_cookies_file else "sber_cookies.pkl"
        self.session = requests.Session()
        self.request_cookies = None
        self.selenium_driver_cookies = None
        self.headers = None
        self.logger = loguru.logger
        self.driver = webdriver.Chrome()

        # User logs in manually.
        self._login_and_save_session()
        self.logger.info("New session is created. You're in!")
        self.session_started = datetime.datetime.now()

        # Start two daemon threads:
        # 1. To simulate random human-like activity.
        # 2. To watch for warmUp session requests and conserve session data.
        self._start_activity_threads()

    def _start_activity_threads(self):
        human_activity_thread = threading.Thread(target=self._simulate_human_activity, daemon=True)
        warmup_watch_thread = threading.Thread(target=self._watch_warmup_requests, daemon=True)
        human_activity_thread.start()
        warmup_watch_thread.start()

    def _simulate_human_activity(self):
        """
        Periodically performs random actions (e.g. scrolling) to simulate human activity.
        """
        self.driver.get(self.OPERATIONS_PAGE_URL)
        while True:
            try:
                # Example: Scroll by a random amount.
                scroll_amount = random.randint(50, 200)
                self.driver.execute_script("window.scrollBy(0, arguments[0]);", scroll_amount)
                time.sleep(random.uniform(1, 3))
                self.driver.refresh()

                request = self.driver.wait_for_request(self.OPERATIONS_URL, timeout=10)
                self.logger.info(f"_simulate_human_activity invoked get operations request: {request}")
                self.headers = request.headers
                self.logger.info(f"get operations request headers: {request.headers}")
                self.SBERBANK_BACKEND_API_WEB_NODE_HEADERS = request.headers
                self.__conserve_session()

                self.logger.info(f"Simulated human activity: scrolled by {scroll_amount} pixels.")
            except Exception as e:
                self.logger.error(f"Error simulating human activity: {e}")
            # Wait a random period before next action.
            time.sleep(random.uniform(30, 60))

    def _watch_warmup_requests(self):
        """
        Waits for warmUp session requests using Selenium Wire's wait_for_request.
        When such a request is detected, session data is conserved.
        """
        while True:
            try:
                self.logger.info("Waiting for warmUp session request...")
                # Wait for a warmUp request. Adjust the timeout as needed.
                request = self.driver.wait_for_request(self.WARMUP_URL, timeout=800)
                if request:
                    self.logger.info("WarmUp session request detected.")
                    # Clear the request log to prevent memory buildup.
                    self.driver.requests.clear()
                    time.sleep(random.uniform(10, 40))
            except TimeoutException:
                self.logger.warning(f"Timeout occurred while waiting for warmUp request! "
                                    f"Session was kept alive for {datetime.datetime.now() - self.session_started}...")

                # TODO: Check if session is dead

                # TODO: Pause. Send alert to user via telegram with new QR code for re-creating session
                #  (if session is dead, otherwise do nothing)
            except Exception as e:
                self.logger.error(f"Error in warmUp watch thread: {e}")

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
        self.OPERATIONS_PAGE_URL = f"https://{self.SBERBANK_FRONTEND_WEB_NODE_ID}.online.sberbank.ru/operations"
        self.WARMUP_URL = f"https://{self.SBERBANK_FRONTEND_WEB_NODE_ID}.online.sberbank.ru/api/warmUpSession"
        self.LOG_REPORT_URL = f"https://{self.SBERBANK_FRONTEND_WEB_NODE_ID}.online.sberbank.ru/api/log/report"
        self.OPERATIONS_URL = f"https://{self.SBERBANK_BACKEND_API_WEB_NODE_ID}.online.sberbank.ru/uoh-bh/v1/operations/list"

    def _login_and_save_session(self):
        try:
            self.logger.info("No valid session found. Initiating login process...")
            self.driver.get(self.LOGIN_URL)
            self.logger.info("Waiting for the user to log in manually...")

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
                raise Exception(
                    f"Missing SBERBANK_FRONTEND_WEB_NODE_ID ({self.SBERBANK_FRONTEND_WEB_NODE_ID}) or "
                    f"SBERBANK_BACKEND_API_WEB_NODE_ID ({self.SBERBANK_BACKEND_API_WEB_NODE_ID})."
                )
        except TimeoutException:
            self.logger.error("Failed to wait for request to determine node ID values...")
        except Exception as e:
            self.logger.error(e)

        self.logger.info("Login successful. Retrieving session data...")
        self.__conserve_session()
        self.logger.info("Session data saved. You're in!")

    def __get_sber_frontend_web_node_id(self):
        self.logger.info("Waiting for request to determine SBERBANK_FRONTEND_WEB_NODE_ID...")
        request = self.driver.wait_for_request('/main', timeout=100)  # Adjust timeout as needed.
        return request.url.split(".")[:1:][0].split("https://")[1]

    def __get_sber_backend_api_web_node_id(self):
        self.logger.info("Waiting for request to determine SBERBANK_BACKEND_API_WEB_NODE_ID...")
        request = self.driver.wait_for_request('/main-screen/rest/v2/m1/web/section/meta', timeout=20)
        self.SBERBANK_BACKEND_API_WEB_NODE_HEADERS = request.headers
        endpoint_parts = request.url.split(".")
        return endpoint_parts[:1:][0].split("https://")[1]

    def __conserve_session(self):
        """
        Saves session data: cookies from the Selenium driver, headers, and local storage.
        Also updates the requests.Session with the latest cookies.
        """
        self.request_cookies = {cookie["name"]: cookie["value"] for cookie in self.driver.get_cookies()}
        self.selenium_driver_cookies = self.driver.get_cookies()
        self.session.cookies.update(self.request_cookies)

        self.headers = {
            "User-Agent": self.driver.execute_script("return navigator.userAgent;")
        }
        self.headers.update(self.SBERBANK_BACKEND_API_WEB_NODE_HEADERS)

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
        self.logger.info("Session conserved to file.")

    def get_local_storage(self):
        return self.driver.execute_script("""
            var ls = {};
            for (var i = 0; i < localStorage.length; i++) {
                var key = localStorage.key(i);
                ls[key] = localStorage.getItem(key);
            }
            return ls;
        """)

    @staticmethod
    def __parse_operations_json_response(data: dict) -> list[dict]:
        return data['body']['operations']

    def get_operations_via_requests(self, _filter: SberBankOperationsFilter):
        payload = _filter.to_json()
        response = self.session.post(
            self.OPERATIONS_URL, json=payload, headers=self.headers, cookies=self.request_cookies
        )
        if response.status_code == 200:
            data = response.json()
            if _filter.result_format == pd.DataFrame:
                return pd.DataFrame(self.__parse_operations_json_response(data))
            else:
                return self.__parse_operations_json_response(data)
        else:
            self.logger.info("Failed to get operations. Status code:", response.status_code)
        return None

    def get_operations(self, _filter: SberBankOperationsFilter):
        """
        Uses the browser's fetch() API to POST to the operations endpoint.
        This ensures the request is sent using the live browser session,
        thereby avoiding proxy issues that can occur with requests.Session.
        """
        payload = _filter.to_json()

        # The asynchronous script to run in the browser context.
        # It uses fetch() with credentials included.
        script = """
            const url = arguments[0];
            const payload = arguments[1];
            const additionalHeaders = arguments[2];
            const callback = arguments[3];
            fetch(url, {
                method: 'POST',
                credentials: 'include',
                headers: Object.assign({
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                }, additionalHeaders),
                body: JSON.stringify(payload)
            })
            .then(response => response.json())
            .then(data => callback(data))
            .catch(error => callback({'error': error.toString()}));
        """

        # Execute the async script in the browser.
        data = self.driver.execute_async_script(script, self.OPERATIONS_URL, payload, self.headers)

        # Check if an error occurred.
        if isinstance(data, dict) and 'error' in data:
            self.logger.error("Error fetching operations: " + data['error'])
            return None

        # Parse the response.
        operations = data.get('body', {}).get('operations', [])

        if _filter.result_format == pd.DataFrame:
            return pd.DataFrame(operations)
        else:
            return operations
