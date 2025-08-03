"""
Telegram Middleware - маршрутизация между ботами
"""

import logging
import time
from typing import Optional
from telegram import Update
from telegram.ext import BaseHandler, ContextTypes

logger = logging.getLogger(__name__)


class BotMiddleware(BaseHandler):
    """
    Middleware для маршрутизации сообщений между разными ботами
    Определяет, какой бот должен обработать конкретное сообщение
    """
    
    def __init__(self, bot_manager):
        super().__init__(self._handle_update)
        self.bot_manager = bot_manager
    
    def check_update(self, update: Update) -> bool:
        """Check if this middleware should handle the update"""
        # This middleware handles all updates for routing
        return True
    
    async def _handle_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Route update to appropriate bot handler"""
        try:
            # Determine which bot should handle this update
            target_bot_id = await self._determine_target_bot(update, context)
            
            if target_bot_id:
                # Add routing info to context
                context.user_data = context.user_data or {}
                context.user_data['target_bot_id'] = target_bot_id
                context.user_data['routed_by_middleware'] = True
                
                logger.debug(f"Routed update to bot {target_bot_id}")
            else:
                # Route to master bot (default)
                context.user_data = context.user_data or {}
                context.user_data['target_bot_id'] = 'master'
                context.user_data['routed_by_middleware'] = True
                
                logger.debug("Routed update to master bot")
        
        except Exception as e:
            logger.error(f"Error in middleware routing: {e}")
            # Don't block the update, let it continue
    
    async def _determine_target_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[int]:
        """
        Determine which bot should handle this update
        
        Returns:
            bot_id if should be handled by user bot, None for master bot
        """
        try:
            # Check if it's a callback query with bot-specific data
            if update.callback_query and update.callback_query.data:
                data = update.callback_query.data
                
                # Check for bot-specific callback data: "bot_123_action"
                if data.startswith("bot_"):
                    parts = data.split("_")
                    if len(parts) >= 2:
                        try:
                            bot_id = int(parts[1])
                            # Verify bot exists in manager
                            if self.bot_manager.get_bot_instance(bot_id):
                                return bot_id
                        except ValueError:
                            pass
            
            # Check if it's a private message to a user bot owner
            if update.effective_chat and update.effective_chat.type == 'private':
                user_id = update.effective_user.id
                
                # Check if user owns any bots
                for bot_instance in self.bot_manager.bot_instances.values():
                    if bot_instance.owner_id == user_id:
                        # If user has only one bot, route to it
                        user_bots = [b for b in self.bot_manager.bot_instances.values() 
                                   if b.owner_id == user_id]
                        if len(user_bots) == 1:
                            return user_bots[0].bot_id
                        
                        # If multiple bots, check for context clues
                        if update.message and update.message.text:
                            text = update.message.text.lower()
                            
                            # Look for bot mentions in message
                            for bot_instance in user_bots:
                                if bot_instance.bot_username.lower() in text:
                                    return bot_instance.bot_id
                        
                        # Default to master bot for multi-bot users
                        return None
            
            # Check if it's a channel message
            if update.effective_chat and update.effective_chat.type in ['channel', 'supergroup']:
                chat_id = update.effective_chat.id
                
                # Find bot that manages this channel
                for bot_instance in self.bot_manager.bot_instances.values():
                    if bot_instance.channel_id == chat_id:
                        return bot_instance.bot_id
            
            # Check if it's a join request
            if update.chat_join_request:
                chat_id = update.chat_join_request.chat.id
                
                # Find bot that manages this channel
                for bot_instance in self.bot_manager.bot_instances.values():
                    if bot_instance.channel_id == chat_id:
                        return bot_instance.bot_id
            
            # Check if message mentions a specific bot
            if update.message and update.message.text:
                text = update.message.text.lower()
                
                # Look for @bot_username mentions
                for bot_instance in self.bot_manager.bot_instances.values():
                    if f"@{bot_instance.bot_username.lower()}" in text:
                        return bot_instance.bot_id
            
            # Default to master bot
            return None
            
        except Exception as e:
            logger.error(f"Error determining target bot: {e}")
            return None
    
    def _extract_chat_context(self, update: Update) -> dict:
        """Extract context information from update"""
        context = {}
        
        if update.effective_chat:
            context['chat_id'] = update.effective_chat.id
            context['chat_type'] = update.effective_chat.type
            context['chat_title'] = getattr(update.effective_chat, 'title', None)
            context['chat_username'] = getattr(update.effective_chat, 'username', None)
        
        if update.effective_user:
            context['user_id'] = update.effective_user.id
            context['username'] = update.effective_user.username
            context['first_name'] = update.effective_user.first_name
        
        if update.message:
            context['message_type'] = 'message'
            context['has_text'] = bool(update.message.text)
            context['has_photo'] = bool(update.message.photo)
            context['has_document'] = bool(update.message.document)
        elif update.callback_query:
            context['message_type'] = 'callback_query'
            context['callback_data'] = update.callback_query.data
        elif update.chat_join_request:
            context['message_type'] = 'join_request'
        
        return context
    
    def get_routing_stats(self) -> dict:
        """Get routing statistics"""
        # This would track routing statistics in a real implementation
        return {
            'total_routes': 0,
            'master_bot_routes': 0,
            'user_bot_routes': 0,
            'routing_errors': 0
        }


class RateLimitMiddleware(BaseHandler):
    """Rate limiting middleware"""
    
    def __init__(self, max_requests_per_minute: int = 30):
        super().__init__(self._handle_rate_limit)
        self.max_requests = max_requests_per_minute
        self.user_requests = {}  # user_id -> [(timestamp, count)]
    
    def check_update(self, update: Update) -> bool:
        """Check if this middleware should handle the update"""
        return update.effective_user is not None
    
    async def _handle_rate_limit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check and enforce rate limits"""
        try:
            user_id = update.effective_user.id
            current_time = time.time()
            
            # Clean old requests (older than 1 minute)
            if user_id in self.user_requests:
                self.user_requests[user_id] = [
                    (timestamp, count) for timestamp, count in self.user_requests[user_id]
                    if current_time - timestamp < 60
                ]
            
            # Count current requests
            if user_id not in self.user_requests:
                self.user_requests[user_id] = []
            
            current_requests = sum(count for _, count in self.user_requests[user_id])
            
            if current_requests >= self.max_requests:
                # Rate limit exceeded
                logger.warning(f"Rate limit exceeded for user {user_id}")
                
                if update.message:
                    await update.message.reply_text(
                        "⚠️ Слишком много запросов. Попробуйте через минуту."
                    )
                elif update.callback_query:
                    await update.callback_query.answer(
                        "⚠️ Слишком много запросов. Попробуйте через минуту."
                    )
                
                # Block the update
                return False
            
            # Add current request
            self.user_requests[user_id].append((current_time, 1))
            
        except Exception as e:
            logger.error(f"Error in rate limit middleware: {e}")
            # Don't block on errors
        
        return True


