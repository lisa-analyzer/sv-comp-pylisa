# Standard library imports
import json
import os

# Load vendored packages
from vendor.package_loader import load_packages

load_packages()

# Project-local imports
import pandas

# Third-party imports
import rich
import typer
from pandas import DataFrame, concat
from rich.text import Text

from cli.commands.harvest import get_task, get_tasks
from cli.models.config import Config
from cli.models.lisa_report.lisa_report import LisaReport
from cli.models.task_definition.task_definition import TaskDefinition
from cli.utils.util import (
    RuntimeClassification,
    classify_arithmetic,
    classify_assertion_safety,
    classify_data_lookup,
    classify_dynamic_typing,
)

# CLI setup
cli = typer.Typer()
config = Config.get()

ASSERTIONS_TRUE = "Assertions safety set to TRUE"
ASSERTIONS_FALSE = "Assertions safety set to FALSE"
ARITHMETIC_TRUE = "Arithmetic set to TRUE"
ARITHMETIC_FALSE = "Arithmetic set to FALSE"
LOOKUP_TRUE = "Data lookup set to TRUE"
LOOKUP_FALSE = "Data lookup set to FALSE"
TYPING_TRUE = "Dynamic typing set to TRUE"
TYPING_FALSE = "Dynamic typing set to FALSE"

DEFINITE_NOT_WARNING = "LiSA produced only DEFINITE NOT holds warnings"
POSSIBLE_NOT_WARNING = "LiSA produced only POSSIBLY NOT holds warnings"
CONFLICT_NOT_WARNING = (
    "LiSA produced both DEFINITE and POSSIBLE 'does not hold' warnings"
)
UNKNOWN_WARNING = "LiSA classification unknown"
NO_WARNINGS = "LiSA produced no warnings"


@cli.command()
def statistics():
    """
    Computes statistics on analysis results
    """
    output_dir = os.path.join(str(config.path_to_output_dir), "results")

    parsing_error_table = None
    frontend_error_table = None
    analysis_error_table = None
    svcomp_scores = DataFrame()
    all_bottoms = []
    all_opens = []

    parsing_error_counter = 0
    frontend_error_counter = 0
    analysis_error_counter = 0

    timed_out_tasks = []
    if os.path.exists(f"{config.path_to_output_dir!s}/timed_out.txt"):
        with open(f"{config.path_to_output_dir!s}/timed_out.txt", "r") as f:
            timed_out_tasks = [line.strip() for line in f]

    def process_csv(file_path, dataframe):
        temp = (
            pandas.read_csv(file_path, sep=";")[["Message", "Type"]]
            .groupby(["Message"])
            .count()
        )
        return __add_row(temp, dataframe, os.path.basename(os.path.dirname(file_path)))

    for dir_name in os.listdir(output_dir):
        results_dir = os.path.join(output_dir, dir_name)
        if not os.path.isdir(results_dir):
            continue

        treated = False

        for file in os.listdir(results_dir):
            file_path = os.path.join(results_dir, file)

            if file == "frontend.csv":
                parsing_error_table = process_csv(file_path, parsing_error_table)
                svcomp_iteration_df = __to_svcomp_table_entry(
                    dir_name, "UNKNOWN (parsing)", 0
                )
                svcomp_scores = svcomp_scores._append(svcomp_iteration_df)
                parsing_error_counter += 1
                treated = True

            elif file == "frontend-noparsing.csv":
                frontend_error_table = process_csv(file_path, frontend_error_table)
                svcomp_iteration_df = __to_svcomp_table_entry(
                    dir_name, "UNKNOWN (frontend)", 0
                )
                svcomp_scores = svcomp_scores._append(svcomp_iteration_df)
                frontend_error_counter += 1
                treated = True

            elif file == "analysis.csv":
                analysis_error_table = process_csv(file_path, analysis_error_table)
                svcomp_iteration_df = __to_svcomp_table_entry(
                    dir_name, "UNKNOWN (analysis)", 0
                )
                svcomp_scores = svcomp_scores._append(svcomp_iteration_df)
                analysis_error_counter += 1
                treated = True

        if not treated and dir_name not in timed_out_tasks:
            svcomp_iteration_df, bottoms, opens = __compute_score(results_dir, dir_name)
            for notice in bottoms:
                all_bottoms.append((dir_name, notice.message))
            for notice in opens:
                all_opens.append((dir_name, notice.message))
            svcomp_scores = svcomp_scores._append(svcomp_iteration_df)

    for t in timed_out_tasks:
        svcomp_iteration_df = __to_svcomp_table_entry(t, "TIMEOUT", 0)
        svcomp_scores = svcomp_scores._append(svcomp_iteration_df)

    __save_output_csvs(
        parsing_error_table,
        frontend_error_table,
        analysis_error_table,
        svcomp_scores,
        all_bottoms,
        all_opens,
    )
    __save_summary(
        svcomp_scores,
        parsing_error_counter,
        frontend_error_counter,
        analysis_error_counter,
        timed_out_tasks,
    )


