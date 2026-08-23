#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations


BASE_DIR = Path(__file__).resolve().parent
SCRIPT = BASE_DIR / "scripts" / "ynab.py"
DEFAULT_TIMEOUT_SECONDS = int(os.environ.get("MCP_SCRIPT_TIMEOUT_SECONDS", "90"))

mcp = MCPServer("ynab")

# Hint groups surfaced to MCP clients so they can decide when to prompt for
# confirmation. destructiveHint marks calls that overwrite or remove existing data
# (updates, deletes) as opposed to calls that only add new data (creates, import).
READ_ONLY_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True
)
CREATE_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True
)
IMPORT_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True
)
UPDATE_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=True
)
DELETE_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=True
)


def run_helper(args: list[str], timeout_seconds: int | None = None) -> Any:
    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        return {"ok": False, "error": "args must be a list of strings"}

    timeout = timeout_seconds or DEFAULT_TIMEOUT_SECONDS
    try:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=str(BASE_DIR),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        return {
            "ok": False,
            "args": args,
            "error": f"Timed out after {timeout} seconds",
            "stdout": error.stdout,
            "stderr": error.stderr,
        }

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    if completed.returncode != 0:
        return {
            "ok": False,
            "args": args,
            "returncode": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }

    if not stdout:
        return {"ok": True}

    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {"ok": True, "stdout": stdout, "stderr": stderr}


def add_optional(args: list[str], flag: str, value: Any) -> None:
    if value is not None:
        args.extend([flag, str(value)])


def add_optional_bool(args: list[str], flag: str, value: bool | None) -> None:
    if value is True:
        args.append(flag)
    elif value is False:
        args.append(f"--no-{flag.removeprefix('--')}")


def add_plan(args: list[str], plan_id: str | None) -> None:
    add_optional(args, "--plan-id", plan_id)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def ynab_get_user(timeout_seconds: int | None = None) -> Any:
    """Get the authenticated YNAB user."""
    return run_helper(["user"], timeout_seconds)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def ynab_list_plans(timeout_seconds: int | None = None) -> Any:
    """List YNAB plans."""
    return run_helper(["plans"], timeout_seconds)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def ynab_get_plan(
    plan_id: str | None = None,
    timeout_seconds: int | None = None,
) -> Any:
    """Get one YNAB plan. Defaults to YNAB_PLAN_ID or the API's default plan."""
    args = ["plan"]
    add_plan(args, plan_id)
    return run_helper(args, timeout_seconds)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def ynab_list_accounts(
    plan_id: str | None = None,
    timeout_seconds: int | None = None,
) -> Any:
    """List accounts for a plan."""
    args = ["accounts"]
    add_plan(args, plan_id)
    return run_helper(args, timeout_seconds)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def ynab_get_account(
    account_id: str,
    plan_id: str | None = None,
    timeout_seconds: int | None = None,
) -> Any:
    """Get one account."""
    args = ["account", account_id]
    add_plan(args, plan_id)
    return run_helper(args, timeout_seconds)


@mcp.tool(annotations=CREATE_ANNOTATIONS)
def ynab_create_account(
    name: str,
    account_type: str,
    balance: int,
    plan_id: str | None = None,
    timeout_seconds: int | None = None,
) -> Any:
    """Create one unlinked YNAB account. Balance is in milliunits; $12.34 is 12340 and debt is negative.

    The account_type must be one of: checking, savings, cash, creditCard, otherAsset,
    otherLiability. These are the only values YNAB's account-creation API (POST
    /budgets/{budget_id}/accounts, the SaveAccount schema -- see
    https://api.ynab.com/v1 -> Accounts) accepts. lineOfCredit and the debt subtypes
    (mortgage, autoLoan, studentLoan, personalLoan, medicalDebt, otherDebt) are real
    YNAB account types you'll see on existing accounts and can pick in the app, but
    the public API can't set them at creation, and there is no update/PATCH endpoint
    for accounts to change one afterward either. 
    """
    args = [
        "create-account",
        "--name",
        name,
        "--type",
        account_type,
        "--balance",
        str(balance),
    ]
    if plan_id:
        args.extend(["--plan-id", plan_id])
    return run_helper(args, timeout_seconds)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def ynab_list_category_groups(
    plan_id: str | None = None,
    timeout_seconds: int | None = None,
) -> Any:
    """List category groups for a plan."""
    args = ["category-groups"]
    add_plan(args, plan_id)
    return run_helper(args, timeout_seconds)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def ynab_get_category_group(
    category_group_id: str,
    plan_id: str | None = None,
    timeout_seconds: int | None = None,
) -> Any:
    """Get one category group."""
    args = ["category-group", category_group_id]
    add_plan(args, plan_id)
    return run_helper(args, timeout_seconds)


