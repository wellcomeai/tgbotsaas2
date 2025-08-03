"""
UTM Utils - утилиты для UTM трекинга
"""

import re
import logging
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


def add_utm_to_url(
    url: str, 
    source: str = 'bot',
    campaign: str = 'auto',
    medium: str = 'telegram',
    content: Optional[str] = None,
    term: Optional[str] = None,
    user_id: Optional[int] = None
) -> str:
    """
    Add UTM parameters to URL
    
    Args:
        url: Original URL
        source: UTM source (default: 'bot')
        campaign: UTM campaign (default: 'auto')
        medium: UTM medium (default: 'telegram')
        content: UTM content
        term: UTM term
        user_id: User ID for tracking
        
    Returns:
        URL with UTM parameters
    """
    try:
        # Parse URL
        parsed = urlparse(url)
        
        # Skip if not http/https
        if parsed.scheme not in ['http', 'https']:
            return url
            
        query_params = parse_qs(parsed.query)
        
        # Add UTM parameters if not already present
        utm_params = {
            'utm_source': source,
            'utm_medium': medium,
            'utm_campaign': campaign
        }
        
        if content:
            utm_params['utm_content'] = content
        
        if term:
            utm_params['utm_term'] = term
        
        if user_id:
            utm_params['utm_id'] = str(user_id)
        
        # Only add parameters that don't already exist
        for key, value in utm_params.items():
            if key not in query_params:
                query_params[key] = [value]
        
        # Rebuild URL
        new_query = urlencode(query_params, doseq=True)
        new_parsed = parsed._replace(query=new_query)
        
        return urlunparse(new_parsed)
        
    except Exception as e:
        logger.error(f"Error adding UTM to URL {url}: {e}")
        return url  # Return original URL if error


def add_utm_to_text(
    text: str, 
    source: str = 'bot',
    campaign: str = 'auto',
    medium: str = 'telegram',
    user_id: Optional[int] = None
) -> str:
    """
    Process all links in text and add UTM parameters
    
    Args:
        text: Text containing URLs
        source: UTM source
        campaign: UTM campaign
        medium: UTM medium
        user_id: User ID for tracking
        
    Returns:
        Text with UTM-enhanced URLs
    """
    try:
        # Pattern for URLs
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        
        def replace_url(match):
            original_url = match.group(0)
            utm_url = add_utm_to_url(
                original_url, 
                source=source, 
                campaign=campaign, 
                medium=medium,
                user_id=user_id
            )
            return utm_url
        
        # Replace all URLs with UTM versions
        processed_text = re.sub(url_pattern, replace_url, text)
        
        return processed_text
        
    except Exception as e:
        logger.error(f"Error processing text links: {e}")
        return text  # Return original text if error


def extract_utm_params(url: str) -> Dict[str, str]:
    """
    Extract UTM parameters from URL
    
    Args:
        url: URL to extract UTM parameters from
        
    Returns:
        Dictionary with UTM parameters
    """
    try:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        
        utm_params = {}
        utm_keys = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'utm_id']
        
        for key in utm_keys:
            if key in query_params and query_params[key]:
                utm_params[key] = query_params[key][0]  # Take first value
        
        return utm_params
        
    except Exception as e:
        logger.error(f"Error extracting UTM params from {url}: {e}")
        return {}


def is_utm_url(url: str) -> bool:
    """
    Check if URL already contains UTM parameters
    
    Args:
        url: URL to check
        
    Returns:
        True if URL contains UTM parameters
    """
    utm_params = extract_utm_params(url)
    return len(utm_params) > 0


def remove_utm_params(url: str) -> str:
    """
    Remove UTM parameters from URL
    
    Args:
        url: URL to clean
        
    Returns:
        URL without UTM parameters
    """
    try:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        
        # Remove UTM parameters
        utm_keys = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'utm_id']
        for key in utm_keys:
            if key in query_params:
                del query_params[key]
        
        # Rebuild URL
        new_query = urlencode(query_params, doseq=True)
        new_parsed = parsed._replace(query=new_query)
        
        return urlunparse(new_parsed)
        
    except Exception as e:
        logger.error(f"Error removing UTM params from {url}: {e}")
        return url


def generate_campaign_name(
    message_type: str, 
    bot_id: Optional[int] = None,
    user_count: Optional[int] = None
) -> str:
    """
    Generate campaign name based on message type
    
    Args:
        message_type: Type of message ('welcome', 'broadcast', 'auto_message', etc.)
        bot_id: Bot ID
        user_count: Number of users (for broadcasts)
        
    Returns:
        Generated campaign name
    """
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        
        if message_type == 'welcome':
            return f'welcome_{timestamp}'
        elif message_type == 'broadcast':
            if user_count:
                return f'broadcast_{user_count}users_{timestamp}'
            return f'broadcast_{timestamp}'
        elif message_type == 'auto_message':
            return f'auto_sequence_{timestamp}'
        elif message_type == 'scheduled':
            return f'scheduled_{timestamp}'
        elif message_type == 'admin':
            return f'admin_{timestamp}'
        else:
            base = message_type.replace(' ', '_').lower()
            return f'{base}_{timestamp}'
            
    except Exception as e:
        logger.error(f"Error generating campaign name: {e}")
        return f'campaign_{datetime.now().strftime("%Y%m%d_%H%M")}'


