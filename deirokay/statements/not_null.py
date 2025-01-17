"""
Statement to check the number of not-null rows in a scope.
"""
from pandas import DataFrame

from .._typing import DeirokayStatement
from .base_statement import BaseStatement


class NotNull(BaseStatement):
    """Check if the rows of a scoped DataFrame are not null, possibly
    setting boundaries for the minimum and maximum percentage of
    not-null rows.

    The available options are:

    * `at_least_%`: The minimum percentage of not-null rows.
      Default: 100.0.
    * `at_most_%`: The maximum percentage of not-null rows.
      Default: 100.0.
    * `multicolumn_logic`: The logic to use when checking for not-null
      values in multicolumn scopes (either 'any' or 'all').
      Default: 'any'.

    Be careful When using multicolumn scopes: the `any` logic considers
    a row as null only if all columns are null.
    The `all` logic considers a row as null when any of its columns is
    null.

    Examples
    --------
    * You want to ensure that less than 1% of the values in a column
      `foo` are null. You can declare the following validation item:

    .. code-block:: json

        {
            "scope": "foo",
            "statements": [
                {
                    "name": "not_null",
                    "at_least_%": 99.0
                }
            ]
        }

    You noticed that you imposed a unrealistic value for `at_least_%`,
    and maybe less than 10% should be a reasonable percentage of null
    values.
    Still, you don't want to lose track of that ideal <= 1% checks,
    since you intend to improve your data quality in the near future.
    You may take advantage of `severity` to set different exception
    levels for different values of `at_least_%`:

    .. code-block:: json

        {
            "scope": "foo",
            "statements": [
                {
                    "name": "not_null",
                    "at_least_%": 99.0,
                    "severity": 3
                },
                {
                    "name": "not_null",
                    "at_least_%": 90.0,
                    "severity": 5
                }
            ]
        }

    This way, values between 90% and 99% will only raise a warning,
    while values below 90% will raise a validation exception (by
    default).

    * You don't tolerate any null values in a list of columns:

    .. code-block:: json

        {
            "scope": ["foo", "bar", "baz", "qux"],
            "statements": [
                {
                    "name": "not_null",
                    "multicolumn_logic": "all"
                }
            ]
        }

    """

    name = 'not_null'
    expected_parameters = ['at_least_%', 'at_most_%', 'multicolumn_logic']

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.at_least_perc = self.options.get('at_least_%', 100.0)
        self.at_most_perc = self.options.get('at_most_%', 100.0)
        self.multicolumn_logic = self.options.get('multicolumn_logic', 'any')

        assert self.multicolumn_logic in ('any', 'all')

    # docstr-coverage:inherited
    def report(self, df: DataFrame) -> dict:
        if self.multicolumn_logic == 'all':
            #  REMINDER: ~all == any
            not_nulls = ~df.isnull().any(axis=1)
        else:
            not_nulls = ~df.isnull().all(axis=1)

        report = {
            'null_rows': int((~not_nulls).sum()),
            'null_rows_%': float(100.0*(~not_nulls).sum()/len(not_nulls)),
            'not_null_rows': int(not_nulls.sum()),
            'not_null_rows_%': float(100.0*not_nulls.sum()/len(not_nulls)),
        }
        return report

    # docstr-coverage:inherited
    def result(self, report: dict) -> bool:
        if not report.get('not_null_rows_%') >= self.at_least_perc:
            return False
        if not report.get('not_null_rows_%') <= self.at_most_perc:
            return False
        return True

    # docstr-coverage:inherited
    @staticmethod
    def profile(df: DataFrame) -> DeirokayStatement:
        not_nulls = ~df.isnull().all(axis=1)

        statement = {
            'type': 'not_null'
        }  # type: DeirokayStatement

        at_least_perc = float(100.0*not_nulls.sum()/len(not_nulls))

        if at_least_perc == 0.0:
            raise NotImplementedError(
                'Statement is useless when all rows are null.'
            )

        if at_least_perc != 100.0:
            statement['at_least_%'] = at_least_perc

        return statement
