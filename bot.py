"""
Financial Tracker Telegram Bot
Records spending, income, and savings directly into Financial_Tracker.xlsx
"""

from __future__ import annotations

import asyncio
import datetime
import io
import json
import logging
import os
import re
import time
import uuid

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import is_user_allowed, settings
from excel_manager import ExcelManager
from chart_generator import ChartGenerator
from onboarding import build_onboarding_handler


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

excel: ExcelManager | None = None

# ── Conversation states ──
(
    SPEND_AMOUNT,
    SPEND_CATEGORY,
    SPEND_DESC,
    SPEND_PAYMENT,
    INCOME_AMOUNT,
    INCOME_SOURCE,
    INCOME_CATEGORY,
    SAVE_AMOUNT,
    SAVE_ACCOUNT,
    SAVE_TYPE,
    # Investment states
    INVEST_TYPE,
    INVEST_PLATFORM,
    INVEST_NAME,
    INVEST_PURCHASE,
    INVEST_CURRENT,
    INVEST_NOTES,
    # Debt states
    DEBT_TYPE,
    DEBT_BANK,
    DEBT_NAME,
    DEBT_TOTAL,
    DEBT_REMAINING,
    DEBT_MONTHLY,
    DEBT_INTEREST,
    DEBT_TENOR,
    DEBT_START_DATE,
    DEBT_NOTES,
    PDF_PASSWORD,
) = range(27)

HELP_TEXT = (
    "*Financial Tracker Bot*\n\n"
    "Record your finances directly from Telegram\\!\n\n"
    "*Setup & Recording:*\n"
    "/start \\- Start onboarding if needed or show this overview\n"
    "/setup \\- Run the financial setup flow again\n"
    "/spend \\- Record a spending transaction\n"
    "/income \\- Record income\n"
    "/save \\- Record savings deposit or withdrawal\n"
    "/quick \\- Quick record \\(e\\.g\\. `/quick Rp50.000 makan nasi padang`\\)\n\n"
    "*Investments & Debts:*\n"
    "/invest \\- Record an investment \\(stocks, bonds, mutual funds, etc\\.\\)\n"
    "/portfolio \\- View investment portfolio summary\n"
    "/debt \\- Record a debt \\(KPR, KTA, credit card, etc\\.\\)\n"
    "/liabilities \\- View debt summary\n\n"
    "*Reports:*\n"
    "/summary \\- Monthly financial summary \\(`/summary 2026\\-03`\\)\n"
    "/budget \\- Budget status \\(`/budget 2026\\-03`\\)\n"
    "/savings \\- Savings overview\n"
    "/recent \\- Last transactions \\(`/recent 10`\\)\n"
    "/dashboard \\- Full dashboard \\(`/dashboard 2026\\-03`\\)\n"
    "/health \\- Financial health score & analysis\n"
    "/updateprices \\- Update stock prices from Yahoo Finance\n\n"
    "*Info:*\n"
    "/categories \\- List supported categories\n"
    "/download \\- Download Excel tracker file\n"
    "/help \\- Show this message"
)


CATEGORY_KEYWORDS = {
    "food": "Food & Groceries",
    "groceries": "Food & Groceries",
    "eat": "Food & Groceries",
    "makan": "Food & Groceries",
    "snack": "Food & Groceries",
    "transport": "Transportation",
    "uber": "Transportation",
    "grab": "Transportation",
    "gojek": "Transportation",
    "ojol": "Transportation",
    "taxi": "Transportation",
    "bus": "Transportation",
    "train": "Transportation",
    "gas": "Transportation",
    "fuel": "Transportation",
    "bensin": "Transportation",
    "parkir": "Transportation",
    "house": "Housing",
    "rent": "Housing",
    "kos": "Housing",
    "sewa": "Housing",
    "entertainment": "Entertainment",
    "fun": "Entertainment",
    "movie": "Entertainment",
    "game": "Entertainment",
    "hiburan": "Entertainment",
    "netflix": "Entertainment",
    "spotify": "Entertainment",
    "health": "Healthcare",
    "doctor": "Healthcare",
    "medicine": "Healthcare",
    "obat": "Healthcare",
    "education": "Education",
    "course": "Education",
    "book": "Education",
    "buku": "Education",
    "kursus": "Education",
    "shop": "Shopping",
    "shopping": "Shopping",
    "beli": "Shopping",
    "belanja": "Shopping",
    "clothes": "Shopping",
    "bill": "Bills & Utilities",
    "bills": "Bills & Utilities",
    "electric": "Bills & Utilities",
    "listrik": "Bills & Utilities",
    "water": "Bills & Utilities",
    "internet": "Bills & Utilities",
    "phone": "Bills & Utilities",
    "pulsa": "Bills & Utilities",
    "wifi": "Bills & Utilities",
    "pln": "Bills & Utilities",
}


def format_number(n) -> str:
    """Format number with thousand separators."""
    if n is None:
        return "0"
    return f"{n:,.0f}"


def get_excel_manager(context: ContextTypes.DEFAULT_TYPE | None = None) -> ExcelManager:
    """Get the shared Excel manager from app state or the module fallback."""
    manager = None
    if context is not None:
        manager = context.bot_data.get("excel_manager")
    manager = manager or excel
    if manager is None:
        raise RuntimeError("Excel manager is not configured.")
    return manager


def is_authorized(update: Update) -> bool:
    user = update.effective_user
    if user is None:
        return False
    return is_user_allowed(user.id)


async def reply_unauthorized(update: Update) -> None:
    message = update.effective_message
    if message is not None:
        await message.reply_text("Unauthorized. Update ALLOWED_USER_IDS to grant access.")


def parse_amount(raw: str) -> float:
    """Parse user-entered amounts like 50000, 50.000, or Rp50,000."""
    cleaned = raw.lower().strip()
    cleaned = cleaned.replace("rp", "")
    digits = re.sub(r"[^\d]", "", cleaned)
    if not digits:
        raise ValueError("Invalid amount.")
    return float(digits)


def parse_month_arg(args: list[str], usage: str) -> str | None:
    """Validate a single optional month argument in YYYY-MM format."""
    if not args:
        return None
    if len(args) != 1:
        raise ValueError(usage)
    month = args[0].strip()
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise ValueError(usage)
    year, month_num = month.split("-", 1)
    if not 1 <= int(month_num) <= 12:
        raise ValueError(usage)
    return f"{year}-{month_num}"


def match_category(keyword: str) -> str | None:
    """Match a keyword to a spending category."""
    normalized = keyword.lower().strip()
    if normalized in CATEGORY_KEYWORDS:
        return CATEGORY_KEYWORDS[normalized]

    manager = excel
    for cat in manager.CATEGORIES if manager else ExcelManager.CATEGORIES:
        cat_lower = cat.lower()
        if normalized in cat_lower or cat_lower in normalized:
            return cat
    return None


# ── NLP mode state ──
nlp_state: dict = {"enabled": False}

# ── Pending confirmation store (UUID-keyed, 1-hour TTL) ──
_pending_confirmations: dict[str, dict] = {}
_PENDING_TTL_SECONDS = 3600


def _store_pending(user_id: int, data: dict) -> str:
    """Store extracted data awaiting user confirmation. Returns UUID key."""
    now = time.time()
    expired = [k for k, v in _pending_confirmations.items() if now - v["ts"] > _PENDING_TTL_SECONDS]
    for k in expired:
        del _pending_confirmations[k]

    key = uuid.uuid4().hex[:12]
    _pending_confirmations[key] = {
        "user_id": user_id,
        "data": data,
        "ts": now,
    }
    return key


def _retrieve_pending(key: str, user_id: int) -> dict | None:
    """Retrieve and remove a pending confirmation. Returns None if expired/invalid."""
    entry = _pending_confirmations.pop(key, None)
    if entry is None:
        return None
    if entry["user_id"] != user_id:
        return None
    if time.time() - entry["ts"] > _PENDING_TTL_SECONDS:
        return None
    return entry["data"]


def _build_preview_text(data: dict, duplicates: list[dict] | None = None) -> str:
    """Build human-readable preview text from extracted financial data."""
    doc_type = data.get("type", "unknown")

    if doc_type == "spending":
        amount = float(data.get("amount", 0))
        text = (
            f"🧾 *Preview Pengeluaran*\n\n"
            f"Amount:   Rp {format_number(amount)}\n"
            f"Category: {data.get('category', 'Other')}\n"
            f"Desc:     {data.get('description', '') or data.get('merchant', '')}\n\n"
            f"📝 {data.get('summary', '')}"
        )

    elif doc_type == "income":
        amount = float(data.get("amount", 0))
        text = (
            f"💰 *Preview Pemasukan*\n\n"
            f"Amount:   Rp {format_number(amount)}\n"
            f"Source:   {data.get('source', '')}\n"
            f"Category: {data.get('category', 'Salary')}\n\n"
            f"📝 {data.get('summary', '')}"
        )

    elif doc_type == "investment":
        items = data.get("items", [])
        lines = [f"📊 *Preview Investasi*\n"]
        for item in items:
            val = float(item.get("value", 0))
            lines.append(f"  • {item.get('name', 'Unknown')}: Rp {format_number(val)} ({item.get('platform', '')})")
        lines.append(f"\n📝 {data.get('summary', '')}")
        text = "\n".join(lines)

    elif doc_type == "cc_statement":
        transactions = data.get("transactions", [])
        card = data.get("card", "Credit Card")
        period = data.get("period", "")
        total = sum(float(tx.get("amount", 0)) for tx in transactions)
        n = len(transactions)
        cicilan_count = sum(1 for tx in transactions if tx.get("is_cicilan"))
        regular_count = n - cicilan_count

        lines = [f"💳 *Preview E-Statement {card} ({period})*\n"]
        if cicilan_count > 0:
            lines.append(
                f"Total: {n} transaksi ({regular_count} reguler, {cicilan_count} cicilan), Rp {format_number(total)}\n"
            )
        else:
            lines.append(f"Total: {n} transaksi, Rp {format_number(total)}\n")

        for tx in transactions[:5]:
            amt = float(tx.get("amount", 0))
            cicilan_tag = " [Cicilan]" if tx.get("is_cicilan") else ""
            card_tag = f" [{tx.get('card_label')}]" if tx.get("card_label") else ""
            lines.append(
                f"  • {tx.get('date', '')} {tx.get('description', '')}: Rp {format_number(amt)}{cicilan_tag}{card_tag}"
            )

        if n > 10:
            lines.append(f"  ... ({n - 10} transaksi lainnya) ...")
            for tx in transactions[-5:]:
                amt = float(tx.get("amount", 0))
                cicilan_tag = " [Cicilan]" if tx.get("is_cicilan") else ""
                card_tag = f" [{tx.get('card_label')}]" if tx.get("card_label") else ""
                lines.append(
                    f"  • {tx.get('date', '')} {tx.get('description', '')}: Rp {format_number(amt)}{cicilan_tag}{card_tag}"
                )
        elif n > 5:
            for tx in transactions[5:]:
                amt = float(tx.get("amount", 0))
                cicilan_tag = " [Cicilan]" if tx.get("is_cicilan") else ""
                card_tag = f" [{tx.get('card_label')}]" if tx.get("card_label") else ""
                lines.append(
                    f"  • {tx.get('date', '')} {tx.get('description', '')}: Rp {format_number(amt)}{cicilan_tag}{card_tag}"
                )

        text = "\n".join(lines)

    elif doc_type == "payslip":
        net_pay = float(data.get("net_pay", 0))
        gross = float(data.get("gross", 0))
        deductions = float(data.get("deductions", 0))
        text = (
            f"📋 *Preview Slip Gaji*\n\n"
            f"Company:    {data.get('company', '')}\n"
            f"Period:     {data.get('period', '')}\n"
            f"Gross:      Rp {format_number(gross)}\n"
            f"Deductions: Rp {format_number(deductions)}\n"
            f"Net Pay:    Rp {format_number(net_pay)}\n\n"
            f"📝 {data.get('summary', '')}"
        )

    else:
        text = f"📋 {data.get('summary', 'Data tidak dikenali')}"

    if duplicates:
        text += f"\n\n⚠️ *Potensi Duplikat Terdeteksi ({len(duplicates)}):*\n"
        for dup in duplicates[:3]:
            amt = float(dup.get("amount", 0))
            label = dup.get("description") or dup.get("source", "")
            text += f"  • {dup.get('date', '')} {label}: Rp {format_number(amt)}\n"
        if len(duplicates) > 3:
            text += f"  ... dan {len(duplicates) - 3} lainnya\n"

    return text


