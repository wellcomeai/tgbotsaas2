"""
Telegram Utilities - утилиты для работы с Telegram API
"""

import httpx
import logging
from typing import Optional, Dict, Any
from app.core.exceptions import TelegramAPIError

logger = logging.getLogger(__name__)


async def verify_bot_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify bot token by calling getMe method
    
    Args:
        token: Bot token from BotFather
        
    Returns:
        Dict with bot info if valid, None if invalid
    """
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    bot_info = data['result']
                    return {
                        'id': bot_info['id'],
                        'username': bot_info['username'],
                        'first_name': bot_info['first_name'],
                        'is_bot': bot_info['is_bot'],
                        'can_join_groups': bot_info.get('can_join_groups', False),
                        'can_read_all_group_messages': bot_info.get('can_read_all_group_messages', False),
                        'supports_inline_queries': bot_info.get('supports_inline_queries', False)
                    }
                else:
                    logger.warning(f"Bot API returned error: {data.get('description')}")
                    return None
            else:
                logger.warning(f"HTTP error verifying token: {response.status_code}")
                return None
                
    except httpx.TimeoutException:
        logger.error("Timeout verifying bot token")
        return None
    except Exception as e:
        logger.error(f"Error verifying bot token: {e}")
        return None


async def send_telegram_message(
    token: str, 
    chat_id: int, 
    text: str,
    parse_mode: Optional[str] = None,
    reply_markup: Optional[Dict] = None,
    disable_web_page_preview: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Send message via Telegram Bot API
    
    Args:
        token: Bot token
        chat_id: Chat ID to send to
        text: Message text
        parse_mode: Parse mode (Markdown, HTML, etc.)
        reply_markup: Inline keyboard markup
        disable_web_page_preview: Disable link previews
        
    Returns:
        Message info if sent successfully, None otherwise
    """
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        
        payload = {
            'chat_id': chat_id,
            'text': text,
            'disable_web_page_preview': disable_web_page_preview
        }
        
        if parse_mode:
            payload['parse_mode'] = parse_mode
        
        if reply_markup:
            payload['reply_markup'] = reply_markup
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    return data['result']
                else:
                    error_description = data.get('description', 'Unknown error')
                    logger.error(f"Telegram API error: {error_description}")
                    raise TelegramAPIError(error_description, error_code=str(data.get('error_code')))
            else:
                logger.error(f"HTTP error sending message: {response.status_code}")
                raise TelegramAPIError(f"HTTP {response.status_code}", status_code=response.status_code)
                
    except httpx.TimeoutException:
        logger.error("Timeout sending telegram message")
        raise TelegramAPIError("Request timeout")
    except TelegramAPIError:
        raise
    except Exception as e:
        logger.error(f"Error sending telegram message: {e}")
        raise TelegramAPIError(str(e))


async def send_photo(
    token: str,
    chat_id: int,
    photo: str,
    caption: Optional[str] = None,
    parse_mode: Optional[str] = None,
    reply_markup: Optional[Dict] = None
) -> Optional[Dict[str, Any]]:
    """Send photo via Telegram Bot API"""
    try:
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        
        payload = {
            'chat_id': chat_id,
            'photo': photo
        }
        
        if caption:
            payload['caption'] = caption
        
        if parse_mode:
            payload['parse_mode'] = parse_mode
        
        if reply_markup:
            payload['reply_markup'] = reply_markup
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    return data['result']
                else:
                    error_description = data.get('description', 'Unknown error')
                    raise TelegramAPIError(error_description, error_code=str(data.get('error_code')))
            else:
                raise TelegramAPIError(f"HTTP {response.status_code}", status_code=response.status_code)
                
    except TelegramAPIError:
        raise
    except Exception as e:
        logger.error(f"Error sending photo: {e}")
        raise TelegramAPIError(str(e))


async def approve_chat_join_request(
    token: str,
    chat_id: int,
    user_id: int
) -> bool:
    """Approve chat join request"""
    try:
        url = f"https://api.telegram.org/bot{token}/approveChatJoinRequest"
        
        payload = {
            'chat_id': chat_id,
            'user_id': user_id
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('ok', False)
            else:
                logger.error(f"HTTP error approving join request: {response.status_code}")
                return False
                
    except Exception as e:
        logger.error(f"Error approving join request: {e}")
        return False


async def decline_chat_join_request(
    token: str,
    chat_id: int,
    user_id: int
) -> bool:
    """Decline chat join request"""
    try:
        url = f"https://api.telegram.org/bot{token}/declineChatJoinRequest"
        
        payload = {
            'chat_id': chat_id,
            'user_id': user_id
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('ok', False)
            else:
                logger.error(f"HTTP error declining join request: {response.status_code}")
                return False
                
    except Exception as e:
        logger.error(f"Error declining join request: {e}")
        return False


def format_username(username: str) -> str:
    """Format username with @ prefix if not present"""
    if username and not username.startswith('@'):
        return f"@{username}"
    return username or ""


def extract_bot_id_from_token(token: str) -> Optional[int]:
    """Extract bot ID from token"""
    try:
        bot_id = token.split(':')[0]
        return int(bot_id)
    except (ValueError, IndexError):
        return None


def validate_bot_token(token: str) -> bool:
    """Validate bot token format"""
    if not token or ':' not in token:
        return False
    
    parts = token.split(':')
    if len(parts) != 2:
        return False
    
    try:
        int(parts[0])  # Bot ID should be numeric
        return len(parts[1]) >= 35  # Token part should be at least 35 chars
    except ValueError:
        return False


def escape_markdown(text: str) -> str:
    """Escape special characters for Markdown"""
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    
    return text


def escape_html(text: str) -> str:
    """Escape special characters for HTML"""
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#x27;'))


def truncate_text(text: str, max_length: int = 4096) -> str:
    """Truncate text to fit Telegram message limits"""
    if len(text) <= max_length:
        return text
    
    return text[:max_length - 3] + "..."


async def get_chat_info(token: str, chat_id: int) -> Optional[Dict[str, Any]]:
    """Get chat information"""
    try:
        url = f"https://api.telegram.org/bot{token}/getChat"
        
        payload = {'chat_id': chat_id}
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    return data['result']
            
            return None
            
    except Exception as e:
        logger.error(f"Error getting chat info: {e}")
        return None


async def get_chat_member_count(token: str, chat_id: int) -> Optional[int]:
    """Get chat member count"""
    try:
        url = f"https://api.telegram.org/bot{token}/getChatMemberCount"
        
        payload = {'chat_id': chat_id}
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    return data['result']
            
            return None
            
    except Exception as e:
        logger.error(f"Error getting chat member count: {e}")
        return None
