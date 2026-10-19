# Standard library imports
from dataclasses import dataclass
from pathlib import Path

# Project-local imports
from cli.models.task_definition.fields.property import Property


@dataclass
class TaskDefinition:
    """
    Represents the definition of a task
    """

    file_name: str
    path_to_definition: Path
    input_file: Path
    properties: list[Property]

    def __init__(
        self,
        file_name: str,
        path_to_definition: Path,
        input_file: Path,
        properties: list[Property],
    ):
        self.file_name = file_name
        self.path_to_definition = path_to_definition
        self.input_file = input_file
        self.properties = [
            p if isinstance(p, Property) else Property(**p) for p in properties
        ]

    def are_arithmetic_expected(self) -> bool | None:
        for prop in self.properties:
            if "arithmetic" in prop.property_file:
                return prop.expected_verdict
        return None

    def are_data_lookup_expected(self) -> bool | None:
        for prop in self.properties:
            if "data-lookup" in prop.property_file:
                return prop.expected_verdict
        return None

    def are_dynamic_typing_expected(self) -> bool | None:
        for prop in self.properties:
            if "dynamic-typing" in prop.property_file:
                return prop.expected_verdict
        return None

    def are_assertion_safety_expected(self) -> bool | None:
        for prop in self.properties:
            if "assertion-safety" in prop.property_file:
                return prop.expected_verdict
        return None