def _build_confirm_keyboard(pending_key: str) -> InlineKeyboardMarkup:
    """Build Save / Cancel inline keyboard for confirmation."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Simpan", callback_data=f"cfm_save_{pending_key}"),
                InlineKeyboardButton("❌ Batal", callback_data=f"cfm_cancel_{pending_key}"),
            ]
        ]
    )


# ── OpenAI function-calling tools for edit/delete ──

FINANCIAL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_sheet_data",
            "description": (
                "Search rows in the user's financial spreadsheet. "
                "Use this to find existing records before proposing edits or deletions. "
                "Returns up to 20 matching rows with their row numbers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sheet": {
                        "type": "string",
                        "enum": [
                            "transactions",
                            "income",
                            "savings",
                            "assets",
                            "debts",
                        ],
                        "description": "Which sheet to search.",
                    },
                    "filters": {
                        "type": "object",
                        "description": (
                            "Key-value filters. Keys are column names for the sheet. "
                            "Strings match as substring (case-insensitive). "
                            "Numbers match within 1% tolerance. "
                            "Dates match as prefix (e.g. '2025-03' matches all March 2025)."
                        ),
                        "additionalProperties": True,
                    },
                },
                "required": ["sheet", "filters"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_edit",
            "description": (
                "Propose editing specific cells in a row. The edit will NOT happen immediately — "
                "it will be shown as a preview for user confirmation first. "
                "Always search first to find the correct row number."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sheet": {
                        "type": "string",
                        "enum": [
                            "transactions",
                            "income",
                            "savings",
                            "assets",
                            "debts",
                        ],
                        "description": "Which sheet the row is in.",
                    },
                    "row_number": {
                        "type": "integer",
                        "description": "The row number to edit (from search results).",
                    },
                    "updates": {
                        "type": "object",
                        "description": (
                            "Fields to update. Keys are column names, values are new values. "
                            "Only include fields that need to change."
                        ),
                        "additionalProperties": True,
                    },
                    "reason": {
                        "type": "string",
                        "description": "Brief description of why this edit is needed.",
                    },
                },
                "required": ["sheet", "row_number", "updates", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_delete",
            "description": (
                "Propose deleting one or more rows. The deletion will NOT happen immediately — "
                "it will be shown as a preview for user confirmation first. "
                "Always search first to find the correct row numbers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sheet": {
                        "type": "string",
                        "enum": [
                            "transactions",
                            "income",
                            "savings",
                            "assets",
                            "debts",
                        ],
                        "description": "Which sheet the rows are in.",
                    },
                    "row_numbers": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Row numbers to delete (from search results).",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Brief description of why these rows should be deleted.",
                    },
                },
                "required": ["sheet", "row_numbers", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_add",
            "description": (
                "Propose adding a NEW row to a sheet. The addition will NOT happen immediately — "
                "it will be shown as a preview for user confirmation first. "
                "Use this when the user wants to ADD new data, not edit existing data. "
                "For assets: use this to add new bank accounts, investments, or cash entries. "
                "For transactions: use this to add new spending records. "
                "For income: use this to add new income entries."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sheet": {
                        "type": "string",
                        "enum": [
                            "transactions",
                            "income",
                            "savings",
                            "assets",
                            "debts",
                        ],
                        "description": "Which sheet to add the new row to.",
                    },
                    "data": {
                        "type": "object",
                        "description": (
                            "Field values for the new row. Keys are column names. "
                            "transactions: amount (required), category, description, payment_method, notes. "
                            "income: amount (required), source (required), category, notes. "
                            "savings: amount (required), account (required), transaction_type (Deposit/Withdrawal/Interest), goal. "
                            "assets: name (required), type (Ekuitas/Reksadana/Obligasi/Kas/Property/Crypto/Other), "
                            "current_value (required), purchase_value, platform, notes. "
                            "debts: name (required), type (KPR/KTA/Kartu Kredit/Pinjaman Online/Other), "
                            "bank (required), total_loan, remaining, monthly_payment, interest_rate, tenor, notes."
                        ),
                        "additionalProperties": True,
                    },
                    "reason": {
                        "type": "string",
                        "description": "Brief description of why this data is being added.",
                    },
                },
                "required": ["sheet", "data", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_kpr_payment",
            "description": (
                "Propose recording a monthly KPR/mortgage payment. This is a compound action that will: "
                "1) Add a Housing transaction for the full payment amount, "
                "2) Record parent/family contribution as Family Support income (if any), "
                "3) Update the debt remaining balance, "
                "4) Deduct the user's own portion from Cash (Tabungan). "
                "All 4 changes are shown in one preview for single confirmation. "
                "Use when user mentions: bayar KPR, cicilan rumah, mortgage payment."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "parent_contribution": {
                        "type": "number",
                        "description": "Amount contributed by parents/family (Rp). 0 if user pays entirely alone.",
                    },
                    "month": {
                        "type": "string",
                        "description": "Payment month, e.g. 'Mar 2026' or 'April 2026'.",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional notes about this payment.",
                    },
                },
                "required": ["parent_contribution", "month"],
            },
        },
    },
]


def _build_edit_preview(pending_data: dict) -> str:
    """Build human-readable preview for edit/delete proposals in Indonesian."""
    action = pending_data.get("action", "")
    sheet = pending_data.get("sheet", "")
    reason = pending_data.get("reason", "")

    if action == "propose_edit":
        row_num = pending_data.get("row_number", "?")
        current = pending_data.get("current_row", {})
        updates = pending_data.get("updates", {})

        lines = [f"✏️ *Preview Edit — {sheet}* (baris {row_num})\n"]
        lines.append(f"Alasan: {reason}\n")
        lines.append("Perubahan:")
        for field, new_val in updates.items():
            old_val = current.get(field, "")
            lines.append(f"  • {field}: `{old_val}` → `{new_val}`")

        unchanged = {k: v for k, v in current.items() if k not in updates and k != "_row" and v != ""}
        if unchanged:
            lines.append("\nData lain (tidak berubah):")
            for field, val in list(unchanged.items())[:5]:
                lines.append(f"  • {field}: {val}")

        return "\n".join(lines)

    elif action == "propose_delete":
        row_numbers = pending_data.get("row_numbers", [])
        rows_data = pending_data.get("rows_data", [])

        lines = [f"🗑️ *Preview Hapus — {sheet}* ({len(row_numbers)} baris)\n"]
        lines.append(f"Alasan: {reason}\n")
        lines.append("Data yang akan dihapus:")
        for rd in rows_data:
            row_num = rd.get("_row", "?")
            display_parts = []
            for k, v in rd.items():
                if k == "_row" or v == "":
                    continue
                display_parts.append(f"{k}={v}")
            lines.append(f"  • Baris {row_num}: {', '.join(display_parts[:4])}")

        return "\n".join(lines)

    elif action == "propose_add":
        data = pending_data.get("data", {})
        lines = [f"➕ *Preview Tambah Data Baru — {sheet}*\n"]
        lines.append(f"Alasan: {reason}\n")
        lines.append("Data yang akan ditambahkan:")
        for field, val in data.items():
            if isinstance(val, (int, float)) and field not in (
                "tenor",
                "interest_rate",
            ):
                lines.append(f"  • {field}: Rp {val:,.0f}")
            else:
                lines.append(f"  • {field}: {val}")
        return "\n".join(lines)

    elif action == "propose_kpr_payment":
        kpr_amount = pending_data.get("kpr_amount", 0)
        parent_amt = pending_data.get("parent_contribution", 0)
        user_portion = kpr_amount - parent_amt
        month = pending_data.get("month", "")
        debt_remaining = pending_data.get("debt_remaining", 0)
        new_remaining = debt_remaining - kpr_amount
        cash_balance = pending_data.get("cash_balance", 0)
        new_cash = cash_balance - user_portion

        lines = [f"🏠 *Preview Pembayaran KPR — {month}*\n"]
        lines.append("Berikut 4 perubahan yang akan dilakukan:\n")
        lines.append(f"1️⃣ *Transaksi Housing*: Rp {kpr_amount:,.0f}")
        if parent_amt > 0:
            lines.append(f"2️⃣ *Income Family Support*: Rp {parent_amt:,.0f}")
        lines.append(f"3️⃣ *Sisa Hutang KPR*: Rp {debt_remaining:,.0f} → Rp {new_remaining:,.0f}")
        lines.append(f"4️⃣ *Cash (Tabungan)*: Rp {cash_balance:,.0f} → Rp {new_cash:,.0f} (bayar Rp {user_portion:,.0f})")
        if pending_data.get("notes"):
            lines.append(f"\nCatatan: {pending_data['notes']}")
        return "\n".join(lines)

    return "⚠️ Preview tidak tersedia."


async def handle_extraction_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle confirmation callbacks for image/document extraction results."""
    query = update.callback_query
    await query.answer()

    data_str = query.data or ""
    user_id = query.from_user.id

    if data_str.startswith("cfm_save_"):
        pending_key = data_str[len("cfm_save_") :]
        pending_data = _retrieve_pending(pending_key, user_id)
        if pending_data is None:
            await query.edit_message_text("⏰ Data sudah expired atau tidak ditemukan. Coba upload ulang.")
            return

        em = get_excel_manager(context)
        action = pending_data.get("action")

        try:
            if action == "propose_edit":
                sheet = pending_data["sheet"]
                row_number = pending_data["row_number"]
                updates = pending_data["updates"]
                result = em.update_row(sheet, row_number, updates)
                lines = [f"✅ Data berhasil diperbarui! (baris {row_number} di {sheet})\n"]
                for field, new_val in updates.items():
                    lines.append(f"  • {field}: {result.get(field, new_val)}")
                await query.edit_message_text("\n".join(lines))
                return

            elif action == "propose_delete":
                sheet = pending_data["sheet"]
                row_numbers = pending_data["row_numbers"]
                count = em.delete_rows(sheet, row_numbers)
                await query.edit_message_text(f"✅ {count} baris berhasil dihapus dari {sheet}.")
                return

            elif action == "propose_add":
                sheet = pending_data["sheet"]
                data = pending_data.get("data", {})

                if sheet == "transactions":
                    result = em.add_transaction(
                        amount=float(data.get("amount", 0)),
                        category=data.get("category", "Other"),
                        description=data.get("description", ""),
                        payment_method=data.get("payment_method", "Cash"),
                        notes=data.get("notes", ""),
                    )
                    await query.edit_message_text(
                        f"✅ Pengeluaran baru ditambahkan!\n"
                        f"  • Jumlah: Rp {result.get('amount', 0):,.0f}\n"
                        f"  • Kategori: {result.get('category', '')}\n"
                        f"  • Deskripsi: {result.get('description', '')}\n"
                        f"  • Tanggal: {result.get('date', '')}"
                    )
                elif sheet == "income":
                    result = em.add_income(
                        amount=float(data.get("amount", 0)),
                        source=data.get("source", "Unknown"),
                        category=data.get("category", "Salary"),
                        notes=data.get("notes", ""),
                    )
                    await query.edit_message_text(
                        f"✅ Pemasukan baru ditambahkan!\n"
                        f"  • Jumlah: Rp {result.get('amount', 0):,.0f}\n"
                        f"  • Sumber: {result.get('source', '')}\n"
                        f"  • Tanggal: {result.get('date', '')}"
                    )
                elif sheet == "savings":
                    result = em.add_savings(
                        amount=float(data.get("amount", 0)),
                        account=data.get("account", ""),
                        transaction_type=data.get("transaction_type", "Deposit"),
                        goal=float(data["goal"]) if data.get("goal") else None,
                    )
                    await query.edit_message_text(
                        f"✅ Tabungan baru ditambahkan!\n"
                        f"  • Jumlah: Rp {result.get('amount', 0):,.0f}\n"
                        f"  • Akun: {result.get('account', '')}\n"
                        f"  • Tipe: {result.get('type', '')}\n"
                        f"  • Tanggal: {result.get('date', '')}"
                    )
                elif sheet == "assets":
                    result = em.add_asset(
                        name=data.get("name", ""),
                        asset_type=data.get("type", "Other"),
                        current_value=float(data.get("current_value", 0)),
                        purchase_value=float(data.get("purchase_value", data.get("current_value", 0))),
                        platform=data.get("platform", ""),
                        notes=data.get("notes", ""),
                    )
                    await query.edit_message_text(
                        f"✅ Aset baru ditambahkan!\n"
                        f"  • Nama: {result.get('name', '')}\n"
                        f"  • Tipe: {result.get('type', '')}\n"
                        f"  • Nilai: Rp {result.get('current_value', 0):,.0f}\n"
                        f"  • Tanggal: {result.get('date', '')}"
                    )
                elif sheet == "debts":
                    result = em.add_debt(
                        name=data.get("name", ""),
                        debt_type=data.get("type", "Other"),
                        bank=data.get("bank", ""),
                        total_loan=float(data.get("total_loan", 0)),
                        remaining=float(data.get("remaining", data.get("total_loan", 0))),
                        monthly_payment=float(data.get("monthly_payment", 0)),
                        interest_rate=float(data.get("interest_rate", 0)),
                        tenor_months=int(data.get("tenor", 0)),
                        notes=data.get("notes", ""),
                    )
                    await query.edit_message_text(
                        f"✅ Hutang baru ditambahkan!\n"
                        f"  • Nama: {result.get('name', '')}\n"
                        f"  • Tipe: {result.get('type', '')}\n"
                        f"  • Bank: {result.get('bank', '')}\n"
                        f"  • Total: Rp {result.get('total_loan', 0):,.0f}\n"
                        f"  • Tanggal: {result.get('date', '')}"
                    )
                else:
                    await query.edit_message_text(f"⚠️ Sheet '{sheet}' tidak dikenali.")
                return

            elif action == "propose_kpr_payment":
                kpr_amount = pending_data["kpr_amount"]
                parent_amt = pending_data["parent_contribution"]
                user_portion = kpr_amount - parent_amt
                month = pending_data["month"]
                notes = pending_data.get("notes", "")
                debt_row = pending_data["debt_row"]
                debt_remaining = pending_data["debt_remaining"]
                cash_row = pending_data["cash_row"]
                cash_balance = pending_data["cash_balance"]

                results = []

                em.add_transaction(
                    amount=kpr_amount,
                    category="Housing",
                    description=f"Cicilan KPR {month}",
                    payment_method="Cash",
                    notes=notes or f"KPR payment {month}",
                )
                results.append(f"✅ Transaksi Housing: Rp {kpr_amount:,.0f}")

                if parent_amt > 0:
                    em.add_income(
                        amount=parent_amt,
                        source="Orang Tua",
                        category="Family Support",
                        notes=f"Bantuan cicilan KPR {month}",
                    )
                    results.append(f"✅ Income Family Support: Rp {parent_amt:,.0f}")

                new_remaining = debt_remaining - kpr_amount
                em.update_row("debts", debt_row, {"remaining": new_remaining})
                results.append(f"✅ Sisa KPR: Rp {debt_remaining:,.0f} → Rp {new_remaining:,.0f}")

                new_cash = cash_balance - user_portion
                em.update_row(
                    "assets",
                    cash_row,
                    {
                        "purchase_value": new_cash,
                        "current_value": new_cash,
                    },
                )
                results.append(f"✅ Cash: Rp {cash_balance:,.0f} → Rp {new_cash:,.0f} (-Rp {user_portion:,.0f})")

                await query.edit_message_text(f"🏠 Pembayaran KPR {month} berhasil!\n\n" + "\n".join(results))
                return

            doc_type = pending_data.get("type", "unknown")
            if doc_type == "spending":
                amount = float(pending_data.get("amount", 0))
                result = em.add_transaction(
                    amount=amount,
                    category=pending_data.get("category", "Other"),
                    description=pending_data.get("description", "") or pending_data.get("merchant", ""),
                    payment_method="Other",
                )
                await query.edit_message_text(
                    f"✅ Pengeluaran tercatat!\n\n"
                    f"Amount:   Rp {format_number(amount)}\n"
                    f"Category: {pending_data.get('category', 'Other')}\n"
                    f"Date:     {result['date']}"
                )

            elif doc_type == "income":
                amount = float(pending_data.get("amount", 0))
                result = em.add_income(
                    amount=amount,
                    source=pending_data.get("source", ""),
                    category=pending_data.get("category", "Salary"),
                    notes=pending_data.get("description", ""),
                )
                await query.edit_message_text(
                    f"✅ Pemasukan tercatat!\n\n"
                    f"Amount:   Rp {format_number(amount)}\n"
                    f"Source:   {pending_data.get('source', '')}\n"
                    f"Date:     {result['date']}"
                )

            elif doc_type == "investment":
                items = pending_data.get("items", [])
                recorded = 0
                lines = ["✅ Investasi tercatat!\n"]
                for item in items:
                    try:
                        em.add_asset(
                            name=item.get("name", "Unknown"),
                            asset_type=item.get("asset_type", "Other"),
                            platform=item.get("platform", "Other"),
                            purchase_value=float(item.get("value", 0)),
                            current_value=float(item.get("value", 0)),
                        )
                        recorded += 1
                        lines.append(f"  ✅ {item.get('name')}: Rp {format_number(float(item.get('value', 0)))}")
                    except Exception as e:
                        lines.append(f"  ⚠️ {item.get('name')}: gagal ({e})")
                lines.append(f"\n{recorded}/{len(items)} investasi tercatat.")
                await query.edit_message_text("\n".join(lines))

            elif doc_type == "cc_statement":
                transactions = pending_data.get("transactions", [])
                card = pending_data.get("card", "Credit Card")
                period = pending_data.get("period", "")
                recorded = 0
                total = 0
                cicilan_count = 0
                from datetime import datetime as _dt

                for tx in transactions:
                    amount = float(tx.get("amount", 0))
                    if amount <= 0:
                        continue
                    try:
                        tx_date = None
                        date_str = tx.get("date", "")
                        if date_str:
                            for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
                                try:
                                    tx_date = _dt.strptime(date_str, fmt)
                                    break
                                except ValueError:
                                    continue

                        is_cicilan = bool(tx.get("is_cicilan", False))
                        card_label = tx.get("card_label", "")
                        note_parts = []
                        if card_label:
                            note_parts.append(f"CC {card} {card_label}")
                        else:
                            note_parts.append(f"CC {card}")
                        if is_cicilan:
                            note_parts.append("Cicilan")
                            cicilan_count += 1
                        notes = " ".join(note_parts)

                        em.add_transaction(
                            amount=amount,
                            category=tx.get("category", "Other"),
                            description=tx.get("description", ""),
                            payment_method="Credit Card",
                            notes=notes,
                            date=tx_date,
                        )
                        recorded += 1
                        total += amount
                    except Exception:
                        pass

                budget_msg = ""
                if period:
                    try:
                        for fmt in ("%b %Y", "%B %Y", "%m/%Y", "%Y-%m"):
                            try:
                                parsed = _dt.strptime(period.strip(), fmt)
                                yyyy_mm = parsed.strftime("%Y-%m")
                                em.set_budget_month(yyyy_mm)
                                budget_msg = f"\n📊 Budget Month updated: {yyyy_mm}"
                                break
                            except ValueError:
                                continue
                    except Exception:
                        pass

                cicilan_msg = ""
                if cicilan_count > 0:
                    cicilan_msg = f"\n  💳 {cicilan_count} cicilan, {recorded - cicilan_count} reguler"

                await query.edit_message_text(
                    f"✅ E-Statement {card} tercatat!\n\n"
                    f"Total: Rp {format_number(total)}\n"
                    f"{recorded}/{len(transactions)} transaksi berhasil disimpan."
                    f"{cicilan_msg}{budget_msg}"
                )

            elif doc_type == "payslip":
                net_pay = float(pending_data.get("net_pay", 0))
                gross = float(pending_data.get("gross", 0))
                deductions = float(pending_data.get("deductions", 0))
                company = pending_data.get("company", "")
                period = pending_data.get("period", "")
                result = em.add_income(
                    amount=net_pay,
                    source=company,
                    category="Salary",
                    notes=f"Net Pay {period} (Gross: {format_number(gross)}, Deductions: {format_number(deductions)})",
                )

                # Auto-update Cash (Tabungan) balance in Assets
                cash_msg = ""
                try:
                    cash_rows = em.search_rows("assets", {"name": "Cash (Tabungan)", "type": "Kas"}, limit=1)
                    if cash_rows:
                        cash_row = cash_rows[0]
                        old_balance = float(cash_row.get("current_value", 0) or 0)
                        new_balance = old_balance + net_pay
                        em.update_row(
                            "assets",
                            cash_row["_row"],
                            {
                                "purchase_value": new_balance,
                                "current_value": new_balance,
                            },
                        )
                        cash_msg = (
                            f"\n💰 Cash (Tabungan): Rp {format_number(old_balance)} → Rp {format_number(new_balance)}"
                        )
                    else:
                        cash_msg = "\n⚠️ Row 'Cash (Tabungan)' tidak ditemukan di Assets."
                except Exception as cash_err:
                    cash_msg = f"\n⚠️ Gagal update Cash: {cash_err}"

                # Auto-add transaction record for salary
                tx_msg = ""
                try:
                    em.add_transaction(
                        amount=net_pay,
                        category="Salary/Income",
                        description=f"Gaji {period} - {company}",
                        payment_method="Cash",
                        notes=f"Net Pay (Gross: {format_number(gross)}, Deductions: {format_number(deductions)})",
                    )
                    tx_msg = f"\n📝 Transaksi gaji tercatat di Transactions."
                except Exception as tx_err:
                    tx_msg = f"\n⚠️ Gagal catat transaksi: {tx_err}"

                await query.edit_message_text(
                    f"✅ Gaji tercatat!\n\n"
                    f"Company:  {company}\n"
                    f"Net Pay:  Rp {format_number(net_pay)}\n"
                    f"Date:     {result['date']}"
                    f"{cash_msg}"
                    f"{tx_msg}"
                )

            else:
                await query.edit_message_text("⚠️ Tipe data tidak dikenali.")

        except Exception as e:
            await query.edit_message_text(f"⚠️ Gagal menyimpan: {e}")

    elif data_str.startswith("cfm_cancel_"):
        pending_key = data_str[len("cfm_cancel_") :]
        _retrieve_pending(pending_key, user_id)
        await query.edit_message_text("❌ Dibatalkan. Data tidak disimpan.")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await reply_unauthorized(update)
        return

    await update.message.reply_text(HELP_TEXT, parse_mode="MarkdownV2")


