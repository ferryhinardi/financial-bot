import io
import matplotlib
import matplotlib.pyplot as plt

matplotlib.use("Agg")

DARK_BLUE = "#1F4E79"
GREEN = "#548235"
RED = "#C00000"


class ChartGenerator:
    def spending_pie_chart(self, data: dict) -> bytes:
        fig, ax = plt.subplots(figsize=(8, 6))
        by_category = data.get("by_category", {})
        if not by_category:
            by_category = {"No Data": 1}
        colors = [DARK_BLUE, GREEN, RED] * ((len(by_category) // 3) + 1)
        colors = colors[: len(by_category)]
        ax.pie(by_category.values(), labels=by_category.keys(), autopct="%1.1f%%", colors=colors)
        ax.set_title("Spending by Category")
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)
        return buf.getvalue()

    def monthly_bar_chart(self, data: dict) -> bytes:
        fig, ax = plt.subplots(figsize=(10, 6))
        by_category = data.get("by_category", {})
        if not by_category:
            by_category = {"No Data": 0}
        categories = list(by_category.keys())
        amounts = list(by_category.values())
        ax.bar(categories, amounts, color=DARK_BLUE)
        ax.set_ylabel("Amount (Rp)")
        ax.set_title("Monthly Spending")
        plt.xticks(rotation=45, ha="right")
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)
        return buf.getvalue()

    def budget_status_chart(self, data: dict) -> bytes:
        fig, ax = plt.subplots(figsize=(10, 6))
        items = data.get("items", [])
        if not items:
            items = [{"category": "No Data", "budget": 0, "spent": 0}]
        categories = [item["category"] for item in items]
        spent = [item["spent"] for item in items]
        budget = [item["budget"] for item in items]
        x = range(len(categories))
        width = 0.35
        ax.bar([i - width / 2 for i in x], budget, width, label="Budget", color=GREEN)
        ax.bar([i + width / 2 for i in x], spent, width, label="Spent", color=RED)
        ax.set_ylabel("Amount (Rp)")
        ax.set_title("Budget Status")
        ax.set_xticks(x)
        ax.set_xticklabels(categories, rotation=45, ha="right")
        ax.legend()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)
        return buf.getvalue()

    def savings_progress_chart(self, data: dict) -> bytes:
        fig, ax = plt.subplots(figsize=(8, 6))
        savings_total = data.get("savings_total", 0)
        target = savings_total * 1.2
        progress = savings_total / target * 100 if target > 0 else 0
        ax.bar(["Savings"], [savings_total], color=GREEN)
        ax.axhline(y=target, color=RED, linestyle="--", label=f"Target: Rp {target:,.0f}")
        ax.set_ylabel("Amount (Rp)")
        ax.set_title("Savings Progress")
        ax.legend()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)
        return buf.getvalue()

    def health_score_chart(self, data: dict) -> bytes:
        fig, ax = plt.subplots(figsize=(8, 6))
        score = data.get("score", 0)
        label = data.get("label", "Unknown")
        ax.barh(["Financial Health"], [score], color=DARK_BLUE, height=0.3)
        ax.set_xlim(0, 100)
        ax.set_xlabel("Score")
        ax.set_title(f"Financial Health Score: {label}")
        ax.text(score + 2, 0, f"{score}", va="center")
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)
        return buf.getvalue()
