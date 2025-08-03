"""
Master Bot Handler - обработчики для главного бота
"""

import logging
from typing import Dict, Any, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.core.database import get_db
from app.services.user_service import UserService
from app.services.bot_service import BotService
from app.schemas.user import UserCreate
from app.schemas.bot import BotCreate
from app.utils.telegram import verify_bot_token
from app.core.exceptions import ValidationError, BotLimitReachedError

logger = logging.getLogger(__name__)


class MasterBotHandler:
    """Handler for master bot interactions"""
    
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.user_service = UserService()
        self.bot_service = BotService()
        
        # User states for bot creation flow
        self.user_states: Dict[int, Dict[str, Any]] = {}
    
    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        
        try:
            async for db in get_db():
                # Get or create user
                db_user = await self.user_service.get_or_create_user(
                    db,
                    telegram_id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name
                )
                
                # Get user's bots
                user_bots = await self.bot_service.get_user_bots(db, db_user.id)
                
                if not user_bots:
                    # New user - show welcome
                    await self._send_welcome_message(update, context)
                else:
                    # Existing user - show dashboard
                    await self._show_user_dashboard(update, context, db_user, user_bots)
                
                break
                
        except Exception as e:
            logger.error(f"Error in handle_start: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка. Попробуйте позже."
            )
    
    async def handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
🤖 **Bot Factory - Помощь**

**Команды:**
/start - Главное меню
/help - Эта помощь
/stats - Статистика (только для владельца)

**Как создать бота:**
1. Создайте бота через @BotFather
2. Получите токен
3. Отправьте токен мне
4. Настройте бота через админ-панель

**Возможности ботов:**
- Автоматическое одобрение заявок
- Приветственные сообщения
- Массовые рассылки
- UTM-трекинг ссылок
- Подробная аналитика