async def quick_record(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick record: /quick 50000 food lunch with friends"""
    if not is_authorized(update):
        await reply_unauthorized(update)
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: /quick <amount> <category> [description]\n"
            "Examples:\n"
            "  /quick 50000 food lunch at office\n"
            "  /quick Rp75.000 makan nasi padang\n"
            "  /quick 200000 shopping new shoes"
        )
        return

    try:
        amount = parse_amount(args[0])
    except ValueError:
        await update.message.reply_text("Invalid amount. Try values like 50000, 50.000, or Rp50,000.")
        return

    category = match_category(args[1])
    if not category:
        cats = "\n".join(f"  - {c}" for c in ExcelManager.CATEGORIES)
        await update.message.reply_text(
            f"Unknown category '{args[1]}'. Try one of these categories:\n{cats}\n\n"
            "You can also use shortcuts like food, makan, transport, bensin, bill, listrik, shop, or health."
        )
        return

    description = " ".join(args[2:]).strip()

    try:
        result = get_excel_manager(context).add_transaction(
            amount=amount,
            category=category,
            description=description,
            payment_method="Cash",
        )
    except ValueError as exc:
        await update.message.reply_text(f"Could not record spending: {exc}")
        return

    await update.message.reply_text(
        "Spending recorded.\n"
        f"Amount: {format_number(amount)}\n"
        f"Category: {category}\n"
        f"Description: {description or '-'}\n"
        f"Payment: {result['payment_method']}\n"
        f"Date: {result['date']}"
    )


async def spend_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await reply_unauthorized(update)
        return ConversationHandler.END
    await update.message.reply_text("How much did you spend?\nExamples: 50000, 50.000, Rp50,000")
    return SPEND_AMOUNT


async def spend_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = parse_amount(update.message.text)
        context.user_data["spend_amount"] = amount
    except ValueError:
        await update.message.reply_text("Please enter a valid amount, for example 50000 or Rp50.000.")
        return SPEND_AMOUNT

    keyboard = []
    row = []
    for cat in ExcelManager.CATEGORIES:
        row.append(InlineKeyboardButton(cat, callback_data=f"scat_{cat}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    await update.message.reply_text(
        f"Amount: {format_number(amount)}\nSelect category:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return SPEND_CATEGORY


async def spend_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.replace("scat_", "")
    context.user_data["spend_category"] = category
    await query.edit_message_text(
        f"Amount: {format_number(context.user_data['spend_amount'])}\n"
        f"Category: {category}\n\n"
        "Enter a description, or type /skip to leave it blank."
    )
    return SPEND_DESC


async def spend_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text.strip()
    if desc == "/skip":
        desc = ""
    context.user_data["spend_desc"] = desc

    keyboard = []
    row = []
    for pm in ExcelManager.PAYMENT_METHODS:
        row.append(InlineKeyboardButton(pm, callback_data=f"spay_{pm}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    await update.message.reply_text(
        "Select payment method:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return SPEND_PAYMENT


async def spend_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    payment = query.data.replace("spay_", "")

    try:
        result = get_excel_manager(context).add_transaction(
            amount=context.user_data["spend_amount"],
            category=context.user_data["spend_category"],
            description=context.user_data.get("spend_desc", ""),
            payment_method=payment,
        )
    except ValueError as exc:
        await query.edit_message_text(f"Could not record spending: {exc}")
        context.user_data.clear()
        return ConversationHandler.END

    await query.edit_message_text(
        "Spending recorded.\n\n"
        f"Date: {result['date']}\n"
        f"Amount: {format_number(result['amount'])}\n"
        f"Category: {result['category']}\n"
        f"Description: {result['description'] or '-'}\n"
        f"Payment: {payment}"
    )
    context.user_data.clear()
    return ConversationHandler.END


async def income_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await reply_unauthorized(update)
        return ConversationHandler.END
    await update.message.reply_text("Enter income amount.\nExamples: 8000000, 8.000.000, Rp8,000,000")
    return INCOME_AMOUNT


async def income_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = parse_amount(update.message.text)
        context.user_data["income_amount"] = amount
    except ValueError:
        await update.message.reply_text("Please enter a valid amount, for example 8000000 or Rp8.000.000.")
        return INCOME_AMOUNT

    await update.message.reply_text(
        f"Amount: {format_number(amount)}\nEnter income source (for example Company Name or Client):"
    )
    return INCOME_SOURCE


async def income_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    source = update.message.text.strip()
    if not source:
        await update.message.reply_text("Income source cannot be empty.")
        return INCOME_SOURCE

    context.user_data["income_source"] = source

    keyboard = []
    row = []
    for cat in ExcelManager.INCOME_CATEGORIES:
        row.append(InlineKeyboardButton(cat, callback_data=f"icat_{cat}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    await update.message.reply_text(
        "Select income category:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return INCOME_CATEGORY


async def income_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.replace("icat_", "")

    try:
        result = get_excel_manager(context).add_income(
            amount=context.user_data["income_amount"],
            source=context.user_data["income_source"],
            category=category,
        )
    except ValueError as exc:
        await query.edit_message_text(f"Could not record income: {exc}")
        context.user_data.clear()
        return ConversationHandler.END

    await query.edit_message_text(
        "Income recorded.\n\n"
        f"Date: {result['date']}\n"
        f"Amount: {format_number(result['amount'])}\n"
        f"Source: {result['source']}\n"
        f"Category: {result['category']}"
    )
    context.user_data.clear()
    return ConversationHandler.END


async def save_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await reply_unauthorized(update)
        return ConversationHandler.END

    keyboard = [
        [
            InlineKeyboardButton("Deposit", callback_data="stype_Deposit"),
            InlineKeyboardButton("Withdrawal", callback_data="stype_Withdrawal"),
        ]
    ]
    await update.message.reply_text(
        "Deposit or Withdrawal?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return SAVE_TYPE


async def save_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["save_type"] = query.data.replace("stype_", "")
    await query.edit_message_text(f"Type: {context.user_data['save_type']}\nEnter amount:")
    return SAVE_AMOUNT


async def save_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = parse_amount(update.message.text)
        context.user_data["save_amount"] = amount
    except ValueError:
        await update.message.reply_text("Please enter a valid amount, for example 1000000 or Rp1.000.000.")
        return SAVE_AMOUNT

    keyboard = []
    row = []
    for acct in ExcelManager.SAVINGS_ACCOUNTS:
        row.append(InlineKeyboardButton(acct, callback_data=f"sacct_{acct}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    await update.message.reply_text(
        f"Amount: {format_number(amount)}\nSelect savings account:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return SAVE_ACCOUNT


async def save_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    account = query.data.replace("sacct_", "")

    try:
        result = get_excel_manager(context).add_savings(
            amount=context.user_data["save_amount"],
            account=account,
            transaction_type=context.user_data["save_type"],
        )
    except ValueError as exc:
        await query.edit_message_text(f"Could not record savings entry: {exc}")
        context.user_data.clear()
        return ConversationHandler.END

    emoji_type = "+" if result["type"] != "Withdrawal" else "-"
    await query.edit_message_text(
        "Savings recorded.\n\n"
        f"Account: {result['account']}\n"
        f"Type: {result['type']}\n"
        f"Amount: {emoji_type}{format_number(result['amount'])}\n"
        f"Balance: {format_number(result['balance'])}"
    )

    # Check for milestone celebration after deposit
    if result["type"] != "Withdrawal":
        try:
            em = get_excel_manager(context)
            milestone = em.check_milestone(account)
            if milestone is not None:
                await query.message.reply_text(milestone["message"])
        except Exception as e:
            logger.warning(f"Milestone check failed: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def summary_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await reply_unauthorized(update)
        return

    try:
        month = parse_month_arg(context.args, "Usage: /summary or /summary YYYY-MM")
        spending = get_excel_manager(context).get_spending_summary(month)
        income = get_excel_manager(context).get_income_summary(month)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return

    lines = [f"Financial Summary ({spending['month']})\n"]
    lines.append(f"Income:   {format_number(income['total'])}")
    lines.append(f"Spending: {format_number(spending['total'])}")
    net = income["total"] - spending["total"]
    lines.append(f"Net:      {format_number(net)} {'(surplus)' if net >= 0 else '(deficit)'}")

    if spending["by_category"]:
        lines.append(f"\nSpending Breakdown ({spending['transaction_count']} transactions):")
        for cat, amt in sorted(spending["by_category"].items(), key=lambda x: -x[1]):
            pct = (amt / spending["total"] * 100) if spending["total"] > 0 else 0
            lines.append(f"  {cat}: {format_number(amt)} ({pct:.0f}%)")
    else:
        lines.append("\nNo spending recorded for that month.")

    await update.message.reply_text("\n".join(lines))

    try:
        chart_bytes = ChartGenerator().spending_pie_chart(spending)
        await update.message.reply_photo(photo=io.BytesIO(chart_bytes))
    except Exception as e:
        logger.warning(f"Chart generation failed for /summary: {e}")


async def budget_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await reply_unauthorized(update)
        return

    try:
        month = parse_month_arg(context.args, "Usage: /budget or /budget YYYY-MM")
        budget = get_excel_manager(context).get_budget_status(month)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return

    lines = [f"Budget Status ({budget['month']})\n"]
    for item in budget["items"]:
        if item["budget"] == 0:
            continue
        icon = {"OK": ".", "WARNING": "!", "OVER BUDGET": "X"}[item["status"]]
        lines.append(
            f"[{icon}] {item['category']}: "
            f"{format_number(item['spent'])}/{format_number(item['budget'])} "
            f"({item['percentage']:.0f}%)"
        )

    lines.append(f"\nTotal: {format_number(budget['total_spent'])}/{format_number(budget['total_budget'])}")
    lines.append(f"Remaining: {format_number(budget['total_remaining'])}")

    await update.message.reply_text("\n".join(lines))

    try:
        chart_bytes = ChartGenerator().budget_status_chart(budget)
        await update.message.reply_photo(photo=io.BytesIO(chart_bytes))
    except Exception as e:
        logger.warning(f"Chart generation failed for /budget: {e}")


async def savings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await reply_unauthorized(update)
        return

    em = get_excel_manager(context)
    savings = em.get_savings_summary()
    goals = em.get_savings_goals()

    # Build a lookup by account name for goal data
    goals_by_account = {g["account"]: g for g in goals}

    lines = ["Savings Overview\n"]
    for account, data in savings["accounts"].items():
        goal_data = goals_by_account.get(account)
        if data["goal"] and goal_data:
            progress_bar = em.get_progress_bar(goal_data["progress_pct"])
            eta = goal_data["eta_months"]
            if eta is None:
                eta_text = "ETA: -"
            elif eta == 0:
                eta_text = "ETA: ✅ Tercapai!"
            else:
                eta_text = f"ETA: ~{eta} bulan"
            milestones = goal_data.get("milestones_hit", [])
            milestone_text = f"  🏅 Milestone: {', '.join(str(m) + '%' for m in milestones)}" if milestones else ""
            lines.append(
                f"  {account}: Rp {format_number(data['balance'])} / Rp {format_number(data['goal'])}\n"
                f"  {progress_bar}  •  {eta_text}"
                + (f"\n{milestone_text}" if milestone_text else "")
            )
        elif data["goal"]:
            pct = data["balance"] / data["goal"] * 100
            lines.append(f"  {account}: {format_number(data['balance'])} / Goal: {format_number(data['goal'])} ({pct:.0f}%)")
        else:
            lines.append(f"  {account}: {format_number(data['balance'])}")

    lines.append(f"\nTotal Savings: {format_number(savings['total_savings'])}")
    await update.message.reply_text("\n".join(lines))

    # Send savings progress chart
    try:
        chart_accounts = [
            {
                "name": account,
                "balance": data["balance"],
                "goal": data["goal"] if data["goal"] else data["balance"] * 1.2 if data["balance"] else 1,
            }
            for account, data in savings["accounts"].items()
        ]
        chart_data = {"accounts": chart_accounts, "savings_total": savings["total_savings"]}
        chart_bytes = ChartGenerator().savings_progress_chart(chart_data)
        await update.message.reply_photo(photo=io.BytesIO(chart_bytes))
    except Exception as e:
        logger.warning(f"Chart generation failed for /savings: {e}")


async def recent_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await reply_unauthorized(update)
        return

    try:
        limit = int(context.args[0]) if context.args else 5
    except ValueError:
        await update.message.reply_text("Usage: /recent or /recent <positive number>")
        return

    if limit <= 0:
        await update.message.reply_text("Usage: /recent or /recent <positive number>")
        return

    try:
        transactions = get_excel_manager(context).get_recent_transactions(limit)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return

    if not transactions:
        await update.message.reply_text("No transactions recorded yet.")
        return

    lines = [f"Last {len(transactions)} Transactions\n"]
    for transaction in reversed(transactions):
        lines.append(
            f"  {transaction['date']} | {format_number(transaction['amount'])} | "
            f"{transaction['category']} | {transaction['description'] or '-'}"
        )

    await update.message.reply_text("\n".join(lines))


async def dashboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await reply_unauthorized(update)
        return

    try:
        month = parse_month_arg(context.args, "Usage: /dashboard or /dashboard YYYY-MM")
        data = get_excel_manager(context).get_dashboard(month)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return

    lines = [
        f"FINANCIAL DASHBOARD ({data['month']})",
        "=" * 35,
        f"Income:        {format_number(data['income'])}",
        f"Spending:      {format_number(data['spending'])}",
        f"Net:           {format_number(data['net'])}",
        f"Total Savings: {format_number(data['savings_total'])}",
        "",
        f"Investments:   {format_number(data.get('investment_total', 0))}",
        f"Invest G/L:    {format_number(data.get('investment_gain_loss', 0))}",
        f"Total Debts:   {format_number(data.get('debt_total', 0))}",
        f"Net Worth:     {format_number(data.get('net_worth', 0))}",
        "",
        "Spending by Category:",
    ]
    if data["spending_by_category"]:
        for cat, amt in sorted(data["spending_by_category"].items(), key=lambda x: -x[1]):
            lines.append(f"  {cat}: {format_number(amt)}")
    else:
        lines.append("  No spending data for this month.")

    lines.append("\nSavings Accounts:")
    if data["savings_accounts"]:
        for acct, info in data["savings_accounts"].items():
            lines.append(f"  {acct}: {format_number(info['balance'])}")
    else:
        lines.append("  No savings data yet.")

    await update.message.reply_text("\n".join(lines))

    try:
        spending_data = {"month": data["month"], "by_category": data["spending_by_category"]}
        chart_bytes = ChartGenerator().spending_pie_chart(spending_data)
        await update.message.reply_photo(photo=io.BytesIO(chart_bytes))
    except Exception as e:
        logger.warning(f"Chart generation failed for /dashboard: {e}")


async def categories_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await reply_unauthorized(update)
        return

    lines = ["Spending Categories:"]
    for cat in ExcelManager.CATEGORIES:
        lines.append(f"  - {cat}")
    lines.append("\nSavings Accounts:")
    for acct in ExcelManager.SAVINGS_ACCOUNTS:
        lines.append(f"  - {acct}")
    lines.append("\nIncome Categories:")
    for cat in ExcelManager.INCOME_CATEGORIES:
        lines.append(f"  - {cat}")
    lines.append("\nInvestment Types:")
    for at in ExcelManager.ASSET_TYPES:
        lines.append(f"  - {at}")
    lines.append("\nDebt Types:")
    for dt in ExcelManager.DEBT_TYPES:
        lines.append(f"  - {dt}")
    lines.append("\nQuick Keywords:")
    lines.append("  food, makan, transport, bensin, kos, listrik, pulsa, belanja, health")
    await update.message.reply_text("\n".join(lines))


# ── Investment conversation ──


async def invest_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await reply_unauthorized(update)
        return ConversationHandler.END

    keyboard = []
    row = []
    for at in ExcelManager.ASSET_TYPES:
        row.append(InlineKeyboardButton(at, callback_data=f"invt_{at}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    await update.message.reply_text(
        "Record Investment\n\nSelect asset type:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return INVEST_TYPE


async def invest_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    asset_type = query.data.replace("invt_", "")
    context.user_data["invest_type"] = asset_type

    keyboard = []
    row = []
    for plat in ExcelManager.INVESTMENT_PLATFORMS:
        row.append(InlineKeyboardButton(plat, callback_data=f"invp_{plat}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    await query.edit_message_text(
        f"Type: {asset_type}\n\nSelect platform/broker:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return INVEST_PLATFORM


async def invest_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    platform = query.data.replace("invp_", "")
    context.user_data["invest_platform"] = platform

    asset_type = context.user_data["invest_type"]
    examples = {
        "Ekuitas": "e.g. BBCA, BBRI, BMRI",
        "Reksadana": "e.g. Reksa Dana Syariah Manulife",
        "Obligasi": "e.g. Savings Bond Ritel SR019",
        "Kas": "e.g. Rekening IDR, Saldo Cash",
    }
    hint = examples.get(asset_type, "e.g. asset name")

    await query.edit_message_text(
        f"Type: {asset_type}\nPlatform: {platform}\n\nEnter the security/asset name ({hint}):"
    )
    return INVEST_NAME


async def invest_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Name cannot be empty. Please enter asset name:")
        return INVEST_NAME

    context.user_data["invest_name"] = name
    await update.message.reply_text(
        f"Type: {context.user_data['invest_type']}\n"
        f"Platform: {context.user_data['invest_platform']}\n"
        f"Name: {name}\n\n"
        "Enter purchase/cost value (IDR):\n"
        "Examples: 50000000, 50.000.000, Rp50,000,000"
    )
    return INVEST_PURCHASE


async def invest_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = parse_amount(update.message.text)
        context.user_data["invest_purchase"] = amount
    except ValueError:
        await update.message.reply_text("Invalid amount. Enter purchase value like 50000000 or Rp50.000.000:")
        return INVEST_PURCHASE

    await update.message.reply_text(
        f"Purchase value: {format_number(amount)}\n\n"
        "Enter current/market value (IDR):\n"
        "(Enter the same amount if you just bought it)"
    )
    return INVEST_CURRENT


async def invest_current(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = parse_amount(update.message.text)
        context.user_data["invest_current"] = amount
    except ValueError:
        await update.message.reply_text("Invalid amount. Enter current value like 55000000 or Rp55.000.000:")
        return INVEST_CURRENT

    await update.message.reply_text(
        f"Current value: {format_number(amount)}\n\nEnter any notes (or /skip to leave blank):"
    )
    return INVEST_NOTES


async def invest_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    notes = update.message.text.strip()
    if notes == "/skip":
        notes = ""
    context.user_data["invest_notes"] = notes

    ud = context.user_data
    try:
        result = get_excel_manager(context).add_asset(
            name=ud["invest_name"],
            asset_type=ud["invest_type"],
            current_value=ud["invest_current"],
            purchase_value=ud["invest_purchase"],
            platform=ud["invest_platform"],
            notes=notes,
        )
    except ValueError as exc:
        await update.message.reply_text(f"Could not record investment: {exc}")
        context.user_data.clear()
        return ConversationHandler.END

    gain = result["current_value"] - result["purchase_value"]
    gain_text = f"+{format_number(gain)}" if gain >= 0 else format_number(gain)

    await update.message.reply_text(
        "Investment recorded!\n\n"
        f"Date: {result['date']}\n"
        f"Type: {result['type']}\n"
        f"Platform: {result['platform']}\n"
        f"Name: {result['name']}\n"
        f"Purchase: {format_number(result['purchase_value'])}\n"
        f"Current:  {format_number(result['current_value'])}\n"
        f"Gain/Loss: {gain_text}"
    )
    context.user_data.clear()
    return ConversationHandler.END


async def portfolio_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await reply_unauthorized(update)
        return

    summary = get_excel_manager(context).get_investment_summary()

    if summary["asset_count"] == 0:
        await update.message.reply_text("No investments recorded yet.\nUse /invest to add your first investment.")
        return

    lines = [
        "INVESTMENT PORTFOLIO",
        "=" * 35,
        f"Total Assets: {summary['asset_count']}",
        f"Total Value:  {format_number(summary['total_current'])}",
        f"Total Cost:   {format_number(summary['total_purchase'])}",
    ]
    gl = summary["total_gain_loss"]
    gl_text = f"+{format_number(gl)}" if gl >= 0 else format_number(gl)
    lines.append(f"Gain/Loss:    {gl_text}")

    lines.append("\nBy Asset Type:")
    for atype, data in summary["by_type"].items():
        pct = (data["current_value"] / summary["total_current"] * 100) if summary["total_current"] > 0 else 0
        lines.append(f"\n  {atype} ({pct:.1f}%) - {format_number(data['current_value'])}")
        for item in data["items"]:
            igl = item["gain_loss"]
            igl_text = f"+{format_number(igl)}" if igl >= 0 else format_number(igl)
            platform_text = f" [{item['platform']}]" if item["platform"] else ""
            lines.append(f"    {item['name']}{platform_text}: {format_number(item['current_value'])} ({igl_text})")

    if summary["by_platform"]:
        lines.append("\nBy Platform:")
        for plat, data in summary["by_platform"].items():
            lines.append(f"  {plat}: {format_number(data['current_value'])}")

    await update.message.reply_text("\n".join(lines))


# ── Debt conversation ──


async def debt_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await reply_unauthorized(update)
        return ConversationHandler.END

    keyboard = []
    row = []
    for dt in ExcelManager.DEBT_TYPES:
        row.append(InlineKeyboardButton(dt, callback_data=f"dtyp_{dt}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    await update.message.reply_text(
        "Record Debt/Liability\n\nSelect debt type:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return DEBT_TYPE


async def debt_type_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    debt_type = query.data.replace("dtyp_", "")
    context.user_data["debt_type"] = debt_type

    keyboard = []
    row = []
    for bank in ExcelManager.DEBT_BANKS:
        row.append(InlineKeyboardButton(bank, callback_data=f"dbnk_{bank}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    await query.edit_message_text(
        f"Type: {debt_type}\n\nSelect bank/lender:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return DEBT_BANK


async def debt_bank_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    bank = query.data.replace("dbnk_", "")
    context.user_data["debt_bank"] = bank

    await query.edit_message_text(
        f"Type: {context.user_data['debt_type']}\n"
        f"Bank: {bank}\n\n"
        "Enter a name for this debt:\n"
        "(e.g. KPR Rumah Depok, CC BCA Platinum)"
    )
    return DEBT_NAME


async def debt_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Name cannot be empty. Please enter debt name:")
        return DEBT_NAME
    context.user_data["debt_name"] = name

    await update.message.reply_text(
        f"Name: {name}\n\nEnter total loan amount (IDR):\nExamples: 500000000, Rp500.000.000"
    )
    return DEBT_TOTAL


async def debt_total(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = parse_amount(update.message.text)
        context.user_data["debt_total"] = amount
    except ValueError:
        await update.message.reply_text("Invalid amount. Enter total loan amount:")
        return DEBT_TOTAL

    await update.message.reply_text(
        f"Total loan: {format_number(amount)}\n\nEnter remaining balance (IDR):\n(How much you still owe)"
    )
    return DEBT_REMAINING


async def debt_remaining(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = parse_amount(update.message.text)
        context.user_data["debt_remaining"] = amount
    except ValueError:
        await update.message.reply_text("Invalid amount. Enter remaining balance:")
        return DEBT_REMAINING

    await update.message.reply_text(
        f"Remaining: {format_number(amount)}\n\nEnter monthly payment (cicilan per bulan) in IDR:"
    )
    return DEBT_MONTHLY


async def debt_monthly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = parse_amount(update.message.text)
        context.user_data["debt_monthly"] = amount
    except ValueError:
        await update.message.reply_text("Invalid amount. Enter monthly payment:")
        return DEBT_MONTHLY

    await update.message.reply_text(
        f"Monthly payment: {format_number(amount)}\n\n"
        "Enter annual interest rate (%):\n"
        "(e.g. 5.5 for 5.5%, or 0 if not applicable)"
    )
    return DEBT_INTEREST


async def debt_interest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        raw = update.message.text.strip().replace(",", ".").replace("%", "")
        rate = float(raw) / 100  # Convert from percentage to decimal
        context.user_data["debt_interest"] = rate
    except (ValueError, ZeroDivisionError):
        await update.message.reply_text("Invalid rate. Enter like: 5.5 or 0")
        return DEBT_INTEREST

    await update.message.reply_text(
        f"Interest rate: {rate * 100:.2f}%\n\n"
        "Enter the ORIGINAL loan tenor (total duration):\n"
        "Examples: 10 (years), 120 (months)\n"
        "(Numbers <= 30 are treated as years, >30 as months)"
    )
    return DEBT_TENOR


async def debt_tenor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = int(update.message.text.strip())
        if val <= 0:
            raise ValueError
        # Heuristic: if <= 30, treat as years; otherwise months
        if val <= 30:
            tenor_months = val * 12
            tenor_display = f"{val} years ({tenor_months} months)"
        else:
            tenor_months = val
            tenor_display = f"{tenor_months} months ({tenor_months // 12} years {tenor_months % 12} months)"
        context.user_data["debt_tenor"] = tenor_months
    except ValueError:
        await update.message.reply_text("Enter a number. E.g. 10 for 10 years, or 120 for 120 months:")
        return DEBT_TENOR

    await update.message.reply_text(
        f"Original tenor: {tenor_display}\n\n"
        "When did this loan START?\n"
        "Enter the start date (YYYY-MM):\n"
        "Examples: 2023-03, 2020-01"
    )
    return DEBT_START_DATE


async def debt_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from datetime import datetime as dt

    text = update.message.text.strip()

    try:
        # Parse YYYY-MM format
        parts = text.replace("/", "-").split("-")
        year = int(parts[0])
        month = int(parts[1])
        start_date = dt(year, month, 1)
        context.user_data["debt_start_date"] = text

        now = dt.now()
        months_elapsed = (now.year - year) * 12 + (now.month - month)
        tenor = context.user_data["debt_tenor"]
        months_remaining = max(0, tenor - months_elapsed)
        years_remaining = months_remaining // 12
        extra_months = months_remaining % 12
        progress_pct = (months_elapsed / tenor * 100) if tenor > 0 else 0

        # Build a visual progress bar
        filled = int(progress_pct / 5)
        bar = "█" * filled + "░" * (20 - filled)

        summary = (
            f"Loan started: {text}\n"
            f"Elapsed: {months_elapsed} months ({months_elapsed // 12}y {months_elapsed % 12}m)\n"
            f"Remaining: {months_remaining} months ({years_remaining}y {extra_months}m)\n"
            f"Progress: [{bar}] {progress_pct:.1f}%\n\n"
            "Enter any notes (or /skip to leave blank):"
        )
    except (ValueError, IndexError):
        await update.message.reply_text("Invalid date format. Enter like: 2023-03")
        return DEBT_START_DATE

    await update.message.reply_text(summary)
    return DEBT_NOTES


async def debt_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from datetime import datetime as dt

    notes = update.message.text.strip()
    if notes == "/skip":
        notes = ""

    ud = context.user_data

    # Calculate months elapsed for the notes/context
    start_str = ud.get("debt_start_date", "")
    if start_str:
        try:
            parts = start_str.replace("/", "-").split("-")
            now = dt.now()
            months_elapsed = (now.year - int(parts[0])) * 12 + (now.month - int(parts[1]))
            months_remaining = max(0, ud.get("debt_tenor", 0) - months_elapsed)
            if notes:
                notes = f"Start: {start_str} | Elapsed: {months_elapsed}m | Remaining: {months_remaining}m | {notes}"
            else:
                notes = f"Start: {start_str} | Elapsed: {months_elapsed}m | Remaining: {months_remaining}m"
        except (ValueError, IndexError):
            pass

    try:
        result = get_excel_manager(context).add_debt(
            name=ud["debt_name"],
            debt_type=ud["debt_type"],
            bank=ud["debt_bank"],
            total_loan=ud["debt_total"],
            remaining=ud["debt_remaining"],
            monthly_payment=ud["debt_monthly"],
            interest_rate=ud.get("debt_interest", 0),
            tenor_months=ud.get("debt_tenor", 0),
            notes=notes,
        )
    except ValueError as exc:
        await update.message.reply_text(f"Could not record debt: {exc}")
        context.user_data.clear()
        return ConversationHandler.END

    # Build a nice summary with progress
    tenor = result["tenor_months"]
    if start_str:
        try:
            parts = start_str.replace("/", "-").split("-")
            now = dt.now()
            elapsed = (now.year - int(parts[0])) * 12 + (now.month - int(parts[1]))
            remaining_m = max(0, tenor - elapsed)
            progress = (elapsed / tenor * 100) if tenor > 0 else 0
            filled = int(progress / 5)
            bar = "█" * filled + "░" * (20 - filled)
            progress_text = (
                f"\nStarted:       {start_str}\n"
                f"Elapsed:       {elapsed} months ({elapsed // 12}y {elapsed % 12}m)\n"
                f"Remaining:     {remaining_m} months ({remaining_m // 12}y {remaining_m % 12}m)\n"
                f"Progress:      [{bar}] {progress:.1f}%"
            )
        except (ValueError, IndexError):
            progress_text = ""
    else:
        progress_text = ""

    await update.message.reply_text(
        "Debt recorded!\n\n"
        f"Name: {result['name']}\n"
        f"Type: {result['type']}\n"
        f"Bank: {result['bank']}\n"
        f"Total Loan:    {format_number(result['total_loan'])}\n"
        f"Remaining:     {format_number(result['remaining'])}\n"
        f"Monthly:       {format_number(result['monthly_payment'])}\n"
        f"Interest:      {result['interest_rate'] * 100:.2f}%\n"
        f"Tenor:         {tenor} months ({tenor // 12}y {tenor % 12}m)\n"
        f"Paid (amount): {result['paid_pct']:.1f}%"
        f"{progress_text}"
    )
    context.user_data.clear()
    return ConversationHandler.END


async def liabilities_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await reply_unauthorized(update)
        return

    summary = get_excel_manager(context).get_debt_summary()

    if summary["debt_count"] == 0:
        await update.message.reply_text("No debts recorded yet.\nUse /debt to add your first debt.")
        return

    lines = [
        "DEBT / LIABILITIES SUMMARY",
        "=" * 35,
        f"Total Debts:     {summary['debt_count']}",
        f"Total Loan:      {format_number(summary['total_loan'])}",
        f"Remaining:       {format_number(summary['total_remaining'])}",
        f"Monthly Payment: {format_number(summary['total_monthly'])}",
    ]

    paid = summary["total_loan"] - summary["total_remaining"]
    pct = (paid / summary["total_loan"] * 100) if summary["total_loan"] > 0 else 0
    lines.append(f"Total Paid:      {format_number(paid)} ({pct:.1f}%)")

    for dtype, data in summary["by_type"].items():
        lines.append(f"\n  {dtype}:")
        for item in data["items"]:
            lines.append(
                f"    {item['name']} ({item['bank']})\n"
                f"      Remaining: {format_number(item['remaining'])} / {format_number(item['total_loan'])}\n"
                f"      Monthly: {format_number(item['monthly_payment'])} | {item['paid_pct']:.1f}% paid"
            )

    await update.message.reply_text("\n".join(lines))



# ── NLP handlers ──

async def nlp_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /nlp [on|off] command."""
    if not is_authorized(update):
        await reply_unauthorized(update)
        return

    args = context.args
    if not args:
        status = "aktif ✅" if nlp_state["enabled"] else "nonaktif ❌"
        await update.message.reply_text(
            f"🤖 Mode NLP saat ini: {status}\n\n"
            "Gunakan `/nlp on` untuk mengaktifkan atau `/nlp off` untuk menonaktifkan."
        )
        return

    cmd = args[0].lower()
    if cmd == "on":
        nlp_state["enabled"] = True
        await update.message.reply_text(
            "🤖 Mode NLP aktif. Kirim pesan bebas seperti 'beli makan 50k'"
        )
    elif cmd == "off":
        nlp_state["enabled"] = False
        await update.message.reply_text("🤖 Mode NLP nonaktif.")
    else:
        await update.message.reply_text(
            "⚠️ Argumen tidak dikenal. Gunakan `/nlp on` atau `/nlp off`."
        )


async def nlp_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Intercept free-text messages when NLP mode is on."""
    if not nlp_state["enabled"]:
        return  # Let chat_handler handle it

    if not is_authorized(update):
        return

    message = update.message
    if message is None:
        return

    text = (message.text or "").strip()
    if text.startswith("/") or len(text) <= 5:
        return  # Skip commands and very short messages

    nullclaw_path = os.getenv("NULLCLAW_PATH", "")
    if not nullclaw_path:
        await message.reply_text(
            "⚠️ NLP belum dikonfigurasi. Set NULLCLAW_PATH di .env untuk mengaktifkan fitur ini."
        )
        raise ApplicationHandlerStop

    from nlp_parser import NLPParser

    parser = NLPParser(nullclaw_path=nullclaw_path)

    await message.reply_text("🤖 Memproses pesan...")

    try:
        result = parser.parse_financial_message(text)
    except RuntimeError:
        await message.reply_text(
            "⚠️ NLP belum dikonfigurasi. Set NULLCLAW_PATH di .env untuk mengaktifkan fitur ini."
        )
        raise ApplicationHandlerStop
    except Exception as e:
        await message.reply_text(f"⚠️ Gagal memproses pesan: {str(e)[:200]}")
        raise ApplicationHandlerStop

    confidence = result.get("confidence", 0.0)
    tx_type = result.get("type", "spending")
    amount = result.get("amount", 0)
    category = result.get("category", "Other")
    description = result.get("description", "")

    type_label = {"spending": "Pengeluaran", "income": "Pemasukan", "savings": "Tabungan"}.get(tx_type, tx_type)

    if confidence < 0.7:
        await message.reply_text(
            "🤔 Maksudnya?\n"
            "[type] Rp [amount] untuk [category]?\n\n"
            "Contoh: pengeluaran Rp 50.000 untuk Food & Groceries"
        )
        raise ApplicationHandlerStop

    # High confidence — show preview with confirmation keyboard
    user_id = update.effective_user.id
    pending_data = {
        "nlp_source": True,
        "type": tx_type,
        "amount": amount,
        "category": category,
        "description": description,
    }
    pending_key = _store_pending(user_id, pending_data)

    preview = (
        f"🤖 Saya mendeteksi transaksi:\n"
        f"Tipe: {type_label}\n"
        f"Jumlah: Rp {format_number(amount)}\n"
        f"Kategori: {category}\n"
        f"Deskripsi: {description or '-'}\n"
        f"Keyakinan: {int(confidence * 100)}%\n\n"
        f"Simpan transaksi ini?"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Simpan", callback_data=f"nlp_confirm:{pending_key}"),
                InlineKeyboardButton("❌ Batal", callback_data=f"nlp_cancel:{pending_key}"),
            ]
        ]
    )
    await message.reply_text(preview, reply_markup=keyboard)
    raise ApplicationHandlerStop


async def handle_nlp_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle NLP confirm/cancel callback buttons."""
    query = update.callback_query
    await query.answer()

    data_str = query.data or ""
    user_id = query.from_user.id

    if data_str.startswith("nlp_confirm:"):
        pending_key = data_str[len("nlp_confirm:"):]
        pending_data = _retrieve_pending(pending_key, user_id)
        if pending_data is None:
            await query.edit_message_text("⏰ Data sudah expired atau tidak ditemukan. Coba kirim ulang.")
            return

        em = get_excel_manager(context)
        tx_type = pending_data.get("type", "spending")
        amount = float(pending_data.get("amount", 0))
        category = pending_data.get("category", "Other")
        description = pending_data.get("description", "")

        try:
            if tx_type == "spending":
                if category not in ExcelManager.CATEGORIES:
                    category = match_category(category) or "Shopping"
                result = em.add_transaction(
                    amount=amount,
                    category=category,
                    description=description,
                    payment_method="Cash",
                )
                await query.edit_message_text(
                    f"✅ Pengeluaran tercatat!\n\n"
                    f"Jumlah: Rp {format_number(amount)}\n"
                    f"Kategori: {category}\n"
                    f"Deskripsi: {description or '-'}\n"
                    f"Tanggal: {result['date']}"
                )
            elif tx_type == "income":
                if category not in ExcelManager.INCOME_CATEGORIES:
                    category = "Other"
                result = em.add_income(
                    amount=amount,
                    source=description or "Unknown",
                    category=category,
                    notes=description,
                )
                await query.edit_message_text(
                    f"✅ Pemasukan tercatat!\n\n"
                    f"Jumlah: Rp {format_number(amount)}\n"
                    f"Sumber: {description or 'Unknown'}\n"
                    f"Tanggal: {result['date']}"
                )
            elif tx_type == "savings":
                result = em.add_savings(
                    amount=amount,
                    account="Emergency Fund",
                    transaction_type="Deposit",
                )
                await query.edit_message_text(
                    f"✅ Tabungan tercatat!\n\n"
                    f"Jumlah: Rp {format_number(amount)}\n"
                    f"Tanggal: {result['date']}"
                )
            else:
                await query.edit_message_text(f"⚠️ Tipe transaksi tidak dikenal: {tx_type}")
        except Exception as e:
            await query.edit_message_text(f"⚠️ Gagal menyimpan: {e}")

    elif data_str.startswith("nlp_cancel:"):
        pending_key = data_str[len("nlp_cancel:"):]
        _retrieve_pending(pending_key, user_id)
        await query.edit_message_text("❌ Dibatalkan. Data tidak disimpan.")


# ── Natural language chat handler (AI-powered) ──


async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle natural language questions about finances using OpenAI with function calling."""
    if not is_authorized(update):
        await reply_unauthorized(update)
        return

    import openai
    from dotenv import load_dotenv

    load_dotenv()

    text = update.message.text.strip()
    api_key = os.getenv("OPENAI_API_KEY", "")

    if not api_key:
        await update.message.reply_text(
            "Untuk fitur AI chat, set OPENAI_API_KEY di .env\n\n"
            "Sementara gunakan command:\n"
            "/portfolio - Lihat investasi\n"
            "/liabilities - Lihat hutang\n"
            "/dashboard - Dashboard lengkap\n"
            "/help - Semua command"
        )
        return

    em = get_excel_manager(context)
    user_id = update.effective_user.id

    try:
        month = em._current_time().strftime("%Y-%m")
        inv = em.get_investment_summary()
        debt = em.get_debt_summary()
        savings = em.get_savings_summary()
        income = em.get_income_summary(month)
        spending = em.get_spending_summary(month)
        dashboard = em.get_dashboard(month)

        inv_detail = ""
        for atype, data in inv["by_type"].items():
            pct = (data["current_value"] / inv["total_current"] * 100) if inv["total_current"] > 0 else 0
            inv_detail += f"\n  {atype} ({pct:.1f}%): Rp {data['current_value']:,.0f}"
            for item in data["items"]:
                p = f" [{item['platform']}]" if item["platform"] else ""
                gl = item["gain_loss"]
                inv_detail += f"\n    - {item['name']}{p}: Rp {item['current_value']:,.0f} (gain/loss: Rp {gl:,.0f})"

        debt_detail = ""
        for d in debt["debts"]:
            debt_detail += (
                f"\n  - {d['name']} ({d['type']}, {d['bank']})"
                f"\n    Total: Rp {d['total_loan']:,.0f}, Sisa: Rp {d['remaining']:,.0f}"
                f"\n    Cicilan: Rp {d['monthly_payment']:,.0f}/bulan, Bunga: {d['interest_rate'] * 100:.2f}%"
                f"\n    Sudah bayar: {d['paid_pct']:.1f}%"
                f"\n    Notes: {d['notes']}"
            )

        spending_detail = ""
        for cat, amt in sorted(spending.get("by_category", {}).items(), key=lambda x: x[1], reverse=True):
            spending_detail += f"\n  {cat}: Rp {amt:,.0f}"

        savings_detail = ""
        for acct, amt in savings.get("accounts", {}).items():
            savings_detail += f"\n  {acct}: Rp {amt:,.0f}"

        financial_data = (
            f"=== DATA KEUANGAN USER (per {month}) ===\n"
            f"\n--- RINGKASAN ---"
            f"\nPendapatan bulan ini: Rp {income['total']:,.0f}"
            f"\nPengeluaran bulan ini: Rp {spending['total']:,.0f}"
            f"\nSisa (income - spending): Rp {dashboard['net']:,.0f}"
            f"\nTotal Tabungan: Rp {savings['total_savings']:,.0f}"
            f"\nTotal Investasi: Rp {inv['total_current']:,.0f}"
            f"\nTotal Hutang (sisa): Rp {debt['total_remaining']:,.0f}"
            f"\nNet Worth: Rp {dashboard.get('net_worth', 0):,.0f}"
            f"\n\n--- INVESTASI ({inv['asset_count']} aset, total Rp {inv['total_current']:,.0f}) ---"
            f"\nGain/Loss: Rp {inv['total_gain_loss']:,.0f}"
            f"{inv_detail}"
            f"\n\n--- HUTANG ({debt['debt_count']} item, total sisa Rp {debt['total_remaining']:,.0f}) ---"
            f"\nTotal pinjaman awal: Rp {debt['total_loan']:,.0f}"
            f"\nCicilan per bulan: Rp {debt['total_monthly']:,.0f}"
            f"{debt_detail}"
            f"\n\n--- PENGELUARAN BULAN INI ---"
            f"\nTotal: Rp {spending['total']:,.0f}"
            f"{spending_detail}"
            f"\n\n--- TABUNGAN ---"
            f"\nTotal: Rp {savings['total_savings']:,.0f}"
            f"{savings_detail}"
        )
    except Exception as e:
        financial_data = f"Error loading financial data: {e}"

    system_prompt = (
        "Kamu adalah Senior Financial Analyst & Personal Financial Advisor untuk Ferry Hinardi.\n"
        "Kamu memiliki pengalaman 20+ tahun di bidang wealth management, investment analysis, dan financial planning.\n"
        "Kamu memiliki sertifikasi CFA (Chartered Financial Analyst) dan CFP (Certified Financial Planner).\n\n"
        "PENTING:\n"
        "- Kamu SUDAH MEMILIKI AKSES PENUH ke semua data keuangan Ferry yang tertera di bawah.\n"
        "- JANGAN PERNAH bilang kamu tidak punya akses data atau minta user memberikan data.\n"
        "- SELALU gunakan data aktual di bawah ini untuk setiap jawaban.\n"
        "- Berikan analisis level profesional layaknya seorang financial advisor pribadi.\n\n"
        "KEMAMPUAN EDIT & DELETE:\n"
        "- Kamu bisa mencari, mengedit, menghapus, dan MENAMBAH data baru di spreadsheet menggunakan tools.\n"
        "- Jika user minta perbaiki/edit/hapus data, GUNAKAN tools yang tersedia.\n"
        "- Jika user minta TAMBAHKAN/CATAT data baru (rekening baru, aset baru, pengeluaran baru, dll), gunakan propose_add.\n"
        "- PENTING: Bedakan antara EDIT (mengubah data yang sudah ada) dan ADD (menambah baris baru).\n"
        "  * 'Tambahkan cash di BCA sebesar 2 juta' = ADD baris baru di assets (bukan edit Cash Tabungan)\n"
        "  * 'Ubah nilai Cash Tabungan jadi 50 juta' = EDIT baris yang sudah ada\n"
        "  * 'Catat pengeluaran makan 50rb' = ADD baris baru di transactions\n"
        "- SELALU search dulu untuk menemukan data sebelum propose edit/delete.\n"
        "- Untuk propose_add, TIDAK PERLU search dulu — langsung propose dengan data yang diberikan user.\n"
        "- Sheet yang tersedia: transactions, income, savings, assets, debts.\n"
        "- Kolom transactions: amount (wajib), category, description, payment_method, notes.\n"
        "- Kolom income: amount (wajib), source (wajib), category, notes.\n"
        "- Kolom savings: amount (wajib, harus > 0), account (wajib: Emergency Fund/Vacation/Investment/Retirement/Other), "
        "transaction_type (Deposit/Withdrawal/Interest), goal (target Rp, opsional).\n"
        "- SAVINGS GOALS AKTIF: Emergency Fund, Vacation, Investment. "
        "Jika user ingin menabung/deposit ke salah satu goal, gunakan propose_add dengan sheet='savings'. "
        "Jika user ingin tarik/withdraw, gunakan propose_add dengan transaction_type='Withdrawal'. "
        "Jika user ingin set target goal, gunakan propose_edit pada baris savings yang sesuai untuk update kolom 'goal'.\n"
        "- Kolom assets: name (wajib), type (Ekuitas/Reksadana/Obligasi/Kas/Property/Crypto/Other), "
        "current_value (wajib), purchase_value, platform, notes.\n"
        "- Kolom debts: name (wajib), type (KPR/KTA/Kartu Kredit/Pinjaman Online/Other), "
        "bank (wajib), total_loan, remaining, monthly_payment, interest_rate, tenor, notes.\n"
        "- Untuk edit: propose_edit akan menampilkan preview ke user untuk konfirmasi.\n"
        "- Untuk delete: propose_delete akan menampilkan preview ke user untuk konfirmasi.\n"
        "- Untuk add: propose_add akan menampilkan preview ke user untuk konfirmasi.\n"
        "- JANGAN langsung hapus/edit tanpa search dulu — pastikan data yang benar.\n\n"
        "PEMBAYARAN KPR:\n"
        "- Ferry punya KPR rumah di Gading Serpong, cicilan ~Rp 12.955.090/bulan ke BCA.\n"
        "- Setiap bulan orang tua Ferry membantu bayar sebagian cicilan KPR.\n"
        "- Jika user bilang 'bayar KPR', 'cicilan rumah', 'mortgage', gunakan tool propose_kpr_payment.\n"
        "- Tool ini otomatis: (1) catat transaksi Housing, (2) catat bantuan ortu sebagai income Family Support, "
        "(3) kurangi sisa hutang KPR, (4) kurangi Cash Tabungan.\n"
        "- Tanya berapa kontribusi orang tua jika user tidak menyebutkan.\n"
        "- Jika user bayar sendiri tanpa bantuan ortu, set parent_contribution=0.\n\n"
        "BUDGET:\n"
        "- Budget bulanan sudah di-set di sheet Budget. Actual Spent otomatis dari Transactions.\n"
        "- Budget categories: Food & Groceries (3jt), Transportation (2jt), Housing (12.955.090), "
        "Entertainment (500rb), Healthcare (0), Education (0), Shopping (2jt), Bills & Utilities (10jt).\n"
        "- Jika user tanya soal budget, report berdasarkan data Budget yang tersedia.\n"
        "- Jika user mau ubah budget limit, gunakan propose_edit pada sheet 'budget'.\n\n"
        "HARGA SAHAM:\n"
        "- Harga saham Ekuitas (BBNI, BMRI, BBCA, BBRI, BUMI) otomatis diupdate setiap hari jam 17:00 WIB.\n"
        "- User bisa manual update via /updateprices.\n"
        "- Current value di spreadsheet sudah mencerminkan estimasi harga pasar terbaru.\n\n"
        "Gaya komunikasi:\n"
        "- Jawab dalam Bahasa Indonesia yang profesional namun tetap ramah\n"
        "- Format angka uang: Rp 1.200.000.000 (pakai titik sebagai separator ribuan)\n"
        "- Berikan analisis mendalam berdasarkan data: rasio keuangan, health score, rekomendasi\n"
        "- Jika ditanya status finansial, berikan: ringkasan aset, liabilitas, net worth, cash flow, rasio hutang, skor kesehatan keuangan\n"
        "- Berikan saran actionable yang spesifik berdasarkan kondisi Ferry\n"
        "- Gunakan istilah keuangan yang tepat tapi jelaskan jika perlu\n"
        "- Bandingkan dengan benchmark/standar keuangan yang sehat (debt-to-income ratio, emergency fund, dll)\n\n"
        "Konteks tambahan:\n"
        "- Ferry bekerja sebagai Software Engineer Frontend di PT Traveloka Indonesia\n"
        "- Ferry memiliki KPR rumah di Gading Serpong (baru berjalan ~22 bulan dari 120 bulan)\n"
        "- Ferry berinvestasi di saham (Ajaib & Stockbit), reksadana (Manulife), obligasi (Stockbit)\n\n"
        f"{financial_data}"
    )

    try:
        client = openai.OpenAI(api_key=api_key)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]

        max_tool_rounds = 5
        for _round in range(max_tool_rounds):
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=FINANCIAL_TOOLS,
                tool_choice="auto",
                max_tokens=1500,
                temperature=0.7,
            )

            choice = response.choices[0]
            assistant_msg = choice.message

            if not assistant_msg.tool_calls:
                answer = assistant_msg.content or ""
                if len(answer) > 4000:
                    for i in range(0, len(answer), 4000):
                        await update.message.reply_text(answer[i : i + 4000])
                else:
                    await update.message.reply_text(answer or "🤔 Maaf, saya tidak punya jawaban.")
                return

            messages.append(assistant_msg)

            for tool_call in assistant_msg.tool_calls:
                fn_name = tool_call.function.name
                try:
                    fn_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps({"error": "Invalid JSON arguments"}),
                        }
                    )
                    continue

                if fn_name == "search_sheet_data":
                    sheet = fn_args.get("sheet", "")
                    filters = fn_args.get("filters", {})
                    try:
                        rows = em.search_rows(sheet, filters, limit=20)
                        result = {"rows": rows, "count": len(rows), "sheet": sheet}
                    except Exception as e:
                        result = {"error": str(e)}
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(result, default=str),
                        }
                    )

                elif fn_name in (
                    "propose_edit",
                    "propose_delete",
                    "propose_add",
                    "propose_kpr_payment",
                ):
                    if fn_name == "propose_edit":
                        sheet = fn_args.get("sheet", "")
                        row_number = fn_args.get("row_number", 0)
                        updates = fn_args.get("updates", {})
                        reason = fn_args.get("reason", "")

                        try:
                            current_rows = em.search_rows(sheet, {}, limit=1000)
                            current_row = next(
                                (r for r in current_rows if r.get("_row") == row_number),
                                None,
                            )
                        except Exception:
                            current_row = None

                        pending_data = {
                            "action": "propose_edit",
                            "sheet": sheet,
                            "row_number": row_number,
                            "updates": updates,
                            "current_row": current_row or {},
                            "reason": reason,
                        }
                    elif fn_name == "propose_delete":
                        sheet = fn_args.get("sheet", "")
                        row_numbers = fn_args.get("row_numbers", [])
                        reason = fn_args.get("reason", "")

                        rows_data = []
                        try:
                            all_rows = em.search_rows(sheet, {}, limit=1000)
                            for rn in row_numbers:
                                match = next((r for r in all_rows if r.get("_row") == rn), None)
                                if match:
                                    rows_data.append(match)
                        except Exception:
                            pass

                        pending_data = {
                            "action": "propose_delete",
                            "sheet": sheet,
                            "row_numbers": row_numbers,
                            "rows_data": rows_data,
                            "reason": reason,
                        }
                    elif fn_name == "propose_add":
                        sheet = fn_args.get("sheet", "")
                        data = fn_args.get("data", {})
                        reason = fn_args.get("reason", "")

                        pending_data = {
                            "action": "propose_add",
                            "sheet": sheet,
                            "data": data,
                            "reason": reason,
                        }

                    elif fn_name == "propose_kpr_payment":
                        parent_amt = float(fn_args.get("parent_contribution", 0))
                        month = fn_args.get("month", "")
                        notes = fn_args.get("notes", "")

                        debt_rows = em.search_rows("debts", {"type": "KPR"}, limit=1)
                        if not debt_rows:
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "content": json.dumps({"error": "KPR debt not found in Debts sheet"}),
                                }
                            )
                            continue
                        debt = debt_rows[0]
                        kpr_amount = float(debt.get("monthly_payment", 0))
                        debt_remaining = float(debt.get("remaining", 0))
                        debt_row = debt["_row"]

                        cash_rows = em.search_rows(
                            "assets",
                            {"name": "Cash (Tabungan)", "type": "Kas"},
                            limit=1,
                        )
                        cash_balance = 0.0
                        cash_row = 0
                        if cash_rows:
                            cash_balance = float(cash_rows[0].get("current_value", 0) or 0)
                            cash_row = cash_rows[0]["_row"]

                        pending_data = {
                            "action": "propose_kpr_payment",
                            "kpr_amount": kpr_amount,
                            "parent_contribution": parent_amt,
                            "month": month,
                            "notes": notes,
                            "debt_row": debt_row,
                            "debt_remaining": debt_remaining,
                            "cash_row": cash_row,
                            "cash_balance": cash_balance,
                        }

                    pending_key = _store_pending(user_id, pending_data)
                    preview = _build_edit_preview(pending_data)
                    keyboard = _build_confirm_keyboard(pending_key)
                    await update.message.reply_text(preview, reply_markup=keyboard)

                    gpt_reply = assistant_msg.content or ""
                    if gpt_reply:
                        await update.message.reply_text(gpt_reply)
                    return

                else:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps({"error": f"Unknown function: {fn_name}"}),
                        }
                    )

        await update.message.reply_text("⚠️ Terlalu banyak langkah pencarian. Coba pertanyaan yang lebih spesifik.")

    except Exception as e:
        await update.message.reply_text(
            f"AI sedang tidak tersedia ({str(e)[:100]}). Gunakan command:\n"
            "/portfolio - Lihat investasi\n"
            "/liabilities - Lihat hutang\n"
            "/dashboard - Dashboard lengkap"
        )


# ── Image handler (OpenAI Vision) ──


async def image_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle image uploads — analyze receipts, payslips, investment screenshots and auto-record."""
    if not is_authorized(update):
        await reply_unauthorized(update)
        return

    import openai
    import base64
    import json
    from dotenv import load_dotenv

    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        await update.message.reply_text(
            "Image analysis belum bisa digunakan.\nSet OPENAI_API_KEY di file .env untuk mengaktifkan fitur ini."
        )
        return

    await update.message.reply_text("📷 Menganalisis gambar... mohon tunggu sebentar.")

    try:
        # Download the photo (get the highest resolution)
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()
        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        # Get caption if any
        caption = update.message.caption or ""

        # Get current financial context
        em = get_excel_manager(context)

        system_prompt = (
            "Kamu adalah Financial Assistant Bot yang menganalisis gambar keuangan.\n"
            "Analisis gambar ini dan EXTRACT data keuangan dalam format JSON.\n\n"
            "PENTING: Kamu HARUS mengembalikan response dalam format JSON yang valid.\n\n"
            "Jika gambar adalah struk/receipt/nota/bukti pembayaran/transfer:\n"
            "{\n"
            '  "type": "spending",\n'
            '  "amount": 50000,\n'
            '  "category": "Food",\n'
            '  "description": "Makan siang di Warung Padang",\n'
            '  "merchant": "Warung Padang",\n'
            '  "date": "2026-03-19",\n'
            '  "summary": "Struk pembelian makanan Rp 50.000 di Warung Padang"\n'
            "}\n\n"
            "Jika gambar adalah slip gaji/payslip:\n"
            "{\n"
            '  "type": "income",\n'
            '  "amount": 22719200,\n'
            '  "source": "PT Traveloka Indonesia",\n'
            '  "category": "Salary",\n'
            '  "description": "Gaji Februari 2026 net pay",\n'
            '  "summary": "Slip gaji dari Traveloka, net pay Rp 22.719.200"\n'
            "}\n\n"
            "Jika gambar adalah screenshot investasi/portfolio:\n"
            "{\n"
            '  "type": "investment",\n'
            '  "items": [{"name": "BBCA", "platform": "Ajaib", "asset_type": "Ekuitas", "value": 69105000}],\n'
            '  "summary": "Portfolio investasi saham di Ajaib"\n'
            "}\n\n"
            "Jika gambar bukan terkait keuangan atau tidak bisa dianalisis:\n"
            "{\n"
            '  "type": "unknown",\n'
            '  "summary": "Deskripsi gambar"\n'
            "}\n\n"
            f"Category options untuk spending: {', '.join(ExcelManager.CATEGORIES)}\n"
            f"Category options untuk income: {', '.join(ExcelManager.INCOME_CATEGORIES)}\n"
            f"User message: {caption}\n\n"
            "HANYA return JSON, tanpa markdown code block, tanpa text lain."
        )

        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": system_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64_image}",
                                "detail": "high",
                            },
                        },
                    ],
                }
            ],
            max_tokens=1000,
        )

        raw_answer = response.choices[0].message.content.strip()

        # Clean up response — remove markdown code blocks if present
        if raw_answer.startswith("```"):
            raw_answer = re.sub(r"^```(?:json)?\s*", "", raw_answer)
            raw_answer = re.sub(r"\s*```$", "", raw_answer)

        try:
            data = json.loads(raw_answer)
        except json.JSONDecodeError:
            await update.message.reply_text(f"Analisis gambar:\n{raw_answer}")
            return

        doc_type = data.get("type", "unknown")
        user_id = update.effective_user.id

        if doc_type == "spending":
            amount = float(data.get("amount", 0))
            if amount <= 0:
                await update.message.reply_text(
                    f"📋 {data.get('summary', '')}\n\nTidak bisa mendeteksi jumlah. Catat manual: /spend"
                )
                return
            pending_data = {
                "type": "spending",
                "amount": amount,
                "category": data.get("category", "Other"),
                "description": data.get("description", "") or data.get("merchant", ""),
                "payment_method": "Other",
            }
            dupes = em.find_similar_transactions(
                amount=amount,
                description=pending_data["description"],
            )
            key = _store_pending(user_id, pending_data)
            preview = _build_preview_text(pending_data, duplicates=dupes)
            keyboard = _build_confirm_keyboard(key)
            await update.message.reply_text(
                f"📷 Hasil analisis gambar:\n\n{preview}",
                reply_markup=keyboard,
            )

        elif doc_type == "income":
            amount = float(data.get("amount", 0))
            if amount <= 0:
                await update.message.reply_text(f"📋 {data.get('summary', '')}\n\nCatat manual: /income")
                return
            pending_data = {
                "type": "income",
                "amount": amount,
                "source": data.get("source", ""),
                "category": data.get("category", "Salary"),
                "notes": data.get("description", ""),
            }
            dupes = em.find_similar_income(
                amount=amount,
                source=pending_data["source"],
            )
            key = _store_pending(user_id, pending_data)
            preview = _build_preview_text(pending_data, duplicates=dupes)
            keyboard = _build_confirm_keyboard(key)
            await update.message.reply_text(
                f"📷 Hasil analisis gambar:\n\n{preview}",
                reply_markup=keyboard,
            )

        elif doc_type == "investment":
            items = data.get("items", [])
            summary_text = data.get("summary", "Screenshot investasi")
            if not items:
                await update.message.reply_text(f"📊 {summary_text}")
                return
            pending_data = {
                "type": "investment",
                "items": items,
            }
            key = _store_pending(user_id, pending_data)
            preview = _build_preview_text(pending_data)
            keyboard = _build_confirm_keyboard(key)
            await update.message.reply_text(
                f"📷 Hasil analisis gambar:\n\n{preview}",
                reply_markup=keyboard,
            )

        else:
            await update.message.reply_text(
                f"📋 {data.get('summary', 'Gambar tidak dikenali sebagai dokumen keuangan.')}\n\n"
                "Tip: Kirim foto struk belanja, slip gaji, atau screenshot investasi\n"
                "untuk auto-record ke tracker keuangan kamu."
            )

    except Exception as e:
        await update.message.reply_text(f"Error menganalisis gambar: {str(e)}")


