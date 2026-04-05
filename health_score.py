import io
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.use("Agg")

GREEN = "#548235"
YELLOW = "#E2A908"
RED = "#C00000"
DARK_BLUE = "#1F4E79"
LIGHT_GRAY = "#F2F2F2"
MID_GRAY = "#D9D9D9"
TEXT_DARK = "#1A1A1A"
TEXT_LIGHT = "#FFFFFF"

INDICATOR_LABELS_ID = [
    "Tingkat Tabungan",
    "Dana Darurat",
    "Rasio Pengeluaran",
    "Alokasi Investasi",
    "Rasio Utang (DTI)",
    "Pertumbuhan Kekayaan",
    "Kepatuhan Anggaran",
    "Tabungan vs Pemasukan",
]


class HealthScoreGenerator:
    def generate_scorecard(self, data: dict) -> bytes:
        income = data.get("income", 0)
        spending = data.get("spending", 0)
        savings_total = data.get("savings_total", 0)
        investment_total = data.get("investment_total", 0)
        debt_total = data.get("debt_total", 0)
        net_worth = data.get("net_worth", 0)
        budget_remaining = data.get("budget_remaining", 0)
        month = data.get("month", "N/A")

        indicators = self._calculate_indicators(
            income, spending, savings_total, investment_total, debt_total, net_worth, budget_remaining
        )

        overall_score = round(sum(ind["score"] for ind in indicators) / len(indicators))

        fig = plt.figure(figsize=(10, 8), dpi=100, facecolor="white")

        try:
            yr, mo = month.split("-")
            from calendar import month_name

            month_label = f"{month_name[int(mo)]} {yr}"
        except Exception:
            month_label = month

        fig.text(
            0.5,
            0.97,
            f"Laporan Kesehatan Keuangan — {month_label}",
            ha="center",
            va="top",
            fontsize=14,
            fontweight="bold",
            color=DARK_BLUE,
        )

        ax_left = fig.add_axes([0.03, 0.10, 0.30, 0.80])
        ax_left.set_xlim(0, 1)
        ax_left.set_ylim(0, 1)
        ax_left.axis("off")
        ax_left.set_facecolor("white")

        overall_color = self._get_color(overall_score)

        circle_bg = plt.Circle((0.5, 0.60), 0.38, color=MID_GRAY, zorder=1)
        ax_left.add_patch(circle_bg)

        theta = np.linspace(np.pi / 2, np.pi / 2 - 2 * np.pi * overall_score / 100, 300)
        x_outer = 0.5 + 0.38 * np.cos(theta)
        y_outer = 0.60 + 0.38 * np.sin(theta)
        x_inner = 0.5 + 0.28 * np.cos(theta[::-1])
        y_inner = 0.60 + 0.28 * np.sin(theta[::-1])
        x_ring = np.concatenate([x_outer, x_inner])
        y_ring = np.concatenate([y_outer, y_inner])
        ring = plt.Polygon(
            list(zip(x_ring, y_ring)),
            closed=True,
            facecolor=overall_color,
            edgecolor="none",
            zorder=2,
        )
        ax_left.add_patch(ring)

        circle_inner = plt.Circle((0.5, 0.60), 0.27, color="white", zorder=3)
        ax_left.add_patch(circle_inner)

        ax_left.text(
            0.5,
            0.63,
            str(overall_score),
            ha="center",
            va="center",
            fontsize=30,
            fontweight="bold",
            color=overall_color,
            zorder=4,
        )
        ax_left.text(
            0.5,
            0.53,
            "/ 100",
            ha="center",
            va="center",
            fontsize=10,
            color="#666666",
            zorder=4,
        )

        score_label = self._score_label(overall_score)
        ax_left.text(
            0.5,
            0.42,
            score_label,
            ha="center",
            va="center",
            fontsize=11,
            fontweight="bold",
            color=overall_color,
            zorder=4,
        )

        ax_left.text(
            0.5,
            0.18,
            "SKOR KESELURUHAN",
            ha="center",
            va="center",
            fontsize=8,
            fontweight="bold",
            color=DARK_BLUE,
            zorder=4,
        )

        legend_items = [
            (GREEN, "≥ 80  Baik"),
            (YELLOW, "60–79  Cukup"),
            (RED, "< 60   Perhatian"),
        ]
        for i, (col, txt) in enumerate(legend_items):
            y_leg = 0.12 - i * 0.065
            rect = plt.Rectangle((0.10, y_leg - 0.015), 0.08, 0.030, facecolor=col, transform=ax_left.transAxes)
            ax_left.add_patch(rect)
            ax_left.text(0.22, y_leg, txt, va="center", fontsize=7.5, color=TEXT_DARK)

        ax_right = fig.add_axes([0.38, 0.07, 0.58, 0.84])
        ax_right.set_facecolor(LIGHT_GRAY)

        n = len(indicators)
        bar_height = 0.55
        y_positions = np.arange(n)

        scores = [ind["score"] for ind in indicators]
        labels = INDICATOR_LABELS_ID
        details = [ind["label"] for ind in indicators]
        trend_arrows = ["→"] * n

        colors = [self._get_color(s) for s in scores]

        ax_right.barh(y_positions, [100] * n, bar_height, color=MID_GRAY, zorder=2, align="center")

        for i, (score, color) in enumerate(zip(scores, colors)):
            ax_right.barh(y_positions[i], score, bar_height * 0.65, color=color, zorder=3, align="center")

        for i in range(n):
            ax_right.plot(
                [80, 80],
                [y_positions[i] - bar_height / 2, y_positions[i] + bar_height / 2],
                color=GREEN,
                linewidth=1.2,
                linestyle="--",
                zorder=4,
                alpha=0.7,
            )

        for i, (label, score, detail, arrow) in enumerate(zip(labels, scores, details, trend_arrows)):
            ax_right.text(
                -2,
                y_positions[i],
                label,
                ha="right",
                va="center",
                fontsize=8.5,
                fontweight="bold",
                color=TEXT_DARK,
            )
            ax_right.text(
                score + 1.5,
                y_positions[i],
                f"{score}  {arrow}",
                ha="left",
                va="center",
                fontsize=8.5,
                fontweight="bold",
                color=self._get_color(score),
            )
            ax_right.text(
                102,
                y_positions[i],
                f"({detail})",
                ha="left",
                va="center",
                fontsize=7.5,
                style="italic",
                color="#555555",
            )

        ax_right.set_xlim(-60, 135)
        ax_right.set_ylim(-0.6, n - 0.4)
        ax_right.set_yticks([])
        ax_right.set_xticks([0, 20, 40, 60, 80, 100])
        ax_right.set_xticklabels(["0", "20", "40", "60", "80", "100"], fontsize=8)
        ax_right.set_xlabel("Skor (0–100)", fontsize=9, color="#444444")
        ax_right.grid(axis="x", alpha=0.3, zorder=0)

        ax_right.text(
            80,
            -0.55,
            "Batas Baik",
            ha="center",
            va="center",
            fontsize=7,
            color=GREEN,
            style="italic",
        )

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    def _calculate_indicators(
        self, income, spending, savings_total, investment_total, debt_total, net_worth, budget_remaining
    ):
        return [
            self._savings_rate(income, spending),
            self._emergency_fund(savings_total, spending),
            self._expense_ratio(spending, income),
            self._investment_allocation(investment_total, net_worth),
            self._debt_to_income(debt_total, income),
            self._net_worth_growth(net_worth),
            self._budget_compliance(budget_remaining, income),
            self._savings_vs_income(savings_total, income),
        ]

    def _get_color(self, score):
        if score >= 80:
            return GREEN
        elif score >= 60:
            return YELLOW
        else:
            return RED

    def _score_label(self, score):
        if score >= 80:
            return "SEHAT"
        elif score >= 60:
            return "CUKUP"
        else:
            return "PERHATIAN"

    def _savings_rate(self, income, spending):
        if income <= 0:
            return {"name": "Savings Rate", "score": 30, "label": "N/A"}
        rate = ((income - spending) / income) * 100
        if rate >= 20:
            score = 100
            label = f"{rate:.0f}% (Sangat Baik)"
        elif rate >= 10:
            score = 70
            label = f"{rate:.0f}% (Cukup)"
        else:
            score = 30
            label = f"{rate:.0f}% (Rendah)"
        return {"name": "Savings Rate", "score": score, "label": label}

    def _emergency_fund(self, savings_total, monthly_expense):
        if monthly_expense <= 0:
            return {"name": "Emergency Fund", "score": 100, "label": "N/A"}
        months = savings_total / monthly_expense
        if months >= 6:
            score = 100
            label = f"{months:.1f} bulan (Aman)"
        elif months >= 3:
            score = 70
            label = f"{months:.1f} bulan (Cukup)"
        else:
            score = 30
            label = f"{months:.1f} bulan (Kurang)"
        return {"name": "Emergency Fund", "score": score, "label": label}

    def _expense_ratio(self, spending, income):
        if income <= 0:
            return {"name": "Expense Ratio", "score": 20, "label": "N/A"}
        ratio = spending / income
        if ratio <= 0.70:
            score = 100
            label = f"{ratio * 100:.0f}% (Baik)"
        elif ratio <= 0.85:
            score = 60
            label = f"{ratio * 100:.0f}% (Hati-hati)"
        else:
            score = 20
            label = f"{ratio * 100:.0f}% (Tinggi)"
        return {"name": "Expense Ratio", "score": score, "label": label}

    def _investment_allocation(self, investment_total, net_worth):
        if net_worth <= 0:
            return {"name": "Investment Allocation", "score": 20, "label": "N/A"}
        alloc = investment_total / net_worth
        if alloc >= 0.30:
            score = 100
            label = f"{alloc * 100:.0f}% (Baik)"
        elif alloc >= 0.15:
            score = 60
            label = f"{alloc * 100:.0f}% (Cukup)"
        else:
            score = 20
            label = f"{alloc * 100:.0f}% (Rendah)"
        return {"name": "Investment Allocation", "score": score, "label": label}

    def _debt_to_income(self, debt_total, income):
        if debt_total == 0:
            return {"name": "Debt/Income Ratio", "score": 100, "label": "Bebas Utang"}
        if income <= 0:
            return {"name": "Debt/Income Ratio", "score": 100, "label": "N/A"}
        dti = debt_total / income
        if dti < 0.30:
            score = 100
            label = f"{dti * 100:.0f}% (Aman)"
        elif dti < 0.40:
            score = 60
            label = f"{dti * 100:.0f}% (Hati-hati)"
        else:
            score = 20
            label = f"{dti * 100:.0f}% (Tinggi)"
        return {"name": "Debt/Income Ratio", "score": score, "label": label}

    def _net_worth_growth(self, net_worth):
        if net_worth > 0:
            score = 80
            label = "Positif"
        elif net_worth == 0:
            score = 50
            label = "Nol"
        else:
            score = 20
            label = "Negatif"
        return {"name": "Net Worth Growth", "score": score, "label": label}

    def _budget_compliance(self, budget_remaining, income):
        if budget_remaining >= 0:
            score = 100
            label = "On Budget"
        else:
            score = 40
            label = "Over Budget"
        return {"name": "Budget Compliance", "score": score, "label": label}

    def _savings_vs_income(self, savings_total, income):
        if income <= 0:
            return {"name": "Savings vs Income", "score": 80, "label": "N/A"}
        ratio = savings_total / income
        if ratio > 0:
            score = 80
            label = f"{ratio:.1f}x pendapatan"
        else:
            score = 20
            label = "Tidak ada tabungan"
        return {"name": "Savings vs Income", "score": score, "label": label}
