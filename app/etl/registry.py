"""Allowlist of transformations. This is the ONLY place operation names are
mapped to executable code -- AI/user input is validated against these keys
and nothing else is ever executed (spec section 11: never eval/exec AI output).
"""
from app.etl.base import Transformation
from app.etl.transformations.categories import NormalizeCategory
from app.etl.transformations.dates import ParseDate
from app.etl.transformations.duplicates import RemoveDuplicates
from app.etl.transformations.email import NormalizeEmail
from app.etl.transformations.nulls import DropNullRows, FillNull
from app.etl.transformations.numeric import NormalizeNumeric
from app.etl.transformations.phone import NormalizePhone
from app.etl.transformations.strings import LowercaseText, TitlecaseText, UppercaseText
from app.etl.transformations.whitespace import TrimWhitespace

TRANSFORMATIONS: dict[str, Transformation] = {
    "trim_whitespace": TrimWhitespace(),
    "lowercase_text": LowercaseText(),
    "uppercase_text": UppercaseText(),
    "titlecase_text": TitlecaseText(),
    "normalize_email": NormalizeEmail(),
    "normalize_phone": NormalizePhone(),
    "parse_date": ParseDate(),
    "normalize_numeric": NormalizeNumeric(),
    "fill_null": FillNull(),
    "drop_null_rows": DropNullRows(),
    "remove_duplicates": RemoveDuplicates(),
    "normalize_category": NormalizeCategory(),
}


def get_transformation(operation: str) -> Transformation:
    if operation not in TRANSFORMATIONS:
        allowed = ", ".join(sorted(TRANSFORMATIONS))
        raise ValueError(f"Unknown transformation '{operation}'. Allowed operations: {allowed}")
    return TRANSFORMATIONS[operation]
