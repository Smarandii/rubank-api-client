import os
import json
import time
import gzip
import random
import pickle
import loguru
import datetime
import requests
import threading
import pandas as pd
from seleniumwire import webdriver
from selenium.common import TimeoutException


class TBankOperationsFilter:
    def __init__(
            self,
            date_from: str = '31.12.2005T00:00:00',
            date_to: str = None,
            result_format: any = None
    ):
        self.logger = loguru.logger
        # Convert provided date strings to Unix timestamp (milliseconds)
        self.date_from = self._convert_date_to_timestamp(date_from)
        if date_to is None:
            # Use current time if not provided (in ms)
            self.date_to = str(int(datetime.datetime.now().timestamp() * 1000))
        else:
            self.date_to = self._convert_date_to_timestamp(date_to)

        # Allow only dict or pandas DataFrame as result_format
        self.result_format = result_format if result_format in (dict, pd.DataFrame) else None
        if result_format and not self.result_format:
            self.logger.warning(
                f"TBankOperationsFilter doesn't support result format: {result_format}. "
                f"result_format is set to None"
            )

    def _convert_date_to_timestamp(self, date_str: str) -> str:
        # If the string is numeric, assume it's already a timestamp (in ms)
        if date_str.isdigit():
            return date_str
        try:
            # Parse the string using the provided format (example: "01.02.2024T00:00:00")
            dt = datetime.datetime.strptime(date_str, "%d.%m.%YT%H:%M:%S")
            # Convert to Unix timestamp in milliseconds
            timestamp = int(dt.timestamp() * 1000)
            return str(timestamp)
        except Exception as e:
            self.logger.error(f"Error parsing date '{date_str}': {e}")
            raise

    def to_json(self):
        if not (self.date_to and self.date_from):
            raise Exception("date_to and date_from parameters are required! "
                            "Example: date_to='31.12.2024T00:00:00', date_from='31.12.2005T00:00:00'")
        return {
            "start": self.date_from,
            "end": self.date_to
        }


