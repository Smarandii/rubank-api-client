import pandas as pd
from pprint import pprint
from rubank_api_client import SberBankApiClient, SberBankOperationsFilter

if __name__ == "__main__":
    sbac = SberBankApiClient(path_to_cookies_file='../cookies.pkl')

    _filter: SberBankOperationsFilter = SberBankOperationsFilter(
        operation_type='income',
        date_from='01.02.2025T00:00:00',
        date_to='15.02.2025T23:59:59',
        pagination_size=100,
        pagination_offset=0,
        result_format=None
    )
    _filter.result_format = dict
    operations_json = sbac.get_operations(
        _filter=_filter
    )

    pprint(operations_json)

    _filter.result_format = pd.DataFrame
    operations_pandas_df = sbac.get_operations(
        _filter=_filter
    )

    pprint(operations_pandas_df)

    pass