class LoggingMiddleware(BaseHandler):
    """Logging middleware for debugging"""
    
    def __init__(self):
        super().__init__(self._handle_logging)
    
    def check_update(self, update: Update) -> bool:
        """Check if this middleware should handle the update"""
        return True
    
    async def _handle_logging(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Log update information"""
        try:
            user_id = getattr(update.effective_user, 'id', 'unknown')
            chat_id = getattr(update.effective_chat, 'id', 'unknown')
            
            if update.message:
                message_type = "message"
                content = update.message.text[:50] if update.message.text else "non-text"
            elif update.callback_query:
                message_type = "callback"
                content = update.callback_query.data
            elif update.chat_join_request:
                message_type = "join_request"
                content = "join_request"
            else:
                message_type = "other"
                content = str(type(update))
            
            logger.debug(
                f"Update: {message_type} from user {user_id} in chat {chat_id}: {content}"
            )
            
        except Exception as e:
            logger.error(f"Error in logging middleware: {e}")


class SecurityMiddleware(BaseHandler):
    """Security middleware for basic protection"""
    
    def __init__(self, blocked_users: set = None):
        super().__init__(self._handle_security)
        self.blocked_users = blocked_users or set()
        self.suspicious_patterns = [
            r'(?i)(hack|crack|exploit|spam|flood)',
            r'(?i)(bot.*token|api.*key)',
            r'(?i)(admin.*password|secret.*key)'
        ]
    
    def check_update(self, update: Update) -> bool:
        """Check if this middleware should handle the update"""
        return True
    
    async def _handle_security(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check for security threats"""
        try:
            # Check blocked users
            if update.effective_user and update.effective_user.id in self.blocked_users:
                logger.warning(f"Blocked user {update.effective_user.id} attempted access")
                return False
            
            # Check for suspicious content
            if update.message and update.message.text:
                import re
                text = update.message.text
                
                for pattern in self.suspicious_patterns:
                    if re.search(pattern, text):
                        logger.warning(f"Suspicious content from user {update.effective_user.id}: {text[:100]}")
                        
                        if update.message:
                            await update.message.reply_text(
                                "⚠️ Сообщение заблокировано системой безопасности."
                            )
                        
                        return False
            
            # Check message frequency (simple flood protection)
            if update.effective_user:
                user_id = update.effective_user.id
                current_time = time.time()
                
                # Simple flood detection - more than 10 messages in 10 seconds
                if not hasattr(self, '_message_times'):
                    self._message_times = {}
                
                if user_id not in self._message_times:
                    self._message_times[user_id] = []
                
                # Clean old timestamps
                self._message_times[user_id] = [
                    t for t in self._message_times[user_id] 
                    if current_time - t < 10
                ]
                
                if len(self._message_times[user_id]) > 10:
                    logger.warning(f"Flood detected from user {user_id}")
                    
                    if update.message:
                        await update.message.reply_text(
                            "⚠️ Обнаружен флуд. Снизьте частоту сообщений."
                        )
                    
                    return False
                
                self._message_times[user_id].append(current_time)
            
        except Exception as e:
            logger.error(f"Error in security middleware: {e}")
            # Don't block on errors
        
        return True
