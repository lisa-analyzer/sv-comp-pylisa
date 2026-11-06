# Standard library imports
import re
from dataclasses import dataclass


@dataclass
class Warning:
    """
    Represents a 'warning' field of a LiSA's 'report' JSON file. The checker of pylisa tells in the message whether
    a warning is possible (see is_possible_warning), and the verification of warnings then might confirm it
    (definite) or refute it (refuted: it is a false alarm).
    """

    message: str
    definite: bool = False
    refuted: bool = False
    # why the verification confirmed, refuted, or left possible the warning, if known
    explanation: str | None = None

    def __init__(self, message, definite=False, refuted=False, explanation=None, **_):
        self.message = message
        self.definite = bool(definite)
        self.refuted = bool(refuted)
        self.explanation = explanation

    def extract_warning(self) -> str:
        """
        Extracts the analysis warning (e.g. how assertion holds, etc.)
        """

        if not self.message:
            return ""
        # older versions of LiSA prefix the message with its location and its tag (e.g. [STATEMENT]), while newer
        # ones write them in separate fields
        match = re.search(r"\[[A-Z]+\]\s*(.*)$", self.message)
        return match.group(1) if match else self.message

    def is_possible_warning(self) -> bool:
        """
        Whether the warning is possible: neither the checker nor the verification of warnings confirms it
        """
        if self.definite:
            return False
        return "possible" in self.extract_warning() or "might" in self.extract_warning()

    def is_assertion_safety_warning(self) -> bool:
        return "ASSERTIONS" in self.extract_warning()

    def is_dynamic_typing_warning(self) -> bool:
        return "TYPING" in self.extract_warning()

    def is_arithmetic_warning(self) -> bool:
        return "ARITHMETIC" in self.extract_warning()

    def is_data_lookup_warning(self) -> bool:
        return "LOOKUP" in self.extract_warning()
