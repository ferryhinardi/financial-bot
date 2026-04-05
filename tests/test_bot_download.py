"""Test the /download command handler."""
import os
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
import pytest

from bot import download_cmd


@pytest.fixture
def mock_update():
    """Create a mock Update object."""
    mock_message = AsyncMock()
    mock_message.reply_text = AsyncMock()
    mock_message.reply_document = AsyncMock()
    
    mock_update = MagicMock()
    mock_update.message = mock_message
    mock_update.effective_user = MagicMock()
    mock_update.effective_user.id = 123456789
    
    return mock_update


@pytest.fixture
def mock_context():
    """Create a mock ContextTypes object."""
    context = MagicMock()
    return context


@pytest.mark.asyncio
@patch("bot.is_authorized")
@patch("bot.os.path.exists")
@patch("bot.os.getenv")
async def test_download_cmd_authorized_file_exists(
    mock_getenv,
    mock_exists,
    mock_is_authorized,
    mock_update,
    mock_context,
):
    """Test /download when user is authorized and file exists."""
    mock_is_authorized.return_value = True
    mock_getenv.return_value = "./Financial_Tracker.xlsx"
    mock_exists.return_value = True

    file_content = b"fake excel data"
    with patch("builtins.open", mock_open(read_data=file_content)):
        await download_cmd(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args

        text = call_args[0][0] if call_args[0] else ""
        assert "📊" in text
        assert "Panduan" in text
        assert "Buka sheet" in text

        mock_update.message.reply_document.assert_called_once()


@pytest.mark.asyncio
@patch("bot.is_authorized")
@patch("bot.reply_unauthorized", new_callable=AsyncMock)
async def test_download_cmd_unauthorized(
    mock_reply_unauth,
    mock_is_authorized,
    mock_update,
    mock_context,
):
    """Test /download when user is not authorized."""
    mock_is_authorized.return_value = False

    await download_cmd(mock_update, mock_context)
    mock_reply_unauth.assert_called_once_with(mock_update)


@pytest.mark.asyncio
@patch("bot.is_authorized")
@patch("bot.os.path.exists")
@patch("bot.os.getenv")
async def test_download_cmd_file_not_found(
    mock_getenv,
    mock_exists,
    mock_is_authorized,
    mock_update,
    mock_context,
):
    """Test /download when Excel file is not found."""
    mock_is_authorized.return_value = True
    mock_getenv.return_value = "./Financial_Tracker.xlsx"
    mock_exists.return_value = False

    await download_cmd(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once_with("File Excel tidak ditemukan.")
