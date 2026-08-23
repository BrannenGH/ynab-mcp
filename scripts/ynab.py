#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent / "ynab.env"
DEFAULT_API_URL = "https://api.ynab.com/v1"
ACCOUNT_TYPES = (
    "checking",
    "savings",
    "cash",
    "creditCard",
    "lineOfCredit",
    "otherAsset",
    "otherLiability",
    "mortgage",
    "autoLoan",
    "studentLoan",
    "personalLoan",
    "medicalDebt",
    "otherDebt",
)

CREATABLE_ACCOUNT_TYPES = (
    "checking",
    "savings",
    "cash",
    "creditCard",
    "otherAsset",
    "otherLiability",
)

# CANNOT NATIVELY CREATE VIA THE API,
# MAP TO OTHER LIABILITY INSTEAD
ACCOUNT_TYPE_CREATE_ALTERNATIVES = {
    "lineOfCredit": "otherLiability",
    "mortgage": "otherLiability",
    "autoLoan": "otherLiability",
    "studentLoan": "otherLiability",
    "personalLoan": "otherLiability",
    "medicalDebt": "otherLiability",
    "otherDebt": "otherLiability",
}
CATEGORY_GOAL_TYPES = (
    "TB",
    "TBD",
    "MF",
    "NEED",
    "DEBT",
)


def load_env():
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def request_json(path, method="GET", payload=None, params=None):
    load_env()

    token = os.environ.get("YNAB_ACCESS_TOKEN")
    if not token:
        raise SystemExit(f"Set YNAB_ACCESS_TOKEN in {ENV_FILE}.")

    base_url = os.environ.get("YNAB_API_URL", DEFAULT_API_URL).rstrip("/")
    if params:
        query = urllib.parse.urlencode(
            {key: value for key, value in params.items() if value is not None}
        )
        if query:
            path = f"{path}?{query}"

    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        f"{base_url}{path}", data=data, method=method, headers=headers
    )
    try:
        with urllib.request.urlopen(request) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8")
        try:
            details = json.loads(body)
        except json.JSONDecodeError:
            details = body or error.reason
        print(json.dumps({"status": error.code, "error": details}, indent=2), file=sys.stderr)
        raise SystemExit(1) from error


def plan_id(args):
    load_env()
    return getattr(args, "plan_id", None) or os.environ.get("YNAB_PLAN_ID", "default")


def transaction_payload(args, partial=False):
    fields = (
        "account_id",
        "date",
        "amount",
        "payee_id",
        "payee_name",
        "category_id",
        "memo",
        "cleared",
        "approved",
        "flag_color",
        "import_id",
    )
    payload = {
        field: getattr(args, field)
        for field in fields
        if getattr(args, field, None) is not None
    }
    if not partial:
        missing = [field for field in ("account_id", "date", "amount") if field not in payload]
        if missing:
            raise SystemExit(f"Missing required fields: {', '.join(missing)}")
    elif not payload:
        raise SystemExit("No update fields provided.")
    return payload


def account_payload(args):
    return {
        "name": args.name,
        "type": args.type,
        "balance": args.balance,
    }


def compact_payload(args, fields, partial=False):
    payload = {
        field: getattr(args, field)
        for field in fields
        if getattr(args, field, None) is not None
    }
    if partial and not payload:
        raise SystemExit("No update fields provided.")
    return payload


def category_group_payload(args, partial=False):
    return compact_payload(args, ("name", "hidden"), partial=partial)


def category_payload(args, partial=False):
    fields = (
        "name",
        "category_group_id",
        "hidden",
        "note",
        "goal_type",
        "goal_day",
        "goal_cadence",
        "goal_cadence_frequency",
        "goal_target",
        "goal_target_date",
        "goal_needs_whole_amount",
    )
    payload = {
        field: getattr(args, field)
        for field in fields
        if getattr(args, field, None) is not None
    }
    if getattr(args, "clear_goal", False):
        # Setting goal_type to null clears the whole goal (cadence, target,
        # day, etc). It's the only documented way to change goal_cadence,
        # since YNAB silently ignores cadence changes on an existing goal.
        payload["goal_type"] = None
    if partial and not payload:
        raise SystemExit("No update fields provided.")
    if not partial and "name" not in payload:
        raise SystemExit("Missing required field: name")
    return payload