# ── Download Excel file ──


async def download_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send the Excel tracker file to the user."""
    if not is_authorized(update):
        await reply_unauthorized(update)
        return

    excel_path = os.getenv("EXCEL_PATH", "./Financial_Tracker.xlsx")
    if not os.path.exists(excel_path):
        await update.message.reply_text("File Excel tidak ditemukan.")
        return

    # Send explanatory message first
    await update.message.reply_text(
        "📊 *File Excel Financial Tracker Anda*\n\n"
        "💡 *Tips*: Buka sheet *Panduan* (tab pertama) untuk panduan lengkap cara membaca dashboard, "
        "penjelasan setiap sheet, glossary istilah keuangan, dan tips penggunaan.\n\n"
        "📥 Mengunduh file...",
        parse_mode="Markdown",
    )

    await update.message.reply_document(
        document=open(excel_path, "rb"),
        filename="Financial_Tracker.xlsx",
        caption="Ini file Financial Tracker kamu! (updated)",
    )


# ── Financial Health Score ──


async def health_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Calculate and display comprehensive financial health score."""
    if not is_authorized(update):
        await reply_unauthorized(update)
        return

    em = get_excel_manager(context)
    month = em._current_time().strftime("%Y-%m")

    inv = em.get_investment_summary()
    debt = em.get_debt_summary()
    savings = em.get_savings_summary()
    income = em.get_income_summary(month)
    spending = em.get_spending_summary(month)

    monthly_income = income["total"] if income["total"] > 0 else 22_719_200  # fallback to known salary
    monthly_spending = spending["total"]
    total_assets = inv["total_current"]
    total_debt = debt["total_remaining"]
    total_savings = savings["total_savings"]
    monthly_debt_payment = debt["total_monthly"]
    total_kas = inv["by_type"].get("Kas", {}).get("current_value", 0)
    net_worth = total_assets - total_debt

    # ── Calculate Scores (each 0-100) ──
    scores = {}

    # 1. Debt-to-Income Ratio (DTI) — healthy < 36%
    dti = (monthly_debt_payment / monthly_income * 100) if monthly_income > 0 else 100
    if dti <= 20:
        scores["DTI Ratio"] = 100
    elif dti <= 36:
        scores["DTI Ratio"] = 80
    elif dti <= 43:
        scores["DTI Ratio"] = 60
    elif dti <= 50:
        scores["DTI Ratio"] = 40
    elif dti <= 60:
        scores["DTI Ratio"] = 20
    else:
        scores["DTI Ratio"] = 0

    # 2. Savings Rate — healthy > 20% of income
    savings_rate = ((monthly_income - monthly_spending) / monthly_income * 100) if monthly_income > 0 else 0
    if savings_rate >= 30:
        scores["Savings Rate"] = 100
    elif savings_rate >= 20:
        scores["Savings Rate"] = 80
    elif savings_rate >= 10:
        scores["Savings Rate"] = 60
    elif savings_rate >= 5:
        scores["Savings Rate"] = 40
    elif savings_rate > 0:
        scores["Savings Rate"] = 20
    else:
        scores["Savings Rate"] = 0

    # 3. Emergency Fund — healthy = 6-12 months expenses
    monthly_expenses_est = max(monthly_spending, monthly_debt_payment + 5_000_000)
    emergency_months = (total_kas + total_savings) / monthly_expenses_est if monthly_expenses_est > 0 else 0
    if emergency_months >= 12:
        scores["Emergency Fund"] = 100
    elif emergency_months >= 6:
        scores["Emergency Fund"] = 80
    elif emergency_months >= 3:
        scores["Emergency Fund"] = 60
    elif emergency_months >= 1:
        scores["Emergency Fund"] = 40
    else:
        scores["Emergency Fund"] = 20

    # 4. Investment Diversification
    type_count = len(inv["by_type"])
    platform_count = len(inv["by_platform"])
    if type_count >= 4 and platform_count >= 3:
        scores["Diversification"] = 100
    elif type_count >= 3 and platform_count >= 2:
        scores["Diversification"] = 80
    elif type_count >= 2:
        scores["Diversification"] = 60
    elif type_count >= 1:
        scores["Diversification"] = 40
    else:
        scores["Diversification"] = 0

    # 5. Asset-to-Debt Ratio
    asset_debt_ratio = (total_assets / total_debt) if total_debt > 0 else 10
    if asset_debt_ratio >= 2:
        scores["Asset/Debt Ratio"] = 100
    elif asset_debt_ratio >= 1:
        scores["Asset/Debt Ratio"] = 70
    elif asset_debt_ratio >= 0.5:
        scores["Asset/Debt Ratio"] = 40
    else:
        scores["Asset/Debt Ratio"] = 20

    # Overall Score (weighted)
    weights = {
        "DTI Ratio": 0.25,
        "Savings Rate": 0.20,
        "Emergency Fund": 0.25,
        "Diversification": 0.10,
        "Asset/Debt Ratio": 0.20,
    }
    overall = sum(scores[k] * weights[k] for k in scores)

    # Grade
    if overall >= 80:
        grade = "A (Excellent)"
        emoji = "🟢"
    elif overall >= 65:
        grade = "B (Good)"
        emoji = "🟢"
    elif overall >= 50:
        grade = "C (Fair)"
        emoji = "🟡"
    elif overall >= 35:
        grade = "D (Needs Work)"
        emoji = "🟠"
    else:
        grade = "F (Critical)"
        emoji = "🔴"

    # Build output
    filled = int(overall / 5)
    bar = "█" * filled + "░" * (20 - filled)

    lines = [
        f"FINANCIAL HEALTH SCORE",
        f"{'=' * 35}",
        f"",
        f"{emoji} Overall: {overall:.0f}/100 — {grade}",
        f"[{bar}]",
        f"",
        f"{'─' * 35}",
        f"BREAKDOWN:",
        f"",
    ]

    status_emoji = {100: "🟢", 80: "🟢", 60: "🟡", 40: "🟠", 20: "🔴", 0: "🔴"}

    for metric, score in scores.items():
        se = status_emoji.get(score, "⚪")
        bar_m = "█" * (score // 10) + "░" * (10 - score // 10)
        lines.append(f"  {se} {metric}: {score}/100 [{bar_m}]")

    lines.extend(
        [
            f"",
            f"{'─' * 35}",
            f"KEY METRICS:",
            f"",
            f"  Monthly Income:     {format_number(monthly_income)}",
            f"  Monthly Spending:   {format_number(monthly_spending)}",
            f"  Monthly Debt:       {format_number(monthly_debt_payment)}",
            f"  DTI Ratio:          {dti:.1f}% (target: <36%)",
            f"  Savings Rate:       {savings_rate:.1f}% (target: >20%)",
            f"  Emergency Fund:     {emergency_months:.1f} months (target: 6-12)",
            f"  Net Worth:          {format_number(net_worth)}",
            f"  Asset/Debt Ratio:   {asset_debt_ratio:.2f}x",
            f"",
            f"{'─' * 35}",
            f"RECOMMENDATIONS:",
            f"",
        ]
    )

    # Generate recommendations
    if dti > 36:
        lines.append(f"  ⚠️ DTI {dti:.0f}% terlalu tinggi. Hindari hutang baru.")
    if savings_rate < 20:
        target_save = monthly_income * 0.2 - (monthly_income - monthly_spending)
        lines.append(f"  ⚠️ Tingkatkan savings rate. Target tambahan: {format_number(max(0, target_save))}/bulan")
    if emergency_months < 6:
        target_ef = monthly_expenses_est * 6 - (total_kas + total_savings)
        lines.append(f"  ⚠️ Emergency fund kurang. Butuh tambahan: {format_number(max(0, target_ef))}")
    if asset_debt_ratio < 1:
        lines.append(f"  ⚠️ Aset masih lebih kecil dari hutang. Fokus investasi & bayar cicilan.")

    # Positive notes
    if type_count >= 4:
        lines.append(f"  ✅ Diversifikasi investasi bagus ({type_count} jenis aset)")
    if savings_rate > 20:
        lines.append(f"  ✅ Savings rate {savings_rate:.0f}% sudah sehat!")
    if emergency_months >= 6:
        lines.append(f"  ✅ Emergency fund mencukupi ({emergency_months:.1f} bulan)")

    await update.message.reply_text("\n".join(lines))


# ── Stock Price Update ──


def _format_price_results(results: list[dict]) -> str:
    if not results:
        return "Tidak ada aset Ekuitas yang ditemukan untuk diupdate."

    lines = ["📈 *Update Harga Saham*", "=" * 30]
    success = 0
    for r in results:
        status = r.get("status", "")
        ticker = r.get("ticker", "?")
        name = r.get("name", "?")
        if status == "updated":
            old_v = r.get("old_value", 0)
            new_v = r.get("new_value", 0)
            price = r.get("price_per_share", 0)
            shares = r.get("shares_est", 0)
            change = new_v - old_v
            pct = (change / old_v * 100) if old_v > 0 else 0
            arrow = "🟢" if change >= 0 else "🔴"
            lines.append(
                f"\n{arrow} {name} ({ticker}.JK)"
                f"\n   Harga: Rp {price:,.0f}/lembar × {shares:,} lembar"
                f"\n   Nilai: Rp {old_v:,.0f} → Rp {new_v:,.0f}"
                f"\n   Perubahan: {'+' if change >= 0 else ''}{change:,.0f} ({pct:+.1f}%)"
            )
            success += 1
        elif status == "no_price":
            lines.append(f"\n⚠️ {name} ({ticker}.JK): Harga tidak tersedia")
        elif status == "fetch_failed":
            lines.append(f"\n❌ {name} ({ticker}.JK): Gagal fetch data")
        elif status == "update_failed":
            lines.append(f"\n❌ {name} ({ticker}.JK): Gagal update spreadsheet")

    lines.append(f"\n✅ {success}/{len(results)} aset berhasil diupdate")
    return "\n".join(lines)


async def updateprices_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await reply_unauthorized(update)
        return

    em = get_excel_manager(context)
    msg = await update.message.reply_text("⏳ Mengambil harga saham terbaru dari Yahoo Finance...")

    try:
        results = em.update_stock_prices()
        text = _format_price_results(results)
        await msg.edit_text(text)
    except Exception as e:
        await msg.edit_text(f"❌ Error update harga: {str(e)[:500]}")


async def _auto_update_prices(context: ContextTypes.DEFAULT_TYPE):
    """Daily job callback — runs at 17:00 WIB to update stock prices."""
    em = context.bot_data.get("excel_manager")
    if not em:
        logger.warning("auto_update_prices: ExcelManager not found in bot_data")
        return

    try:
        results = em.update_stock_prices()
        success = sum(1 for r in results if r.get("status") == "updated")
        logger.info(f"Auto stock update: {success}/{len(results)} updated")

        for uid in settings.allowed_user_ids:
            try:
                text = _format_price_results(results)
                await context.bot.send_message(chat_id=uid, text=text)
            except Exception:
                logger.warning(f"Failed to notify user {uid} about stock update")
    except Exception as e:
        logger.error(f"Auto stock update failed: {e}")


# ── PDF extraction pipeline ──

_PDF_TEXT_LIMIT = 100_000
_VISION_PAGE_CAP = 5
_SCANNED_PAGE_THRESHOLD = 50


class _PdfEncryptedError(Exception):
    pass


def _extract_pdf_text(pdf_path: str, api_key: str, password: str = "") -> str:
    """Multi-strategy PDF text extraction: pdftotext → PyPDF2 → Vision OCR for scanned pages."""
    import subprocess

    page_texts: list[str] = []
    scanned_page_indices: list[int] = []

    pdftotext_pages: list[str] = []
    pdftotext_args = ["pdftotext", "-layout"]
    if password:
        pdftotext_args.extend(["-upw", password])
    pdftotext_args.extend([pdf_path, "-"])
    try:
        result = subprocess.run(
            pdftotext_args,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.stdout.strip():
            pdftotext_pages = result.stdout.split("\f")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    pypdf2_pages: list[str] = []
    try:
        import PyPDF2

        reader = PyPDF2.PdfReader(pdf_path)
        if reader.is_encrypted:
            decrypt_result = reader.decrypt(password)
            if decrypt_result == 0:
                raise _PdfEncryptedError("Wrong password or no password provided")
        for page in reader.pages:
            pypdf2_pages.append(page.extract_text() or "")
    except _PdfEncryptedError:
        raise
    except Exception:
        pass

    num_pages = max(len(pdftotext_pages), len(pypdf2_pages), 1)

    for i in range(num_pages):
        pt_text = pdftotext_pages[i].strip() if i < len(pdftotext_pages) else ""
        py_text = pypdf2_pages[i].strip() if i < len(pypdf2_pages) else ""

        best = pt_text if len(pt_text) >= len(py_text) else py_text

        if len(best) < _SCANNED_PAGE_THRESHOLD:
            scanned_page_indices.append(i)
            page_texts.append("")
        else:
            page_texts.append(best)

    if scanned_page_indices and api_key:
        ocr_indices = scanned_page_indices[:_VISION_PAGE_CAP]
        try:
            from pdf2image import convert_from_path
            import base64
            import io
            import openai

            images = convert_from_path(
                pdf_path,
                first_page=min(ocr_indices) + 1,
                last_page=max(ocr_indices) + 1,
                dpi=200,
            )

            page_to_img: dict[int, object] = {}
            converted_start = min(ocr_indices)
            for offset, img in enumerate(images):
                page_idx = converted_start + offset
                if page_idx in ocr_indices:
                    page_to_img[page_idx] = img

            client = openai.OpenAI(api_key=api_key)
            for page_idx in ocr_indices:
                img = page_to_img.get(page_idx)
                if img is None:
                    continue
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=85)
                b64 = base64.b64encode(buf.getvalue()).decode()

                resp = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": (
                                        "Extract ALL text from this scanned document page. "
                                        "Preserve numbers, dates, currency amounts exactly. "
                                        "Return only the extracted text, no commentary."
                                    ),
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{b64}",
                                    },
                                },
                            ],
                        }
                    ],
                    max_tokens=4000,
                )
                ocr_text = resp.choices[0].message.content.strip()
                if len(ocr_text) >= _SCANNED_PAGE_THRESHOLD:
                    page_texts[page_idx] = ocr_text
        except ImportError:
            pass
        except Exception:
            pass

    parts = []
    total = 0
    for i, text in enumerate(page_texts):
        if not text:
            continue
        header = f"\n--- Page {i + 1} ---\n"
        segment = header + text
        if total + len(segment) > _PDF_TEXT_LIMIT:
            remaining = _PDF_TEXT_LIMIT - total
            if remaining > 100:
                parts.append(segment[:remaining] + "\n...(truncated)")
            break
        parts.append(segment)
        total += len(segment)

    return "\n".join(parts)


