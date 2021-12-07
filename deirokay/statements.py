"""
Module for BaseStatement and builtin Deirokay statements.
"""

from typing import Optional

import numpy as np
import pandas as pd
from jinja2 import BaseLoader
from jinja2.nativetypes import NativeEnvironment

from .fs import FileSystem
from .history_template import get_series
from .parser import get_dtype_treater, get_treater_instance


class BaseStatement:
    """Base abstract statement class for all Deirokay statements.

    Parameters
    ----------
    options : dict
        Statement parameters provided by user.
    read_from : Optional[FileSystem], optional
        Where read past validation logs from
        (necessary for templated moving statistics).
        By default None.

    Attributes
    ----------
    name : str
        Statement name when referred in Validation Documents (only
        valid for non-custom statements).
    expected_parameters : List[str]
        Parameters expected for this statement.
    table_only : bool
        Whether or not this statement in applicable only to the entire
        table, instead of scoped columns.
    jinjaenv : NativeEnvironment
        Jinja Environment to use when rendering templates. Only for
        advanced users.
    """

    name = 'base_statement'
    expected_parameters = ['type', 'severity', 'location']
    table_only = False
    jinjaenv = NativeEnvironment(loader=BaseLoader())

    def __init__(self, options: dict, read_from: Optional[FileSystem] = None):
        self._validate_options(options)
        self.options = options
        self._read_from = read_from
        self._parse_options()

    def _validate_options(self, options: dict):
        """Make sure all providded statement parameters are expected
        by statement classes"""
        cls = type(self)
        unexpected_parameters = [
            option for option in options
            if option not in (cls.expected_parameters +
                              BaseStatement.expected_parameters)
        ]
        if unexpected_parameters:
            raise ValueError(
                f'Invalid parameters passed to {cls.__name__} statement: '
                f'{unexpected_parameters}\n'
                f'The valid parameters are: {cls.expected_parameters}'
            )

    def _parse_options(self):
        """Render Jinja templates in statement parameters."""
        for key, value in self.options.items():
            if isinstance(value, str):
                rendered = (
                    BaseStatement.jinjaenv.from_string(value)
                    .render(
                        series=lambda x, y: get_series(x, y, self._read_from)
                    )
                )
                self.options[key] = rendered

    def __call__(self, df: pd.DataFrame):
        """Run statement instance."""
        internal_report = self.report(df)
        result = self.result(internal_report)

        final_report = {
            'detail': internal_report,
            'result': result
        }
        return final_report

    def report(self, df: pd.DataFrame) -> dict:
        """Receive a DataFrame containing only columns on the scope of
        validation and returns a report of related metrics that can
        be used later to declare this Statement as fulfilled or
        failed.

        Parameters
        ----------
        df : pd.DataFrame
            The scoped DataFrame columns to be analysed in this report
            by this statement.

        Returns
        -------
        dict
            A dictionary of useful statistics about the target columns.
        """
        return {}

    def result(self, report: dict) -> bool:
        """Receive the report previously generated and declare this
        statement as either fulfilled (True) or failed (False).

        Parameters
        ----------
        report : dict
            Report generated by `report` method. Should ideally
            contain all statistics necessary to evaluate the statement
            validity.

        Returns
        -------
        bool
            Whether or not this statement passed.
        """
        return True

    @staticmethod
    def profile(df: pd.DataFrame) -> dict:
        """Given a template data table, generate a statement dict
        from it.

        Parameters
        ----------
        df : pd.DataFrame
            The DataFrame to be used as template.

        Returns
        -------
        dict
            Statement dict.
        """
        raise NotImplementedError


# docstr-coverage:inherited
class Unique(BaseStatement):
    """Check if the rows of a scoped DataFrame are unique."""

    name = 'unique'
    expected_parameters = ['at_least_%']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.at_least_perc = self.options.get('at_least_%', 100.0)

    # docstr-coverage:inherited
    def report(self, df):
        unique = ~df.duplicated(keep=False)

        report = {
            'unique_rows': int(unique.sum()),
            'unique_rows_%': float(100.0*unique.sum()/len(unique)),
        }
        return report

    # docstr-coverage:inherited
    def result(self, report):
        return report.get('unique_rows_%') >= self.at_least_perc

    # docstr-coverage:inherited
    @staticmethod
    def profile(df):
        unique = ~df.duplicated(keep=False)

        statement = {
            'type': 'unique',
            'at_least_%': float(100.0*unique.sum()/len(unique)),
        }
        return statement