def __to_svcomp_table_entry(file_name, virdict, score):
    task: TaskDefinition = get_task(file_name)
    svcomp_data = []
    if task.are_arithmetic_expected() is not None:
        svcomp_data.append(
            [
                f"{file_name}|arithmetic|{task.are_arithmetic_expected()}",
                virdict,
                score,
            ]
        )
    if task.are_assertion_safety_expected() is not None:
        svcomp_data.append(
            [
                f"{file_name}|assert|{task.are_assertion_safety_expected()}",
                virdict,
                score,
            ]
        )
    if task.are_data_lookup_expected() is not None:
        svcomp_data.append(
            [
                f"{file_name}|lookup|{task.are_data_lookup_expected()}",
                virdict,
                score,
            ]
        )
    if task.are_dynamic_typing_expected() is not None:
        svcomp_data.append(
            [
                f"{file_name}|typing|{task.are_dynamic_typing_expected()}",
                virdict,
                score,
            ]
        )
    svcomp_iteration_df = DataFrame(
        svcomp_data, columns=["Test case", "Virdict", "Score"]
    )
    return svcomp_iteration_df


def __add_row(temp, dataframe, test_case):
    temp["Test_cases"] = str(test_case) + "\n"
    if dataframe is None:
        dataframe = temp
    else:
        merge = pandas.merge(
            dataframe, temp, left_index=True, right_index=True, how="outer"
        )
        merge["Test_cases_x"] = merge["Test_cases_x"].fillna("")
        merge["Test_cases_y"] = merge["Test_cases_y"].fillna("")
        merge = merge.fillna(0)
        merge["Type"] = merge["Type_x"] + merge["Type_y"]
        merge["Test_cases"] = merge["Test_cases_x"].astype(str) + merge[
            "Test_cases_y"
        ].astype(str)
        dataframe = merge[["Type", "Test_cases"]]
    return dataframe


