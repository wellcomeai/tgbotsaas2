"""
Utility Functions
"""

from app.utils.telegram import (
    verify_bot_token, send_telegram_message, send_photo,
    approve_chat_join_request, decline_chat_join_request,
    format_username, extract_bot_id_from_token, validate_bot_token,
    escape_markdown, escape_html, truncate_text
)
from app.utils.utm import (
    add_utm_to_url, add_utm_to_text, extract_utm_params,
    is_utm_url, remove_utm_params, generate_campaign_name,
    validate_url, format_utm_report, create_tracking_link
)

__all__ = [
    # Telegram utils
    "verify_bot_token", "send_telegram_message", "send_photo",
    "approve_chat_join_request", "decline_chat_join_request",
    "format_username", "extract_bot_id_from_token", "validate_bot_token",
    "escape_markdown", "escape_html", "truncate_text",
    
    # UTM utils
    "add_utm_to_url", "add_utm_to_text", "extract_utm_params",
    "is_utm_url", "remove_utm_params", "generate_campaign_name", 
    "validate_url", "format_utm_report", "create_tracking_link"
]
