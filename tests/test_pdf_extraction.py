import unittest

import bot


class ChunkDocumentTextTestCase(unittest.TestCase):
    def test_short_text_returns_single_chunk(self):
        text = "Hello world"
        chunks = bot._chunk_document_text(text, max_chars=100)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], text)

    def test_text_at_limit_returns_single_chunk(self):
        text = "x" * 100
        chunks = bot._chunk_document_text(text, max_chars=100)
        self.assertEqual(len(chunks), 1)

    def test_long_text_with_form_feeds_splits_on_pages(self):
        page1 = "Page 1 content " * 50
        page2 = "Page 2 content " * 50
        text = page1 + "\f" + page2
        chunks = bot._chunk_document_text(text, max_chars=len(page1) + 10)
        self.assertGreaterEqual(len(chunks), 2)

    def test_long_text_with_page_headers_splits(self):
        page1 = "\n--- Page 1 ---\n" + "A" * 500
        page2 = "\n--- Page 2 ---\n" + "B" * 500
        text = page1 + page2
        chunks = bot._chunk_document_text(text, max_chars=600)
        self.assertGreaterEqual(len(chunks), 2)

    def test_long_text_without_delimiters_falls_back_to_fixed_split(self):
        text = "X" * 300
        chunks = bot._chunk_document_text(text, max_chars=100)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0], "X" * 100)
        self.assertEqual(chunks[1], "X" * 100)
        self.assertEqual(chunks[2], "X" * 100)

    def test_empty_pages_skipped(self):
        text = "Content\f\f\fMore content"
        chunks = bot._chunk_document_text(text, max_chars=5000)
        self.assertEqual(len(chunks), 1)
        for chunk in chunks:
            self.assertTrue(chunk.strip())


class MergeExtractionResultsTestCase(unittest.TestCase):
    def test_empty_results(self):
        result = bot._merge_extraction_results([])
        self.assertEqual(result["type"], "other")

    def test_single_result_returned_as_is(self):
        data = {"type": "cc_statement", "card": "BCA", "transactions": [{"amount": 50000}]}
        result = bot._merge_extraction_results([data])
        self.assertIs(result, data)

    def test_cc_statement_transactions_merged(self):
        r1 = {
            "type": "cc_statement",
            "card": "BCA Visa",
            "period": "Jan 2026",
            "transactions": [
                {"date": "2026-01-02", "description": "GRAB", "amount": 50000},
            ],
        }
        r2 = {
            "type": "cc_statement",
            "card": "BCA Visa",
            "period": "Jan 2026",
            "transactions": [
                {"date": "2026-01-05", "description": "SHOPEE", "amount": 100000},
            ],
        }
        merged = bot._merge_extraction_results([r1, r2])
        self.assertEqual(merged["type"], "cc_statement")
        self.assertEqual(len(merged["transactions"]), 2)
        self.assertAlmostEqual(merged["total"], 150000)

    def test_cc_statement_deduplicates_transactions(self):
        tx = {"date": "2026-01-02", "description": "GRAB", "amount": 50000}
        r1 = {"type": "cc_statement", "card": "BCA", "period": "Jan", "transactions": [tx]}
        r2 = {"type": "cc_statement", "card": "BCA", "period": "Jan", "transactions": [tx.copy()]}
        merged = bot._merge_extraction_results([r1, r2])
        self.assertEqual(len(merged["transactions"]), 1)

    def test_payslip_picks_highest_net_pay(self):
        r1 = {"type": "payslip", "company": "PT A", "net_pay": 10000000}
        r2 = {"type": "payslip", "company": "PT A", "net_pay": 22000000}
        merged = bot._merge_extraction_results([r1, r2])
        self.assertEqual(merged["net_pay"], 22000000)

    def test_other_type_merges_summaries(self):
        r1 = {"type": "other", "summary": "Part 1 data"}
        r2 = {"type": "other", "summary": "Part 2 data"}
        merged = bot._merge_extraction_results([r1, r2])
        self.assertIn("Part 1", merged["summary"])
        self.assertIn("Part 2", merged["summary"])


if __name__ == "__main__":
    unittest.main()