class TBankApiClient:
    LOGIN_URL = "https://www.tbank.ru/login/"
    MAIN_URL = "https://www.tbank.ru/mybank/"
    OPERATIONS_PAGE_URL = "https://www.tbank.ru/events/feed/?preset=all&pieType=Debit"
    AUTH_CHECK_URL = "https://www.tbank.ru/api/common/v1/session/check_auth"

    SESSION_STATUS_ENDPOINT = "https://www.tbank.ru/api/common/v1/session_status"
    OPERATIONS_ENDPOINT_REGEX = \
        r"^https://www\.tbank\.ru/api/common/v1/operations(?!(_piechart|_histogram|_category_list)).*"

    # self.LOG_REPORT_URL = f"https://www.tbank.ru/api/front/log/collect"

    # self.OPERATIONS_PIE_CHART_URL = f"https://www.tbank.ru/api/common/v1/operations_piechart?
    # config=spending&end=1743465599000&groupBy=spendingCategory&start=1740776400000&trancheCreationAllowed=false&
    # sessionid=6ufDbQczM0U0h96w92XrlA8O8T6Ty4lw.m1-prod-api-026&wuid=a576971cf8abf006c861b0fe100a8f13"

    # self.USER_INFO_URL = "GET https://tmsg.tbank.ru/app/bank/messenger/userInfo"

    def __init__(self, path_to_cookies_file: str = "tbank_cookies.pkl"):
        self.operations_file = '../tbank_operations.json'

        self.login_timeout_seconds = 240
        self.operations_page_timeout_seconds = 100
        self.path_to_cookies_file = path_to_cookies_file
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
        self.all_operations = json.loads(self.operations_file)

        # Start two daemon threads:
        # 1. To simulate random human-like activity.
        # 2. To watch for warmUp session requests and conserve session data.
        self._start_activity_threads()

    def _start_activity_threads(self):
        watch_session_status_thread = threading.Thread(target=self._watch_session_status_requests, daemon=True)
        watch_session_status_thread.start()

        watch_get_operations_requests_thread = threading.Thread(target=self._watch_get_operations_requests, daemon=True)
        watch_get_operations_requests_thread.start()

        human_activity_thread = threading.Thread(target=self._simulate_human_activity, daemon=True)
        human_activity_thread.start()

    def _simulate_human_activity(self):
        """
        Periodically performs random actions (e.g. scrolling) to simulate human activity.
        """
        self.driver.get(self.OPERATIONS_PAGE_URL)
        while True:
            try:
                scroll_amount = random.randint(50, 200)
                self.driver.execute_script("window.scrollBy(0, arguments[0]);", scroll_amount)
                time.sleep(random.uniform(1, 3))
                self.driver.refresh()

                request = self.driver.wait_for_request(self.OPERATIONS_ENDPOINT_REGEX, timeout=10)
                self.logger.info(f"_simulate_human_activity invoked get operations request: {request}")
                self.headers = request.headers
                self.logger.info(f"get operations request headers: {request.headers}")
                self.__conserve_session()

                self.logger.info(f"Simulated human activity: scrolled by {scroll_amount} pixels.")
            except Exception as e:
                self.logger.error(f"Error simulating human activity: {e}")
            # Wait a random period before next action.
            time.sleep(random.uniform(30, 60))

    def _watch_session_status_requests(self):
        """
        Waits for warmUp session requests using Selenium Wire's wait_for_request.
        When such a request is detected, session data is conserved.
        """
        while True:
            try:
                self.logger.info("Waiting for session status request...")
                # Wait for a warmUp request. Adjust the timeout as needed.
                request = self.driver.wait_for_request(self.SESSION_STATUS_ENDPOINT, timeout=800)
                self.__initialize_tbank_public_api_endpoints(request.params)
                self.headers = request.headers

                if request:
                    self.logger.info("Session status request detected.")
                    # Clear the request log to prevent memory buildup.
                    self.driver.requests.clear()
                    time.sleep(random.uniform(10, 40))
            except TimeoutException:
                self.logger.warning(f"Timeout occurred while waiting for session status request! "
                                    f"Session was kept alive for {datetime.datetime.now() - self.session_started}...")

                # TODO: Check if session is dead

                # TODO: Pause. Send alert to user via telegram with new QR code for re-creating session
                #  (if session is dead, otherwise do nothing)
            except Exception as e:
                self.logger.error(f"Error in session status watch thread: {e}")

    def _watch_get_operations_requests(self):
        while True:
            try:
                self.logger.info("Waiting for get_operations request...")
                # Wait for a warmUp request. Adjust the timeout as needed.
                request = self.driver.wait_for_request(self.OPERATIONS_ENDPOINT_REGEX, timeout=800)
                self.__initialize_tbank_public_api_endpoints(request.params)
                self.headers = request.headers

                if request:
                    self.logger.info("get_operations request detected.")
                    self.__save_new_operations_to_cache_file(request.response.body)
                    # Clear the request log to prevent memory buildup.
                    self.driver.requests.clear()
                    time.sleep(random.uniform(10, 40))
            except Exception as e:
                self.logger.error(f"Error in _watch_get_operations_requests thread: {e}")

    def __initialize_tbank_public_api_endpoints(
            self,
            params: dict = None
    ):
        pass
        # self.tbank_app_name: str = params['tbank_app_name'] if params else None
        # self.tbank_app_version: str = params['tbank_app_version'] if params else None
        # self.origin: str = params['origin'] if params else None
        # self.sessionid: str = params['sessionid'] if params else None
        # self.wuid: str = params['wuid'] if params else None
        #
        # if not (self.tbank_app_name and self.tbank_app_version and self.origin and self.sessionid and self.wuid):
        #     raise Exception("Parameters missing some of the must have values...")
        #
        # self.SESSION_STATUS_URL = (
        #     f"https://www.tbank.ru/api/common/v1/session_status?"
        #     f"appName={self.tbank_app_name}&"
        #     f"appVersion={self.tbank_app_version}&"
        #     f"origin={self.origin}&"
        #     f"sessionid={self.sessionid}&"
        #     f"wuid={self.wuid}"
        # )
        # self.OPERATIONS_URL = (
        #     f"https://www.tbank.ru/api/common/v1/operations?"
        #     f"sessionid={self.sessionid}&"
        #     f"wuid={self.wuid}"
        # )

    def __load_cached_operations(self):
        """
        Loads the cached operations from the JSON file.
        Returns a dict keyed by each operation's unique id.
        If the file does not exist or is empty, returns an empty dict.
        """
        if not os.path.exists(self.operations_file):
            return {}
        try:
            with open(self.operations_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    operations = json.loads(content)
                else:
                    operations = {}
        except Exception as e:
            self.logger.error(f"Error loading cached operations: {e}")
            operations = {}
        return operations

    def __save_new_operations_to_cache_file(self, get_operations_body: bytes):
        """
        Extracts operations from the raw response bytes,
        merges them with any existing operations in the cache,
        and saves the unique set back to the file.
        """
        # Load existing operations (if any)
        existing_operations = self.__load_cached_operations()
        # self.logger.debug(f"existing_operations: {existing_operations}")
        try:
            # If the data is gzip-compressed (first two bytes are 0x1f, 0x8b), decompress it.
            # self.logger.debug(f"get_operations_body: {get_operations_body}")
            if get_operations_body.startswith(b'\x1f\x8b'):
                get_operations_body = gzip.decompress(get_operations_body)
                # self.logger.debug(f"Decompressed gzip get_operations_body: {get_operations_body}")
            # Decode and load the JSON response from the API
            # self.logger.debug(f"UTF-8 decoded: {get_operations_body.decode("utf-8")}")
            new_data = json.loads(get_operations_body.decode("utf-8"))
            # Expect operations to be in the "payload" key (a list)
            # self.logger.debug(f"Deserialized object: {new_data}")
            new_operations = new_data.get("payload", [])
            # Merge each new operation into the existing dictionary using its unique id
            for op in new_operations:
                op_id = op.get("id")
                if op_id:
                    existing_operations[op_id] = op
            # Save the merged operations dictionary back to file (overwrite existing file)
            with open(self.operations_file, "w", encoding="utf-8") as f:
                self.all_operations = existing_operations
                json.dump(existing_operations, f, ensure_ascii=False, indent=4)
        except Exception as e:
            self.logger.error(f"Error processing new operations: {e}")

    def _login_and_save_session(self):
        try:
            self.logger.info("No valid session found. Initiating login process...")
            self.driver.get(self.LOGIN_URL)
            self.logger.info(f"Waiting {self.login_timeout_seconds} seconds for the user to log in manually...")
            self.driver.wait_for_request(self.MAIN_URL, self.login_timeout_seconds)

            self.logger.info(f"Opening operations page...")
            self.driver.get(self.OPERATIONS_PAGE_URL)
            request = self.driver.wait_for_request(self.OPERATIONS_ENDPOINT_REGEX,
                                                   timeout=self.operations_page_timeout_seconds)
            self.headers = request.headers
            self.__initialize_tbank_public_api_endpoints(request.params)

            if request:
                self.logger.info("get_operations request detected.")
                self.__save_new_operations_to_cache_file(request.response.body)

        except TimeoutException:
            self.logger.error(f"User didn't logged in in {self.login_timeout_seconds} seconds...")
        except Exception as e:
            self.logger.error(e)

        self.logger.info("Login successful. Retrieving session data...")
        self.__conserve_session()
        self.logger.info("Session data saved. You're in!")

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

        session_data = {
            "cookies": self.request_cookies,
            "selenium_driver_cookies": self.selenium_driver_cookies,
            "headers": self.headers,
            "local_storage": self.get_local_storage()
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

    def get_operations(self, _filter: TBankOperationsFilter):
        """
        Loads all cached operations, filters them according to the provided TBankOperationsFilter,
        and returns the result in the desired format (either as a list of dicts or a pandas DataFrame).
        Filtering is done based on the 'debitingTime' field (milliseconds).
        """
        # Load all cached operations (a dict keyed by operation id)
        cached_ops = self.all_operations
        # Convert the filter's date_from and date_to to integers (assumed to be in milliseconds)
        date_from = int(_filter.date_from)
        date_to = int(_filter.date_to)
        # Filter operations based on their debitingTime milliseconds value
        filtered_ops = [
            op for op in cached_ops.values()
            if op.get("debitingTime", {}).get("milliseconds") is not None and
            date_from <= int(op["debitingTime"]["milliseconds"]) <= date_to
        ]
        # Return result as DataFrame or list, depending on _filter.result_format
        if _filter.result_format == pd.DataFrame:
            return pd.DataFrame(filtered_ops)
        else:
            return filtered_ops