# docstr-coverage:inherited
class NotNull(BaseStatement):
    """Check if the rows of a scoped DataFrame are not null."""

    name = 'not_null'
    expected_parameters = ['at_least_%', 'at_most_%', 'multicolumn_logic']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.at_least_perc = self.options.get('at_least_%', 100.0)
        self.at_most_perc = self.options.get('at_most_%', 100.0)
        self.multicolumn_logic = self.options.get('multicolumn_logic', 'any')

        assert self.multicolumn_logic in ('any', 'all')

    # docstr-coverage:inherited
    def report(self, df):
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
    def result(self, report):
        if not report.get('not_null_rows_%') >= self.at_least_perc:
            return False
        if not report.get('not_null_rows_%') <= self.at_most_perc:
            return False
        return True

    # docstr-coverage:inherited
    @staticmethod
    def profile(df):
        not_nulls = ~df.isnull().all(axis=1)

        statement = {
            'type': 'not_null',
            'multicolumn_logic': 'any',
            'at_least_%': float(100.0*not_nulls.sum()/len(not_nulls)),
            'at_most_%': float(100.0*not_nulls.sum()/len(not_nulls))
        }
        return statement


# docstr-coverage:inherited
class RowCount(BaseStatement):
    """Check if the number of rows in a DataFrame is within a
    range."""

    name = 'row_count'
    expected_parameters = ['min', 'max']
    table_only = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.min = self.options.get('min', None)
        self.max = self.options.get('max', None)

    # docstr-coverage:inherited
    def report(self, df):
        row_count = len(df)

        report = {
            'rows': row_count,
        }
        return report

    # docstr-coverage:inherited
    def result(self, report):
        row_count = report['rows']

        if self.min is not None:
            if not row_count >= self.min:
                return False
        if self.max is not None:
            if not row_count <= self.max:
                return False
        return True

    # docstr-coverage:inherited
    @staticmethod
    def profile(df):
        row_count = len(df)

        statement = {
            'type': 'row_count',
            'min': row_count,
            'max': row_count,
        }
        return statement


