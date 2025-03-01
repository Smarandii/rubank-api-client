import time

import pandas as pd
from pprint import pprint
from rubank_api_client import SberBankApiClient, SberBankOperationsFilter

if __name__ == "__main__":
    sbac = SberBankApiClient(path_to_cookies_file='../sberbank_cookies.pkl')

    _filter: SberBankOperationsFilter = SberBankOperationsFilter(
        # operation_type='income',  # operation_type optional
        # date_from='01.02.2024T00:00:00',  # date_from optional
        # date_to='15.04.2024T23:59:59',  # date_to optional
        pagination_size=51,  # number from 1 to 200, sberbank uses 51 by default
        pagination_offset=0,
        # To see more than 50 operations increase pagination_offset
        # (e.g. we already got 50 operations, we need to set pagination_offset to 50 to see next 50 operations)
        result_format=None,  # dict or pd.DataFrame
        show_hidden=False  # Unknown filter, sberbank uses False by default
    )
    _filter.result_format = dict
    operations_json = sbac.get_operations(
        _filter=_filter
    )

    pprint(operations_json)

    # _filter.result_format = pd.DataFrame
    # operations_pandas_df = sbac.get_operations(
    #     _filter=_filter
    # )
    #
    # pprint(operations_pandas_df)

    pagination_offset = 0
    while True:
        sbac.logger.info("Sleeping for 600 seconds...")
        time.sleep(600)
        _filter: SberBankOperationsFilter = SberBankOperationsFilter(
            # operation_type='income',  # operation_type optional
            # date_from='01.02.2024T00:00:00',  # date_from optional
            # date_to='15.04.2024T23:59:59',  # date_to optional
            pagination_size=51,  # number from 1 to 200, sberbank uses 51 by default
            pagination_offset=pagination_offset,
            # To see more than 50 operations increase pagination_offset
            # (e.g. we already got 50 operations, we need to set pagination_offset to 50 to see next 50 operations)
            result_format=dict,  # dict or pd.DataFrame
            show_hidden=False  # Unknown filter, sberbank uses False by default
        )
        sbac.logger.info("Trying to get new operations batch...")
        operations_json = sbac.get_operations(
            _filter=_filter
        )
        sbac.logger.info("Got new operations batch...")
        pprint(operations_json)

        pagination_offset += 51