def _chunk_document_text(text: str, max_chars: int = _PDF_TEXT_LIMIT) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    pages = text.split("\f")
    if len(pages) <= 1:
        pages = re.split(r"(?=\n--- Page \d+ ---\n)", text)

    if len(pages) <= 1:
        chunks = []
        for start in range(0, len(text), max_chars):
            chunks.append(text[start : start + max_chars])
        return chunks

    chunks: list[str] = []
    current_chunk = ""
    for page in pages:
        if not page.strip():
            continue
        if current_chunk and len(current_chunk) + len(page) + 1 > max_chars:
            chunks.append(current_chunk)
            current_chunk = page
        else:
            current_chunk = current_chunk + ("\f" if current_chunk else "") + page
    if current_chunk.strip():
        chunks.append(current_chunk)

    return chunks if chunks else [text[:max_chars]]


def _merge_extraction_results(results: list[dict]) -> dict:
    if not results:
        return {"type": "other", "summary": "No data extracted"}
    if len(results) == 1:
        return results[0]

    merged_type = results[0].get("type", "other")
    for r in results[1:]:
        if r.get("type", "other") != merged_type:
            merged_type = results[0].get("type", "other")
            break

    if merged_type == "cc_statement":
        all_txns: list[dict] = []
        seen_keys: set[tuple] = set()
        card = results[0].get("card", "Credit Card")
        period = results[0].get("period", "")
        total = 0.0

        for r in results:
            for tx in r.get("transactions", []):
                tx_key = (
                    tx.get("date", ""),
                    tx.get("description", ""),
                    float(tx.get("amount", 0)),
                )
                if tx_key not in seen_keys:
                    seen_keys.add(tx_key)
                    all_txns.append(tx)
                    total += float(tx.get("amount", 0))

        return {
            "type": "cc_statement",
            "card": card,
            "period": period,
            "transactions": all_txns,
            "total": total,
            "summary": f"E-statement {card} ({period}), {len(all_txns)} transaksi (merged from {len(results)} chunks)",
        }

    elif merged_type == "payslip":
        best = max(results, key=lambda r: float(r.get("net_pay", 0)))
        return best

    else:
        summaries = [r.get("summary", "") for r in results if r.get("summary")]
        return {
            "type": merged_type,
            "summary": " | ".join(summaries) if summaries else "Document analyzed",
        }