class Contain(BaseStatement):
    """
    Checks if a given column contains specific values. We can also
    check the number of their occurrences, specifying a minimum and
    maximum value of frequency.
    """
    name = 'contain'
    expected_parameters = [
        'rule',
        'values',
        'parser',
        'occurrences_per_value',
        'min_occurrences',
        'max_occurrences',
        'verbose'
    ]
    table_only = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.rule = self.options['rule']
        self.treater = get_treater_instance(self.options['parser'])
        self.values = self.treater(self.options['values'])

        self.min_occurrences = self.options.get('min_occurrences', None)
        self.max_occurrences = self.options.get('max_occurrences', None)
        self.occurrences_per_value = self.options.get(
            'occurrences_per_value', {}
        )
        self.verbose = self.options.get('verbose', True)

        self._set_default_minmax_occurrences()
        self._assert_parameters()

    def _set_default_minmax_occurrences(self):
        min_occurrences_rule_default = {
            'all': 1,
            'only': 0,
            'all_and_only': 1
        }
        max_occurrences_rule_default = {
            'all': np.inf,
            'only': np.inf,
            'all_and_only': np.inf
        }

        if self.min_occurrences is None:
            self.min_occurrences = min_occurrences_rule_default[self.rule]
        if self.max_occurrences is None:
            self.max_occurrences = max_occurrences_rule_default[self.rule]

    def _assert_parameters(self):
        assert self.rule in ('all', 'only', 'all_and_only')
        assert self.min_occurrences >= 0
        assert self.max_occurrences >= 0

    # docstr-coverage:inherited
    def report(self, df):
        count_isin = (
            pd.concat(df[col] for col in df.columns).value_counts()
        )
        self.value_count = count_isin.to_dict()

        keys = self.treater.serialize(self.value_count.keys())['values']
        values = (int(freq) for freq in self.value_count.values())
        report = {
            'value_frequency': dict(zip(keys, values))
        }
        if self.verbose:
            total = int(count_isin.sum())
            values = (
                int(freq)*100/total for freq in self.value_count.values()
            )
            report['value_rel_frequency_%'] = dict(zip(keys, values))
        return report

    # docstr-coverage:inherited
    def result(self, report):
        self._set_min_max_boundaries(self.value_count)
        self._set_values_scope()

        if not self._check_interval(self.value_count):
            return False
        if not self._check_rule(self.value_count):
            return False
        return True

    def _set_min_max_boundaries(self, value_count):
        # Global boundaries
        min_max_boundaries = {}
        for value in self.values:
            min_max_boundaries.update({
                value: {
                    'min_occurrences': self.min_occurrences,
                    'max_occurrences': self.max_occurrences
                }
            })

        # Dedicated boundaries
        if self.occurrences_per_value:
            for occurrence in self.occurrences_per_value:
                values = occurrence['values']
                values = [values] if not isinstance(values, list) else values
                values = self.treater(values)

                for value in values:
                    min_max_boundaries[value][
                        'min_occurrences'
                    ] = occurrence.get(
                        'min_occurrences', self.min_occurrences
                    )

                    min_max_boundaries[value][
                        'max_occurrences'
                    ] = occurrence.get(
                        'max_occurrences', self.max_occurrences
                    )

        self.min_max_boundaries = min_max_boundaries

    def _set_values_scope(self):
        """
        Set the scope of values to be analyzed according to the given
        `self.rule`. Excludes the cases of values where its
        corresponding `max_occurrences` is zero, since these cases
        won't matter for the `rule` analysis, as they must be absent
        in the column.
        """
        values_col = [
            value for value in self.min_max_boundaries
            if self.min_max_boundaries[value]['max_occurrences'] != 0
        ]
        self.values_scope_filter = values_col

    def _check_interval(self, value_count):
        """
        Check if each value is inside an interval of min and max
        number of occurrencies. These values are set globally in
        `self.min_occurrencies` and `self.max_occurrencies`, but the
        user can specify dedicated intervals for a given value in
        `self.occurrences_per_value`
        """
        for value in self.values:
            min_value = self.min_max_boundaries[value][
                'min_occurrences'
            ]
            max_value = self.min_max_boundaries[value][
                'max_occurrences'
            ]
            if value in value_count:
                if not (
                    min_value <= value_count[value] <= max_value
                ):
                    return False
            else:
                if self.rule != 'only' and max_value != 0 and min_value != 0:
                    return False
        return True

    def _check_rule(self, value_count):
        """
        Checks if given columns attend the given requirements
        of presence or absence of values, according to a criteria
        specified in `self.rule`

        Parameters
        ----------
        value_count: dict
            Got from `report` method, it contains the count of
            occurrences for each column for each value

        Notes
        -----
        `self.rule` parameter defines the criteria to use for checking
        the presence or absence of values in a column. Its values
        should be:

        * all: all the values in `self.values` are present in the
        column, but there can be other values also
        * only: only the values in `self.values` (but not necessarilly
        all of them) are present in the given column
        * all_and_only: the column must contain exactly the values in
          `self.values` - neither more than less. As the name says, it
          is an `and` boolean operation between `all` and `only` modes
        """
        if self.rule == 'all':
            return self._check_all(value_count)
        elif self.rule == 'only':
            return self._check_only(value_count)
        elif self.rule == 'all_and_only':
            is_check_all = self._check_all(value_count)
            is_check_only = self._check_only(value_count)
            return is_check_all and is_check_only

    def _check_all(self, value_count):
        """
        Checks if values in df contains all the expected values
        """
        values_in_col = set(value_count.keys())
        values = set(self.values_scope_filter)
        if values - values_in_col:
            return False
        return True

    def _check_only(self, value_count):
        """
        Checks if all values in df are inside the expected values
        """
        values_in_col = set(value_count.keys())
        values = set(self.values_scope_filter)
        if values_in_col - values:
            return False
        return True

    # docstr-coverage:inherited
    @staticmethod
    def profile(df):
        series = pd.concat(df[col] for col in df.columns)

        value_frequency = series.value_counts()
        min_occurrences = int(value_frequency.min())
        max_occurrences = int(value_frequency.max())

        # unique series
        series = series.drop_duplicates()

        statement_template = {
            'type': 'contain',
            'rule': 'all_and_only'
        }
        # Get most common type to infer treater
        try:
            statement_template.update(
                get_dtype_treater(series.map(type).mode()[0])
                .serialize(series)
            )
        except TypeError:
            raise NotImplementedError("Can't handle mixed types")
        statement_template['values'].sort()

        if min_occurrences != 1:
            statement_template['min_occurrences'] = min_occurrences
        statement_template['max_occurrences'] = max_occurrences

        return statement_template