@mcp.tool(annotations=CREATE_ANNOTATIONS)
def ynab_create_category_group(
    name: str,
    hidden: bool | None = None,
    plan_id: str | None = None,
    timeout_seconds: int | None = None,
) -> Any:
    """Create one category group."""
    args = ["create-category-group", "--name", name]
    add_optional_bool(args, "--hidden", hidden)
    add_plan(args, plan_id)
    return run_helper(args, timeout_seconds)


@mcp.tool(annotations=UPDATE_ANNOTATIONS)
def ynab_update_category_group(
    category_group_id: str,
    name: str | None = None,
    hidden: bool | None = None,
    plan_id: str | None = None,
    timeout_seconds: int | None = None,
) -> Any:
    """Update a category group's name and/or hidden status."""
    args = ["update-category-group", category_group_id]
    add_optional(args, "--name", name)
    add_optional_bool(args, "--hidden", hidden)
    add_plan(args, plan_id)
    return run_helper(args, timeout_seconds)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def ynab_list_categories(
    plan_id: str | None = None,
    last_knowledge_of_server: int | None = None,
    timeout_seconds: int | None = None,
) -> Any:
    """List category groups and categories for a plan."""
    args = ["categories"]
    add_optional(args, "--last-knowledge-of-server", last_knowledge_of_server)
    add_plan(args, plan_id)
    return run_helper(args, timeout_seconds)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def ynab_get_category(
    category_id: str,
    plan_id: str | None = None,
    timeout_seconds: int | None = None,
) -> Any:
    """Get one category."""
    args = ["category", category_id]
    add_plan(args, plan_id)
    return run_helper(args, timeout_seconds)


def add_category_options(
    args: list[str],
    category_group_id: str | None = None,
    hidden: bool | None = None,
    note: str | None = None,
    goal_type: str | None = None,
    goal_day: int | None = None,
    goal_cadence: int | None = None,
    goal_cadence_frequency: int | None = None,
    goal_target: int | None = None,
    goal_target_date: str | None = None,
    goal_needs_whole_amount: bool | None = None,
    clear_goal: bool = False,
) -> None:
    add_optional(args, "--category-group-id", category_group_id)
    add_optional_bool(args, "--hidden", hidden)
    add_optional(args, "--note", note)
    add_optional(args, "--goal-type", goal_type)
    add_optional(args, "--goal-day", goal_day)
    add_optional(args, "--goal-cadence", goal_cadence)
    add_optional(args, "--goal-cadence-frequency", goal_cadence_frequency)
    add_optional(args, "--goal-target", goal_target)
    add_optional(args, "--goal-target-date", goal_target_date)
    add_optional_bool(args, "--goal-needs-whole-amount", goal_needs_whole_amount)
    if clear_goal:
        args.append("--clear-goal")


@mcp.tool(annotations=CREATE_ANNOTATIONS)
def ynab_create_category(
    name: str,
    category_group_id: str | None = None,
    hidden: bool | None = None,
    note: str | None = None,
    goal_type: str | None = None,
    goal_day: int | None = None,
    goal_cadence: int | None = None,
    goal_cadence_frequency: int | None = None,
    goal_target: int | None = None,
    goal_target_date: str | None = None,
    goal_needs_whole_amount: bool | None = None,
    plan_id: str | None = None,
    timeout_seconds: int | None = None,
) -> Any:
    """Create one category, optionally with target/goal settings.

    goal_cadence values (0-14): 0=none, 1=monthly, 2=weekly, 13=yearly (due
    date repeats every goal_cadence * goal_cadence_frequency); 3=every 2
    months, 4=every 3 months, ... 12=every 11 months, 14=every 2 years
    (goal_cadence_frequency is ignored for these).
    """
    args = ["create-category", "--name", name]
    add_category_options(
        args,
        category_group_id,
        hidden,
        note,
        goal_type,
        goal_day,
        goal_cadence,
        goal_cadence_frequency,
        goal_target,
        goal_target_date,
        goal_needs_whole_amount,
    )
    add_plan(args, plan_id)
    return run_helper(args, timeout_seconds)