# ── Document handler (PDF statements) ──


async def _analyze_and_confirm_document(
    text_content: str,
    caption: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    import openai
    import json
    from dotenv import load_dotenv

    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY", "")

    if len(text_content) < 20:
        await update.message.reply_text("Tidak bisa membaca isi file. Coba kirim sebagai screenshot/foto.")
        return

    chunks = _chunk_document_text(text_content)

    em = get_excel_manager(context)

    prompt_template = (
        "Kamu adalah Financial Data Extraction Expert.\n"
        "Analisis dokumen keuangan berikut dan extract transaksi dalam format JSON.\n\n"
        "=== E-STATEMENT KARTU KREDIT ===\n"
        "ATURAN PENTING:\n"
        "1. EXCLUDE semua entry REVERSAL, PEMBATALAN, atau yang bertanda CR (credit/refund)\n"
        "2. EXCLUDE entry 'Bea Meterai' (stamp duty)\n"
        "3. EXCLUDE payment/pembayaran ke bank (e.g. 'PAYMENT THANK YOU', bayar tagihan)\n"
        "4. Untuk CICILAN/INSTALLMENT (bertanda 'CICILAN BCA', 'INST', installment),\n"
        "   catat HANYA jumlah cicilan bulanan, set is_cicilan=true\n"
        "5. Jika ada REVERSAL diikuti CICILAN untuk item yang sama,\n"
        "   catat HANYA cicilan bulanannya (skip reversal DAN original charge)\n"
        "6. Gunakan tanggal ASLI transaksi dari e-statement (format YYYY-MM-DD)\n"
        "7. Jika ada multiple kartu (misal Everyday card), sertakan card_label per transaksi\n\n"
        "FORMAT OUTPUT CC STATEMENT:\n"
        '{"type": "cc_statement", "card": "BCA Visa", "period": "Jan 2026",\n'
        ' "transactions": [\n'
        '   {"date": "2026-01-02", "description": "GRAB", "amount": 50000,\n'
        '    "category": "Transportation", "is_cicilan": false, "card_label": ""},\n'
        '   {"date": "2026-01-11", "description": "CICILAN BCA 01/03 SHOPEE",\n'
        '    "amount": 429421, "category": "Shopping", "is_cicilan": true, "card_label": ""},\n'
        '   {"date": "2026-01-05", "description": "ADIDAS", "amount": 225000,\n'
        '    "category": "Shopping", "is_cicilan": true, "card_label": "Everyday"}\n'
        " ],\n"
        ' "total": 704421,\n'
        ' "summary": "E-statement BCA Jan 2026, 3 transaksi (1 cicilan)"\n'
        "}\n\n"
        "CATEGORY MAPPING (gunakan PERSIS ini):\n"
        f"  Pilihan: {', '.join(ExcelManager.CATEGORIES)}\n"
        "  - Grab, Gojek, SPBU, taxi, parkir → Transportation\n"
        "  - Restaurant, cafe, kopi, bakery, food court, supermarket, buah → Food & Groceries\n"
        "  - Shopee, Tokopedia, Lazada, toko retail, pakaian, eyewear → Shopping\n"
        "  - CICILAN apapun (kecuali healthcare) → Shopping\n"
        "  - Netflix, Spotify, Nintendo, game, bioskop, ClassPass → Entertainment\n"
        "  - Rumah sakit, hospital, apotek, klinik → Healthcare\n"
        "  - Laundry, studio, subscription (OPENAI, AWS, GoDaddy), Apple.com → Bills & Utilities\n"
        "  - Kursus, buku, training → Education\n\n"
        "=== SLIP GAJI / PAYSLIP ===\n"
        '{"type": "payslip", "company": "PT Traveloka", "period": "Feb 2026",\n'
        ' "gross": 28214842, "deductions": 5495642, "net_pay": 22719200,\n'
        ' "summary": "Slip gaji Traveloka Feb 2026, net Rp 22.719.200"\n'
        "}\n\n"
        "Jika dokumen lainnya:\n"
        '{"type": "other", "summary": "deskripsi dokumen"}\n\n'
        f"User message: {caption}\n\n"
        "HANYA return JSON valid, tanpa markdown code block.\n\n"
    )

    client = openai.OpenAI(api_key=api_key)
    chunk_results: list[dict] = []

    for chunk in chunks:
        prompt = prompt_template + f"ISI DOKUMEN:\n{chunk}"
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=8000,
        )

        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

        try:
            chunk_results.append(json.loads(raw))
        except json.JSONDecodeError:
            if len(chunks) == 1:
                await update.message.reply_text(f"Hasil analisis:\n{raw[:2000]}")
                return

    if not chunk_results:
        await update.message.reply_text("Gagal menganalisis dokumen. Coba kirim ulang.")
        return

    data = _merge_extraction_results(chunk_results) if len(chunk_results) > 1 else chunk_results[0]

    doc_type = data.get("type", "other")
    user_id = update.effective_user.id

    if doc_type == "cc_statement":
        transactions = data.get("transactions", [])
        card = data.get("card", "Credit Card")
        period = data.get("period", "")

        if not transactions:
            await update.message.reply_text(f"💳 E-Statement {card} ({period})\n\nTidak ada transaksi yang terdeteksi.")
            return

        valid_txns = []
        for tx in transactions:
            amount = float(tx.get("amount", 0))
            if amount > 0:
                valid_txns.append(
                    {
                        "date": tx.get("date", ""),
                        "description": tx.get("description", ""),
                        "amount": amount,
                        "category": tx.get("category", "Other"),
                        "is_cicilan": bool(tx.get("is_cicilan", False)),
                        "card_label": tx.get("card_label", ""),
                    }
                )

        if not valid_txns:
            await update.message.reply_text(
                f"💳 E-Statement {card} ({period})\n\nTidak ada transaksi valid yang terdeteksi."
            )
            return

        pending_data = {
            "type": "cc_statement",
            "card": card,
            "period": period,
            "transactions": valid_txns,
        }
        all_dupes = []
        for tx in valid_txns:
            tx_dupes = em.find_similar_transactions(
                amount=tx["amount"],
                description=tx.get("description", ""),
            )
            all_dupes.extend(tx_dupes)
        seen = set()
        unique_dupes = []
        for d in all_dupes:
            dup_key = (d["date"], d["amount"], d["description"])
            if dup_key not in seen:
                seen.add(dup_key)
                unique_dupes.append(d)
        key = _store_pending(user_id, pending_data)
        preview = _build_preview_text(pending_data, duplicates=unique_dupes or None)
        keyboard = _build_confirm_keyboard(key)
        await update.message.reply_text(
            f"📄 Hasil analisis dokumen:\n\n{preview}",
            reply_markup=keyboard,
        )

    elif doc_type == "payslip":
        net_pay = float(data.get("net_pay", 0))
        if net_pay <= 0:
            await update.message.reply_text(
                f"📋 {data.get('summary', '')}\n\nTidak bisa mendeteksi net pay. Catat manual: /income"
            )
            return

        pending_data = {
            "type": "payslip",
            "company": data.get("company", ""),
            "period": data.get("period", ""),
            "gross": float(data.get("gross", 0)),
            "deductions": float(data.get("deductions", 0)),
            "net_pay": net_pay,
        }
        dupes = em.find_similar_income(
            amount=net_pay,
            source=pending_data["company"],
        )
        key = _store_pending(user_id, pending_data)
        preview = _build_preview_text(pending_data, duplicates=dupes)
        keyboard = _build_confirm_keyboard(key)
        await update.message.reply_text(
            f"📄 Hasil analisis dokumen:\n\n{preview}",
            reply_markup=keyboard,
        )

    else:
        await update.message.reply_text(
            f"📋 {data.get('summary', 'Dokumen dianalisis')}\n\n"
            "Tip: Kirim e-statement kartu kredit (PDF) atau slip gaji."
        )