def __compute_score(results_dir: str, file_name: str) -> DataFrame:
    task: TaskDefinition = get_task(file_name)
    with open(os.path.join(results_dir, "report.json"), encoding="utf-8") as f:
        lisa_report = LisaReport(**json.load(f))

    sv_arithmetic, due_arithmetic, virdict_arithmetic = __score_result(
        task,
        lisa_report,
        task.are_arithmetic_expected(),
        classify_arithmetic(lisa_report),
    )
    sv_typing, due_typing, virdict_typing = __score_result(
        task,
        lisa_report,
        task.are_dynamic_typing_expected(),
        classify_dynamic_typing(lisa_report),
    )
    sv_lookup, due_lookup, virdict_lookup = __score_result(
        task,
        lisa_report,
        task.are_data_lookup_expected(),
        classify_data_lookup(lisa_report),
    )
    sv_assert, due_assert, virdict_assert = __score_result(
        task,
        lisa_report,
        task.are_assertion_safety_expected(),
        classify_assertion_safety(lisa_report),
    )

    svcomp_data = []
    if task.are_arithmetic_expected() is not None:
        svcomp_data.append(
            [
                f"{file_name}|arithmetic|{task.are_arithmetic_expected()}",
                virdict_arithmetic,
                sv_arithmetic,
                "\n".join(due_arithmetic),
                lisa_report.count_bottom_notices(),
                lisa_report.count_open_call_notices(),
            ]
        )
    if task.are_assertion_safety_expected() is not None:
        svcomp_data.append(
            [
                f"{file_name}|assert|{task.are_assertion_safety_expected()}",
                virdict_assert,
                sv_assert,
                "\n".join(due_assert),
                lisa_report.count_bottom_notices(),
                lisa_report.count_open_call_notices(),
            ]
        )
    if task.are_data_lookup_expected() is not None:
        svcomp_data.append(
            [
                f"{file_name}|lookup|{task.are_data_lookup_expected()}",
                virdict_lookup,
                sv_lookup,
                "\n".join(due_lookup),
                lisa_report.count_bottom_notices(),
                lisa_report.count_open_call_notices(),
            ]
        )
    if task.are_dynamic_typing_expected() is not None:
        svcomp_data.append(
            [
                f"{file_name}|typing|{task.are_dynamic_typing_expected()}",
                virdict_typing,
                sv_typing,
                "\n".join(due_typing),
                lisa_report.count_bottom_notices(),
                lisa_report.count_open_call_notices(),
            ]
        )

    svcomp_table = DataFrame(
        svcomp_data,
        columns=[
            "Test case",
            "Virdict",
            "Score",
            "Due to",
            "Num Bottom",
            "Num Open Calls",
        ],
    )

    return (
        svcomp_table,
        lisa_report.get_bottom_notices(),
        lisa_report.get_open_call_notices(),
    )


def __score_result(
    task: TaskDefinition,
    lisa_report: LisaReport,
    expected: bool,
    classification: RuntimeClassification,
) -> tuple[int, list[str], str]:
    sv_comp_score = 0
    due_to: list[str] = []

    virdict = classification.value[1]
    if expected:  # TRUE
        expected_res = ASSERTIONS_TRUE
        match classification.value[1]:
            case "TRUE":
                sv_comp_score = 2
            case "FALSE":
                sv_comp_score = -16
            case "UNKNOWN":
                sv_comp_score = 0
    elif expected is False:  # FALSE
        expected_res = ASSERTIONS_FALSE
        match classification.value[1]:
            case "TRUE":
                sv_comp_score = -32
            case "FALSE":
                sv_comp_score = 1
            case "UNKNOWN":
                sv_comp_score = 0
    else:  # PROPERTY IS ABSENT
        return 0, [], "UNKNOWN"

    match classification:
        case RuntimeClassification.NO_WARNINGS:
            due_to.append(f"{expected_res}, and {NO_WARNINGS}")
        case RuntimeClassification.ONLY_POSSIBLE_NOT_HOLDS:
            due_to.append(f"{expected_res}, and {POSSIBLE_NOT_WARNING}")
        case RuntimeClassification.ONLY_DEFINITE_NOT_HOLDS:
            due_to.append(f"{expected_res}, and {DEFINITE_NOT_WARNING}")
        case RuntimeClassification.CONFLICTING_NOT_HOLDS:
            due_to.append(f"{expected_res}, and {CONFLICT_NOT_WARNING}")
        case RuntimeClassification.UNKNOWN:
            due_to.append(f"{expected_res}, and {UNKNOWN_WARNING}")

    return sv_comp_score, due_to, virdict


