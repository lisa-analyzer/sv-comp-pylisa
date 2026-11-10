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
    z3: str | None = typer.Option(
        None,
        "--z3",
        help="Path to the z3 executable that pylisa uses to verify its warnings (by default, the one in the PATH)",
    ),
):
    """
    Check input files against a specified property
    """

    __use_writable_output_directory()
    __clean_output_directory()
    __validate_input_paths(inputs)
    property_to_check = __resolve_property(property)

    lisa_report = __run_analysis(inputs, z3)

    if lisa_report:
        __display_results(property_to_check, lisa_report)


def __use_writable_output_directory():
    """
    pylisa writes its results to outputs/ in the working directory, where BenchExec
    collects the result files. The output directory of config.json is a path of the machine where the
    archive was built, outside the working directory of a BenchExec run, and shared by all the runs.
    """
    config.path_to_output_dir = Path.cwd() / "outputs"
    config.path_to_output_dir.mkdir(parents=True, exist_ok=True)


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


def __run_analysis(inputs: str, z3: str | None) -> LisaReport | None:
    command = get_lisa_cmd(config, inputs, None, 10, z3=z3, log_level="INFO")

    try:
        # pylisa writes to the stdout and stderr of the wrapper, so that whoever captures them also sees its
        # output: what the wrapper printed so far is flushed first, to keep the order
        sys.stdout.flush()
        sys.stderr.flush()
        proc = subprocess.run(command, shell=True)
        if proc.returncode == 0:
            report_path = config.path_to_output_dir / "report.json"
            with open(report_path, encoding="utf-8") as f:
                return LisaReport(**json.load(f))
        else:
            rich.print(
                f"[bold red]LiSA analysis failed with exit code {proc.returncode}[/bold red]"
            )
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