@mcp.tool(annotations=UPDATE_ANNOTATIONS)
def ynab_update_category(
    category_id: str,
    name: str | None = None,
    category_group_id: str | None = None,
    hidden: bool | None = None,
    note: str | None = None,
    goal_type: str | None = None,
    goal_day: int | None = None,
    goal_cadence: int | None = None,
    goal_cadence_frequency: int | None = None,
    goal_target: int | None = None,
    goal_target_date: str | None = None,
    goal_needs_whole_amount: bool | None = None,
    clear_goal: bool = False,
    plan_id: str | None = None,
    timeout_seconds: int | None = None,
) -> Any:
    """Update a category's metadata, group, hidden status, note, or target settings.

    goal_cadence values (0-14): 0=none, 1=monthly, 2=weekly, 13=yearly (due
    date repeats every goal_cadence * goal_cadence_frequency); 3=every 2
    months, 4=every 3 months, ... 12=every 11 months, 14=every 2 years
    (goal_cadence_frequency is ignored for these).

    Warning: YNAB silently ignores attempts to change goal_cadence on an
    existing goal -- if the response's goal_cadence doesn't match the
    request, this tool adds a "warning" field to the result instead of
    failing. To actually change cadence, call again with clear_goal=True to
    remove the goal, then set the new goal (with the desired goal_cadence)
    in a separate call.
    """
    args = ["update-category", category_id]
    add_optional(args, "--name", name)
    add_category_options(
        args,
        category_group_id,
        hidden,
        note,
        goal_type,
        goal_day,
        goal_cadence,
        goal_cadence_frequency,
        goal_target,
        goal_target_date,
        goal_needs_whole_amount,
        clear_goal,
    )
    add_plan(args, plan_id)
    return run_helper(args, timeout_seconds)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def ynab_get_month_category(
    month: str,
    category_id: str,
    plan_id: str | None = None,
    timeout_seconds: int | None = None,
) -> Any:
    """Get one category for one month. Month should be YYYY-MM-DD, usually the first of the month."""
    args = ["month-category", month, category_id]
    add_plan(args, plan_id)
    return run_helper(args, timeout_seconds)


@mcp.tool(annotations=UPDATE_ANNOTATIONS)
def ynab_update_month_category_budget(
    month: str,
    category_id: str,
    budgeted: int,
    plan_id: str | None = None,
    timeout_seconds: int | None = None,
) -> Any:
    """Set a category's budgeted amount for one month. Budgeted is in milliunits; $12.34 is 12340."""
    args = ["update-month-category", month, category_id, "--budgeted", str(budgeted)]
    add_plan(args, plan_id)
    return run_helper(args, timeout_seconds)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def ynab_list_payees(
    plan_id: str | None = None,
    timeout_seconds: int | None = None,
) -> Any:
    """List payees for a plan."""
    args = ["payees"]
    add_plan(args, plan_id)
    return run_helper(args, timeout_seconds)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def ynab_get_payee(
    payee_id: str,
    plan_id: str | None = None,
    timeout_seconds: int | None = None,
) -> Any:
    """Get one payee."""
    args = ["payee", payee_id]
    add_plan(args, plan_id)
    return run_helper(args, timeout_seconds)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def ynab_list_months(
    plan_id: str | None = None,
    timeout_seconds: int | None = None,
) -> Any:
    """List plan months."""
    args = ["months"]
    add_plan(args, plan_id)
    return run_helper(args, timeout_seconds)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def ynab_get_month(
    month: str,
    plan_id: str | None = None,
    timeout_seconds: int | None = None,
) -> Any:
    """Get one plan month. Month should be YYYY-MM-DD, usually the first of the month."""
    args = ["month", month]
    add_plan(args, plan_id)
    return run_helper(args, timeout_seconds)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def ynab_list_transactions(
    since_date: str | None = None,
    until_date: str | None = None,
    category_id: str | None = None,
    account_id: str | None = None,
    transaction_type: str | None = None,
    plan_id: str | None = None,
    timeout_seconds: int | None = None,
) -> Any:
    """List transactions, optionally scoped to a category or account and/or a date range.

    since_date and until_date are inclusive ISO dates (YYYY-MM-DD). Set only
    one of category_id or account_id (not both) to scope the results to a
    single category or account server-side instead of fetching everything and
    filtering client-side. transaction_type may be uncategorized or unapproved.
    """
    args = ["transactions"]
    add_optional(args, "--since-date", since_date)
    add_optional(args, "--until-date", until_date)
    add_optional(args, "--category-id", category_id)
    add_optional(args, "--account-id", account_id)
    add_optional(args, "--type", transaction_type)
    add_plan(args, plan_id)
    return run_helper(args, timeout_seconds)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def ynab_get_transaction(
    transaction_id: str,
    plan_id: str | None = None,
    timeout_seconds: int | None = None,
) -> Any:
    """Get one transaction."""
    args = ["transaction", transaction_id]
    add_plan(args, plan_id)
    return run_helper(args, timeout_seconds)


