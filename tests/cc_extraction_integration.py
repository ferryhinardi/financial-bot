#!/usr/bin/env python3
"""Test CC e-statement extraction pipeline against existing Jan PDF."""

import sys
import os
import json
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
)

from excel_manager import ExcelManager


def extract_pdf_text(pdf_path: str, api_key: str, password: str = "") -> str:
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
            pdftotext_args, capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            pdftotext_pages = result.stdout.split("\f")
    except Exception:
        pass

    pypdf_pages: list[str] = []
    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(pdf_path, password=password if password else None)
        for page in reader.pages:
            pypdf_pages.append(page.extract_text() or "")
    except Exception:
        pass

    num_pages = max(len(pdftotext_pages), len(pypdf_pages), 1)
    SCANNED_THRESHOLD = 50

    for i in range(num_pages):
        pt_text = pdftotext_pages[i].strip() if i < len(pdftotext_pages) else ""
        py_text = pypdf_pages[i].strip() if i < len(pypdf_pages) else ""
        best = pt_text if len(pt_text) >= len(py_text) else py_text
        if len(best) < SCANNED_THRESHOLD:
            scanned_page_indices.append(i)
            page_texts.append("")
        else:
            page_texts.append(best)

    if scanned_page_indices and api_key:
        try:
            import fitz
            import openai
            import base64
            from io import BytesIO
            from PIL import Image

            doc = fitz.open(pdf_path)
            client = openai.OpenAI(api_key=api_key)

            for idx in scanned_page_indices:
                if idx >= len(doc):
                    continue
                page = doc[idx]
                pix = page.get_pixmap(dpi=200)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                buf = BytesIO()
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
                                    "text": "Extract ALL text from this scanned document page. Preserve numbers, dates, currency amounts exactly. Return only the extracted text, no commentary.",
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{b64}"
                                    },
                                },
                            ],
                        }
                    ],
                    max_tokens=4000,
                )
                ocr_text = resp.choices[0].message.content.strip()
                if len(ocr_text) >= SCANNED_THRESHOLD:
                    page_texts[idx] = ocr_text
            doc.close()
        except Exception as e:
            print(f"  OCR fallback failed: {e}")

    return "\n\n".join(page_texts)


def build_cc_prompt(text_content: str, caption: str = "") -> str:
    return (
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
        f"ISI DOKUMEN:\n{text_content}"
    )


def analyze_with_gpt(text_content: str, api_key: str) -> dict:
    import openai

    prompt = build_cc_prompt(text_content)
    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=8000,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    return json.loads(raw)


def validate_cc_result(data: dict) -> list[str]:
    errors = []

    if data.get("type") != "cc_statement":
        errors.append(f"Expected type=cc_statement, got {data.get('type')}")
        return errors

    if not data.get("card"):
        errors.append("Missing card name")

    if not data.get("period"):
        errors.append("Missing period")

    transactions = data.get("transactions", [])
    if not transactions:
        errors.append("No transactions extracted")
        return errors

    valid_categories = set(ExcelManager.CATEGORIES)
    for i, tx in enumerate(transactions):
        if not tx.get("date"):
            errors.append(f"Transaction {i}: missing date")
        elif not re.match(r"\d{4}-\d{2}-\d{2}", tx["date"]):
            errors.append(
                f"Transaction {i}: bad date format '{tx['date']}' (expected YYYY-MM-DD)"
            )

        if not tx.get("description"):
            errors.append(f"Transaction {i}: missing description")

        amount = tx.get("amount", 0)
        if amount <= 0:
            errors.append(f"Transaction {i}: invalid amount {amount}")

        cat = tx.get("category", "")
        if cat not in valid_categories:
            errors.append(f"Transaction {i}: invalid category '{cat}'")

        if "is_cicilan" not in tx:
            errors.append(f"Transaction {i}: missing is_cicilan flag")

        desc_upper = tx.get("description", "").upper()
        if any(kw in desc_upper for kw in ["REVERSAL", "PEMBATALAN"]):
            errors.append(
                f"Transaction {i}: REVERSAL not excluded: {tx['description']}"
            )

        if "card_label" not in tx:
            errors.append(f"Transaction {i}: missing card_label field")

    cicilan_count = sum(1 for tx in transactions if tx.get("is_cicilan"))
    regular_count = len(transactions) - cicilan_count

    print(f"\n📊 Extraction Summary:")
    print(f"  Card: {data.get('card')}")
    print(f"  Period: {data.get('period')}")
    print(
        f"  Total transactions: {len(transactions)} ({regular_count} regular, {cicilan_count} cicilan)"
    )
    print(f"  Total amount: Rp {data.get('total', 0):,.0f}")

    return errors


def main():
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        print("❌ OPENAI_API_KEY not set")
        sys.exit(1)

    pdf_path = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.path.expanduser(
            "~/Downloads/16070214_05022026_1770339024564_unlocked.pdf"
        )
    )

    if not os.path.exists(pdf_path):
        print(f"❌ PDF not found: {pdf_path}")
        sys.exit(1)

    print(f"📄 Extracting text from: {pdf_path}")
    text = extract_pdf_text(pdf_path, api_key)
    print(f"  Extracted {len(text)} characters")

    if len(text) < 50:
        print("❌ Not enough text extracted from PDF")
        sys.exit(1)

    print("\n🤖 Sending to GPT-4o-mini for analysis...")
    data = analyze_with_gpt(text, api_key)

    print("\n✅ GPT response parsed successfully")
    errors = validate_cc_result(data)

    if errors:
        print(f"\n⚠️  Validation issues ({len(errors)}):")
        for err in errors:
            print(f"  - {err}")
    else:
        print("\n✅ All validations passed!")

    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "cc_extraction_result.json"
    )
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Full result saved to: {output_path}")

    transactions = data.get("transactions", [])
    print(f"\n📋 First 10 transactions:")
    for tx in transactions[:10]:
        cicilan = " [Cicilan]" if tx.get("is_cicilan") else ""
        card_lbl = f" [{tx.get('card_label')}]" if tx.get("card_label") else ""
        print(
            f"  {tx['date']} | {tx['description'][:40]:<40} | Rp {tx['amount']:>12,.0f}{cicilan}{card_lbl}"
        )


if __name__ == "__main__":
    main()
