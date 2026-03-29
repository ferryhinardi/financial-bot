"""
Onboarding Flow for Financial Tracker Bot
Walks new users through initial financial setup via Telegram conversation.
"""

import json
import os
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from config import is_user_allowed, local_now

# ── Conversation States ──
(
    WELCOME,
    # Savings
    ASK_HAS_SAVINGS,
    ASK_SAVINGS_ACCOUNT,
    ASK_SAVINGS_AMOUNT,
    ASK_SAVINGS_GOAL,
    ASK_MORE_SAVINGS,
    # Investments / Assets
    ASK_HAS_ASSETS,
    ASK_ASSET_NAME,
    ASK_ASSET_VALUE,
    ASK_ASSET_TYPE,
    ASK_MORE_ASSETS,
    # Income
    ASK_HAS_INCOME,
    ASK_INCOME_SOURCE,
    ASK_INCOME_AMOUNT,
    ASK_INCOME_FREQUENCY,
    ASK_MORE_INCOME,
    # Recurring Bills
    ASK_HAS_BILLS,
    ASK_BILL_NAME,
    ASK_BILL_AMOUNT,
    ASK_BILL_CATEGORY,
    ASK_MORE_BILLS,
    # Budget
    ASK_SET_BUDGET,
    ASK_BUDGET_CATEGORY,
    ASK_BUDGET_AMOUNT,
    ASK_MORE_BUDGET,
    # Finish
    CONFIRM_SETUP,
) = range(26)

ONBOARDING_FILE = "onboarding_state.json"

SAVINGS_ACCOUNTS = [
    "Emergency Fund",
    "Vacation",
    "Investment",
    "Retirement",
    "Other",
]

BILL_CATEGORIES = [
    "Housing",
    "Bills & Utilities",
    "Transportation",
    "Healthcare",
    "Education",
    "Entertainment",
]

BUDGET_CATEGORIES = [
    "Food & Groceries",
    "Transportation",
    "Housing",
    "Entertainment",
    "Healthcare",
    "Education",
    "Shopping",
    "Bills & Utilities",
]

START_HELP_TEXT = (
    "Financial Tracker Bot is ready.\n\n"
    "Use /setup to run onboarding again.\n"
    "Use /quick, /spend, /income, /save, /summary, /budget, /savings, or /dashboard to manage your data."
)


def format_number(n):
    """Format number with thousand separators."""
    try:
        return f"{int(float(n)):,}"
    except (ValueError, TypeError):
        return str(n)


def _get_state_path(bot_dir=None):
    """Get path to onboarding state file."""
    if bot_dir:
        return os.path.join(bot_dir, ONBOARDING_FILE)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), ONBOARDING_FILE)


def is_onboarding_complete(user_id: int) -> bool:
    """Check if user has completed onboarding."""
    path = _get_state_path()
    if not os.path.exists(path):
        return False
    with open(path, "r") as f:
        data = json.load(f)
    return data.get(str(user_id), {}).get("completed", False)


def mark_onboarding_complete(user_id: int):
    """Mark onboarding as done for a user."""
    path = _get_state_path()
    data = {}
    if os.path.exists(path):
        with open(path, "r") as f:
            data = json.load(f)
    data.setdefault(str(user_id), {})["completed"] = True
    data[str(user_id)]["completed_at"] = local_now().isoformat()
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ═══════════════════════════════════════════════════════════════
# HANDLERS
# ═══════════════════════════════════════════════════════════════


