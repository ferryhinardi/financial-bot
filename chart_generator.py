import io
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.use("Agg")

DARK_BLUE = "#1F4E79"
GREEN = "#548235"
RED = "#C00000"
YELLOW = "#E2A908"

MONTH_NAMES = [
    "Januari",
    "Februari",
    "Maret",
    "April",
    "Mei",
    "Juni",
    "Juli",
    "Agustus",
    "September",
    "Oktober",
    "November",
    "Desember",
]
MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agt", "Sep", "Okt", "Nov", "Des"]

CHART_COLORS = [
    DARK_BLUE,
    GREEN,
    RED,
    YELLOW,
    "#2E75B6",
    "#70AD47",
    "#FF0000",
    "#FFC000",
    "#4472C4",
    "#ED7D31",
    "#A5A5A5",
    "#5B9BD5",
]


class ChartGenerator:
    def _fmt_rp(self, amount):
        return f"Rp {amount:,.0f}".replace(",", ".")

    def _save_fig(self, fig):
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)
        return buf.getvalue()

    def spending_pie_chart(self, data: dict) -> bytes:
        by_category = data.get("by_category", {})
        if not by_category:
            by_category = {"No Data": 1}

        labels = list(by_category.keys())
        values = list(by_category.values())
        total = sum(values)

        colors = (CHART_COLORS * ((len(labels) // len(CHART_COLORS)) + 1))[: len(labels)]

        fig, ax = plt.subplots(figsize=(8, 6), dpi=100)
        fig.patch.set_facecolor("white")

        wedges, texts, autotexts = ax.pie(
            values,
            labels=None,
            autopct="%1.1f%%",
            colors=colors,
            startangle=90,
            pctdistance=0.75,
        )

        for autotext in autotexts:
            autotext.set_fontsize(9)
            autotext.set_color("white")
            autotext.set_fontweight("bold")

        legend_labels = [f"{label}: {self._fmt_rp(val)}" for label, val in zip(labels, values)]
        ax.legend(
            wedges,
            legend_labels,
            loc="lower center",
            bbox_to_anchor=(0.5, -0.18),
            ncol=2,
            fontsize=8,
            frameon=True,
        )

        month = data.get("month", "")
        title = f"Pengeluaran per Kategori"
        if month:
            try:
                year, m = month.split("-")
                title += f" — {MONTH_NAMES[int(m) - 1]} {year}"
            except (ValueError, IndexError):
                pass
        ax.set_title(title, fontsize=12, fontweight="bold", color=DARK_BLUE, pad=15)

        plt.tight_layout()
        return self._save_fig(fig)

    def monthly_bar_chart(self, data: dict) -> bytes:
        monthly = data.get("monthly", [])

        if monthly:
            months_raw = [item["month"] for item in monthly]
            incomes = [item.get("income", 0) for item in monthly]
            spendings = [item.get("spending", 0) for item in monthly]

            def _abbr(m):
                try:
                    idx = int(m.split("-")[1]) - 1
                    return MONTH_ABBR[idx]
                except (ValueError, IndexError):
                    return m

            month_labels = [_abbr(m) for m in months_raw]
        else:
            by_category = data.get("by_category", {})
            if not by_category:
                by_category = {"No Data": 0}
            month_labels = list(by_category.keys())
            spendings = list(by_category.values())
            incomes = []

        fig, ax = plt.subplots(figsize=(8, 6), dpi=100)
        fig.patch.set_facecolor("white")

        x = np.arange(len(month_labels))
        width = 0.35

        if incomes:
            bars_income = ax.bar(x - width / 2, incomes, width, label="Pemasukan", color=GREEN, zorder=3)
            bars_spend = ax.bar(x + width / 2, spendings, width, label="Pengeluaran", color=RED, zorder=3)
        else:
            ax.bar(x, spendings, width * 2, label="Pengeluaran", color=RED, zorder=3)

        ax.set_xticks(x)
        ax.set_xticklabels(month_labels, rotation=45, ha="right", fontsize=9)
        ax.set_ylabel("Jumlah (Rp)", fontsize=10)
        ax.set_title("Pemasukan & Pengeluaran Bulanan", fontsize=12, fontweight="bold", color=DARK_BLUE)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda val, _: self._fmt_rp(val)))
        ax.legend(fontsize=9)
        ax.grid(axis="y", alpha=0.3, zorder=0)
        ax.set_facecolor("#F8F9FA")

        plt.tight_layout()
        return self._save_fig(fig)

    def budget_status_chart(self, data) -> bytes:
        if isinstance(data, dict):
            items = data.get("items", [])
        else:
            items = data if isinstance(data, list) else []

        if not items:
            items = [{"category": "No Data", "budget": 0, "spent": 0, "status": "OK"}]

        fig, ax = plt.subplots(figsize=(8, 6), dpi=100)
        fig.patch.set_facecolor("white")

        categories = [item["category"] for item in items]
        budgets = [item.get("budget", 0) for item in items]
        spents = [item.get("spent", 0) for item in items]
        statuses = [item.get("status", "OK") for item in items]

        y = np.arange(len(categories))
        bar_height = 0.5

        for i, (budget, spent, status) in enumerate(zip(budgets, spents, statuses)):
            ax.barh(y[i], budget, bar_height, color="#D9D9D9", zorder=2)

            s_upper = status.upper() if status else "OK"
            if "OVER" in s_upper:
                bar_color = RED
            elif "WARN" in s_upper:
                bar_color = YELLOW
            else:
                bar_color = GREEN

            ax.barh(y[i], spent, bar_height * 0.6, color=bar_color, zorder=3)

            label = f"{self._fmt_rp(spent)} / {self._fmt_rp(budget)}"
            ax.text(
                max(budget, spent) * 1.02,
                y[i],
                label,
                va="center",
                ha="left",
                fontsize=8,
                color="#333333",
            )

        ax.set_yticks(y)
        ax.set_yticklabels(categories, fontsize=9)
        ax.set_xlabel("Jumlah (Rp)", fontsize=10)
        ax.set_title("Status Budget per Kategori", fontsize=12, fontweight="bold", color=DARK_BLUE)
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda val, _: self._fmt_rp(val)))
        ax.tick_params(axis="x", rotation=30)

        from matplotlib.patches import Patch

        legend_elements = [
            Patch(facecolor=GREEN, label="OK"),
            Patch(facecolor=YELLOW, label="Warning"),
            Patch(facecolor=RED, label="Over Budget"),
            Patch(facecolor="#D9D9D9", label="Batas Budget"),
        ]
        ax.legend(handles=legend_elements, loc="lower right", fontsize=8)
        ax.grid(axis="x", alpha=0.3)
        ax.set_facecolor("#F8F9FA")

        plt.tight_layout()
        return self._save_fig(fig)

    def savings_progress_chart(self, data: dict) -> bytes:
        accounts = data.get("accounts", [])

        if not accounts:
            savings_total = data.get("savings_total", 0)
            accounts = [
                {
                    "name": "Total Tabungan",
                    "balance": savings_total,
                    "goal": savings_total * 1.2 if savings_total else 1,
                }
            ]

        fig, ax = plt.subplots(figsize=(8, 6), dpi=100)
        fig.patch.set_facecolor("white")

        names = [acc["name"] for acc in accounts]
        balances = [acc.get("balance", 0) for acc in accounts]
        goals = [acc.get("goal", 1) for acc in accounts]

        y = np.arange(len(names))
        bar_height = 0.5

        for i, (balance, goal) in enumerate(zip(balances, goals)):
            safe_goal = goal if goal > 0 else 1
            pct = min(balance / safe_goal * 100, 100)

            ax.barh(y[i], goal, bar_height, color="#D9D9D9", zorder=2)
            ax.barh(y[i], balance, bar_height * 0.6, color=GREEN, zorder=3)

            label = f"{self._fmt_rp(balance)} / {self._fmt_rp(goal)} ({pct:.0f}%)"
            ax.text(
                goal * 1.02,
                y[i],
                label,
                va="center",
                ha="left",
                fontsize=8,
                color="#333333",
            )

        ax.set_yticks(y)
        ax.set_yticklabels(names, fontsize=9)
        ax.set_xlabel("Jumlah (Rp)", fontsize=10)
        ax.set_title("Progress Tabungan per Akun", fontsize=12, fontweight="bold", color=DARK_BLUE)
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda val, _: self._fmt_rp(val)))
        ax.tick_params(axis="x", rotation=30)
        ax.grid(axis="x", alpha=0.3)
        ax.set_facecolor("#F8F9FA")

        plt.tight_layout()
        return self._save_fig(fig)

    def health_score_chart(self, data: dict) -> bytes:
        score = data.get("score", 0)
        label = data.get("label", "Unknown")

        if score >= 80:
            bar_color = GREEN
        elif score >= 60:
            bar_color = YELLOW
        else:
            bar_color = RED

        fig, ax = plt.subplots(figsize=(8, 6), dpi=100)
        fig.patch.set_facecolor("white")

        ax.barh([""], [100], 0.4, color="#E0E0E0", zorder=2)
        ax.barh([""], [score], 0.4, color=bar_color, zorder=3)

        ax.set_xlim(0, 115)
        ax.set_xlabel("Skor", fontsize=10)
        ax.set_title(
            f"Skor Kesehatan Keuangan: {label}",
            fontsize=12,
            fontweight="bold",
            color=DARK_BLUE,
        )

        ax.text(
            score + 2,
            0,
            f"{score}/100",
            va="center",
            ha="left",
            fontsize=16,
            fontweight="bold",
            color=bar_color,
        )

        for threshold, color, txt in [
            (80, GREEN, "Baik (80+)"),
            (60, YELLOW, "Cukup (60+)"),
            (0, RED, "Perlu Perhatian"),
        ]:
            ax.axvline(x=threshold, color=color, linestyle="--", alpha=0.5, linewidth=1)

        ax.grid(axis="x", alpha=0.3)
        ax.set_facecolor("#F8F9FA")

        plt.tight_layout()
        return self._save_fig(fig)
