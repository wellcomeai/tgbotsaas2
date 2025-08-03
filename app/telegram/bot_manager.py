"""
Bot Manager - единый менеджер всех ботов
🔥 КЛЮЧЕВОЙ КОМПОНЕНТ: все боты работают в одном Application
"""

import asyncio
import logging
from typing import Dict, List, Optional, Set, Any
from datetime import datetime
from telegram import Bot, Update
from telegram.ext import Application, ApplicationBuilder, ChatJoinRequestHandler, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.models.bot import Bot as BotModel, BotStatus
from app.services.bot_service import BotService
from app.services.user_service import UserService
from app.services.message_service import MessageService
from app.telegram.handlers.master_bot import MasterBotHandler
from app.telegram.handlers.user_bot import UserBotHandler
from app.telegram.middleware import BotMiddleware
from app.utils.telegram import verify_bot_token
from app.core.exceptions import TelegramAPIError, ConfigurationError

logger = logging.getLogger(__name__)


class BotInstance:
    """Экземпляр пользовательского бота"""
    
    def __init__(self, bot_model: BotModel):
        self.bot_id = bot_model.id
        self.bot_token = bot_model.bot_token
        self.bot_username = bot_model.bot_username
        self.owner_id = bot_model.owner_id
        self.channel_id = bot_model.channel_id
        self.config = bot_model.config or {}
        self.status = bot_model.status
        self.created_at = datetime.utcnow()
        self.last_ping = datetime.utcnow()
        
        # Telegram Bot instance
        self.telegram_bot = Bot(token=bot_model.bot_token)
        
        # Handler instance
        self.handler = UserBotHandler(bot_model)
    
    def __repr__(self):
        return f"<BotInstance(id={self.bot_id}, username={self.bot_username})>"


