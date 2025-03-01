import time
import pandas as pd
from pprint import pprint
from rubank_api_client import TBankApiClient, TBankOperationsFilter

if __name__ == "__main__":
    tbac = TBankApiClient(path_to_cookies_file='../tbank_cookies.pkl')

    _filter: TBankOperationsFilter = TBankOperationsFilter(
        date_from='01.02.2024T00:00:00',  # date_from
        date_to='15.04.2024T23:59:59',  # date_to
    )
    _filter.result_format = dict
    operations_json = tbac.get_operations(
        _filter=_filter
    )

    pprint(operations_json)

    _filter.result_format = pd.DataFrame
    operations_pandas_df = tbac.get_operations(
        _filter=_filter
    )

    pprint(operations_pandas_df)

    while True:
        tbac.logger.info("Sleeping for 600 seconds...")
        time.sleep(600)
        _filter: TBankOperationsFilter = TBankOperationsFilter(
            result_format=dict,  # dict or pd.DataFrame
        )
        tbac.logger.info("Trying to get new operations batch...")
        operations_json = tbac.get_operations(
            _filter=_filter
        )
        tbac.logger.info("Got new operations batch...")
        pprint(operations_json)
