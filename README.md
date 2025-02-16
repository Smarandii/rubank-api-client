# SberBankApiClient

SberBankApiClient is a Python client designed to interact with SberBank's online services. It handles user authentication and session management, as well as retrieval of banking operations through secure API endpoints.

## Overview

The client is responsible for:
- Managing user sessions by handling cookies and headers.
- Performing user authentication via the SberBank login page.
- Maintaining a valid session by periodically "warming up" the session.
- Retrieving detailed operation data with customizable filters.

## Authentication Workflow

When an instance of the `SberBankApiClient` class is initialized, it follows one of two paths based on the state of stored session data.

### 1. No Saved or Expired Cookies & Headers

If there are no stored cookies and headers, or if they have expired, the client performs the following steps:

1. **Initialize Login Process:**  
   The client opens the SberBank login page:  
   `https://online.sberbank.ru/CSAFront/index.do`

2. **User Login:**  
   The user must log in with their SberBank credentials.

3. **User Authorization:**  
   After successful login, SberBank authorizes the user and redirects to:  
   `https://web1.online.sberbank.ru/main`

4. **Session Recognition:**  
   The client uses Selenium to detect that the current page is the authorized page (`https://web1.online.sberbank.ru/main`).

5. **Saving Session Data:**  
   The client extracts and saves all cookies and headers by monitoring network traffic for the POST request to:  
   `https://web1.online.sberbank.ru/api/log/report`  
   All headers and cookies used in this request are mimicked and stored.

6. **Success Notification:**  
   A success message is displayed indicating that the authentication process is complete.

### 2. Valid Saved Cookies & Headers

If valid cookies and headers already exist, the client:

1. **Validates the Session:**
   - Loads present cookies and headers from pickle file
   - Makes a POST request to `https://web1.online.sberbank.ru/api/warmUpSession`.  
   - A response of `{"code":0}` confirms that the session is valid.

2. **Success Notification:**  
   - A success message is displayed, confirming that the session is active.

## How to keep session alive:
When user is authorized sberbank creates session with 15 minutes lifespan. 
If we were to use SberBankApiClient for long periods of time we would need to log in manually every 15 minutes.
But there is actually a way to prolong life of your session - you need to perform warmUpSession requests:

In browser web app session is prolonged by sending a POST request to 
     `https://web1.online.sberbank.ru/api/warmUpSession` every 120-160 seconds, a request is sent to prolong the session.


# If your session is alive, then you can use SberBankApiClient methods:

## Operations Retrieval

The `get_operations` method is used to retrieve banking operations from SberBank's API. The process involves:

1. **Operations Endpoint:**  
   The endpoint for retrieving operations is:  
   `https://web-node1.online.sberbank.ru/uoh-bh/v1/operations/list`

2. **Filtering Operations:**  
   The API supports various filters via a JSON body in the request:
   
   - **Operation Types:**  
     Filters can be applied based on the type of operation:
     - `income` (пополнения)
     - `outcome` (расходы)
     - `financialTransactions` (Только финансовые операции)
     - `cashless` (Покупки и платежи)
     - `transfers` (Переводы)
     - `cash` (Наличные)
     - `stateNotifications` (Госуведомления)
     - `promo` (Предложения и промокоды)
   
   - **Date Range Filtering:**  
     Specify the range using `from` and `to` parameters with the date format:  
     `"dd.mm.yyyyT23:59:59"`  
     Example: `from="07.02.2025T23:59:59"` & `to="07.02.2025T23:59:59"`

   - **Resource Filtering:**  
     Use the `usedResource` parameter to filter operations by resource ID.  
     Example:
     ```json
     ["card:1100016973909570"]
     ```
     The resource ID can be extracted from a previous operations response (e.g., from `json["body"]["operations"][index]["fromResource"]["id"]`).

   - **Amount Filtering:**  
     The JSON body can include parameters such as `fromAmount` and `toAmount` to limit operations within a specified monetary range.  
     Example:
     ```json
     {
       "paginationOffset": 0,
       "paginationSize": 51,
       "filterName": "outcome",
       "fromAmount": 1,
       "toAmount": 10000000
     }
     ```
     This example filters withdrawal operations from 1 rouble up to 10 million roubles.

3. **Response Structure:**  
   A typical successful response from the operations endpoint has the following JSON structure:

   ```json
   {
     "success": true,
     "body": {
       "operations": [
         {
           "uohId": "string",
           "date": "dd.mm.yyyyTHH:MM:SS",
           "creationChannel": number,
           "form": "string",
           "state": {
             "name": "string",
             "category": "string"
           },
           "description": "string",
           "toResource": {
             "id": "string",
             "displayedValue": "string"
           },
           "correspondent": "string",
           "operationAmount": {
             "amount": number,
             "currencyCode": "RUB"
           },
           "nationalAmount": {
             "amount": number,
             "currencyCode": "RUB"
           },
           "attributes": {
             "copyable": boolean,
             "nfc": boolean,
             "cashReceipt": boolean,
             "compositePayment": boolean
           },
           "classificationCode": number,
           "type": "string",
           "billingAmount": {
             "amount": number,
             "currencyCode": "RUB"
           },
           "externalId": "string",
           "isFinancial": boolean
         }
       ]
     }
   }

4. **Code example:**  
```py
import pandas as pd
from pprint import pprint
from rubank_api_client import SberBankApiClient, SberBankOperationsFilter

if __name__ == "__main__":
    sbac = SberBankApiClient(path_to_cookies_file=None)

    _filter = SberBankOperationsFilter(
        operation_type='income',
        date_from='01.02.2025T00:00:00',
        date_to='15.02.2025T23:59:59',
        result_format=None
    )
    _filter.format = dict
    operations_json = sbac.get_operations(
        _filter=_filter
    )

    pprint(operations_json)

    _filter.format = pd.DataFrame
    operations_pandas_df = sbac.get_operations(
        _filter=_filter
    )

    pprint(operations_pandas_df)
```