def __save_output_csvs(
    parsing_error_table=None,
    frontend_error_table=None,
    analysis_error_table=None,
    svcomp_scores=None,
    bottom_locations=None,
    open_locations=None,
):
    def __save_sorted_csv(df, filename):
        if df is not None:
            sorted_df = df.sort_values("Type", ascending=False)
            sorted_df.to_csv(
                os.path.join(config.path_to_output_dir, filename), index=True
            )

    __save_sorted_csv(parsing_error_table, "parsing.csv")
    __save_sorted_csv(frontend_error_table, "frontend.csv")
    __save_sorted_csv(analysis_error_table, "analysis.csv")

    if svcomp_scores is not None:
        svcomp_scores = concat([svcomp_scores]).reset_index(drop=True)
        svcomp_scores.index += 1
        svcomp_scores["No."] = svcomp_scores["Test case"].factorize()[0] + 1
        svcomp_scores.set_index("No.", inplace=True)
        svcomp_scores.to_csv(os.path.join(config.path_to_output_dir, "svcomp.csv"))

    bottoms_table = DataFrame(
        bottom_locations,
        columns=[
            "Test case",
            "Notice",
        ],
    )
    bottoms_table.to_csv(os.path.join(config.path_to_output_dir, "bottoms.csv"))
    opens_table = DataFrame(
        open_locations,
        columns=[
            "Test case",
            "Notice",
        ],
    )
    opens_table.to_csv(os.path.join(config.path_to_output_dir, "opens.csv"))


