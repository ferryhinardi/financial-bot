from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from bot import health_cmd


SAMPLE_DASHBOARD = {
    "month": "2026-04",
    "income": 10_000_000,
    "spending": 7_000_000,
    "net": 3_000_000,
    "savings_total": 30_000_000,
    "budget_remaining": 500_000,
    "investment_total": 20_000_000,
    "investment_gain_loss": 1_000_000,
    "debt_total": 5_000_000,
    "net_worth": 45_000_000,
}


@pytest.fixture
def mock_update():
    msg = AsyncMock()
    msg.reply_text = AsyncMock()
    msg.reply_photo = AsyncMock()
    upd = MagicMock()
    upd.message = msg
    upd.effective_user = MagicMock()
    upd.effective_user.id = 123456789
    return upd


@pytest.fixture
def mock_context():
    return MagicMock()


@pytest.mark.asyncio
@patch("bot.is_authorized", return_value=True)
@patch("bot.get_excel_manager")
async def test_health_cmd_sends_text_and_photo(mock_em_factory, _auth, mock_update, mock_context):
    em = MagicMock()
    em.get_dashboard.return_value = SAMPLE_DASHBOARD
    mock_em_factory.return_value = em

    with patch("health_score.HealthScoreGenerator.generate_scorecard", return_value=b"PNG"):
        await health_cmd(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    text = mock_update.message.reply_text.call_args[0][0]
    assert "Skor Kesehatan Keuangan" in text
    assert "Skor Keseluruhan" in text
    assert "Kekuatan" in text
    assert "Perlu Perbaikan" in text

    mock_update.message.reply_photo.assert_called_once()


@pytest.mark.asyncio
@patch("bot.is_authorized", return_value=True)
@patch("bot.get_excel_manager")
async def test_health_cmd_scorecard_failure_no_crash(mock_em_factory, _auth, mock_update, mock_context):
    em = MagicMock()
    em.get_dashboard.return_value = SAMPLE_DASHBOARD
    mock_em_factory.return_value = em

    with patch("health_score.HealthScoreGenerator.generate_scorecard", side_effect=RuntimeError("render error")):
        await health_cmd(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    mock_update.message.reply_photo.assert_not_called()


@pytest.mark.asyncio
@patch("bot.is_authorized", return_value=False)
@patch("bot.reply_unauthorized", new_callable=AsyncMock)
async def test_health_cmd_unauthorized(mock_reply_unauth, _auth, mock_update, mock_context):
    await health_cmd(mock_update, mock_context)
    mock_reply_unauth.assert_called_once_with(mock_update)
    mock_update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
@patch("bot.is_authorized", return_value=True)
@patch("bot.get_excel_manager")
async def test_health_cmd_text_format(mock_em_factory, _auth, mock_update, mock_context):
    em = MagicMock()
    em.get_dashboard.return_value = SAMPLE_DASHBOARD
    mock_em_factory.return_value = em

    with patch("health_score.HealthScoreGenerator.generate_scorecard", return_value=b"PNG"):
        await health_cmd(mock_update, mock_context)

    text = mock_update.message.reply_text.call_args[0][0]
    assert "/100" in text
    assert "•" in text

    call_kwargs = mock_update.message.reply_text.call_args[1]
    assert call_kwargs.get("parse_mode") == "Markdown"


@pytest.mark.asyncio
@patch("bot.is_authorized", return_value=True)
@patch("bot.get_excel_manager")
async def test_health_cmd_strengths_weaknesses_are_indonesian(mock_em_factory, _auth, mock_update, mock_context):
    em = MagicMock()
    em.get_dashboard.return_value = SAMPLE_DASHBOARD
    mock_em_factory.return_value = em

    INDICATOR_NAMES_ID = [
        "Tingkat Tabungan",
        "Dana Darurat",
        "Rasio Pengeluaran",
        "Alokasi Investasi",
        "Rasio Utang (DTI)",
        "Pertumbuhan Kekayaan",
        "Kepatuhan Anggaran",
        "Tabungan vs Pemasukan",
    ]

    with patch("health_score.HealthScoreGenerator.generate_scorecard", return_value=b"PNG"):
        await health_cmd(mock_update, mock_context)

    text = mock_update.message.reply_text.call_args[0][0]
    matched = [name for name in INDICATOR_NAMES_ID if name in text]
    assert len(matched) >= 6
