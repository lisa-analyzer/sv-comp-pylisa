# Standard library imports
import re
from dataclasses import dataclass


@dataclass
class Warning:
    """
    Represents a 'warning' field of a LiSA's 'report' JSON file
    """

    message: str

    def extract_warning(self) -> str:
        """
        Extracts the analysis warning (e.g. how assertion holds, etc.)
        """

        if not self.message:
            return ""
        match = re.search(r"\[[A-Z]+\]\s*(.*)$", self.message)
        return match.group(1) if match else ""

    def is_possible_warning(self) -> bool:
        return "possible" in self.extract_warning() or "might" in self.extract_warning()

    def is_assertion_safety_warning(self) -> bool:
        return "ASSERTIONS" in self.extract_warning()

    def is_dynamic_typing_warning(self) -> bool:
        return "TYPING" in self.extract_warning()

    def is_arithmetic_warning(self) -> bool:
        return "ARITHMETIC" in self.extract_warning()

    def is_data_lookup_warning(self) -> bool:
        return "LOOKUP" in self.extract_warning()