**Поддержка:** @BotFactorySupport
"""
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def handle_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command (admin only)"""
        user_id = update.effective_user.id
        
        # Check if user is admin (you can define admin user IDs)
        admin_ids = [123456789]  # Replace with actual admin IDs
        
        if user_id not in admin_ids:
            await update.message.reply_text("❌ У вас нет прав для этой команды")
            return
        
        try:
            # Get system stats
            bot_manager_stats = self.bot_manager.get_stats()
            
            async for db in get_db():
                total_users = await self.user_service.get_active_users_count(db)
                break
            
            stats_text = f"""
📊 **Статистика системы**

👥 **Пользователи:** {total_users}
🤖 **Всего ботов:** {bot_manager_stats['total_bots']}
✅ **Активных ботов:** {bot_manager_stats['running_bots']}
🟢 **Система работает:** {"Да" if bot_manager_stats['is_running'] else "Нет"}

⏱ **Uptime:** {bot_manager_stats['uptime']:.0f} секунд
"""
            
            await update.message.reply_text(stats_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in handle_stats: {e}")
            await update.message.reply_text("❌ Ошибка получения статистики")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        user_id = update.effective_user.id
        text = update.message.text
        
        # Check if user is in bot creation flow
        if user_id in self.user_states:
            state = self.user_states[user_id]
            
            if state.get('waiting_for') == 'bot_token':
                await self._process_bot_token(update, context, text)
                return
        
        # Default response
        await update.message.reply_text(
            "👋 Привет! Используй /start для начала работы с Bot Factory."
        )
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries"""
        query = update.callback_query
        data = query.data
        user_id = query.from_user.id
        
        await query.answer()
        
        try:
            if data == "master_create_bot":
                await self._initiate_bot_creation(update, context)
            
            elif data == "master_dashboard":
                await self._show_dashboard(update, context)
            
            elif data == "master_help":
                await self._show_help(update, context)
            
            elif data.startswith("master_manage_"):
                bot_id = int(data.split("_")[2])
                await self._manage_bot(update, context, bot_id)
            
            elif data.startswith("master_restart_"):
                bot_id = int(data.split("_")[2])
                await self._restart_bot(update, context, bot_id)
            
            else:
                await query.answer("🚧 Функция в разработке")
                
        except Exception as e:
            logger.error(f"Error in handle_callback_query: {e}")
            await query.answer("❌ Произошла ошибка")
    
    async def _send_welcome_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send welcome message to new user"""
        message = """
🤖 **Добро пожаловать в Bot Factory!**

Создай персонального бота для управления Telegram каналом за 2 минуты:

✅ Автоматические рассылки
✅ Полная админ-панель в Telegram  
✅ UTM-трекинг и аналитика
✅ Управление подписчиками

🎁 **Бесплатно для первых 1000 пользователей**

**Что умеет твой бот:**
- Автоматически одобрять заявки в канал
- Отправлять массовые рассылки
- Показывать детальную статистику
- Управлять приветственными сообщениями

**Как это работает:**
1. Создаешь бота через @BotFather
2. Даешь мне токен - я запускаю твоего бота
3. Добавляешь бота админом в свой канал
4. Управляешь через удобную панель

Готов начать?
"""
        
        keyboard = [
            [InlineKeyboardButton("🚀 Создать первого бота", callback_data="master_create_bot")],
            [InlineKeyboardButton("❓ Помощь", callback_data="master_help")]
        ]
        
        await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def _show_user_dashboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                 user, user_bots):
        """Show user dashboard with existing bots"""
        try:
            display_name = user.display_name
            
            message = f"🏠 **Панель управления**\n\n"
            message += f"👋 Привет, {display_name}!\n\n"
            message += f"**Твои боты ({len(user_bots)}):**\n\n"
            
            keyboard = []
            
            for bot in user_bots:
                status_emoji = {
                    'active': '✅',
                    'creating': '🔄',
                    'stopped': '⏸️',
                    'error': '❌'
                }.get(bot.status, '❓')
                
                message += f"{status_emoji} @{bot.bot_username} - {bot.status}\n"
                
                keyboard.append([
                    InlineKeyboardButton(
                        f"⚙️ @{bot.bot_username}", 
                        callback_data=f"master_manage_{bot.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("➕ Создать нового бота", callback_data="master_create_bot")
            ])
            keyboard.append([
                InlineKeyboardButton("❓ Помощь", callback_data="master_help")
            ])
            
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
            logger.error(f"Error showing dashboard: {e}")
            fallback_message = "🏠 Панель управления\n\nВыберите действие:"
            
            keyboard = [
                [InlineKeyboardButton("➕ Создать бота", callback_data="master_create_bot")],
                [InlineKeyboardButton("❓ Помощь", callback_data="master_help")]
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
    
    async def _initiate_bot_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start bot creation process"""
        user_id = update.callback_query.from_user.id
        
        # Set user state
        self.user_states[user_id] = {
            'step': 'waiting_token',
            'waiting_for': 'bot_token'
        }
        
        message = """
📝 **Создание бота - Шаг 1/2**

Сначала создай бота через @BotFather:

**Пошаговая инструкция:**
1️⃣ Перейди к @BotFather
2️⃣ Отправь команду: `/newbot`
3️⃣ Придумай имя: "Мой канал помощник"
4️⃣ Придумай username: `@mychannel_helper_bot`
5️⃣ Получи токен

**⚠️ Важно:**
- Username должен заканчиваться на `bot`
- Токен выглядит как: `123456789:ABC-DEF1234567890`
- Сохрани токен - он нужен только один раз

Когда получишь токен - пришли его мне следующим сообщением.

**Пример токена:**
`1234567890:ABCdefGHI123-456789JKLmnop`
"""
        
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="master_dashboard")]
        ]
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def _process_bot_token(self, update: Update, context: ContextTypes.DEFAULT_TYPE, token: str):
        """Process and validate bot token"""
        user_id = update.effective_user.id
        
        try:
            # Clear user state
            if user_id in self.user_states:
                del self.user_states[user_id]
            
            # Validate token format
            if not token or ':' not in token:
                await update.message.reply_text(
                    "❌ **Неверный формат токена**\n\n"
                    "Токен должен выглядеть так:\n"
                    "`1234567890:ABCdefGHI123-456789JKLmnop`\n\n"
                    "Попробуй еще раз или нажми /start для возврата в меню.",
                    parse_mode='Markdown'
                )
                return
            
            # Show processing message
            processing_msg = await update.message.reply_text("🔄 Проверяю токен...")
            
            # Verify token works
            bot_info = await verify_bot_token(token)
            if not bot_info:
                await processing_msg.edit_text(
                    "❌ **Токен не работает**\n\n"
                    "Возможные причины:\n"
                    "• Токен введен неправильно\n"
                    "• Бот заблокирован\n"
                    "• Токен уже недействителен\n\n"
                    "Проверь правильность токена и попробуй еще раз."
                )
                return
            
            async for db in get_db():
                # Get user
                db_user = await self.user_service.get_user_by_telegram_id(db, user_id)
                if not db_user:
                    await processing_msg.edit_text("❌ Пользователь не найден")
                    return
                
                # Check if token already exists
                existing_bot = await self.bot_service._get_bot_by_token(db, token)
                if existing_bot:
                    await processing_msg.edit_text(
                        "❌ **Этот бот уже зарегистрирован**\n\n"
                        "Используй другого бота или обратись в поддержку."
                    )
                    return
                
                # Create bot record
                bot_data = BotCreate(
                    bot_token=token,
                    bot_username=bot_info['username'],
                    bot_display_name=bot_info.get('first_name', bot_info['username'])
                )
                
                try:
                    bot = await self.bot_service.create_bot(db, bot_data, db_user.id)
                    await processing_msg.edit_text("✅ Бот создан! Запускаю...")
                    
                    # Add bot to manager
                    success = await self.bot_manager.add_bot(bot)
                    
                    if success:
                        await self._show_deployment_success(update, context, bot_info, processing_msg)
                    else:
                        await self._show_deployment_error(update, context, processing_msg)
                        
                except BotLimitReachedError as e:
                    await processing_msg.edit_text(f"❌ {str(e)}")
                except ValidationError as e:
                    await processing_msg.edit_text(f"❌ {str(e)}")
                
                break
                
        except Exception as e:
            logger.error(f"Error processing bot token: {e}")
            await update.message.reply_text("❌ Произошла ошибка при обработке токена")
    
    async def _show_deployment_success(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                     bot_info: dict, message_to_edit):
        """Show successful deployment message"""
        bot_username = bot_info['username']
        
        message = f"""
🎉 **Готово! Твой @{bot_username} запущен!**

📋 **Что делать дальше:**

**1️⃣ Добавь бота в канал как администратора:**
- Зайди в настройки канала
- Администраторы → Добавить администратора  
- Найди @{bot_username} и добавь
- Дай права: "Удаление сообщений" и "Приглашение пользователей"

**2️⃣ Перейди к своему боту:** @{bot_username}

**3️⃣ Напиши ему /start** - откроется админ-панель!

🎁 **Все функции доступны бесплатно**
📊 Полная статистика и аналитика
⚡ Мгновенные рассылки и автоматизация

**Нужна помощь?** Обращайся в поддержку!
"""
        
        keyboard = [
            [InlineKeyboardButton(
                f"🤖 Перейти к @{bot_username}", 
                url=f"https://t.me/{bot_username}"
            )],
            [InlineKeyboardButton("🏠 Мои боты", callback_data="master_dashboard")]
        ]
        
        await message_to_edit.edit_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def _show_deployment_error(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                   message_to_edit, error_details: str = None):
        """Show deployment error message"""
        message = """
❌ **Ошибка при запуске бота**

К сожалению, произошла ошибка при создании твоего бота.

**Что делать:**
- Попробуй еще раз через несколько минут
- Обратись в поддержку для решения проблемы
- Проверь, что токен был скопирован правильно

Мы уже получили уведомление об ошибке и работаем над исправлением.
"""
        
        keyboard = [
            [InlineKeyboardButton("🔄 Попробовать еще раз", callback_data="master_create_bot")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="master_dashboard")]
        ]
        
        await message_to_edit.edit_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def _show_dashboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main dashboard"""
        user_id = update.callback_query.from_user.id
        
        try:
            async for db in get_db():
                db_user = await self.user_service.get_user_by_telegram_id(db, user_id)
                user_bots = await self.bot_service.get_user_bots(db, db_user.id)
                break
            
            await self._show_user_dashboard(update, context, db_user, user_bots)
            
        except Exception as e:
            logger.error(f"Error showing dashboard: {e}")
            await update.callback_query.answer("❌ Ошибка загрузки панели")
    
    async def _show_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help information"""
        help_text = """
❓ **Помощь по Bot Factory**

**🚀 Быстрый старт:**
1. Создай бота через @BotFather
2. Получи токен
3. Отправь токен мне
4. Добавь бота в канал как админа
5. Настрой через админ-панель

**📋 Основные функции:**

**📊 Статистика**
- Количество подписчиков
- Активность пользователей  
- Клики по ссылкам
- Эффективность рассылок

**✉️ Рассылки**
- Массовые рассылки
- Приветственные сообщения
- UTM-трекинг ссылок
- Планирование отправки

**👥 Управление**
- Автоодобрение заявок
- Просмотр подписчиков
- Модерация участников

**💬 Поддержка**
Если нужна помощь - @BotFactorySupport

**Bot Factory** 🤖
"""
        
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="master_dashboard")]
        ]
        
        await update.callback_query.edit_message_text(
            help_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def _manage_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE, bot_id: int):
        """Show bot management options"""
        try:
            async for db in get_db():
                bot = await self.bot_service.get_bot(db, bot_id)
                break
            
            status_text = {
                'active': '✅ Активен',
                'creating': '🔄 Создается',
                'stopped': '⏸️ Остановлен',
                'error': '❌ Ошибка'
            }.get(bot.status, '❓ Неизвестно')
            
            # Check if bot is in manager
            bot_instance = self.bot_manager.get_bot_instance(bot_id)
            actual_status = "✅ Запущен" if bot_instance else "❌ Не запущен"
            
            message = f"""
⚙️ **Управление ботом @{bot.bot_username}**

**Статус в БД:** {status_text}
**Фактический статус:** {actual_status}
**Создан:** {bot.created_at.strftime('%d.%m.%Y %H:%M')}
**Подписчиков:** {bot.total_subscribers}
**Сообщений отправлено:** {bot.messages_sent}

**Доступные действия:**
"""
            
            keyboard = [
                [InlineKeyboardButton(
                    f"🤖 Перейти к @{bot.bot_username}", 
                    url=f"https://t.me/{bot.bot_username}"
                )],
                [InlineKeyboardButton("🔄 Перезапустить", callback_data=f"master_restart_{bot_id}")],
                [InlineKeyboardButton("🔙 Назад", callback_data="master_dashboard")]
            ]
            
            await update.callback_query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in manage_bot: {e}")
            await update.callback_query.answer("❌ Ошибка при загрузке информации о боте")
    
    async def _restart_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE, bot_id: int):
        """Restart a user bot"""
        try:
            # Show processing message
            await update.callback_query.edit_message_text(
                f"🔄 Перезапускаю бота...\n\n"
                "Это может занять несколько секунд."
            )
            
            # Restart the bot
            success = await self.bot_manager.restart_bot(bot_id)
            
            if success:
                async for db in get_db():
                    bot = await self.bot_service.get_bot(db, bot_id)
                    break
                
                await update.callback_query.edit_message_text(
                    f"✅ **Бот @{bot.bot_username} успешно перезапущен!**\n\n"
                    "Попробуй написать ему /start для проверки работы.",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(
                            f"🤖 Перейти к @{bot.bot_username}", 
                            url=f"https://t.me/{bot.bot_username}"
                        )],
                        [InlineKeyboardButton("🔙 Назад к управлению", 
                                            callback_data=f"master_manage_{bot_id}")]
                    ])
                )
            else:
                await update.callback_query.edit_message_text(
                    f"❌ **Не удалось перезапустить бота**\n\n"
                    "Попробуйте еще раз или обратитесь в поддержку.",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Попробовать еще раз", 
                                            callback_data=f"master_restart_{bot_id}")],
                        [InlineKeyboardButton("🔙 Назад к управлению", 
                                            callback_data=f"master_manage_{bot_id}")]
                    ])
                )
                
        except Exception as e:
            logger.error(f"Error restarting bot {bot_id}: {e}")
            await update.callback_query.edit_message_text(
                f"❌ **Ошибка при перезапуске бота**\n\n"
                f"Обратитесь в поддержку.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад к управлению", 
                                        callback_data=f"master_manage_{bot_id}")]
                ])
            )