def validate_url(url: str) -> bool:
    """
    Validate URL format
    
    Args:
        url: URL to validate
        
    Returns:
        True if URL is valid
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc]) and result.scheme in ['http', 'https']
    except Exception:
        return False


def format_utm_report(utm_stats: Dict[str, Any]) -> str:
    """
    Format UTM statistics for reporting
    
    Args:
        utm_stats: Dictionary with UTM statistics
        
    Returns:
        Formatted report string
    """
    try:
        report = "📊 **UTM Трекинг - Отчет**\n\n"
        
        if 'total_clicks' in utm_stats:
            report += f"🔗 Всего кликов: {utm_stats['total_clicks']}\n"
        
        if 'unique_users' in utm_stats:
            report += f"👥 Уникальных пользователей: {utm_stats['unique_users']}\n"
        
        if 'by_source' in utm_stats:
            report += "\n**По источникам:**\n"
            for source, count in utm_stats['by_source'].items():
                report += f"• {source}: {count} кликов\n"
        
        if 'by_campaign' in utm_stats:
            report += "\n**По кампаниям:**\n"
            for campaign, count in utm_stats['by_campaign'].items():
                report += f"• {campaign}: {count} кликов\n"
        
        if 'top_urls' in utm_stats:
            report += "\n**Популярные ссылки:**\n"
            for url, count in utm_stats['top_urls'].items():
                # Shorten URL for display
                display_url = url[:50] + "..." if len(url) > 50 else url
                report += f"• {display_url}: {count} кликов\n"
        
        if 'conversion_rate' in utm_stats:
            report += f"\n📈 Конверсия: {utm_stats['conversion_rate']:.1f}%\n"
        
        return report
        
    except Exception as e:
        logger.error(f"Error formatting UTM report: {e}")
        return "Ошибка при формировании отчета"


def create_tracking_link(
    base_url: str, 
    user_id: int, 
    message_type: str,
    bot_id: Optional[int] = None,
    button_text: Optional[str] = None
) -> str:
    """
    Create tracking link with specific parameters
    
    Args:
        base_url: Base URL to track
        user_id: User ID
        message_type: Type of message containing the link
        bot_id: Bot ID
        button_text: Text of button (if applicable)
        
    Returns:
        Tracking URL
    """
    try:
        campaign = generate_campaign_name(message_type, bot_id)
        source = f'bot_{bot_id}' if bot_id else 'bot'
        medium = 'telegram'
        content = button_text.lower().replace(' ', '_') if button_text else None
        
        return add_utm_to_url(
            base_url, 
            source=source, 
            campaign=campaign, 
            medium=medium,
            content=content,
            user_id=user_id
        )
        
    except Exception as e:
        logger.error(f"Error creating tracking link: {e}")
        return base_url


def parse_utm_analytics(utm_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Parse UTM analytics data into useful statistics
    
    Args:
        utm_data: List of UTM tracking records
        
    Returns:
        Aggregated analytics
    """
    try:
        analytics = {
            'total_clicks': len(utm_data),
            'unique_users': len(set(record.get('user_id') for record in utm_data if record.get('user_id'))),
            'by_source': {},
            'by_campaign': {},
            'by_medium': {},
            'by_content': {},
            'top_urls': {},
            'hourly_distribution': {},
            'daily_distribution': {}
        }
        
        for record in utm_data:
            # Count by source
            source = record.get('utm_source', 'unknown')
            analytics['by_source'][source] = analytics['by_source'].get(source, 0) + 1
            
            # Count by campaign
            campaign = record.get('utm_campaign', 'unknown')
            analytics['by_campaign'][campaign] = analytics['by_campaign'].get(campaign, 0) + 1
            
            # Count by medium
            medium = record.get('utm_medium', 'unknown')
            analytics['by_medium'][medium] = analytics['by_medium'].get(medium, 0) + 1
            
            # Count by content
            content = record.get('utm_content')
            if content:
                analytics['by_content'][content] = analytics['by_content'].get(content, 0) + 1
            
            # Count by URL
            url = record.get('original_url', 'unknown')
            analytics['top_urls'][url] = analytics['top_urls'].get(url, 0) + 1
            
            # Time distribution
            created_at = record.get('created_at')
            if created_at:
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                
                hour = created_at.hour
                analytics['hourly_distribution'][hour] = analytics['hourly_distribution'].get(hour, 0) + 1
                
                day = created_at.strftime('%Y-%m-%d')
                analytics['daily_distribution'][day] = analytics['daily_distribution'].get(day, 0) + 1
        
        # Sort by count (descending)
        for key in ['by_source', 'by_campaign', 'by_medium', 'by_content', 'top_urls']:
            analytics[key] = dict(sorted(analytics[key].items(), key=lambda x: x[1], reverse=True))
        
        return analytics
        
    except Exception as e:
        logger.error(f"Error parsing UTM analytics: {e}")
        return {
            'total_clicks': 0,
            'unique_users': 0,
            'error': str(e)
        }
