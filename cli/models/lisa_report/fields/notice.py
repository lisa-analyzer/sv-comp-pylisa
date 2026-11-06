# Standard library imports
import re
from dataclasses import dataclass


@dataclass
class Notice:
    """
    Represents a 'notice' field of a LiSA's 'report' JSON file
    """

    message: str

    def __init__(self, message, **_):
        self.message = message

    def extract_notice(self) -> str:
        """
        Extracts the analysis notice (e.g. some event happened, etc.)
        """

        if not self.message:
            return ""
        # older versions of LiSA prefix the message with its location and its tag (e.g. [STATEMENT]), while newer
        # ones write them in separate fields
        match = re.search(r"\[[A-Z]+\]\s*(.*)$", self.message)
        return match.group(1) if match else self.message

    def is_bottom_notice(self) -> bool:
        return "Analysis produced" in self.extract_notice()

    def is_open_call_notice(self) -> bool:
        return "to any target and is thus open" in self.extract_notice()