async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await reply_unauthorized(update)
        return ConversationHandler.END

    from dotenv import load_dotenv

    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        await update.message.reply_text("Set OPENAI_API_KEY di .env untuk fitur ini.")
        return ConversationHandler.END

    doc = update.message.document
    file_name = doc.file_name or "unknown"

    if not file_name.lower().endswith((".pdf", ".csv", ".txt")):
        await update.message.reply_text(
            "Format file tidak didukung. Kirim file PDF (e-statement kartu kredit atau slip gaji)."
        )
        return ConversationHandler.END

    await update.message.reply_text(f"📄 Membaca {file_name}... mohon tunggu.")

    try:
        file = await context.bot.get_file(doc.file_id)
        file_bytes = await file.download_as_bytearray()

        text_content = ""
        if file_name.lower().endswith(".pdf"):
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            try:
                text_content = _extract_pdf_text(tmp_path, api_key)
            except _PdfEncryptedError:
                context.user_data["pdf_tmp_path"] = tmp_path
                context.user_data["pdf_api_key"] = api_key
                context.user_data["pdf_caption"] = update.message.caption or ""
                await update.message.reply_text(
                    "🔒 PDF ini dilindungi password.\n\n"
                    "Silakan kirim password PDF-nya.\n"
                    "Ketik /cancel untuk membatalkan."
                )
                return PDF_PASSWORD
            finally:
                if "pdf_tmp_path" not in context.user_data:
                    os.unlink(tmp_path)
        else:
            text_content = file_bytes.decode("utf-8", errors="replace")

        caption = update.message.caption or ""
        await _analyze_and_confirm_document(text_content, caption, update, context)

    except Exception as e:
        await update.message.reply_text(f"Error membaca dokumen: {str(e)[:500]}")

    return ConversationHandler.END