def add_plan_argument(parser):
    parser.add_argument(
        "--plan-id",
        help="YNAB plan ID; defaults to YNAB_PLAN_ID or 'default'.",
    )


def add_transaction_fields(parser, required=False):
    parser.add_argument("--account-id", required=required)
    parser.add_argument("--date", required=required, help="ISO date: YYYY-MM-DD")
    parser.add_argument(
        "--amount",
        required=required,
        type=int,
        help="Amount in milliunits; $12.34 is 12340 and an outflow is negative.",
    )
    parser.add_argument("--payee-id")
    parser.add_argument("--payee-name")
    parser.add_argument("--category-id")
    parser.add_argument("--memo")
    parser.add_argument("--cleared", choices=("cleared", "uncleared", "reconciled"))
    parser.add_argument("--approved", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument(
        "--flag-color",
        choices=("red", "orange", "yellow", "green", "blue", "purple", "none"),
    )
    parser.add_argument("--import-id")


def add_category_group_fields(parser, required=False):
    parser.add_argument("--name", required=required)
    parser.add_argument("--hidden", action=argparse.BooleanOptionalAction, default=None)


def add_category_fields(parser, required=False):
    parser.add_argument("--name", required=required)
    parser.add_argument("--category-group-id")
    parser.add_argument("--hidden", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--note")
    parser.add_argument("--goal-type", choices=CATEGORY_GOAL_TYPES)
    parser.add_argument("--goal-day", type=int)
    parser.add_argument(
        "--goal-cadence",
        type=int,
        help=(
            "Goal cadence, 0-14: 0=none, 1=monthly, 2=weekly, 13=yearly "
            "(due date repeats every goal_cadence * goal_cadence_frequency); "
            "3=every 2 months, 4=every 3 months, ... 12=every 11 months, "
            "14=every 2 years (goal_cadence_frequency ignored). YNAB silently "
            "ignores attempts to change goal_cadence on an existing goal; use "
            "--clear-goal first, then set the new goal in a separate call."
        ),
    )
    parser.add_argument("--goal-cadence-frequency", type=int)
    parser.add_argument(
        "--goal-target",
        type=int,
        help="Target amount in milliunits; $12.34 is 12340.",
    )
    parser.add_argument("--goal-target-date", help="ISO date: YYYY-MM-DD")
    parser.add_argument(
        "--goal-needs-whole-amount",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    parser.add_argument(
        "--clear-goal",
        action="store_true",
        help="Clear the category's existing goal (goal_type, cadence, target, day).",
    )


def main():
    parser = argparse.ArgumentParser(description="Small YNAB API helper.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("user", help="Get the authenticated user.")
    sub.add_parser("plans", help="List YNAB plans.")

    plan = sub.add_parser("plan", help="Get one plan.")
    add_plan_argument(plan)

    accounts = sub.add_parser("accounts", help="List accounts.")
    add_plan_argument(accounts)
    account = sub.add_parser("account", help="Get one account.")
    account.add_argument("account_id")
    add_plan_argument(account)
    create_account = sub.add_parser("create-account", help="Create one unlinked account.")
    create_account.add_argument("--name", required=True)
    create_account.add_argument("--type", required=True, choices=ACCOUNT_TYPES)
    create_account.add_argument(
        "--balance",
        required=True,
        type=int,
        help="Starting balance in milliunits; $12.34 is 12340 and debt is negative.",
    )
    add_plan_argument(create_account)

    categories = sub.add_parser("categories", help="List category groups and categories.")
    categories.add_argument("--last-knowledge-of-server", type=int)
    add_plan_argument(categories)
    category_groups = sub.add_parser("category-groups", help="List category groups.")
    add_plan_argument(category_groups)
    category_group = sub.add_parser("category-group", help="Get one category group.")
    category_group.add_argument("category_group_id")
    add_plan_argument(category_group)
    create_category_group = sub.add_parser(
        "create-category-group", help="Create one category group."
    )
    add_category_group_fields(create_category_group, required=True)
    add_plan_argument(create_category_group)
    update_category_group = sub.add_parser(
        "update-category-group", help="Update one category group."
    )
    update_category_group.add_argument("category_group_id")
    add_category_group_fields(update_category_group)
    add_plan_argument(update_category_group)
    category = sub.add_parser("category", help="Get one category.")
    category.add_argument("category_id")
    add_plan_argument(category)
    create_category = sub.add_parser("create-category", help="Create one category.")
    add_category_fields(create_category, required=True)
    add_plan_argument(create_category)
    update_category = sub.add_parser("update-category", help="Update one category.")
    update_category.add_argument("category_id")
    add_category_fields(update_category)
    add_plan_argument(update_category)

    payees = sub.add_parser("payees", help="List payees.")
    add_plan_argument(payees)
    payee = sub.add_parser("payee", help="Get one payee.")
    payee.add_argument("payee_id")
    add_plan_argument(payee)

    months = sub.add_parser("months", help="List plan months.")
    add_plan_argument(months)
    month = sub.add_parser("month", help="Get one plan month.")
    month.add_argument("month", help="YYYY-MM-DD, usually the first of the month")
    add_plan_argument(month)
    month_category = sub.add_parser("month-category", help="Get one category in one month.")
    month_category.add_argument("month", help="YYYY-MM-DD, usually the first of the month")
    month_category.add_argument("category_id")
    add_plan_argument(month_category)
    update_month_category = sub.add_parser(
        "update-month-category", help="Update one category's budgeted amount for one month."
    )
    update_month_category.add_argument("month", help="YYYY-MM-DD, usually the first of the month")
    update_month_category.add_argument("category_id")
    update_month_category.add_argument(
        "--budgeted",
        required=True,
        type=int,
        help="Budgeted amount in milliunits; $12.34 is 12340.",
    )
    add_plan_argument(update_month_category)

    transactions = sub.add_parser("transactions", help="List transactions.")
    transactions.add_argument("--since-date", help="Only transactions on or after YYYY-MM-DD.")
    transactions.add_argument(
        "--until-date", help="Only transactions on or before YYYY-MM-DD (inclusive)."
    )
    transactions.add_argument("--category-id", help="Only transactions in this category.")
    transactions.add_argument("--account-id", help="Only transactions in this account.")
    transactions.add_argument(
        "--type", choices=("uncategorized", "unapproved"), dest="transaction_type"
    )
    add_plan_argument(transactions)

    transaction = sub.add_parser("transaction", help="Get one transaction.")
    transaction.add_argument("transaction_id")
    add_plan_argument(transaction)

    create = sub.add_parser("create-transaction", help="Create one transaction.")
    add_transaction_fields(create, required=True)
    add_plan_argument(create)

    update = sub.add_parser("update-transaction", help="Update one transaction.")
    update.add_argument("transaction_id")
    add_transaction_fields(update)
    add_plan_argument(update)

    update_many = sub.add_parser(
        "update-transactions", help="Update multiple transactions in one call."
    )
    update_many.add_argument(
        "--updates-json",
        required=True,
        help=(
            'JSON array of updates, each an object with "id" (the '
            'transaction_id) plus the fields to change, e.g. '
            '\'[{"id": "txn-1", "category_id": "cat-1"}, '
            '{"id": "txn-2", "memo": "fixed"}]\'.'
        ),
    )
    add_plan_argument(update_many)

    delete = sub.add_parser("delete-transaction", help="Delete one transaction.")
    delete.add_argument("transaction_id")
    add_plan_argument(delete)

    import_transactions = sub.add_parser(
        "import-transactions", help="Import transactions from linked accounts."
    )
    add_plan_argument(import_transactions)

    args = parser.parse_args()
    plan = urllib.parse.quote(plan_id(args), safe="")

    if args.cmd == "user":
        result = request_json("/user")
    elif args.cmd == "plans":
        result = request_json("/plans")
    elif args.cmd == "plan":
        result = request_json(f"/plans/{plan}")
    elif args.cmd == "accounts":
        result = request_json(f"/plans/{plan}/accounts")
    elif args.cmd == "account":
        result = request_json(f"/plans/{plan}/accounts/{args.account_id}")
    elif args.cmd == "create-account":
        if args.type not in CREATABLE_ACCOUNT_TYPES:
            alternative = ACCOUNT_TYPE_CREATE_ALTERNATIVES.get(args.type, "otherLiability")
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": "invalid_account_type_for_creation",
                        "message": (
                            f"'{args.type}' is a valid YNAB account type, but it is not "
                            "one YNAB's account-creation API accepts. POST "
                            "/budgets/{budget_id}/accounts (the SaveAccount schema; see "
                            "https://api.ynab.com/v1 -> Accounts) only allows type to be "
                            f"one of: {', '.join(CREATABLE_ACCOUNT_TYPES)}. "
                            f"'{args.type}' shows up when reading existing accounts and is "
                            "selectable in the YNAB app, but the public API has no way to "
                            "set it at creation, and no update/PATCH endpoint for accounts "
                            "exists to change it afterward either."
                        ),
                        "requested_type": args.type,
                        "suggested_type": alternative,
                        "next_step": (
                            f"Create the account with --type {alternative} (use "
                            "otherAsset instead if this account tracks money owed TO "
                            "you, e.g. accounts receivable), then open it in the YNAB "
                            f"web or mobile app and change its type to '{args.type}' "
                            "from Account Settings."
                        ),
                    },
                    indent=2,
                ),
                file=sys.stderr,
            )
            raise SystemExit(1)
        result = request_json(
            f"/plans/{plan}/accounts",
            method="POST",
            payload={"account": account_payload(args)},
        )
    elif args.cmd == "categories":
        result = request_json(
            f"/plans/{plan}/categories",
            params={"last_knowledge_of_server": args.last_knowledge_of_server},
        )
    elif args.cmd == "category-groups":
        categories_result = request_json(f"/plans/{plan}/categories")
        data = categories_result.get("data", {})
        result = {
            "data": {
                "category_groups": data.get("category_groups", []),
                "server_knowledge": data.get("server_knowledge"),
            }
        }
    elif args.cmd == "category-group":
        categories_result = request_json(f"/plans/{plan}/categories")
        data = categories_result.get("data", {})
        category_group = next(
            (
                group
                for group in data.get("category_groups", [])
                if group.get("id") == args.category_group_id
            ),
            None,
        )
        if category_group is None:
            print(
                json.dumps(
                    {
                        "status": 404,
                        "error": {
                            "error": {
                                "id": "404.2",
                                "name": "resource_not_found",
                                "detail": "Resource not found",
                            }
                        },
                    },
                    indent=2,
                ),
                file=sys.stderr,
            )
            raise SystemExit(1)
        result = {
            "data": {
                "category_group": category_group,
                "server_knowledge": data.get("server_knowledge"),
            }
        }
    elif args.cmd == "create-category-group":
        result = request_json(
            f"/plans/{plan}/category_groups",
            method="POST",
            payload={"category_group": category_group_payload(args)},
        )
    elif args.cmd == "update-category-group":
        result = request_json(
            f"/plans/{plan}/category_groups/{args.category_group_id}",
            method="PATCH",
            payload={"category_group": category_group_payload(args, partial=True)},
        )
    elif args.cmd == "category":
        result = request_json(f"/plans/{plan}/categories/{args.category_id}")
    elif args.cmd == "create-category":
        result = request_json(
            f"/plans/{plan}/categories",
            method="POST",
            payload={"category": category_payload(args)},
        )
    elif args.cmd == "update-category":
        payload = category_payload(args, partial=True)
        result = request_json(
            f"/plans/{plan}/categories/{args.category_id}",
            method="PATCH",
            payload={"category": payload},
        )
        requested_cadence = payload.get("goal_cadence")
        if requested_cadence is not None:
            actual_cadence = result.get("data", {}).get("category", {}).get("goal_cadence")
            if actual_cadence != requested_cadence:
                result["warning"] = (
                    f"goal_cadence could not be changed from {actual_cadence} to "
                    f"{requested_cadence} on an existing goal; YNAB silently "
                    "ignores cadence changes on existing goals. Call update-category "
                    "again with --clear-goal to clear it, then set the new goal "
                    "(including the desired goal_cadence) in a separate call."
                )
    elif args.cmd == "payees":
        result = request_json(f"/plans/{plan}/payees")
    elif args.cmd == "payee":
        result = request_json(f"/plans/{plan}/payees/{args.payee_id}")
    elif args.cmd == "months":
        result = request_json(f"/plans/{plan}/months")
    elif args.cmd == "month":
        result = request_json(f"/plans/{plan}/months/{args.month}")
    elif args.cmd == "month-category":
        result = request_json(
            f"/plans/{plan}/months/{args.month}/categories/{args.category_id}"
        )
    elif args.cmd == "update-month-category":
        result = request_json(
            f"/plans/{plan}/months/{args.month}/categories/{args.category_id}",
            method="PATCH",
            payload={"month_category": {"budgeted": args.budgeted}},
        )
    elif args.cmd == "transactions":
        if args.category_id and args.account_id:
            raise SystemExit("Use only one of --category-id or --account-id.")
        if args.category_id:
            path = f"/plans/{plan}/transactions/by_category/{args.category_id}"
        elif args.account_id:
            path = f"/plans/{plan}/transactions/by_account/{args.account_id}"
        else:
            path = f"/plans/{plan}/transactions"
        result = request_json(
            path,
            params={"since_date": args.since_date, "type": args.transaction_type},
        )
        if args.until_date:
            data = result.get("data", {})
            data["transactions"] = [
                txn
                for txn in data.get("transactions", [])
                if txn.get("date") and txn["date"] <= args.until_date
            ]
    elif args.cmd == "transaction":
        result = request_json(f"/plans/{plan}/transactions/{args.transaction_id}")
    elif args.cmd == "create-transaction":
        result = request_json(
            f"/plans/{plan}/transactions",
            method="POST",
            payload={"transaction": transaction_payload(args)},
        )
    elif args.cmd == "update-transaction":
        result = request_json(
            f"/plans/{plan}/transactions/{args.transaction_id}",
            method="PUT",
            payload={"transaction": transaction_payload(args, partial=True)},
        )
    elif args.cmd == "update-transactions":
        try:
            updates = json.loads(args.updates_json)
        except json.JSONDecodeError as error:
            raise SystemExit(f"Invalid --updates-json: {error}") from error
        if not isinstance(updates, list) or not updates:
            raise SystemExit("--updates-json must be a non-empty JSON array.")
        for update in updates:
            if not isinstance(update, dict) or "id" not in update:
                raise SystemExit('Each update must be an object with an "id" field.')
        result = request_json(
            f"/plans/{plan}/transactions",
            method="PATCH",
            payload={"transactions": updates},
        )
    elif args.cmd == "delete-transaction":
        result = request_json(
            f"/plans/{plan}/transactions/{args.transaction_id}", method="DELETE"
        )
    elif args.cmd == "import-transactions":
        result = request_json(f"/plans/{plan}/transactions/import", method="POST")

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
