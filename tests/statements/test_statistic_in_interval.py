import pytest

from deirokay import data_reader, validate


@pytest.mark.parametrize(
    'scope, statistic, intervals, result',
    [
        ('NUM_TRANSACAO01', 'mean', {'>': 16780.0,
                                     '<': 16900.0}, 'pass'),
        ('PROD_VENDA', 'count', {'==': 17}, 'fail'),
        ('PROD_VENDA', 'count', {'==': 20}, 'pass'),
        ('PROD_VENDA', 'nunique', {'==': 17}, 'fail'),
        ('COD_MERC_SERV02', 'max', {'<=': 7100900}, 'pass'),
        ('COD_SETVENDAS', 'mode', {'>=': 6001628,
                                   '<=': 6001628}, 'pass'),
        ('NUMERO_PDV_ORIGIN', 'min', {'>=': 10.5,
                                      '<=': 11.5}, 'pass'),
        ('NUMERO_PDV_ORIGIN', 'max', {'>=': 12,
                                      '<=': 12.5}, 'pass'),
    ]
)
def test_statistic_in_interval(scope, statistic, intervals, result):
    df = data_reader('tests/transactions_sample.csv',
                     options='tests/options.yaml')
    assertions = {
        'name': 'statistic_in_interval',
        'items': [
            {
                'scope': scope,
                'statements': [
                    {
                        'type': 'statistic_in_interval',
                        'statistic': statistic,
                        **intervals
                    }
                ]
            }
        ]
    }
    report = (validate(df, against=assertions, raise_exception=False)
              ['items'][0]['statements'][0]['report'])
    print(report['detail']['actual_value'])
    assert report['result'] == result
