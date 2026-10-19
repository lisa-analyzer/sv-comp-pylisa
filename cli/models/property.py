from enum import Enum


class Property(Enum):
    """
    Represents an enumeration of properties of interest that are accepted and passed to LiSA
    """

    ASSERTION_SAFETY = "assertion-safety"
    ARITHMETIC = "arithmetic"
    DATA_LOOKUP = "data-lookup"
    DYNAMIC_TYPING = "dynamic-typing"