class UnifiedBotManager:
    """
    Единый менеджер всех ботов
    Все боты работают в одном Application для максимальной эффективности
    """
    
    def __init__(self):
        self.application: Optional[Application] = None
        self.master_bot_token = settings.MASTER_BOT_TOKEN
        self.master_handler: Optional[MasterBotHandler] = None
        
        # Active bot instances
        self.bot_instances: Dict[int, BotInstance] = {}  # bot_id -> BotInstance
        self.token_to_bot_id: Dict[str, int] = {}  # token -> bot_id
        self.username_to_bot_id: Dict[str, int] = {}  # username -> bot_id
        
        # Services
        self.bot_service = BotService()
        self.user_service = UserService()
        self.message_service = MessageService()
        
        # State
        self.is_running = False
        self.initialization_lock = asyncio.Lock()
        
        logger.info("🤖 UnifiedBotManager initialized")
    
    async def initialize(self):
        """Initialize the bot manager"""
        async with self.initialization_lock:
            if self.application:
                logger.warning("Bot manager already initialized")
                return
            
            try:
                logger.info("🔄 Initializing UnifiedBotManager...")
                
                # Verify master bot token
                if not self.master_bot_token:
                    raise ConfigurationError("MASTER_BOT_TOKEN not configured")
                
                bot_info = await verify_bot_token(self.master_bot_token)
                if not bot_info:
                    raise ConfigurationError("Invalid MASTER_BOT_TOKEN")
                
                logger.info(f"✅ Master bot verified: @{bot_info['username']}")
                
                # Create Application with master bot token
                self.application = ApplicationBuilder().token(self.master_bot_token).build()
                
                # Add middleware
                middleware = BotMiddleware(self)
                self.application.add_handler(middleware, group=-1)
                
                # Initialize master bot handler
                self.master_handler = MasterBotHandler(self)
                await self._setup_master_bot_handlers()
                
                # Load and register existing user bots
                await self._load_existing_bots()
                
                logger.info("✅ UnifiedBotManager initialized successfully")
                
            except Exception as e:
                logger.error(f"❌ Failed to initialize UnifiedBotManager: {e}")
                raise
    
    async def start(self):
        """Start the bot manager"""
        if not self.application:
            await self.initialize()
        
        try:
            logger.info("🚀 Starting UnifiedBotManager...")
            
            # Initialize application
            await self.application.initialize()
            await self.application.start()
            
            # Start polling
            await self.application.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES
            )
            
            self.is_running = True
            
            # Start background tasks
            asyncio.create_task(self._health_check_loop())
            asyncio.create_task(self._stats_update_loop())
            
            logger.info("🎉 UnifiedBotManager started successfully")
            logger.info(f"📊 Managing {len(self.bot_instances)} user bots")
            
        except Exception as e:
            logger.error(f"❌ Failed to start UnifiedBotManager: {e}")
            raise
    
    async def stop(self):
        """Stop the bot manager"""
        try:
            logger.info("🛑 Stopping UnifiedBotManager...")
            
            self.is_running = False
            
            if self.application:
                # Stop polling
                if self.application.updater.running:
                    await self.application.updater.stop()
                
                # Stop application
                await self.application.stop()
                await self.application.shutdown()
            
            # Update all bots status to stopped
            async for db in get_db():
                for bot_id in self.bot_instances:
                    await self.bot_service.update_bot_status(
                        db, bot_id, BotStatus.STOPPED
                    )
                break
            
            logger.info("✅ UnifiedBotManager stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping UnifiedBotManager: {e}")
    
    async def add_bot(self, bot_model: BotModel) -> bool:
        """
        Добавить пользовательского бота в систему
        
        Args:
            bot_model: Модель бота из базы данных
            
        Returns:
            True если бот успешно добавлен
        """
        try:
            logger.info(f"🔄 Adding bot {bot_model.id} (@{bot_model.bot_username})")
            
            # Check if bot already exists
            if bot_model.id in self.bot_instances:
                logger.warning(f"Bot {bot_model.id} already exists")
                return True
            
            # Verify bot token
            bot_info = await verify_bot_token(bot_model.bot_token)
            if not bot_info:
                logger.error(f"❌ Invalid token for bot {bot_model.id}")
                return False
            
            # Create bot instance
            bot_instance = BotInstance(bot_model)
            
            # Register handlers for this bot
            await self._register_bot_handlers(bot_instance)
            
            # Add to tracking
            self.bot_instances[bot_model.id] = bot_instance
            self.token_to_bot_id[bot_model.bot_token] = bot_model.id
            self.username_to_bot_id[bot_model.bot_username.lower()] = bot_model.id
            
            # Update bot status
            async for db in get_db():
                await self.bot_service.update_bot_status(
                    db, bot_model.id, BotStatus.ACTIVE
                )
                break
            
            logger.info(f"✅ Bot {bot_model.id} (@{bot_model.bot_username}) added successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error adding bot {bot_model.id}: {e}")
            return False
    
    async def remove_bot(self, bot_id: int) -> bool:
        """
        Удалить пользовательского бота из системы
        
        Args:
            bot_id: ID бота
            
        Returns:
            True если бот успешно удален
        """
        try:
            logger.info(f"🔄 Removing bot {bot_id}")
            
            if bot_id not in self.bot_instances:
                logger.warning(f"Bot {bot_id} not found")
                return True
            
            bot_instance = self.bot_instances[bot_id]
            
            # Unregister handlers
            await self._unregister_bot_handlers(bot_instance)
            
            # Remove from tracking
            del self.bot_instances[bot_id]
            if bot_instance.bot_token in self.token_to_bot_id:
                del self.token_to_bot_id[bot_instance.bot_token]
            if bot_instance.bot_username.lower() in self.username_to_bot_id:
                del self.username_to_bot_id[bot_instance.bot_username.lower()]
            
            # Update bot status
            async for db in get_db():
                await self.bot_service.update_bot_status(
                    db, bot_id, BotStatus.STOPPED
                )
                break
            
            logger.info(f"✅ Bot {bot_id} removed successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error removing bot {bot_id}: {e}")
            return False
    
    async def restart_bot(self, bot_id: int) -> bool:
        """
        Перезапустить пользовательского бота
        
        Args:
            bot_id: ID бота
            
        Returns:
            True если бот успешно перезапущен
        """
        try:
            logger.info(f"🔄 Restarting bot {bot_id}")
            
            # Remove existing bot
            await self.remove_bot(bot_id)
            
            # Wait a moment
            await asyncio.sleep(1)
            
            # Get updated bot model from database
            async for db in get_db():
                bot_model = await self.bot_service.get_bot(db, bot_id)
                break
            
            # Add bot back
            success = await self.add_bot(bot_model)
            
            if success:
                logger.info(f"✅ Bot {bot_id} restarted successfully")
            else:
                logger.error(f"❌ Failed to restart bot {bot_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error restarting bot {bot_id}: {e}")
            return False
    
    def get_bot_instance(self, bot_id: int) -> Optional[BotInstance]:
        """Получить экземпляр бота по ID"""
        return self.bot_instances.get(bot_id)
    
    def get_bot_by_username(self, username: str) -> Optional[BotInstance]:
        """Получить экземпляр бота по username"""
        username = username.lower().replace('@', '')
        bot_id = self.username_to_bot_id.get(username)
        return self.bot_instances.get(bot_id) if bot_id else None
    
    def get_running_bots(self) -> List[int]:
        """Получить список ID запущенных ботов"""
        return list(self.bot_instances.keys())
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику менеджера"""
        return {
            "total_bots": len(self.bot_instances),
            "running_bots": len([b for b in self.bot_instances.values() if b.status == BotStatus.ACTIVE.value]),
            "is_running": self.is_running,
            "uptime": (datetime.utcnow() - min(b.created_at for b in self.bot_instances.values())).total_seconds() if self.bot_instances else 0,
            "master_bot_running": self.application is not None and self.application.running
        }
    
    async def _setup_master_bot_handlers(self):
        """Настройка обработчиков для главного бота"""
        try:
            logger.info("🔄 Setting up master bot handlers...")
            
            # Command handlers
            self.application.add_handler(CommandHandler("start", self.master_handler.handle_start))
            self.application.add_handler(CommandHandler("help", self.master_handler.handle_help))
            self.application.add_handler(CommandHandler("stats", self.master_handler.handle_stats))
            
            # Callback query handler
            self.application.add_handler(CallbackQueryHandler(
                self.master_handler.handle_callback_query,
                pattern="^master_"
            ))
            
            # Message handler (for text input)
            self.application.add_handler(MessageHandler(
                filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
                self.master_handler.handle_message
            ))
            
            logger.info("✅ Master bot handlers set up")
            
        except Exception as e:
            logger.error(f"❌ Error setting up master bot handlers: {e}")
            raise
    
    async def _register_bot_handlers(self, bot_instance: BotInstance):
        """Регистрация обработчиков для пользовательского бота"""
        try:
            logger.info(f"🔄 Registering handlers for bot {bot_instance.bot_id}")
            
            # Create filters for this specific bot
            bot_filter = filters.User(user_id=lambda u: self._is_bot_update(u, bot_instance))
            
            # Join request handler
            self.application.add_handler(ChatJoinRequestHandler(
                bot_instance.handler.handle_join_request,
                chat_id=bot_instance.channel_id
            ))
            
            # Command handlers for bot admin
            admin_filter = filters.User(user_id=bot_instance.owner_id) & filters.ChatType.PRIVATE
            
            self.application.add_handler(CommandHandler(
                "start",
                bot_instance.handler.handle_admin_start,
                filters=admin_filter
            ))
            
            self.application.add_handler(CommandHandler(
                "admin",
                bot_instance.handler.handle_admin_panel,
                filters=admin_filter
            ))
            
            # Callback query handler for this bot's admin
            self.application.add_handler(CallbackQueryHandler(
                bot_instance.handler.handle_callback_query,
                pattern=f"^bot_{bot_instance.bot_id}_"
            ))
            
            # Message handlers
            self.application.add_handler(MessageHandler(
                filters.ChatType.PRIVATE & filters.User(user_id=bot_instance.owner_id),
                bot_instance.handler.handle_private_message
            ))
            
            # Channel message handler
            if bot_instance.channel_id:
                self.application.add_handler(MessageHandler(
                    filters.Chat(chat_id=bot_instance.channel_id),
                    bot_instance.handler.handle_channel_message
                ))
            
            logger.info(f"✅ Handlers registered for bot {bot_instance.bot_id}")
            
        except Exception as e:
            logger.error(f"❌ Error registering handlers for bot {bot_instance.bot_id}: {e}")
            raise
    
    async def _unregister_bot_handlers(self, bot_instance: BotInstance):
        """Отмена регистрации обработчиков для пользовательского бота"""
        try:
            logger.info(f"🔄 Unregistering handlers for bot {bot_instance.bot_id}")
            
            # Remove handlers from application
            # Note: telegram-python-bot doesn't have direct remove_handler method
            # So we'll mark the handlers as inactive in the bot instance
            bot_instance.handler.active = False
            
            logger.info(f"✅ Handlers unregistered for bot {bot_instance.bot_id}")
            
        except Exception as e:
            logger.error(f"❌ Error unregistering handlers for bot {bot_instance.bot_id}: {e}")
    
    async def _load_existing_bots(self):
        """Загрузка существующих ботов из базы данных"""
        try:
            logger.info("🔄 Loading existing bots from database...")
            
            async for db in get_db():
                # Get all active bots
                active_bots = await self.bot_service.get_active_bots(db)
                
                logger.info(f"📋 Found {len(active_bots)} active bots in database")
                
                loaded_count = 0
                failed_count = 0
                
                for bot_model in active_bots:
                    try:
                        success = await self.add_bot(bot_model)
                        if success:
                            loaded_count += 1
                        else:
                            failed_count += 1
                            # Update bot status to error
                            await self.bot_service.update_bot_status(
                                db, bot_model.id, BotStatus.ERROR, 
                                "Failed to load during startup"
                            )
                    except Exception as e:
                        logger.error(f"❌ Error loading bot {bot_model.id}: {e}")
                        failed_count += 1
                
                logger.info(f"✅ Loaded {loaded_count} bots, {failed_count} failed")
                break
                
        except Exception as e:
            logger.error(f"❌ Error loading existing bots: {e}")
    
    def _is_bot_update(self, user, bot_instance: BotInstance) -> bool:
        """Check if update is for specific bot"""
        # This is a placeholder - actual implementation would need to check
        # the update context to determine which bot it's for
        return True
    
    async def _health_check_loop(self):
        """Background task for health checking bots"""
        while self.is_running:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                
                logger.debug("🏥 Running health check for all bots")
                
                unhealthy_bots = []
                
                for bot_id, bot_instance in self.bot_instances.items():
                    try:
                        # Simple health check - verify bot token still works
                        bot_info = await verify_bot_token(bot_instance.bot_token)
                        if not bot_info:
                            unhealthy_bots.append(bot_id)
                            logger.warning(f"⚠️ Bot {bot_id} failed health check")
                        else:
                            # Update last ping
                            bot_instance.last_ping = datetime.utcnow()
                            
                    except Exception as e:
                        logger.error(f"❌ Health check error for bot {bot_id}: {e}")
                        unhealthy_bots.append(bot_id)
                
                # Update database with health status
                if unhealthy_bots:
                    async for db in get_db():
                        for bot_id in unhealthy_bots:
                            await self.bot_service.update_bot_status(
                                db, bot_id, BotStatus.ERROR, 
                                "Failed health check"
                            )
                        break
                
                logger.debug(f"🏥 Health check complete: {len(unhealthy_bots)} unhealthy bots")
                
            except Exception as e:
                logger.error(f"❌ Error in health check loop: {e}")
                await asyncio.sleep(60)
    
    async def _stats_update_loop(self):
        """Background task for updating statistics"""
        while self.is_running:
            try:
                await asyncio.sleep(3600)  # Update every hour
                
                logger.debug("📊 Updating bot statistics")
                
                async for db in get_db():
                    for bot_id, bot_instance in self.bot_instances.items():
                        try:
                            # Update last ping in database
                            await self.bot_service.update_bot_status(
                                db, bot_id, BotStatus.ACTIVE
                            )
                            
                        except Exception as e:
                            logger.error(f"❌ Error updating stats for bot {bot_id}: {e}")
                    break
                
                logger.debug("📊 Statistics update complete")
                
            except Exception as e:
                logger.error(f"❌ Error in stats update loop: {e}")
                await asyncio.sleep(300)


# Global instance
bot_manager = UnifiedBotManager()
