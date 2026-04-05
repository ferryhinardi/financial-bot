import io
import matplotlib
import matplotlib.pyplot as plt

matplotlib.use("Agg")

GREEN = "#548235"
YELLOW = "#E2A908"
RED = "#C00000"
DARK_BLUE = "#1F4E79"


class HealthScoreGenerator:
    def generate_scorecard(self, data: dict) -> bytes:
        income = data.get("income", 0)
        spending = data.get("spending", 0)
        savings_total = data.get("savings_total", 0)
        investment_total = data.get("investment_total", 0)
        debt_total = data.get("debt_total", 0)
        net_worth = data.get("net_worth", 0)
        budget_remaining = data.get("budget_remaining", 0)

        indicators = self._calculate_indicators(
            income, spending, savings_total, investment_total, debt_total, net_worth, budget_remaining
        )

        overall_score = sum(ind["score"] for ind in indicators) / len(indicators)

        fig, ax = plt.subplots(figsize=(12, 10))
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")

        title_text = f"Financial Health Scorecard - {data.get('month', 'N/A')}"
        fig.text(0.5, 0.96, title_text, ha="center", fontsize=16, fontweight="bold")

        fig.text(
            0.5,
            0.90,
            f"Overall Score: {overall_score:.0f} / 100",
            ha="center",
            fontsize=14,
            fontweight="bold",
            color=DARK_BLUE,
        )

        y_start = 0.85
        bar_height = 0.08

        for i, indicator in enumerate(indicators):
            y_pos = y_start - (i * bar_height)

            color = self._get_color(indicator["score"])

            fig.patches.append(
                plt.Rectangle((0.1, y_pos - 0.025), 0.3, 0.05, facecolor=color, transform=fig.transFigure)
            )

            fig.text(0.08, y_pos, indicator["name"], fontsize=10, va="center", fontweight="bold")
            fig.text(0.42, y_pos, f"{indicator['score']:.0f}", fontsize=10, va="center")
            fig.text(0.48, y_pos, f"({indicator['label']})", fontsize=8, va="center", style="italic")

        ax.axis("off")

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    def _calculate_indicators(
        self, income, spending, savings_total, investment_total, debt_total, net_worth, budget_remaining
    ):
        monthly_expense = spending

        indicators = [
            self._savings_rate(income, spending),
            self._emergency_fund(savings_total, monthly_expense),
            self._expense_ratio(spending, income),
            self._budget_compliance(budget_remaining, income),
            self._needs_vs_wants(spending),
            self._investment_allocation(investment_total, net_worth),
            self._debt_to_income(debt_total, income),
            self._net_worth_growth(net_worth),
        ]

        return indicators

    def _get_color(self, score):
        if score >= 70:
            return GREEN
        elif score >= 50:
            return YELLOW
        else:
            return RED

    def _savings_rate(self, income, spending):
        if income == 0:
            return {"name": "Savings Rate", "score": 0, "label": "Poor"}
        rate = ((income - spending) / income) * 100

        if rate >= 20:
            score = 100
            label = "Excellent"
        elif rate >= 10:
            score = 70
            label = "Good"
        else:
            score = 40
            label = "Poor"

        return {"name": "Savings Rate", "score": score, "label": label}

    def _emergency_fund(self, savings_total, monthly_expense):
        if monthly_expense == 0:
            return {"name": "Emergency Fund", "score": 0, "label": "N/A"}

        months = savings_total / monthly_expense if monthly_expense > 0 else 0

        if months >= 6:
            score = 100
            label = "6+ months"
        elif months >= 3:
            score = 70
            label = "3-6 months"
        else:
            score = 40
            label = f"{months:.1f} months"

        return {"name": "Emergency Fund", "score": score, "label": label}

    def _expense_ratio(self, spending, income):
        if income == 0:
            return {"name": "Expense Ratio", "score": 0, "label": "N/A"}

        ratio = (spending / income) * 100

        if ratio <= 70:
            score = 100
            label = f"{ratio:.0f}%"
        elif ratio <= 85:
            score = 70
            label = f"{ratio:.0f}%"
        else:
            score = 40
            label = f"{ratio:.0f}%"

        return {"name": "Expense Ratio", "score": score, "label": label}

    def _budget_compliance(self, budget_remaining, income):
        if income == 0:
            return {"name": "Budget Compliance", "score": 100, "label": "N/A"}

        if budget_remaining >= 0:
            score = 100
            label = "On Budget"
        elif budget_remaining >= -income * 0.20:
            score = 70
            label = "Minor Over"
        else:
            score = 40
            label = "Over Budget"

        return {"name": "Budget Compliance", "score": score, "label": label}

    def _needs_vs_wants(self, spending):
        needs_ratio = 0.45

        if needs_ratio >= 0.40 and needs_ratio <= 0.50:
            score = 100
            label = "Balanced"
        elif needs_ratio >= 0.50 and needs_ratio <= 0.60:
            score = 70
            label = "Warning"
        else:
            score = 40
            label = "High Wants"

        return {"name": "Needs vs Wants", "score": score, "label": label}

    def _investment_allocation(self, investment_total, net_worth):
        if net_worth == 0:
            return {"name": "Investment Allocation", "score": 0, "label": "N/A"}

        allocation = (investment_total / net_worth) * 100

        if allocation >= 30:
            score = 100
            label = f"{allocation:.0f}%"
        else:
            score = 50
            label = f"{allocation:.0f}%"

        return {"name": "Investment Allocation", "score": score, "label": label}

    def _debt_to_income(self, debt_total, income):
        if income == 0:
            return {"name": "Debt/Income Ratio", "score": 100, "label": "N/A"}

        dti = (debt_total / income) * 100

        if dti < 30:
            score = 100
            label = f"{dti:.0f}%"
        elif dti < 40:
            score = 70
            label = f"{dti:.0f}%"
        else:
            score = 40
            label = f"{dti:.0f}%"

        return {"name": "Debt/Income Ratio", "score": score, "label": label}

    def _net_worth_growth(self, net_worth):
        inflation_rate = 3.5
        if net_worth > 0:
            score = 100
            label = "Positive"
        else:
            score = 50
            label = "Below Inflation"

        return {"name": "Net Worth Growth", "score": score, "label": label}