async def pdf_password_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    tmp_path = context.user_data.pop("pdf_tmp_path", None)
    api_key = context.user_data.pop("pdf_api_key", "")
    caption = context.user_data.pop("pdf_caption", "")

    if not tmp_path or not os.path.exists(tmp_path):
        await update.message.reply_text("Session expired. Kirim ulang file PDF-nya.")
        return ConversationHandler.END

    try:
        await update.message.reply_text("🔓 Membuka PDF... mohon tunggu.")
        text_content = _extract_pdf_text(tmp_path, api_key, password=password)
        await _analyze_and_confirm_document(text_content, caption, update, context)
    except _PdfEncryptedError:
        context.user_data["pdf_tmp_path"] = tmp_path
        context.user_data["pdf_api_key"] = api_key
        context.user_data["pdf_caption"] = caption
        await update.message.reply_text("❌ Password salah. Coba lagi atau ketik /cancel untuk membatalkan.")
        return PDF_PASSWORD
    except Exception as e:
        await update.message.reply_text(f"Error membaca dokumen: {str(e)[:500]}")
    finally:
        if "pdf_tmp_path" not in context.user_data and tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END



# ── /remind command and recurring bill flow ──


async def remind_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await reply_unauthorized(update)
        return

    rm = RecurringManager(RECURRING_PATH)
    bills = rm.list_recurring()

    if bills:
        lines = ["🔔 *Tagihan Rutin*\n"]
        for bill in bills:
            active_tag = "" if bill["active"] else " _(nonaktif)_"
            lines.append(
                f"• {bill['name']} — Rp {bill['amount']:,.0f} "
                f"(tgl {bill['day_of_month']}, {bill['category']}){active_tag}"
            )
        text = "\n".join(lines)
    else:
        text = "Tidak ada tagihan rutin yang tersimpan."

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("➕ Tambah Tagihan", callback_data="remind_add"),
                InlineKeyboardButton("📋 Lihat Semua", callback_data="remind_list"),
            ]
        ]
    )
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")


async def remind_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "remind_list":
        rm = RecurringManager(RECURRING_PATH)
        bills = rm.list_recurring()
        if not bills:
            await query.edit_message_text("Tidak ada tagihan rutin.")
            return
        lines = ["🔔 *Semua Tagihan Rutin*\n"]
        for bill in bills:
            paid_tag = f" _(lunas {bill['last_paid']})_" if bill["last_paid"] else ""
            active_tag = "" if bill["active"] else " _(nonaktif)_"
            lines.append(
                f"• *{bill['name']}* — Rp {bill['amount']:,.0f} "
                f"| Tgl {bill['day_of_month']} | {bill['category']}{active_tag}{paid_tag}"
            )
        await query.edit_message_text("\n".join(lines), parse_mode="Markdown")
        return

    if query.data == "remind_add":
        await query.edit_message_text("Nama tagihan? (contoh: Listrik PLN, Internet Indihome)")
        return REMIND_NAME


async def remind_start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await reply_unauthorized(update)
        return ConversationHandler.END
    await update.message.reply_text("Nama tagihan? (contoh: Listrik PLN, Internet Indihome)")
    return REMIND_NAME


async def remind_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Nama tidak boleh kosong. Masukkan nama tagihan:")
        return REMIND_NAME
    context.user_data["remind_name"] = name
    await update.message.reply_text(f"Nama: {name}\n\nJumlah tagihan per bulan? (contoh: 150000, Rp150.000)")
    return REMIND_AMOUNT


async def remind_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = parse_amount(update.message.text)
        context.user_data["remind_amount"] = amount
    except ValueError:
        await update.message.reply_text("Masukkan jumlah yang valid, contoh: 150000 atau Rp150.000")
        return REMIND_AMOUNT

    await update.message.reply_text(
        f"Jumlah: Rp {amount:,.0f}\n\nTanggal jatuh tempo per bulan? (1-31, contoh: 5 untuk tanggal 5)"
    )
    return REMIND_DAY


async def remind_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        day = int(update.message.text.strip())
        if not 1 <= day <= 31:
            raise ValueError
        context.user_data["remind_day"] = day
    except ValueError:
        await update.message.reply_text("Masukkan angka 1-31 untuk tanggal jatuh tempo:")
        return REMIND_DAY

    keyboard = []
    row = []
    for cat in ExcelManager.CATEGORIES:
        row.append(InlineKeyboardButton(cat, callback_data=f"rcat_{cat}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    await update.message.reply_text(
        f"Tanggal jatuh tempo: {day}\n\nPilih kategori:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return REMIND_CATEGORY


async def remind_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.replace("rcat_", "")
    context.user_data["remind_category"] = category

    ud = context.user_data
    confirm_text = (
        f"*Konfirmasi Tagihan Baru*\n\n"
        f"Nama: {ud['remind_name']}\n"
        f"Jumlah: Rp {ud['remind_amount']:,.0f}\n"
        f"Jatuh tempo: tgl {ud['remind_day']} setiap bulan\n"
        f"Kategori: {category}\n\n"
        "Simpan tagihan ini?"
    )
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Simpan", callback_data="remind_confirm_yes"),
                InlineKeyboardButton("❌ Batal", callback_data="remind_confirm_no"),
            ]
        ]
    )
    await query.edit_message_text(confirm_text, reply_markup=keyboard, parse_mode="Markdown")
    return REMIND_CONFIRM


async def remind_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "remind_confirm_no":
        context.user_data.clear()
        await query.edit_message_text("❌ Dibatalkan. Tagihan tidak disimpan.")
        return ConversationHandler.END

    ud = context.user_data
    rm = RecurringManager(RECURRING_PATH)
    rm.add_recurring(
        name=ud["remind_name"],
        amount=ud["remind_amount"],
        category=ud["remind_category"],
        payment_method="Cash",
        day_of_month=ud["remind_day"],
    )
    saved_name = ud["remind_name"]
    saved_day = ud["remind_day"]
    context.user_data.clear()
    await query.edit_message_text(
        f"✅ Tagihan *{saved_name}* berhasil disimpan!\n"
        f"Kamu akan diingatkan setiap tanggal {saved_day}.",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def send_daily_reminders(context: ContextTypes.DEFAULT_TYPE):
    rm = RecurringManager(RECURRING_PATH)
    due_bills = rm.get_due_today()
    if not due_bills:
        logger.info("send_daily_reminders: no bills due today")
        return

    for uid in settings.allowed_user_ids:
        for bill in due_bills:
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("✅ Bayar", callback_data=f"pay_bill:{bill['id']}"),
                        InlineKeyboardButton("⏭️ Skip", callback_data=f"skip_bill:{bill['id']}"),
                    ]
                ]
            )
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=(
                        f"🔔 *Tagihan hari ini:* {bill['name']}\n"
                        f"Jumlah: Rp {bill['amount']:,.0f}\n"
                        f"Kategori: {bill['category']}"
                    ),
                    reply_markup=keyboard,
                    parse_mode="Markdown",
                )
            except Exception:
                logger.warning(f"send_daily_reminders: failed to send to uid {uid}")


async def handle_bill_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data_str = query.data or ""
    if data_str.startswith("pay_bill:"):
        bill_id = data_str[len("pay_bill:"):]
        rm = RecurringManager(RECURRING_PATH)
        bill = rm.get_bill_by_id(bill_id)
        if bill is None:
            await query.edit_message_text("⚠️ Tagihan tidak ditemukan.")
            return

        em = get_excel_manager(context)
        try:
            em.add_transaction(
                amount=bill["amount"],
                category=bill["category"],
                description=f"Bayar {bill['name']}",
                payment_method=bill.get("payment_method", "Cash"),
                notes="Dari reminder otomatis",
            )
            rm.mark_paid(bill_id)
            await query.edit_message_text(
                f"✅ *{bill['name']}* sudah dibayar!\n"
                f"Rp {bill['amount']:,.0f} dicatat ke transaksi.",
                parse_mode="Markdown",
            )
        except Exception as exc:
            await query.edit_message_text(f"⚠️ Gagal mencatat pembayaran: {exc}")

    elif data_str.startswith("skip_bill:"):
        bill_id = data_str[len("skip_bill:"):]
        rm = RecurringManager(RECURRING_PATH)
        bill = rm.get_bill_by_id(bill_id)
        if bill is None:
            await query.edit_message_text("⚠️ Tagihan tidak ditemukan.")
            return
        rm.mark_paid(bill_id)
        await query.edit_message_text(
            f"⏭️ *{bill['name']}* dilewati untuk bulan ini.",
            parse_mode="Markdown",
        )


def main():
    global excel

    if not settings.bot_token:
        print("ERROR: Set TELEGRAM_BOT_TOKEN in .env file")
        print("Get a token from @BotFather on Telegram")
        return

    excel = ExcelManager(settings.excel_path)
    app = Application.builder().token(settings.bot_token).build()
    app.bot_data["excel_manager"] = excel

    spend_conv = ConversationHandler(
        entry_points=[CommandHandler("spend", spend_start)],
        states={
            SPEND_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, spend_amount)],
            SPEND_CATEGORY: [CallbackQueryHandler(spend_category, pattern=r"^scat_")],
            SPEND_DESC: [MessageHandler(filters.TEXT, spend_desc)],
            SPEND_PAYMENT: [CallbackQueryHandler(spend_payment, pattern=r"^spay_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    income_conv = ConversationHandler(
        entry_points=[CommandHandler("income", income_start)],
        states={
            INCOME_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, income_amount)],
            INCOME_SOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, income_source)],
            INCOME_CATEGORY: [CallbackQueryHandler(income_category, pattern=r"^icat_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    save_conv = ConversationHandler(
        entry_points=[CommandHandler("save", save_start)],
        states={
            SAVE_TYPE: [CallbackQueryHandler(save_type, pattern=r"^stype_")],
            SAVE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_amount)],
            SAVE_ACCOUNT: [CallbackQueryHandler(save_account, pattern=r"^sacct_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    invest_conv = ConversationHandler(
        entry_points=[CommandHandler("invest", invest_start)],
        states={
            INVEST_TYPE: [CallbackQueryHandler(invest_type, pattern=r"^invt_")],
            INVEST_PLATFORM: [CallbackQueryHandler(invest_platform, pattern=r"^invp_")],
            INVEST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, invest_name)],
            INVEST_PURCHASE: [MessageHandler(filters.TEXT & ~filters.COMMAND, invest_purchase)],
            INVEST_CURRENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, invest_current)],
            INVEST_NOTES: [MessageHandler(filters.TEXT, invest_notes)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    debt_conv = ConversationHandler(
        entry_points=[CommandHandler("debt", debt_start)],
        states={
            DEBT_TYPE: [CallbackQueryHandler(debt_type_cb, pattern=r"^dtyp_")],
            DEBT_BANK: [CallbackQueryHandler(debt_bank_cb, pattern=r"^dbnk_")],
            DEBT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_name)],
            DEBT_TOTAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_total)],
            DEBT_REMAINING: [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_remaining)],
            DEBT_MONTHLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_monthly)],
            DEBT_INTEREST: [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_interest)],
            DEBT_TENOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_tenor)],
            DEBT_START_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_start_date)],
            DEBT_NOTES: [MessageHandler(filters.TEXT, debt_notes)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(build_onboarding_handler())
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("quick", quick_record))
    app.add_handler(CommandHandler("summary", summary_cmd))
    app.add_handler(CommandHandler("budget", budget_cmd))
    app.add_handler(CommandHandler("savings", savings_cmd))
    app.add_handler(CommandHandler("recent", recent_cmd))
    app.add_handler(CommandHandler("dashboard", dashboard_cmd))
    app.add_handler(CommandHandler("categories", categories_cmd))
    app.add_handler(CommandHandler("portfolio", portfolio_cmd))
    app.add_handler(CommandHandler("liabilities", liabilities_cmd))
    app.add_handler(CommandHandler("download", download_cmd))
    app.add_handler(CommandHandler("health", health_cmd))
    app.add_handler(CommandHandler("updateprices", updateprices_cmd))
    app.add_handler(spend_conv)
    app.add_handler(income_conv)
    app.add_handler(save_conv)
    app.add_handler(invest_conv)
    app.add_handler(debt_conv)

    remind_conv = ConversationHandler(
        entry_points=[
            CommandHandler("remindadd", remind_start_add),
            CallbackQueryHandler(remind_menu_callback, pattern=r"^remind_add$"),
        ],
        states={
            REMIND_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, remind_name)],
            REMIND_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, remind_amount)],
            REMIND_DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, remind_day)],
            REMIND_CATEGORY: [CallbackQueryHandler(remind_category, pattern=r"^rcat_")],
            REMIND_CONFIRM: [CallbackQueryHandler(remind_confirm, pattern=r"^remind_confirm_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("remind", remind_cmd))
    app.add_handler(remind_conv)
    app.add_handler(CallbackQueryHandler(remind_menu_callback, pattern=r"^remind_list$"))
    app.add_handler(CallbackQueryHandler(handle_bill_action, pattern=r"^(pay_bill|skip_bill):"))
    app.add_handler(CallbackQueryHandler(handle_extraction_confirm, pattern=r"^cfm_"))
    app.add_handler(CommandHandler("nlp", nlp_cmd))
    app.add_handler(CallbackQueryHandler(handle_nlp_confirm, pattern=r"^nlp_(confirm|cancel):"))

    # NLP message handler in group 0 (higher priority); raises ApplicationHandlerStop when it handles the message
    # When NLP is off it returns None so processing falls through to group 1
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, nlp_message_handler), group=0)

    # Image handler (must be before text chat handler)
    app.add_handler(MessageHandler(filters.PHOTO, image_handler))

    doc_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Document.ALL, document_handler)],
        states={
            PDF_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, pdf_password_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(doc_conv)

    # Natural language chat handler in group 1 — runs ONLY when NLP handler (group 0) did not stop processing
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler), group=1)

    print(f"Bot started! Tracking: {settings.excel_path}")
    print("Press Ctrl+C to stop.")

    async def run():
        async with app:
            await app.initialize()
            await app.start()
            await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)

            from zoneinfo import ZoneInfo as _ZoneInfo
            _WIB = _ZoneInfo("Asia/Jakarta")
            wib = datetime.timezone(datetime.timedelta(hours=7))
            if app.job_queue:
                app.job_queue.run_daily(
                    _auto_update_prices,
                    time=datetime.time(hour=17, minute=0, tzinfo=wib),
                    name="daily_stock_update",
                )
                app.job_queue.run_daily(
                    send_daily_reminders,
                    time=datetime.time(hour=7, minute=0, tzinfo=_WIB),
                    name="daily_bill_reminders",
                )
            else:
                logger.warning("JobQueue not available — install python-telegram-bot[job-queue]")

            stop_event = asyncio.Event()
            try:
                await stop_event.wait()
            except (KeyboardInterrupt, SystemExit):
                pass
            finally:
                await app.updater.stop()
                await app.stop()
                await app.shutdown()

    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        print("\nBot stopped.")


if __name__ == "__main__":
    main()
