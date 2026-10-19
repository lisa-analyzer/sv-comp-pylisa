# Standard library imports
import dataclasses
import json
import sys
import tomllib
from enum import Enum
from pathlib import Path

from cli.models.lisa_report.lisa_report import LisaReport


def json_serializer(obj):
    """
    Converts path objects or other complex types to strings for JSON serialization
    """

    if isinstance(obj, Path):
        return str(obj)
    elif dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    else:
        return json.JSONEncoder.default(obj)


def resource_path(relative_path: str) -> Path:
    """
    Get the absolute path to a resource, works for dev and PyInstaller bundle.

    When running as a PyInstaller bundle, files are unpacked to a temporary folder
    accessible via sys._MEIPASS. This function returns the correct path to the resource.

    Args:
        relative_path: Relative path to the resource file inside your project or bundle.

    Returns:
        An absolute Path object to the resource.
    """
    if hasattr(sys, "_MEIPASS"):
        # Running in PyInstaller bundle
        base_path = Path(sys._MEIPASS)
    else:
        # Running in normal Python environment
        base_path = Path(__file__).resolve().parent.parent.parent

    return base_path / relative_path


def get_meta_info(field: str):
    """
    Get field value from a pyproject.toml
    """
    pyproject_path = resource_path("pyproject.toml")

    if not pyproject_path.exists():
        raise FileNotFoundError(f"pyproject.toml not found at {pyproject_path}")

    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    keys = field.split(".")
    try:
        for key in keys:
            data = data[key]
        return data
    except (KeyError, TypeError):
        raise KeyError(f"Field '{field}' not found in {pyproject_path}")


class RuntimeClassification(Enum):
    ### FORMAT: (code, sv-comp verdict)

    # no warnings are issued
    NO_WARNINGS = 1, "TRUE"

    # only "possible runtime exception" warnings are issued
    ONLY_POSSIBLE_NOT_HOLDS = 2, "UNKNOWN"

    # only "definite runtime exception" warnings are issued
    ONLY_DEFINITE_NOT_HOLDS = 3, "FALSE"

    # both "possible runtime exception" and "definite runtime exception" warnings are issued
    CONFLICTING_NOT_HOLDS = 4, "FALSE"

    # unknown classification
    UNKNOWN = 5, "UNKNOWN"


def classify_arithmetic(lisa_report: LisaReport):
    if not lisa_report.has_arithmetic_warnings():
        return RuntimeClassification.NO_WARNINGS
    elif lisa_report.has_only_possible_arithmetic_warnings():
        return RuntimeClassification.ONLY_POSSIBLE_NOT_HOLDS
    elif lisa_report.has_only_definite_arithmetic_warnings():
        return RuntimeClassification.ONLY_DEFINITE_NOT_HOLDS
    elif (
        lisa_report.has_possible_arithmetic_warning()
        and lisa_report.has_definite_arithmetic_warning()
    ):
        return RuntimeClassification.CONFLICTING_NOT_HOLDS
    return RuntimeClassification.UNKNOWN


def classify_assertion_safety(lisa_report: LisaReport):
    if not lisa_report.has_assertion_safety_warnings():
        return RuntimeClassification.NO_WARNINGS
    elif lisa_report.has_only_possible_assertion_safety_warnings():
        return RuntimeClassification.ONLY_POSSIBLE_NOT_HOLDS
    elif lisa_report.has_only_definite_assertion_safety_warnings():
        return RuntimeClassification.ONLY_DEFINITE_NOT_HOLDS
    elif (
        lisa_report.has_possible_assertion_safety_warning()
        and lisa_report.has_definite_assertion_safety_warning()
    ):
        return RuntimeClassification.CONFLICTING_NOT_HOLDS
    return RuntimeClassification.UNKNOWN


def classify_data_lookup(lisa_report: LisaReport):
    if not lisa_report.has_data_lookup_warnings():
        return RuntimeClassification.NO_WARNINGS
    elif lisa_report.has_only_possible_data_lookup_warnings():
        return RuntimeClassification.ONLY_POSSIBLE_NOT_HOLDS
    elif lisa_report.has_only_definite_data_lookup_warnings():
        return RuntimeClassification.ONLY_DEFINITE_NOT_HOLDS
    elif (
        lisa_report.has_possible_data_lookup_warning()
        and lisa_report.has_definite_data_lookup_warning()
    ):
        return RuntimeClassification.CONFLICTING_NOT_HOLDS
    return RuntimeClassification.UNKNOWN


def classify_dynamic_typing(lisa_report: LisaReport):
    if not lisa_report.has_dynamic_typing_warnings():
        return RuntimeClassification.NO_WARNINGS
    elif lisa_report.has_only_possible_dynamic_typing_warnings():
        return RuntimeClassification.ONLY_POSSIBLE_NOT_HOLDS
    elif lisa_report.has_only_definite_dynamic_typing_warnings():
        return RuntimeClassification.ONLY_DEFINITE_NOT_HOLDS
    elif (
        lisa_report.has_possible_dynamic_typing_warning()
        and lisa_report.has_definite_dynamic_typing_warning()
    ):
        return RuntimeClassification.CONFLICTING_NOT_HOLDS
    return RuntimeClassification.UNKNOWN
