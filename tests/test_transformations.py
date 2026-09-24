import pandas as pd
import pytest

from app.etl.registry import TRANSFORMATIONS, get_transformation
from app.etl.transformations.dates import ParseDate
from app.etl.transformations.duplicates import RemoveDuplicates
from app.etl.transformations.email import NormalizeEmail
from app.etl.transformations.nulls import DropNullRows, FillNull
from app.etl.transformations.numeric import NormalizeNumeric
from app.etl.transformations.whitespace import TrimWhitespace


def test_registry_contains_expected_operations():
    for op in [
        "trim_whitespace",
        "normalize_email",
        "normalize_phone",
        "parse_date",
        "normalize_numeric",
        "fill_null",
        "drop_null_rows",
        "remove_duplicates",
        "normalize_category",
    ]:
        assert op in TRANSFORMATIONS


def test_get_transformation_unknown_operation_raises():
    with pytest.raises(ValueError):
        get_transformation("drop_table_students")  # not in allowlist


class TestTrimWhitespace:
    def test_normal_data(self):
        df = pd.DataFrame({"name": [" Alice ", "Bob"]})
        t = TrimWhitespace()
        assert t.detect(df) == 1
        result = t.apply(df)
        assert result["name"].tolist() == ["Alice", "Bob"]

    def test_empty_data(self):
        df = pd.DataFrame({"name": []})
        t = TrimWhitespace()
        assert t.detect(df) == 0
        assert t.apply(df).empty

    def test_nulls_are_preserved(self):
        df = pd.DataFrame({"name": [" Alice ", None]})
        t = TrimWhitespace()
        result = t.apply(df)
        assert pd.isna(result["name"].iloc[1])

    def test_idempotent(self):
        df = pd.DataFrame({"name": [" Alice ", "Bob"]})
        t = TrimWhitespace()
        once = t.apply(df)
        twice = t.apply(once)
        assert once["name"].tolist() == twice["name"].tolist()

    def test_already_clean_data(self):
        df = pd.DataFrame({"name": ["Alice", "Bob"]})
        t = TrimWhitespace()
        assert t.detect(df) == 0


class TestRemoveDuplicates:
    def test_normal_data(self):
        df = pd.DataFrame({"id": [1, 1, 2], "name": ["A", "A", "B"]})
        t = RemoveDuplicates()
        assert t.detect(df) == 1
        result = t.apply(df)
        assert len(result) == 2

    def test_no_silent_extra_row_loss(self):
        df = pd.DataFrame({"id": [1, 2, 3]})
        t = RemoveDuplicates()
        result = t.apply(df)
        assert len(result) == len(df)

    def test_validate_reports_removed_count(self):
        df = pd.DataFrame({"id": [1, 1, 2]})
        t = RemoveDuplicates()
        after = t.apply(df)
        validation = t.validate(df, after)
        assert validation["duplicates_removed"] == 1


class TestFillNullAndDropNullRows:
    def test_fill_null_normal(self):
        df = pd.DataFrame({"amount": [1, None, 3]})
        t = FillNull()
        assert t.detect(df) == 1
        result = t.apply(df, value=0)
        assert result["amount"].tolist() == [1, 0, 3]

    def test_drop_null_rows_normal(self):
        df = pd.DataFrame({"amount": [1, None, 3]})
        t = DropNullRows()
        result = t.apply(df)
        assert len(result) == 2

    def test_drop_null_rows_empty_data(self):
        df = pd.DataFrame({"amount": []})
        t = DropNullRows()
        assert t.apply(df).empty


class TestNormalizeEmail:
    def test_normal_and_malformed(self):
        df = pd.DataFrame({"email": [" JOHN@EXAMPLE.COM ", "not-an-email", None]})
        t = NormalizeEmail()
        result = t.apply(df)
        assert result["email"].iloc[0] == "john@example.com"
        assert result["email"].iloc[1] == "not-an-email"
        assert pd.isna(result["email"].iloc[2])

    def test_idempotent(self):
        df = pd.DataFrame({"email": [" JOHN@EXAMPLE.COM "]})
        t = NormalizeEmail()
        once = t.apply(df)
        twice = t.apply(once)
        assert once["email"].tolist() == twice["email"].tolist()


class TestParseDate:
    def test_normal_data(self):
        df = pd.DataFrame({"joined": ["2024-01-15", "15/01/2024"]})
        t = ParseDate()
        result = t.apply(df)
        assert result["joined"].tolist() == ["2024-01-15", "2024-01-15"]

    def test_malformed_becomes_null_not_dropped(self):
        df = pd.DataFrame({"joined": ["2024-13-40", "2024-01-15"]})
        t = ParseDate()
        result = t.apply(df)
        assert len(result) == 2  # row-count preserved
        assert pd.isna(result["joined"].iloc[0])


class TestNormalizeNumeric:
    def test_currency_and_commas(self):
        df = pd.DataFrame({"amount": ["$1,200.50", "950"]})
        t = NormalizeNumeric()
        result = t.apply(df)
        assert result["amount"].tolist() == [1200.50, 950.0]

    def test_malformed_becomes_null(self):
        df = pd.DataFrame({"amount": ["not-a-number"]})
        t = NormalizeNumeric()
        result = t.apply(df)
        assert pd.isna(result["amount"].iloc[0])


def test_preview_does_not_mutate_input():
    df = pd.DataFrame({"name": [" Alice "]})
    original = df.copy()
    t = TrimWhitespace()
    t.preview(df)
    pd.testing.assert_frame_equal(df, original)