def add_transaction_options(
    args: list[str],
    account_id: str | None = None,
    date: str | None = None,
    amount: int | None = None,
    payee_id: str | None = None,
    payee_name: str | None = None,
    category_id: str | None = None,
    memo: str | None = None,
    cleared: str | None = None,
    approved: bool | None = None,
    flag_color: str | None = None,
    import_id: str | None = None,
) -> None:
    add_optional(args, "--account-id", account_id)
    add_optional(args, "--date", date)
    add_optional(args, "--amount", amount)
    add_optional(args, "--payee-id", payee_id)
    add_optional(args, "--payee-name", payee_name)
    add_optional(args, "--category-id", category_id)
    add_optional(args, "--memo", memo)
    add_optional(args, "--cleared", cleared)
    add_optional_bool(args, "--approved", approved)
    add_optional(args, "--flag-color", flag_color)
    add_optional(args, "--import-id", import_id)


@mcp.tool(annotations=CREATE_ANNOTATIONS)
def ynab_create_transaction(
    account_id: str,
    date: str,
    amount: int,
    payee_id: str | None = None,
    payee_name: str | None = None,
    category_id: str | None = None,
    memo: str | None = None,
    cleared: str | None = None,
    approved: bool | None = None,
    flag_color: str | None = None,
    import_id: str | None = None,
    plan_id: str | None = None,
    timeout_seconds: int | None = None,
) -> Any:
    """Create one transaction. Amount is in milliunits; outflows are negative."""
    args = ["create-transaction"]
    add_transaction_options(
        args,
        account_id,
        date,
        amount,
        payee_id,
        payee_name,
        category_id,
        memo,
        cleared,
        approved,
        flag_color,
        import_id,
    )
    add_plan(args, plan_id)
    return run_helper(args, timeout_seconds)


@mcp.tool(annotations=UPDATE_ANNOTATIONS)
def ynab_update_transaction(
    transaction_id: str,
    account_id: str | None = None,
    date: str | None = None,
    amount: int | None = None,
    payee_id: str | None = None,
    payee_name: str | None = None,
    category_id: str | None = None,
    memo: str | None = None,
    cleared: str | None = None,
    approved: bool | None = None,
    flag_color: str | None = None,
    import_id: str | None = None,
    plan_id: str | None = None,
    timeout_seconds: int | None = None,
) -> Any:
    """Update one transaction."""
    args = ["update-transaction", transaction_id]
    add_transaction_options(
        args,
        account_id,
        date,
        amount,
        payee_id,
        payee_name,
        category_id,
        memo,
        cleared,
        approved,
        flag_color,
        import_id,
    )
    add_plan(args, plan_id)
    return run_helper(args, timeout_seconds)


@mcp.tool(annotations=UPDATE_ANNOTATIONS)
def ynab_update_transactions(
    updates: list[dict[str, Any]],
    plan_id: str | None = None,
    timeout_seconds: int | None = None,
) -> Any:
    """Update multiple transactions in a single call.

    Each item in updates must be an object with "id" (the transaction_id)
    plus any of the fields to change: account_id, date, amount, payee_id,
    payee_name, category_id, memo, cleared, approved, flag_color. Amount is
    in milliunits; outflows are negative.
    """
    args = ["update-transactions", "--updates-json", json.dumps(updates)]
    add_plan(args, plan_id)
    return run_helper(args, timeout_seconds)


@mcp.tool(annotations=DELETE_ANNOTATIONS)
def ynab_delete_transaction(
    transaction_id: str,
    plan_id: str | None = None,
    timeout_seconds: int | None = None,
) -> Any:
    """Delete one transaction."""
    args = ["delete-transaction", transaction_id]
    add_plan(args, plan_id)
    return run_helper(args, timeout_seconds)


@mcp.tool(annotations=IMPORT_ANNOTATIONS)
def ynab_import_transactions(
    plan_id: str | None = None,
    timeout_seconds: int | None = None,
) -> Any:
    """Import transactions from linked accounts."""
    args = ["import-transactions"]
    add_plan(args, plan_id)
    return run_helper(args, timeout_seconds)


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "streamable-http")
    if transport == "stdio":
        mcp.run(transport=transport)
    else:
        mcp.run(
            transport=transport,
            host=os.environ.get("MCP_HOST", "0.0.0.0"),
            port=int(os.environ.get("MCP_PORT", "8000")),
        )
