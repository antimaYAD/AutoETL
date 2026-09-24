import pandas as pd

from app.services.issue_service import compute_quality_score, detect_issues
from tests.conftest import load_fixture_df


def _issue_types(issues):
    return {i["issue_type"] for i in issues}


def test_detect_issues_on_sales_messy():
    df = load_fixture_df("sales_messy.csv")
    issues = detect_issues(df)
    types = _issue_types(issues)

    assert "MISSING_VALUES" in types
    assert "WHITESPACE" in types
    assert "DUPLICATE_ROWS" in types
    assert "INVALID_EMAIL" in types
    assert "CASE_INCONSISTENCY" in types
    assert "CURRENCY_SYMBOL" in types


def test_detect_issues_on_clean_data_returns_nothing():
    df = pd.DataFrame({"id": [1, 2, 3], "name": ["Alice", "Bob", "Carol"]})
    issues = detect_issues(df)
    assert issues == []


def test_detect_issues_on_empty_dataframe():
    df = pd.DataFrame({"id": [], "name": []})
    issues = detect_issues(df)
    assert issues == []


def test_quality_score_is_100_for_clean_data():
    df = pd.DataFrame({"id": [1, 2, 3], "name": ["Alice", "Bob", "Carol"]})
    score = compute_quality_score(df, detect_issues(df))
    assert score == 100.0


def test_quality_score_decreases_with_issues():
    df = load_fixture_df("sales_messy.csv")
    issues = detect_issues(df)
    score = compute_quality_score(df, issues)
    assert 0 <= score < 100
