# SberBankApiClient

SberBankApiClient is a Python client that interacts with SberBank’s online services. It handles user authentication, session management, and operations retrieval using a live browser session (via Selenium and Selenium Wire). The client mimics human activity to keep the session alive, thereby avoiding the need for frequent manual re-logins.

## Features

- **User Authentication:**  
  Opens the SberBank login page so that users can log in manually. After login, the client extracts cookies, headers, and local storage information from the live session.

- **Session Persistence:**  
  Saves session data (cookies, headers, local storage, and node IDs) into a pickle file. The session is continuously kept alive by mimicking human-like actions and monitoring warm-up requests in the browser.

- **Automatic Session Keep-Alive:**  
  Two daemon threads are spawned immediately after login:
  1. **Human Activity Thread:**  
     Simulates random user actions (e.g., scrolling, refreshing, and even triggering operations requests) to mimic real human behavior on the web app.
  2. **Warm-Up Watch Thread:**  
     Monitors for warm-up session requests (POSTs to `/api/warmUpSession`) using Selenium Wire. When such a request is detected, the session data is automatically conserved (i.e., updated cookies, headers, etc., are saved).

- **Operations Retrieval:**  
  Supports fetching banking operations data in two ways:
  - **Via Requests Library:**  
    Uses the saved session data to send requests to the operations API endpoint.
  - **Via Browser's `fetch` API:**  
    Executes asynchronous JavaScript (via Selenium’s `execute_async_script`) to post directly from the browser, leveraging the live session (this approach avoids issues with proxy errors that may occur with the `requests` session).

- **Flexible Filtering:**  
  The `SberBankOperationsFilter` allows you to filter operations by type, date range, resource, and more. Results can be returned as either a Python dictionary or a pandas DataFrame.

## Project Structure

- **rubank_api_client/sber.py**  
  Contains the main `SberBankApiClient` class and `SberBankOperationsFilter` class. This file handles authentication, session management, simulation of human activity, warm-up monitoring, and operations retrieval (both via requests and via the browser).

- **tests/test_get_operations.py**  
  A test script that demonstrates how to use the client to retrieve operations data. It shows both the initial retrieval and how to fetch subsequent batches after waiting (simulating a long-running session).

- **requirements.txt**  
  Lists the project dependencies:
  - requests
  - selenium
  - selenium-wire
  - pandas
  - loguru
  - blinker==1.7.0
  - setuptools

## How It Works

1. **Initialization & Login:**
   - The client opens the SberBank login URL (`https://online.sberbank.ru/CSAFront/index.do`).
   - The user logs in manually.
   - The client waits for specific network requests to determine the SberBank node IDs (frontend and backend).
   - After login, session data (cookies, headers, local storage) is conserved in a pickle file for later reuse.

2. **Session Keep-Alive:**
   - **Human Activity Simulation:**  
     A daemon thread simulates random actions (scrolling, refreshing, etc.) on the operations page to keep the session active.
   - **Warm-Up Monitoring:**  
     A separate thread waits for warm-up requests (`/api/warmUpSession`) using Selenium Wire’s `wait_for_request`. When a warm-up request is detected, session data is updated to ensure that the session remains valid.

3. **Operations Retrieval:**
   - **get_operations_via_requests:**  
     Uses the `requests` library with the saved session cookies and headers to POST a JSON payload to the operations endpoint.
   - **get_operations:**  
     Executes an asynchronous JavaScript snippet in the browser context (using the live session) that makes a POST request via `fetch()`. This method bypasses issues that may occur if the `requests` session is used after prolonged inactivity.

## Usage Example

### SberBankOperationsFilter Usage

The `SberBankOperationsFilter` class allows you to customize the operations query. Its parameters include:

- **`operation_type`** *(str, optional)*:  
  Specify the type of operation. For example: `'income'`, `'outcome'`, `'transfers'`, etc.

- **`date_from`** *(str, optional)*:  
  The start date for filtering operations. Format: `"dd.mm.yyyyT00:00:00"` (e.g., `"01.02.2025T00:00:00"`).

- **`date_to`** *(str, optional)*:  
  The end date for filtering operations. Format: `"dd.mm.yyyyT23:59:59"` (e.g., `"15.02.2025T23:59:59"`).

- **`resource`** *(list, optional)*:  
  A list of resource identifiers to filter operations. For example: `["card:1100016973909570"]`.

- **`result_format`** *(any, optional)*:  
  Determines the format of the result. Supported formats are `dict` (for a dictionary output) or `pd.DataFrame` (for a pandas DataFrame).

- **`pagination_offset`** *(int, default=0)*:  
  Offset for pagination. If you have already retrieved a batch of operations, you can set this to the next index (e.g., 51 for the second batch if the batch size is 51).

- **`pagination_size`** *(int, default=51)*:  
  Number of operations to fetch per request (SberBank uses 51 by default; valid values are typically 1 to 200).

- **`show_hidden`** *(bool, default=False)*:  
  Whether to include hidden operations in the response.

### Example Usage of `SberBankOperationsFilter`

```python
from rubank_api_client import SberBankOperationsFilter

# Create a filter to retrieve income operations within a specific date range.
_filter = SberBankOperationsFilter(
    operation_type='income',          # Optional Type of operation (e.g., income, outcome, transfers, etc.)
    date_from='01.02.2025T00:00:00',     # Optional Start date (inclusive)
    date_to='15.02.2025T23:59:59',       # Optional End date (inclusive)
    resource=["card:1100016973909570"], # Optional list of resources to filter by
    pagination_size=51,                 # Number of operations per batch
    pagination_offset=0,                # Starting offset for pagination
    result_format=dict,                 # Format for results (can be dict or pd.DataFrame)
    show_hidden=False                   # Whether to include hidden operations
)
```

### Example Usage of `get_operations` method
Below is an example of how to use the client (as demonstrated in `tests/test_get_operations.py`):

```python
import time
import pandas as pd
from pprint import pprint
from rubank_api_client import SberBankApiClient, SberBankOperationsFilter

if __name__ == "__main__":
    # Initialize the client; user must log in manually when the browser opens.
    sbac = SberBankApiClient(path_to_cookies_file='../sber_cookies.pkl')

    # Create a filter for operations (customize the filter as needed)
    _filter = SberBankOperationsFilter(
        operation_type='income',
        date_from='01.02.2025T00:00:00',
        date_to='15.02.2025T23:59:59',
        pagination_size=51,
        pagination_offset=0,
        result_format=dict,
        show_hidden=False
    )

    # Retrieve operations using the browser's fetch (live session)
    operations_json = sbac.get_operations(_filter=_filter)
    pprint(operations_json)

    # (Optional) Retrieve operations as a pandas DataFrame:
    _filter.result_format = pd.DataFrame
    operations_df = sbac.get_operations(_filter=_filter)
    pprint(operations_df)

    # Example: Running a loop to fetch subsequent batches after waiting (simulate long-running usage)
    pagination_offset = 0
    while True:
        sbac.logger.info("Sleeping for 600 seconds...")
        time.sleep(600)  # Wait for 10 minutes
        _filter = SberBankOperationsFilter(
            pagination_size=51,
            pagination_offset=pagination_offset,
            result_format=dict,
            show_hidden=False
        )
        sbac.logger.info("Trying to get a new operations batch...")
        operations_batch = sbac.get_operations(_filter=_filter)
        sbac.logger.info("Got new operations batch:")
        pprint(operations_batch)

        pagination_offset += 51
```
