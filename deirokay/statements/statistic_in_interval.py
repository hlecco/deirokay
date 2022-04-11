"""
Statement to check the number of rows in a scope.
"""
import math

from pandas import DataFrame

from .base_statement import BaseStatement


class StatisticInInterval(BaseStatement):
    """Compare the actual value of a statistic for the scope against
    a list of comparison expressions.


    The available options are:

    * `statistic`: One of the following: 'min', 'max', 'mean', 'std',
        'var', 'count', 'nunique', 'sum', 'median', 'mode'.
    * One or more of the following comparators:
      `<`, `<=`, `==`, `!=`, `>=`, `>`.
    * `atol`: Absolute tolerance (for `==` and `!=`). Default is 0.0.
    * `rtol`: Absolute tolerance (for `==` and `!=`). Default is 1e-09.
    * `combination_logic`: 'and' or 'or'. Default is 'and'.

    Multiple comparison expressions can be used to represent multiple
    conditions. The `combination_logic` option can be set to express
    the logical relationship when grouping two or more comparisons.

    Examples
    --------

    To check if the mean of the 'a' column is between 0.4 and 0.6 and
    not equal to 0.5, its standard deviation is less than 0.1 or
    greater than 0.2, and its sum is equal to 1:

    .. code-block:: json

        {
            "scope": "a",
            "statements": [
                {
                    "name": "statistic_in_interval",
                    "statistic": "mean",
                    ">": 0.4,
                    "!=": 0.5,
                    "<": 0.6
                },
                {
                    "name": "statistic_in_interval",
                    "statistic": "std",
                    "<": 0.1,
                    ">": 0.2,
                    "combination_logic": "or"
                },
                {
                    "name": "statistic_in_interval",
                    "statistic": "sum",
                    "==": 1
                },
            ]
        }

    """

    name = 'statistic_in_interval'
    expected_parameters = [
        'statistic',
        '<', '<=', '>', '>=', '==', '!=',
        'combination_logic',
        'atol', 'rtol'
    ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.statistic = self.options['statistic']
        allowed_statistics = ['min', 'max', 'mean', 'std', 'var', 'count',
                              'nunique', 'sum', 'median', 'mode']
        assert self.statistic in allowed_statistics, (
            f"Invalid statistic '{self.statistic}'. "
            f"Allowed values are: {allowed_statistics}"
        )
        self.combination_logic = (
            self.options.get('combination_logic', 'and').lower()
        )
        assert self.combination_logic in ['and', 'or'], (
            f"Invalid combination logic '{self.combination_logic}'. "
            f"Allowed values are: 'and', 'or'"
        )
        self.less_than = self.options.get('<')
        self.less_or_equal_to = self.options.get('<=')
        self.equal_to = self.options.get('==')
        self.not_equal_to = self.options.get('!=')
        self.greater_or_equal_to = self.options.get('>=')
        self.greater_than = self.options.get('>')
        self.atol = self.options.get('atol', 0.0)
        self.rtol = self.options.get('rtol', 1e-09)

    # docstr-coverage:inherited
    def report(self, df: DataFrame) -> dict:
        actual_value = [
            getattr(df[col], self.statistic)() for col in df.columns
        ]
        if self.statistic == 'mode':
            actual_value = [float(vv) for v in actual_value for vv in v]
        else:
            actual_value = [float(v) for v in actual_value]

        report = {
            'actual_value': list(actual_value) if len(actual_value) > 1
            else actual_value[0]
        }
        return report

    # docstr-coverage:inherited
    def result(self, report: dict) -> bool:
        and_logic = self.combination_logic == 'and'
        actual_value = report['actual_value']
        if not isinstance(actual_value, list):
            actual_value = [actual_value]
        elif isinstance(actual_value[0], list):
            actual_value = [item for sublst in actual_value for item in sublst]

        for value in actual_value:
            if self.less_than is not None:
                if value < self.less_than:
                    if not and_logic:
                        return True
                else:
                    if and_logic:
                        return False

            if self.less_or_equal_to is not None:
                if value <= self.less_or_equal_to:
                    if not and_logic:
                        return True
                else:
                    if and_logic:
                        return False

            if self.equal_to is not None:
                if math.isclose(value, self.equal_to, abs_tol=self.atol, rel_tol=self.rtol):  # noqa: E501
                    if not and_logic:
                        return True
                else:
                    if and_logic:
                        return False

            if self.not_equal_to is not None:
                if not math.isclose(value, self.equal_to, abs_tol=self.atol, rel_tol=self.rtol):  # noqa: E501
                    if not and_logic:
                        return True
                else:
                    if and_logic:
                        return False

            if self.greater_or_equal_to is not None:
                if value >= self.greater_or_equal_to:
                    if not and_logic:
                        return True
                else:
                    if and_logic:
                        return False

            if self.greater_than is not None:
                if value > self.greater_than:
                    if not and_logic:
                        return True
                else:
                    if and_logic:
                        return False

        return and_logic