async def start_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for onboarding. Called by /setup or automatically on first /start."""
    if not is_user_allowed(update.effective_user.id):
        await update.message.reply_text(
            "Unauthorized. Update ALLOWED_USER_IDS to grant access."
        )
        return ConversationHandler.END

    command = (update.message.text or "").split()[0].lower()
    if command == "/start" and is_onboarding_complete(update.effective_user.id):
        await update.message.reply_text(START_HELP_TEXT)
        return ConversationHandler.END

    context.user_data["onboarding"] = {
        "savings": [],
        "assets": [],
        "income": [],
        "bills": [],
        "budgets": [],
    }

    await update.message.reply_text(
        "Welcome to your Financial Tracker Bot!\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "I'll help you set up your financial profile.\n"
        "This takes about 3-5 minutes and will ask about:\n\n"
        "1. Your current savings\n"
        "2. Investments & assets\n"
        "3. Income sources\n"
        "4. Recurring monthly bills\n"
        "5. Monthly budget limits\n\n"
        "You can skip any section or type /cancel to stop.\n\n"
        "Let's start!",
    )

    keyboard = [
        [InlineKeyboardButton("Yes, I have savings", callback_data="savings_yes")],
        [InlineKeyboardButton("No savings yet, skip", callback_data="savings_no")],
    ]
    await update.message.reply_text(
        "STEP 1/5 - CURRENT SAVINGS\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Do you currently have any savings?\n"
        "(e.g., emergency fund, vacation fund, etc.)",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ASK_HAS_SAVINGS


# ───────────────────────────────────────────────────
# STEP 1: SAVINGS
# ───────────────────────────────────────────────────


async def handle_has_savings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "savings_no":
        return await _go_to_assets(query, context)

    keyboard = [
        [InlineKeyboardButton(a, callback_data=f"sav_{a}")] for a in SAVINGS_ACCOUNTS
    ]
    await query.edit_message_text(
        "Which savings account do you want to add?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ASK_SAVINGS_ACCOUNT


async def handle_savings_account(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    account = query.data.replace("sav_", "")
    context.user_data["onboarding"]["_current_savings_account"] = account

    await query.edit_message_text(
        f"Savings Account: {account}\n\n"
        "How much do you currently have in this account?\n"
        "(Enter the amount, e.g., 5000000)"
    )
    return ASK_SAVINGS_AMOUNT


async def handle_savings_amount(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    try:
        amount = float(update.message.text.replace(",", "").replace(".", "").strip())
    except ValueError:
        await update.message.reply_text("Please enter a valid number (e.g., 5000000):")
        return ASK_SAVINGS_AMOUNT

    account = context.user_data["onboarding"]["_current_savings_account"]
    context.user_data["onboarding"]["_current_savings_amount"] = amount

    await update.message.reply_text(
        f"{account}: {format_number(amount)}\n\n"
        "What is your savings goal for this account?\n"
        "(Enter the target amount, or type 'skip' if no goal)"
    )
    return ASK_SAVINGS_GOAL


async def handle_savings_goal(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    text = update.message.text.strip().lower()
    goal = None
    if text != "skip":
        try:
            goal = float(text.replace(",", "").replace(".", ""))
        except ValueError:
            await update.message.reply_text("Enter a valid number or 'skip':")
            return ASK_SAVINGS_GOAL

    account = context.user_data["onboarding"]["_current_savings_account"]
    amount = context.user_data["onboarding"]["_current_savings_amount"]

    context.user_data["onboarding"]["savings"].append(
        {
            "account": account,
            "amount": amount,
            "goal": goal,
        }
    )

    goal_text = f" (Goal: {format_number(goal)})" if goal else ""
    await update.message.reply_text(
        f"Saved: {account} = {format_number(amount)}{goal_text}"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "Add another savings account", callback_data="savings_yes"
            )
        ],
        [
            InlineKeyboardButton(
                "Done with savings, continue", callback_data="savings_no"
            )
        ],
    ]
    await update.message.reply_text(
        "Add another savings account?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ASK_MORE_SAVINGS


async def handle_more_savings(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "savings_yes":
        keyboard = [
            [InlineKeyboardButton(a, callback_data=f"sav_{a}")]
            for a in SAVINGS_ACCOUNTS
        ]
        await query.edit_message_text(
            "Which savings account?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return ASK_SAVINGS_ACCOUNT
    return await _go_to_assets(query, context)


# ───────────────────────────────────────────────────
# STEP 2: INVESTMENTS & ASSETS
# ───────────────────────────────────────────────────


async def _go_to_assets(query, context) -> int:
    keyboard = [
        [
            InlineKeyboardButton(
                "Yes, I have assets/investments", callback_data="assets_yes"
            )
        ],
        [InlineKeyboardButton("No, skip this", callback_data="assets_no")],
    ]
    await query.edit_message_text(
        "STEP 2/5 - INVESTMENTS & ASSETS\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Do you have any investments or assets?\n"
        "(e.g., stocks, mutual funds, crypto, gold, property, vehicle)",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ASK_HAS_ASSETS


async def handle_has_assets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "assets_no":
        return await _go_to_income(query, context)

    await query.edit_message_text(
        "What is the name/description of this asset?\n"
        "(e.g., 'BCA Mutual Fund', 'Gold 10g', 'Honda Civic 2020')"
    )
    return ASK_ASSET_NAME


async def handle_asset_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["onboarding"]["_current_asset_name"] = update.message.text.strip()
    await update.message.reply_text(
        f"Asset: {update.message.text.strip()}\n\n"
        "What is the current estimated value?\n"
        "(Enter the amount, e.g., 10000000)"
    )
    return ASK_ASSET_VALUE


async def handle_asset_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        value = float(update.message.text.replace(",", "").replace(".", "").strip())
    except ValueError:
        await update.message.reply_text("Please enter a valid number:")
        return ASK_ASSET_VALUE

    context.user_data["onboarding"]["_current_asset_value"] = value

    keyboard = [
        [InlineKeyboardButton("Stocks", callback_data="atype_Stocks")],
        [InlineKeyboardButton("Mutual Fund", callback_data="atype_Mutual Fund")],
        [InlineKeyboardButton("Crypto", callback_data="atype_Crypto")],
        [InlineKeyboardButton("Gold/Precious Metals", callback_data="atype_Gold")],
        [InlineKeyboardButton("Property", callback_data="atype_Property")],
        [InlineKeyboardButton("Vehicle", callback_data="atype_Vehicle")],
        [InlineKeyboardButton("Other", callback_data="atype_Other")],
    ]
    await update.message.reply_text(
        "What type of asset is this?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ASK_ASSET_TYPE


async def handle_asset_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    asset_type = query.data.replace("atype_", "")

    name = context.user_data["onboarding"]["_current_asset_name"]
    value = context.user_data["onboarding"]["_current_asset_value"]

    context.user_data["onboarding"]["assets"].append(
        {
            "name": name,
            "value": value,
            "type": asset_type,
        }
    )

    await query.edit_message_text(
        f"Saved: {name} ({asset_type}) = {format_number(value)}"
    )

    keyboard = [
        [InlineKeyboardButton("Add another asset", callback_data="assets_yes")],
        [InlineKeyboardButton("Done, continue", callback_data="assets_no")],
    ]
    # Need to send new message since we edited the previous one
    await query.message.reply_text(
        "Add another asset or investment?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ASK_MORE_ASSETS


async def handle_more_assets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "assets_yes":
        await query.edit_message_text("What is the name/description of this asset?")
        return ASK_ASSET_NAME
    return await _go_to_income(query, context)


# ───────────────────────────────────────────────────
# STEP 3: INCOME SOURCES
# ───────────────────────────────────────────────────


async def _go_to_income(query, context) -> int:
    keyboard = [
        [
            InlineKeyboardButton(
                "Yes, let me add income sources", callback_data="income_yes"
            )
        ],
        [InlineKeyboardButton("No, skip", callback_data="income_no")],
    ]
    await query.edit_message_text(
        "STEP 3/5 - INCOME SOURCES\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Do you have regular income sources?\n"
        "(e.g., salary, freelance, side business, rental income)",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ASK_HAS_INCOME


async def handle_has_income(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "income_no":
        return await _go_to_bills(query, context)

    await query.edit_message_text(
        "What is the source name?\n"
        "(e.g., 'PT ABC - Salary', 'Freelance Design', 'Kos Rental')"
    )
    return ASK_INCOME_SOURCE


async def handle_income_source(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    context.user_data["onboarding"]["_current_income_source"] = (
        update.message.text.strip()
    )
    await update.message.reply_text(
        f"Source: {update.message.text.strip()}\n\n"
        "How much do you receive per month (net/take-home)?\n"
        "(Enter the amount, e.g., 8000000)"
    )
    return ASK_INCOME_AMOUNT


async def handle_income_amount(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    try:
        amount = float(update.message.text.replace(",", "").replace(".", "").strip())
    except ValueError:
        await update.message.reply_text("Please enter a valid number:")
        return ASK_INCOME_AMOUNT

    context.user_data["onboarding"]["_current_income_amount"] = amount

    keyboard = [
        [InlineKeyboardButton("Monthly", callback_data="freq_Monthly")],
        [InlineKeyboardButton("Bi-weekly", callback_data="freq_Bi-weekly")],
        [InlineKeyboardButton("Weekly", callback_data="freq_Weekly")],
        [InlineKeyboardButton("Irregular/Varies", callback_data="freq_Irregular")],
    ]
    await update.message.reply_text(
        "How often do you receive this income?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ASK_INCOME_FREQUENCY


async def handle_income_frequency(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    frequency = query.data.replace("freq_", "")

    source = context.user_data["onboarding"]["_current_income_source"]
    amount = context.user_data["onboarding"]["_current_income_amount"]

    context.user_data["onboarding"]["income"].append(
        {
            "source": source,
            "amount": amount,
            "frequency": frequency,
        }
    )

    await query.edit_message_text(
        f"Saved: {source} = {format_number(amount)}/month ({frequency})"
    )

    keyboard = [
        [InlineKeyboardButton("Add another income source", callback_data="income_yes")],
        [InlineKeyboardButton("Done, continue", callback_data="income_no")],
    ]
    await query.message.reply_text(
        "Add another income source?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ASK_MORE_INCOME


async def handle_more_income(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "income_yes":
        await query.edit_message_text("What is the source name?")
        return ASK_INCOME_SOURCE
    return await _go_to_bills(query, context)


# ───────────────────────────────────────────────────
# STEP 4: RECURRING BILLS
# ───────────────────────────────────────────────────


async def _go_to_bills(query, context) -> int:
    keyboard = [
        [
            InlineKeyboardButton(
                "Yes, I have recurring bills", callback_data="bills_yes"
            )
        ],
        [InlineKeyboardButton("No, skip", callback_data="bills_no")],
    ]
    await query.edit_message_text(
        "STEP 4/5 - RECURRING MONTHLY BILLS\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Do you have recurring monthly bills?\n"
        "(e.g., rent, electricity, water, internet,\n"
        " phone plan, insurance, subscriptions,\n"
        " loan/debt payments, gym membership)",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ASK_HAS_BILLS


async def handle_has_bills(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "bills_no":
        return await _go_to_budget(query, context)

    await query.edit_message_text(
        "What is the bill name?\n"
        "(e.g., 'Rent', 'PLN Electricity', 'Indihome Internet',\n"
        " 'Telkomsel Phone', 'BPJS Health', 'Netflix', 'Car Loan')"
    )
    return ASK_BILL_NAME


async def handle_bill_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["onboarding"]["_current_bill_name"] = update.message.text.strip()
    await update.message.reply_text(
        f"Bill: {update.message.text.strip()}\n\n"
        "How much is this bill per month?\n"
        "(Enter the amount, e.g., 500000)"
    )
    return ASK_BILL_AMOUNT


async def handle_bill_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount = float(update.message.text.replace(",", "").replace(".", "").strip())
    except ValueError:
        await update.message.reply_text("Please enter a valid number:")
        return ASK_BILL_AMOUNT

    context.user_data["onboarding"]["_current_bill_amount"] = amount

    keyboard = [
        [InlineKeyboardButton(c, callback_data=f"bcat_{c}")] for c in BILL_CATEGORIES
    ]
    await update.message.reply_text(
        "Which category does this bill belong to?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ASK_BILL_CATEGORY


async def handle_bill_category(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    category = query.data.replace("bcat_", "")

    name = context.user_data["onboarding"]["_current_bill_name"]
    amount = context.user_data["onboarding"]["_current_bill_amount"]

    context.user_data["onboarding"]["bills"].append(
        {
            "name": name,
            "amount": amount,
            "category": category,
        }
    )

    await query.edit_message_text(
        f"Saved: {name} = {format_number(amount)}/month ({category})"
    )

    keyboard = [
        [InlineKeyboardButton("Add another bill", callback_data="bills_yes")],
        [InlineKeyboardButton("Done, continue", callback_data="bills_no")],
    ]
    await query.message.reply_text(
        "Add another recurring bill?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ASK_MORE_BILLS


async def handle_more_bills(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "bills_yes":
        await query.edit_message_text("What is the bill name?")
        return ASK_BILL_NAME
    return await _go_to_budget(query, context)


# ───────────────────────────────────────────────────
# STEP 5: BUDGET LIMITS
# ───────────────────────────────────────────────────


async def _go_to_budget(query, context) -> int:
    # Calculate suggested budgets from bills
    bills = context.user_data["onboarding"].get("bills", [])
    total_bills = sum(b["amount"] for b in bills)
    income = context.user_data["onboarding"].get("income", [])
    total_income = sum(i["amount"] for i in income)

    suggestion = ""
    if total_income > 0:
        suggestion = (
            f"\n\nBased on your income ({format_number(total_income)}/month):\n"
            f"  Bills so far: {format_number(total_bills)}\n"
            f"  Remaining: {format_number(total_income - total_bills)}"
        )

    keyboard = [
        [
            InlineKeyboardButton(
                "Yes, set budgets per category", callback_data="budget_yes"
            )
        ],
        [InlineKeyboardButton("Use defaults, skip", callback_data="budget_default")],
        [InlineKeyboardButton("No budget, skip", callback_data="budget_no")],
    ]
    await query.edit_message_text(
        "STEP 5/5 - MONTHLY BUDGET LIMITS\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Would you like to set monthly spending limits per category?\n"
        "This helps track overspending."
        f"{suggestion}",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ASK_SET_BUDGET


async def handle_set_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "budget_no":
        return await _go_to_confirm(query, context)

    if query.data == "budget_default":
        # Set default budgets
        defaults = {
            "Food & Groceries": 500000,
            "Transportation": 200000,
            "Housing": 1500000,
            "Entertainment": 200000,
            "Healthcare": 300000,
            "Education": 200000,
            "Shopping": 300000,
            "Bills & Utilities": 500000,
        }
        # Adjust based on income if available
        income = context.user_data["onboarding"].get("income", [])
        total_income = sum(i["amount"] for i in income)
        if total_income > 0:
            scale = total_income / 3700000  # default total
            defaults = {
                k: round(v * scale / 10000) * 10000 for k, v in defaults.items()
            }

        for cat, amt in defaults.items():
            context.user_data["onboarding"]["budgets"].append(
                {
                    "category": cat,
                    "amount": amt,
                }
            )
        return await _go_to_confirm(query, context)

    # Manual budget entry
    context.user_data["onboarding"]["_budget_index"] = 0
    cat = BUDGET_CATEGORIES[0]
    await query.edit_message_text(
        f"Budget for: {cat}\n\nEnter the monthly limit (or 'skip' to leave empty):"
    )
    return ASK_BUDGET_AMOUNT


async def handle_budget_amount(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    text = update.message.text.strip().lower()
    idx = context.user_data["onboarding"].get("_budget_index", 0)
    cat = BUDGET_CATEGORIES[idx]

    if text != "skip":
        try:
            amount = float(text.replace(",", "").replace(".", ""))
            context.user_data["onboarding"]["budgets"].append(
                {
                    "category": cat,
                    "amount": amount,
                }
            )
        except ValueError:
            await update.message.reply_text("Enter a valid number or 'skip':")
            return ASK_BUDGET_AMOUNT

    idx += 1
    context.user_data["onboarding"]["_budget_index"] = idx

    if idx < len(BUDGET_CATEGORIES):
        next_cat = BUDGET_CATEGORIES[idx]
        await update.message.reply_text(
            f"Budget for: {next_cat}\n\nEnter the monthly limit (or 'skip'):"
        )
        return ASK_BUDGET_AMOUNT

    # All done
    # Use a callback trick: send an inline message and call _go_to_confirm
    await update.message.reply_text("Budget limits set!")
    # We need to go to confirm, but we're in a message handler, not callback
    return await _show_confirm_from_message(update, context)


# ───────────────────────────────────────────────────
# CONFIRMATION & WRITE TO EXCEL
# ───────────────────────────────────────────────────


async def _go_to_confirm(query, context) -> int:
    ob = context.user_data["onboarding"]
    summary = _build_summary(ob)

    keyboard = [
        [InlineKeyboardButton("Confirm & Save", callback_data="confirm_yes")],
        [InlineKeyboardButton("Start Over", callback_data="confirm_restart")],
        [InlineKeyboardButton("Cancel", callback_data="confirm_cancel")],
    ]
    await query.edit_message_text(
        f"SETUP SUMMARY\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{summary}\n\n"
        f"Save this to your Financial Tracker?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CONFIRM_SETUP


async def _show_confirm_from_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    ob = context.user_data["onboarding"]
    summary = _build_summary(ob)

    keyboard = [
        [InlineKeyboardButton("Confirm & Save", callback_data="confirm_yes")],
        [InlineKeyboardButton("Start Over", callback_data="confirm_restart")],
        [InlineKeyboardButton("Cancel", callback_data="confirm_cancel")],
    ]
    await update.message.reply_text(
        f"SETUP SUMMARY\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{summary}\n\n"
        f"Save this to your Financial Tracker?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CONFIRM_SETUP


def _build_summary(ob: dict) -> str:
    """Build a readable summary of collected onboarding data."""
    lines = []

    # Savings
    if ob["savings"]:
        lines.append("SAVINGS:")
        total_sav = 0
        for s in ob["savings"]:
            goal_text = f" (goal: {format_number(s['goal'])})" if s.get("goal") else ""
            lines.append(f"  {s['account']}: {format_number(s['amount'])}{goal_text}")
            total_sav += s["amount"]
        lines.append(f"  Total: {format_number(total_sav)}")
    else:
        lines.append("SAVINGS: (none)")

    lines.append("")

    # Assets
    if ob["assets"]:
        lines.append("ASSETS & INVESTMENTS:")
        total_assets = 0
        for a in ob["assets"]:
            lines.append(f"  {a['name']} ({a['type']}): {format_number(a['value'])}")
            total_assets += a["value"]
        lines.append(f"  Total: {format_number(total_assets)}")
    else:
        lines.append("ASSETS: (none)")

    lines.append("")

    # Income
    if ob["income"]:
        lines.append("INCOME SOURCES:")
        total_inc = 0
        for i in ob["income"]:
            lines.append(
                f"  {i['source']}: {format_number(i['amount'])}/month ({i['frequency']})"
            )
            total_inc += i["amount"]
        lines.append(f"  Total: {format_number(total_inc)}/month")
    else:
        lines.append("INCOME: (none)")

    lines.append("")

    # Bills
    if ob["bills"]:
        lines.append("RECURRING BILLS:")
        total_bills = 0
        for b in ob["bills"]:
            lines.append(
                f"  {b['name']} ({b['category']}): {format_number(b['amount'])}/month"
            )
            total_bills += b["amount"]
        lines.append(f"  Total: {format_number(total_bills)}/month")
    else:
        lines.append("RECURRING BILLS: (none)")

    lines.append("")

    # Budgets
    if ob["budgets"]:
        lines.append("MONTHLY BUDGETS:")
        total_budget = 0
        for bg in ob["budgets"]:
            lines.append(f"  {bg['category']}: {format_number(bg['amount'])}")
            total_budget += bg["amount"]
        lines.append(f"  Total: {format_number(total_budget)}")
    else:
        lines.append("BUDGETS: (not set)")

    # Net worth
    lines.append("")
    total_savings = sum(s["amount"] for s in ob["savings"])
    total_assets = sum(a["value"] for a in ob["assets"])
    lines.append(f"ESTIMATED NET WORTH: {format_number(total_savings + total_assets)}")

    return "\n".join(lines)


async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_cancel":
        await query.edit_message_text(
            "Setup cancelled. Run /setup anytime to try again."
        )
        return ConversationHandler.END

    if query.data == "confirm_restart":
        # Reset and start over
        context.user_data["onboarding"] = {
            "savings": [],
            "assets": [],
            "income": [],
            "bills": [],
            "budgets": [],
        }
        keyboard = [
            [InlineKeyboardButton("Yes, I have savings", callback_data="savings_yes")],
            [InlineKeyboardButton("No savings yet, skip", callback_data="savings_no")],
        ]
        await query.edit_message_text(
            "Starting over!\n\n"
            "STEP 1/5 - CURRENT SAVINGS\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Do you currently have any savings?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return ASK_HAS_SAVINGS

    # ── CONFIRM: Write everything to Excel ──
    await query.edit_message_text("Saving your financial profile... Please wait.")

    ob = context.user_data["onboarding"]
    excel_mgr = context.bot_data.get("excel_manager")

    if not excel_mgr:
        await query.message.reply_text("Error: Excel manager not configured.")
        return ConversationHandler.END

    errors = []
    today = local_now().replace(tzinfo=None)

    # 1. Write savings
    for s in ob["savings"]:
        try:
            excel_mgr.add_savings(
                amount=s["amount"],
                account=s["account"],
                transaction_type="Deposit",
                goal=s.get("goal"),
                date=today,
            )
        except Exception as e:
            errors.append(f"Savings ({s['account']}): {e}")

    # 2. Write assets to the dedicated Assets sheet
    for a in ob["assets"]:
        try:
            excel_mgr.add_asset(
                name=a["name"],
                asset_type=a["type"],
                current_value=a["value"],
                purchase_value=a["value"],
                notes="Initial setup",
                date=today,
            )
        except Exception as e:
            errors.append(f"Asset ({a['name']}): {e}")

    # 3. Write initial income
    for i in ob["income"]:
        try:
            excel_mgr.add_income(
                amount=i["amount"],
                source=i["source"],
                category="Salary" if "salary" in i["source"].lower() else "Other",
                notes=f"Initial setup - {i['frequency']}",
                date=today,
            )
        except Exception as e:
            errors.append(f"Income ({i['source']}): {e}")

    # 4. Write recurring bills as initial transactions
    for b in ob["bills"]:
        try:
            excel_mgr.add_transaction(
                amount=b["amount"],
                category=b["category"],
                description=f"{b['name']} (recurring)",
                payment_method="Bank Transfer",
                notes="Initial setup - monthly recurring",
                date=today,
            )
        except Exception as e:
            errors.append(f"Bill ({b['name']}): {e}")

    # 5. Write budget limits
    for bg in ob["budgets"]:
        try:
            excel_mgr.set_budget(bg["category"], bg["amount"])
        except Exception as e:
            errors.append(f"Budget ({bg['category']}): {e}")

    # Mark complete
    user_id = query.from_user.id
    mark_onboarding_complete(user_id)

    # Report
    result_lines = [
        "SETUP COMPLETE!",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"  {len(ob['savings'])} savings account(s) recorded",
        f"  {len(ob['assets'])} asset(s)/investment(s) recorded",
        f"  {len(ob['income'])} income source(s) recorded",
        f"  {len(ob['bills'])} recurring bill(s) recorded",
        f"  {len(ob['budgets'])} budget limit(s) set",
        "",
    ]

    if errors:
        result_lines.append(f"Warnings ({len(errors)}):")
        for err in errors:
            result_lines.append(f"  - {err}")
        result_lines.append("")

    result_lines.extend(
        [
            "You're all set! Here are your available commands:",
            "",
            "/quick <amount> <category> <desc> - Quick spend",
            "/spend - Record spending (guided)",
            "/income - Record income",
            "/save - Record savings deposit/withdrawal",
            "/summary - Spending summary",
            "/budget - Budget status",
            "/savings - Savings overview",
            "/dashboard - Full financial dashboard",
            "/setup - Re-run this setup",
        ]
    )

    await query.message.reply_text("\n".join(result_lines))
    return ConversationHandler.END


async def cancel_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Setup cancelled. Run /setup anytime to start again.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════
# BUILD CONVERSATION HANDLER
# ═══════════════════════════════════════════════════════════════


def build_onboarding_handler() -> ConversationHandler:
    """Build and return the onboarding ConversationHandler."""
    return ConversationHandler(
        entry_points=[
            CommandHandler("start", start_onboarding),
            CommandHandler("setup", start_onboarding),
        ],
        states={
            ASK_HAS_SAVINGS: [CallbackQueryHandler(handle_has_savings)],
            ASK_SAVINGS_ACCOUNT: [CallbackQueryHandler(handle_savings_account)],
            ASK_SAVINGS_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_savings_amount)
            ],
            ASK_SAVINGS_GOAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_savings_goal)
            ],
            ASK_MORE_SAVINGS: [CallbackQueryHandler(handle_more_savings)],
            ASK_HAS_ASSETS: [CallbackQueryHandler(handle_has_assets)],
            ASK_ASSET_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_asset_name)
            ],
            ASK_ASSET_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_asset_value)
            ],
            ASK_ASSET_TYPE: [CallbackQueryHandler(handle_asset_type)],
            ASK_MORE_ASSETS: [CallbackQueryHandler(handle_more_assets)],
            ASK_HAS_INCOME: [CallbackQueryHandler(handle_has_income)],
            ASK_INCOME_SOURCE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_income_source)
            ],
            ASK_INCOME_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_income_amount)
            ],
            ASK_INCOME_FREQUENCY: [CallbackQueryHandler(handle_income_frequency)],
            ASK_MORE_INCOME: [CallbackQueryHandler(handle_more_income)],
            ASK_HAS_BILLS: [CallbackQueryHandler(handle_has_bills)],
            ASK_BILL_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bill_name)
            ],
            ASK_BILL_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bill_amount)
            ],
            ASK_BILL_CATEGORY: [CallbackQueryHandler(handle_bill_category)],
            ASK_MORE_BILLS: [CallbackQueryHandler(handle_more_bills)],
            ASK_SET_BUDGET: [CallbackQueryHandler(handle_set_budget)],
            ASK_BUDGET_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_budget_amount)
            ],
            CONFIRM_SETUP: [CallbackQueryHandler(handle_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel_onboarding)],
        name="onboarding",
        persistent=False,
    )