def __save_summary(
    scores,
    parsing_error_counter: int,
    frontend_error_counter: int,
    analysis_error_counter: int,
    timed_out_tasks: list[str],
):
    all_tasks = get_tasks()
    assert_tasks = 0
    typing_tasks = 0
    lookup_tasks = 0
    arithmetic_tasks = 0
    for task in all_tasks:
        if task.are_assertion_safety_expected() is not None:
            assert_tasks += 1
        if task.are_dynamic_typing_expected() is not None:
            typing_tasks += 1
        if task.are_data_lookup_expected() is not None:
            lookup_tasks += 1
        if task.are_arithmetic_expected() is not None:
            arithmetic_tasks += 1

    total_passed = (scores["Score"] > 0).sum()
    total_zero = (scores["Score"] == 0).sum()
    total_failed = (scores["Score"] < 0).sum()

    passed_assert = (
        scores.loc[scores["Test case"].str.contains(r"\|assert\|", na=False), "Score"]
        > 0
    ).sum()
    zero_assert = (
        scores.loc[scores["Test case"].str.contains(r"\|assert\|", na=False), "Score"]
        == 0
    ).sum()
    failed_assert = (
        scores.loc[scores["Test case"].str.contains(r"\|assert\|", na=False), "Score"]
        < 0
    ).sum()

    passed_arithmetic = (
        scores.loc[
            scores["Test case"].str.contains(r"\|arithmetic\|", na=False), "Score"
        ]
        > 0
    ).sum()
    zero_arithmetic = (
        scores.loc[
            scores["Test case"].str.contains(r"\|arithmetic\|", na=False), "Score"
        ]
        == 0
    ).sum()
    failed_arithmetic = (
        scores.loc[
            scores["Test case"].str.contains(r"\|arithmetic\|", na=False), "Score"
        ]
        < 0
    ).sum()

    passed_lookup = (
        scores.loc[scores["Test case"].str.contains(r"\|lookup\|", na=False), "Score"]
        > 0
    ).sum()
    zero_lookup = (
        scores.loc[scores["Test case"].str.contains(r"\|lookup\|", na=False), "Score"]
        == 0
    ).sum()
    failed_lookup = (
        scores.loc[scores["Test case"].str.contains(r"\|lookup\|", na=False), "Score"]
        < 0
    ).sum()

    passed_typing = (
        scores.loc[scores["Test case"].str.contains(r"\|typing\|", na=False), "Score"]
        > 0
    ).sum()
    zero_typing = (
        scores.loc[scores["Test case"].str.contains(r"\|typing\|", na=False), "Score"]
        == 0
    ).sum()
    failed_typing = (
        scores.loc[scores["Test case"].str.contains(r"\|typing\|", na=False), "Score"]
        < 0
    ).sum()

    assert_score = scores.loc[
        scores["Test case"].str.contains(r"\|assert\|", na=False), "Score"
    ].sum()
    arithmetic_score = scores.loc[
        scores["Test case"].str.contains(r"\|arithmetic\|", na=False), "Score"
    ].sum()
    lookup_score = scores.loc[
        scores["Test case"].str.contains(r"\|lookup\|", na=False), "Score"
    ].sum()
    typing_score = scores.loc[
        scores["Test case"].str.contains(r"\|typing\|", na=False), "Score"
    ].sum()
    norm_score = round(
        (
            (assert_score / assert_tasks)
            + (arithmetic_score / arithmetic_tasks)
            + (lookup_score / lookup_tasks)
            + (typing_score / typing_tasks)
        )
        * ((assert_tasks + arithmetic_tasks + lookup_tasks + typing_tasks) / 4)
    )

    count_bot = int(scores["Num Bottom"].sum())
    count_open = int(scores["Num Open Calls"].sum())

    summary_lines = [
        f"Test files: [bold blue]{len(all_tasks)}[/bold blue]",
        f"Test files with assert task: [bold blue]{assert_tasks}[/bold blue]",
        f"Test files with arithmetic task: [bold blue]{arithmetic_tasks}[/bold blue]",
        f"Test files with lookup task: [bold blue]{lookup_tasks}[/bold blue]",
        f"Test files with typing task: [bold blue]{typing_tasks}[/bold blue]",
        f"Total tasks: [bold blue]{assert_tasks + arithmetic_tasks + lookup_tasks + typing_tasks}[/bold blue]\n",
        "[italic]Results[/italic]",
        f"Overall: [bold green]{total_passed} passed[/bold green] / [bold yellow]{total_zero} inconclusive[/bold yellow] / [bold red]{total_failed} failed[/bold red]",
        f"Assert: [bold green]{passed_assert} passed[/bold green] / [bold yellow]{zero_assert} inconclusive[/bold yellow] / [bold red]{failed_assert} failed[/bold red]\n",
        f"Arithmetic: [bold green]{passed_arithmetic} passed[/bold green] / [bold yellow]{zero_arithmetic} inconclusive[/bold yellow] / [bold red]{failed_arithmetic} failed[/bold red]\n",
        f"Lookup: [bold green]{passed_lookup} passed[/bold green] / [bold yellow]{zero_lookup} inconclusive[/bold yellow] / [bold red]{failed_lookup} failed[/bold red]\n",
        f"Typing: [bold green]{passed_typing} passed[/bold green] / [bold yellow]{zero_typing} inconclusive[/bold yellow] / [bold red]{failed_typing} failed[/bold red]\n",
        "[italic]Scores[/italic]",
        f"Absolute: [bold green]{scores['Score'].sum()}[/bold green]",
        f"Normalized: [bold green]{norm_score}[/bold green]",
        f"Assert: [bold yellow]{assert_score}[/bold yellow]\n",
        f"Arithmetic: [bold yellow]{arithmetic_score}[/bold yellow]\n",
        f"Lookup: [bold yellow]{lookup_score}[/bold yellow]\n",
        f"Typing: [bold yellow]{typing_score}[/bold yellow]\n",
        "[red bold]Errors[/red bold] (check corresponding .csv files)",
        f"Parsing: [bold red]{parsing_error_counter}[/bold red]",
        f"Frontend: [bold red]{frontend_error_counter}[/bold red]",
        f"Analysis: [bold red]{analysis_error_counter}[/bold red]",
        f"Timeouts: [bold red]{len(timed_out_tasks)}[/bold red]",
        f"Number of suspicious bottom states computed: [bold red]{count_bot}[/bold red]",
        f"Number of open calls produced: [bold red]{count_open}[/bold red]",
    ]

    for line in summary_lines:
        rich.print(line)

    summary_path = os.path.join(config.path_to_output_dir, "summary.txt")
    with open(summary_path, "w") as f:
        for line in summary_lines:
            f.write(Text.from_markup(line).plain + "\n")
