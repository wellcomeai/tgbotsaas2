"""
User Bot Handler - обработчики для пользовательских ботов
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatJoinRequest
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from app.core.database import get_db
from app.models.bot import Bot as BotModel
from app.services.bot_service import BotService
from app.services.message_service import MessageService
from app.services.analytics_service import AnalyticsService
from app.schemas.message import MessageCreate, BroadcastCreate, MessageType
from app.utils.telegram import send_telegram_message, approve_chat_join_request
from app.utils.utm import add_utm_to_text, generate_campaign_name

logger = logging.getLogger(__name__)


class UserBotHandler:
    """Handler for user bot interactions"""
    
    def __init__(self, bot_model: BotModel):
        self.bot_model = bot_model
        self.bot_id = bot_model.id
        self.bot_token = bot_model.bot_token
        self.bot_username = bot_model.bot_username
        self.owner_id = bot_model.owner_id
        self.channel_id = bot_model.channel_id
        self.config = bot_model.config or {}
        
        # Services
        self.bot_service = BotService()
        self.message_service = MessageService()
        self.analytics_service = AnalyticsService()
        
        # State tracking
        self.active = True
        self.user_states: Dict[int, Dict[str, Any]] = {}
        
        logger.info(f"UserBotHandler initialized for bot {self.bot_id} (@{self.bot_username})")
    
    async def handle_join_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle channel join requests"""
        try:
            join_request: ChatJoinRequest = update.chat_join_request
            user = join_request.from_user
            chat = join_request.chat
            
            logger.info(f"Join request from user {user.id} to channel {chat.id} for bot {self.bot_id}")
            
            # Add subscriber to database
            async for db in get_db():
                await self.bot_service.add_subscriber(
                    db,
                    bot_id=self.bot_id,
                    user_id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    utm_source='channel_join'
                )
                break
            
            # Check auto-approve setting
            auto_approve = self.bot_model.auto_approve_requests
            
            if auto_approve:
                # Auto-approve the request
                try:
                    success = await approve_chat_join_request(
                        self.bot_token,
                        chat.id,
                        user.id
                    )
                    
                    if success:
                        # Send welcome message
                        await self._send_welcome_message(user.id)
                        
                        # Log approval
                        async for db in get_db():
                            await self.message_service.create_message(
                                db,
                                bot_id=self.bot_id,
                                message_data=MessageCreate(
                                    recipient_id=user.id,
                                    content="User auto-approved to channel",
                                    message_type=MessageType.AUTO_APPROVAL,
                                    utm_source='auto_approve'
                                )
                            )
                            break
                        
                        # Notify admin
                        await self._notify_admin_join(user, approved=True)
                        
                        logger.info(f"Auto-approved join request from {user.id}")
                    else:
                        logger.error(f"Failed to approve join request from {user.id}")
                        await self._notify_admin_error(user, "Failed to approve join request")
                        
                except Exception as e:
                    logger.error(f"Error approving join request: {e}")
                    await self._notify_admin_error(user, str(e))
            else:
                # Manual approval needed
                await self._notify_admin_join(user, approved=False)
                logger.info(f"Join request from {user.id} pending manual approval")
                
        except Exception as e:
            logger.error(f"Error handling join request: {e}")
    
    async def handle_admin_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command from bot owner"""
        try:
            # Add user to subscribers if not already
            async for db in get_db():
                await self.bot_service.add_subscriber(
                    db,
                    bot_id=self.bot_id,
                    user_id=update.effective_user.id,
                    username=update.effective_user.username,
                    first_name=update.effective_user.first_name,
                    last_name=update.effective_user.last_name,
                    utm_source='bot_start'
                )
                break
            
            # Show admin dashboard
            await self._show_admin_dashboard(update, context)
            
        except Exception as e:
            logger.error(f"Error in handle_admin_start: {e}")
            await update.message.reply_text("❌ Произошла ошибка")
    
    async def handle_admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /admin command"""
        await self._show_admin_dashboard(update, context)
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries for this bot"""
        if not self.active:
            return
        
        query = update.callback_query
        data = query.data
        
        await query.answer()
        
        try:
            # Parse callback data
            parts = data.split('_')
            if len(parts) < 3 or parts[0] != 'bot' or int(parts[1]) != self.bot_id:
                return  # Not for this bot
            
            action = '_'.join(parts[2:])
            
            if action == "dashboard":
                await self._show_admin_dashboard(update, context)
            
            elif action == "stats":
                await self._show_stats(update, context)
            
            elif action == "broadcast":
                await self._show_broadcast_menu(update, context)
            
            elif action == "users":
                await self._show_users_menu(update, context)
            
            elif action == "settings":
                await self._show_settings_menu(update, context)
            
            elif action.startswith("broadcast_create"):
                await self._initiate_broadcast_creation(update, context)
            
            elif action.startswith("settings_"):
                setting_name = action.split('_', 1)[1]
                await self._toggle_setting(update, context, setting_name)
            
            else:
                await query.answer("🚧 Функция в разработке")
                
        except Exception as e:
            logger.error(f"Error in handle_callback_query: {e}")
            await query.answer("❌ Произошла ошибка")
    
    async def handle_private_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle private messages from bot owner"""
        user_id = update.effective_user.id
        text = update.message.text
        
        # Check if user is in broadcast creation flow
        if user_id in self.user_states:
            state = self.user_states[user_id]
            
            if state.get('waiting_for') == 'broadcast_content':
                await self._process_broadcast_content(update, context, text)
                return
        
        # Default response
        await update.message.reply_text(
            "👋 Привет! Используй /admin для открытия панели управления."
        )
    
    async def handle_channel_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle messages in the channel"""
        try:
            message = update.message
            if not message or not message.from_user:
                return
            
            # Skip bot messages
            if message.from_user.is_bot:
                return
            
            # Update user activity
            async for db in get_db():
                await self.bot_service.add_subscriber(
                    db,
                    bot_id=self.bot_id,
                    user_id=message.from_user.id,
                    username=message.from_user.username,
                    first_name=message.from_user.first_name,
                    last_name=message.from_user.last_name,
                    utm_source='channel_activity'
                )
                break
            
            # Process URLs for tracking if UTM enabled
            if self.bot_model.utm_tracking_enabled and message.text:
                await self._process_message_links(message)
            
        except Exception as e:
            logger.error(f"Error handling channel message: {e}")
    
    async def _show_admin_dashboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show admin dashboard"""
        try:
            # Get bot statistics
            async for db in get_db():
                stats = await self._get_bot_stats(db)
                break
            
            message = f"""
🔧 **Админ-панель @{self.bot_username}**

📊 **Быстрая статистика:**
- Подписчиков: {stats['total_subscribers']}
- Активных (7 дней): {stats['active_users']}
- Сообщений отправлено: {stats['messages_sent']}
- Переходов по ссылкам: {stats['link_clicks']}

⚙️ **Управление:**
Выберите действие из меню ниже
"""
            
            keyboard = [
                [
                    InlineKeyboardButton("📊 Статистика", callback_data=f"bot_{self.bot_id}_stats"),
                    InlineKeyboardButton("✉️ Рассылка", callback_data=f"bot_{self.bot_id}_broadcast")
                ],
                [
                    InlineKeyboardButton("👥 Пользователи", callback_data=f"bot_{self.bot_id}_users"),
                    InlineKeyboardButton("⚙️ Настройки", callback_data=f"bot_{self.bot_id}_settings")
                ]
            ]
            
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Error showing admin dashboard: {e}")
            fallback_message = "🔧 Админ-панель\n\nВыберите действие:"
            
            keyboard = [
                [InlineKeyboardButton("📊 Статистика", callback_data=f"bot_{self.bot_id}_stats")]
            ]
            
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    fallback_message,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await update.message.reply_text(
                    fallback_message,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
    
    async def _show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show detailed statistics"""
        try:
            async for db in get_db():
                stats = await self._get_detailed_stats(db)
                break
            
            message = f"""
📊 **Подробная статистика @{self.bot_username}**

**👥 Пользователи:**
- Всего подписчиков: {stats['total_subscribers']}
- Активных (7 дней): {stats['active_users']}
- Новых за сегодня: {stats['new_today']}
- Взаимодействовали с ботом: {stats['bot_interactions']}

**📬 Сообщения (30 дней):**
- Всего отправлено: {stats['messages_sent']}
- Рассылок создано: {stats['broadcasts_sent']}
- Успешных доставок: {stats['successful_deliveries']}%

**🔗 Переходы по ссылкам (30 дней):**
- Всего кликов: {stats['total_clicks']}
- Уникальных пользователей: {stats['unique_clickers']}
- CTR: {stats['ctr']:.1f}%

**📈 Эффективность:**
- Вовлеченность: {stats['engagement_rate']:.1f}%
- Конверсия: {stats['conversion_rate']:.1f}%
"""
            
            keyboard = [
                [InlineKeyboardButton("🔄 Обновить", callback_data=f"bot_{self.bot_id}_stats")],
                [InlineKeyboardButton("🔙 Назад", callback_data=f"bot_{self.bot_id}_dashboard")]
            ]
            
            await update.callback_query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error showing stats: {e}")
            await update.callback_query.answer("❌ Ошибка загрузки статистики")
    
    async def _show_broadcast_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show broadcast management menu"""
        message = f"""
✉️ **Управление рассылками @{self.bot_username}**

**Доступные действия:**
- Создать новую рассылку
- Посмотреть историю рассылок
- Настроить автоматические сообщения

**Типы рассылок:**
📢 **Обычная рассылка** - отправка всем подписчикам
👋 **Приветственное сообщение** - для новых участников
📅 **Запланированная** - отправка по расписанию

Что хотите сделать?
"""
        
        keyboard = [
            [InlineKeyboardButton("📢 Создать рассылку", callback_data=f"bot_{self.bot_id}_broadcast_create")],
            [InlineKeyboardButton("📋 История", callback_data=f"bot_{self.bot_id}_broadcast_history")],
            [InlineKeyboardButton("🔙 Назад", callback_data=f"bot_{self.bot_id}_dashboard")]
        ]
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def _show_users_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show users management menu"""
        try:
            async for db in get_db():
                subscribers = await self.bot_service.get_bot_subscribers(db, self.bot_id, limit=5)
                total_count = await self.bot_service.count(db, bot_id=self.bot_id, is_active=True)
                break
            
            message = f"""
👥 **Управление пользователями @{self.bot_username}**

**Всего подписчиков:** {total_count}

**Последние подписчики:**
"""
            
            for subscriber in subscribers[:5]:
                name = subscriber.display_name
                joined = subscriber.joined_at.strftime('%d.%m.%Y')
                message += f"• {name} - {joined}\n"
            
            keyboard = [
                [InlineKeyboardButton("📋 Полный список", callback_data=f"bot_{self.bot_id}_users_list")],
                [InlineKeyboardButton("📊 Статистика активности", callback_data=f"bot_{self.bot_id}_users_activity")],
                [InlineKeyboardButton("🔙 Назад", callback_data=f"bot_{self.bot_id}_dashboard")]
            ]
            
            await update.callback_query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error showing users menu: {e}")
            await update.callback_query.answer("❌ Ошибка загрузки пользователей")
    
    async def _show_settings_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show settings menu"""
        auto_approve = "✅" if self.bot_model.auto_approve_requests else "❌"
        welcome_enabled = "✅" if self.bot_model.welcome_message_enabled else "❌"
        utm_enabled = "✅" if self.bot_model.utm_tracking_enabled else "❌"
        
        message = f"""
⚙️ **Настройки бота @{self.bot_username}**

**Текущие настройки:**
- Автоодобрение заявок: {auto_approve}
- Приветственные сообщения: {welcome_enabled}
- UTM трекинг: {utm_enabled}

**ID канала:** {self.channel_id or 'Не настроен'}
**Владелец:** <a href="tg://user?id={self.owner_id}">Перейти</a>

Что хотите изменить?
"""
        
        keyboard = [
            [InlineKeyboardButton(
                f"{'✅' if self.bot_model.auto_approve_requests else '❌'} Автоодобрение",
                callback_data=f"bot_{self.bot_id}_settings_auto_approve"
            )],
            [InlineKeyboardButton(
                f"{'✅' if self.bot_model.welcome_message_enabled else '❌'} Приветствие",
                callback_data=f"bot_{self.bot_id}_settings_welcome"
            )],
            [InlineKeyboardButton(
                f"{'✅' if self.bot_model.utm_tracking_enabled else '❌'} UTM трекинг",
                callback_data=f"bot_{self.bot_id}_settings_utm"
            )],
            [InlineKeyboardButton("🔙 Назад", callback_data=f"bot_{self.bot_id}_dashboard")]
        ]
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    
    async def _initiate_broadcast_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start broadcast creation process"""
        user_id = update.callback_query.from_user.id
        
        # Set user state
        self.user_states[user_id] = {
            'step': 'waiting_content',
            'waiting_for': 'broadcast_content'
        }
        
        message = """
📢 **Создание рассылки**

Отправьте следующим сообщением текст, который хотите разослать всем подписчикам канала.

**Возможности:**
- Поддержка Markdown разметки
- Автоматический UTM трекинг ссылок  
- Статистика доставки
- Защита от спама

**Пример сообщения:**
🎉 Новая акция в нашем магазине!
Скидка 20% на все товары до конца недели.
Переходите по ссылке: https://example.com

Отправьте сообщение или вернитесь в меню:
"""
        
        keyboard = [
            [InlineKeyboardButton("🔙 Отмена", callback_data=f"bot_{self.bot_id}_broadcast")]
        ]
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def _process_broadcast_content(self, update: Update, context: ContextTypes.DEFAULT_TYPE, content: str):
        """Process broadcast content and send it"""
        user_id = update.effective_user.id
        
        try:
            # Clear user state
            if user_id in self.user_states:
                del self.user_states[user_id]
            
            # Validate content
            if not content.strip():
                await update.message.reply_text("❌ Сообщение не может быть пустым")
                return
            
            if len(content) > 4000:
                await update.message.reply_text("❌ Сообщение слишком длинное (максимум 4000 символов)")
                return
            
            # Show processing message
            processing_msg = await update.message.reply_text("🔄 Отправляю рассылку...")
            
            # Get recipients
            async for db in get_db():
                recipients = await self.bot_service.get_bot_subscribers(db, self.bot_id, active_only=True)
                break
            
            if not recipients:
                await processing_msg.edit_text("❌ Нет активных подписчиков для рассылки")
                return
            
            # Process content with UTM
            processed_content = add_utm_to_text(
                content,
                source=f'bot_{self.bot_id}',
                campaign=generate_campaign_name('broadcast'),
                medium='telegram'
            )
            
            # Send to all recipients
            successful_sends = 0
            failed_sends = 0
            
            for recipient in recipients:
                try:
                    await send_telegram_message(
                        self.bot_token,
                        recipient.user_id,
                        processed_content,
                        parse_mode='Markdown'
                    )
                    successful_sends += 1
                    
                    # Log message
                    async for db in get_db():
                        await self.message_service.create_message(
                            db,
                            bot_id=self.bot_id,
                            message_data=MessageCreate(
                                recipient_id=recipient.user_id,
                                content=content[:200],
                                message_type=MessageType.BROADCAST,
                                utm_source=f'bot_{self.bot_id}',
                                utm_campaign=generate_campaign_name('broadcast')
                            )
                        )
                        break
                    
                except TelegramError as e:
                    failed_sends += 1
                    logger.warning(f"Failed to send to {recipient.user_id}: {e}")
                
                # Small delay to avoid rate limits
                await asyncio.sleep(0.1)
            
            # Update status message
            success_rate = (successful_sends / len(recipients)) * 100
            
            await processing_msg.edit_text(
                f"✅ **Рассылка завершена!**\n\n"
                f"📊 **Результаты:**\n"
                f"• Получателей: {len(recipients)}\n"
                f"• Доставлено: {successful_sends}\n"
                f"• Ошибок: {failed_sends}\n"
                f"• Успешность: {success_rate:.1f}%",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error processing broadcast: {e}")
            await update.message.reply_text("❌ Ошибка при отправке рассылки")
    
    async def _toggle_setting(self, update: Update, context: ContextTypes.DEFAULT_TYPE, setting_name: str):
        """Toggle bot setting"""
        try:
            async for db in get_db():
                if setting_name == "auto_approve":
                    new_value = not self.bot_model.auto_approve_requests
                    self.bot_model.auto_approve_requests = new_value
                    
                elif setting_name == "welcome":
                    new_value = not self.bot_model.welcome_message_enabled
                    self.bot_model.welcome_message_enabled = new_value
                    
                elif setting_name == "utm":
                    new_value = not self.bot_model.utm_tracking_enabled
                    self.bot_model.utm_tracking_enabled = new_value
                
                else:
                    await update.callback_query.answer("❌ Неизвестная настройка")
                    return
                
                # Save to database
                await db.flush()
                await db.refresh(self.bot_model)
                break
            
            # Show updated settings
            await self._show_settings_menu(update, context)
            
            # Notify about change
            setting_names = {
                "auto_approve": "Автоодобрение",
                "welcome": "Приветственные сообщения", 
                "utm": "UTM трекинг"
            }
            
            status = "включено" if new_value else "выключено"
            await update.callback_query.answer(
                f"✅ {setting_names[setting_name]} {status}"
            )
            
        except Exception as e:
            logger.error(f"Error toggling setting {setting_name}: {e}")
            await update.callback_query.answer("❌ Ошибка изменения настройки")
    
    async def _send_welcome_message(self, user_id: int):
        """Send welcome message to new user"""
        try:
            if not self.bot_model.welcome_message_enabled:
                return
            
            welcome_message = (
                self.bot_model.welcome_message or 
                "👋 Добро пожаловать в наш канал! Мы рады видеть тебя здесь."
            )
            
            # Process with UTM if enabled
            if self.bot_model.utm_tracking_enabled:
                welcome_message = add_utm_to_text(
                    welcome_message,
                    source=f'bot_{self.bot_id}',
                    campaign='welcome',
                    medium='telegram'
                )
            
            await send_telegram_message(
                self.bot_token,
                user_id,
                welcome_message,
                parse_mode='Markdown'
            )
            
            # Log welcome message
            async for db in get_db():
                await self.message_service.create_message(
                    db,
                    bot_id=self.bot_id,
                    message_data=MessageCreate(
                        recipient_id=user_id,
                        content=welcome_message[:200],
                        message_type=MessageType.WELCOME,
                        utm_source=f'bot_{self.bot_id}',
                        utm_campaign='welcome'
                    )
                )
                break
            
        except Exception as e:
            logger.error(f"Error sending welcome message: {e}")
    
    async def _notify_admin_join(self, user, approved: bool = False):
        """Notify admin about new join request"""
        try:
            username = f"@{user.username}" if user.username else "Без username"
            name = user.first_name or "Без имени"
            
            if approved:
                message = f"""
✅ **Новый участник одобрен автоматически**

👤 **Пользователь:** {name} ({username})
🆔 **ID:** `{user.id}`
📱 **Бот:** @{self.bot_username}
🕐 **Время:** {datetime.now().strftime('%H:%M %d.%m.%Y')}

Пользователь был автоматически добавлен в канал и получил приветственное сообщение.
"""
            else:
                message = f"""
🔔 **Новая заявка на вступление**

👤 **Пользователь:** {name} ({username})
🆔 **ID:** `{user.id}`
📱 **Бот:** @{self.bot_username}
🕐 **Время:** {datetime.now().strftime('%H:%M %d.%m.%Y')}

⚠️ Автоодобрение отключено. Заявка ожидает ручного рассмотрения в настройках канала.
"""
            
            await send_telegram_message(
                self.bot_token,
                self.owner_id,
                message,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error notifying admin: {e}")
    
    async def _notify_admin_error(self, user, error_msg: str):
        """Notify admin about error"""
        try:
            username = f"@{user.username}" if user.username else "Без username"
            name = user.first_name or "Без имени"
            
            message = f"""
❌ **Ошибка при обработке заявки**

👤 **Пользователь:** {name} ({username})
🆔 **ID:** `{user.id}`
📱 **Бот:** @{self.bot_username}
🚫 **Ошибка:** {error_msg}

Пожалуйста, рассмотрите заявку вручную в настройках канала.
"""
            
            await send_telegram_message(
                self.bot_token,
                self.owner_id,
                message,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error notifying admin about error: {e}")
    
    async def _process_message_links(self, message):
        """Process and track links in channel messages"""
        try:
            import re
            
            text = message.text
            urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text)
            
            for url in urls:
                # Log URL for tracking
                async for db in get_db():
                    await self.message_service.create_message(
                        db,
                        bot_id=self.bot_id,
                        message_data=MessageCreate(
                            recipient_id=message.from_user.id,
                            content=f"URL shared: {url}",
                            message_type=MessageType.ADMIN,
                            utm_source='channel_message'
                        )
                    )
                    break
            
        except Exception as e:
            logger.error(f"Error processing message links: {e}")
    
    async def _get_bot_stats(self, db) -> Dict[str, Any]:
        """Get basic bot statistics"""
        try:
            # Get subscriber count
            total_subscribers = await self.bot_service.count(
                db, bot_id=self.bot_id, is_active=True
            )
            
            # Get active users (last 7 days)
            from datetime import timedelta
            week_ago = datetime.utcnow() - timedelta(days=7)
            
            # This would need a proper implementation with date filtering
            active_users = total_subscribers  # Simplified
            
            return {
                'total_subscribers': total_subscribers,
                'active_users': active_users,
                'messages_sent': self.bot_model.messages_sent,
                'link_clicks': 0  # Would come from analytics
            }
            
        except Exception as e:
            logger.error(f"Error getting bot stats: {e}")
            return {
                'total_subscribers': 0,
                'active_users': 0,
                'messages_sent': 0,
                'link_clicks': 0
            }
    
    async def _get_detailed_stats(self, db) -> Dict[str, Any]:
        """Get detailed bot statistics"""
        basic_stats = await self._get_bot_stats(db)
        
        # Add more detailed metrics
        detailed_stats = basic_stats.copy()
        detailed_stats.update({
            'new_today': 0,
            'bot_interactions': 0,
            'broadcasts_sent': 0,
            'successful_deliveries': 95.0,
            'total_clicks': 0,
            'unique_clickers': 0,
            'ctr': 0.0,
            'engagement_rate': 0.0,
            'conversion_rate': 0.0
        })
        
        return detailed_stats
