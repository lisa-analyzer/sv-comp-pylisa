# Standard library imports
import json
import shutil
import subprocess
import sys
from pathlib import Path

# Load vendored packages
from vendor.package_loader import load_packages

load_packages()

# Third-party imports
import rich
import typer

from cli.commands.analyse import get_lisa_cmd

# Project-local imports
from cli.models.config import Config
from cli.models.lisa_report.lisa_report import LisaReport
from cli.models.property import Property
from cli.utils.util import (
    classify_arithmetic,
    classify_assertion_safety,
    classify_data_lookup,
    classify_dynamic_typing,
)

# CLI setup
cli = typer.Typer()
config = Config.get()

# Constants
PROPERTY_ASSERT_TEXT = "CHECK( init(main()), ! uncaught(AssertionError))"
PROPERTY_ARITHMETIC_TEXT = "CHECK( init(main()), ! uncaught(ZeroDivisionError))\nCHECK( init(main()), ! uncaught(FloatingPointError))"
PROPERTY_LOOKUP_TEXT = "CHECK( init(main()), ! uncaught(KeyError))\nCHECK( init(main()), ! uncaught(IndexError))"
PROPERTY_TYPING_TEXT = "CHECK( init(main()), ! uncaught(TypeError))\nCHECK( init(main()), ! uncaught(AttributeError))"


@cli.command()
def check(
    inputs: str = typer.Option(
        ...,
        "-i",
        "--inputs",
        help="In double quotes provide input files separated by empty space",
    ),
    property: str = typer.Option(
        ...,
        "-p",
        "--property",
        help="Provide path to the property file or property name to check",
    ),
):
    """
    Check input files against a specified property
    """

    __clean_output_directory()
    __validate_input_paths(inputs)
    property_to_check = __resolve_property(property)

    lisa_report = __run_analysis(inputs)

    if lisa_report:
        __display_results(property_to_check, lisa_report)


def __clean_output_directory():
    if config.path_to_output_dir and config.path_to_output_dir.exists():
        for item in config.path_to_output_dir.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)


def __resolve_property(property: str) -> Property:
    property_path = Path(property)

    if property_path.exists():
        property_content = property_path.read_text().strip()

        if property_content == PROPERTY_ASSERT_TEXT:
            return Property.ASSERTION_SAFETY
        elif property_content == PROPERTY_ARITHMETIC_TEXT:
            return Property.ARITHMETIC
        elif property_content == PROPERTY_LOOKUP_TEXT:
            return Property.DATA_LOOKUP
        elif property_content == PROPERTY_TYPING_TEXT:
            return Property.DYNAMIC_TYPING
        else:
            rich.print(
                f"[bold red]Specified property is not supported:[/bold red] {property_content}"
            )
            raise typer.Exit(code=1)
    else:
        return Property(property.lower())


def __validate_input_paths(inputs: str) -> list[Path]:
    paths = [Path(p) for p in inputs.split(" ")]

    for path in paths:
        if not path.exists():
            rich.print(f"[bold red]Input file not found:[/bold red] '{path}'")
            rich.print("Please ensure correct path to the input file")
            raise typer.Exit(code=1)

    return paths


def __run_analysis(inputs: str) -> LisaReport | None:
    command = get_lisa_cmd(config, inputs, None, 10)
    (
        f"java"
        f" -Xmx10G"
        f" -cp {config.path_to_lisa_instance}"
        f" it.unive.pylisa.PyLiSA"
        f" -s {inputs}"
        f" -o {config.path_to_output_dir}"
        f" -n ConstantPropagation"
        f" -m Statistics"
        f" -c Assert"
        f" --no-html"
        f" --l ERROR"
    )

    proc = subprocess.Popen(
        command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    try:
        proc.wait()
        if proc.returncode == 0:
            report_path = config.path_to_output_dir / "report.json"
            with open(report_path, encoding="utf-8") as f:
                return LisaReport(**json.load(f))
        else:
            rich.print(
                f"[bold red]LiSA analysis failed with exit code {proc.returncode}[/bold red]"
            )
            if proc.stderr:
                error_output = proc.stderr.read().strip()
                rich.print(f"[red]Error: {error_output}[/red]")
        return None
    except Exception as e:
        rich.print(f"[bold red]An unexpected error occurred:[/bold red] {e}")
        print(f"Error details: {e}", file=sys.stderr)
        return None


def __display_results(property: Property, lisa_report: LisaReport):
    if property == Property.ASSERTION_SAFETY:
        __display(lisa_report, classify_assertion_safety)
    elif property == Property.ARITHMETIC:
        __display(lisa_report, classify_arithmetic)
    elif property == Property.DATA_LOOKUP:
        __display(lisa_report, classify_data_lookup)
    elif property == Property.DYNAMIC_TYPING:
        __display(lisa_report, classify_dynamic_typing)


def __display(lisa_report: LisaReport, classify_func):
    match classify_func(lisa_report).value[1]:
        case "TRUE":
            rich.print("[bold green]TRUE[/bold green]")
        case "FALSE":
            rich.print("[bold red]FALSE[/bold red]")
        case "UNKNOWN":
            rich.print("[bold orange3]UNKNOWN[/bold orange3]")
