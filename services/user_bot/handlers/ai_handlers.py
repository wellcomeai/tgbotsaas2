"""
AI обработчики для UserBot
Управление ИИ агентами, диалогами и настройками
✅ ДОБАВЛЕНО: Критичные роутеры навигации для OpenAI интерфейса
✅ ДОБАВЛЕНО: Полная интеграция с OpenAIHandler
"""

import structlog
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from ..states import AISettingsStates
from ..keyboards import AIKeyboards, AdminKeyboards

logger = structlog.get_logger()

# Создаем router для AI обработчиков
router = Router()

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

async def get_bot_config(callback_or_message, db):
    """Получение конфигурации бота из сообщения/callback"""
    try:
        # Определяем тип объекта
        if hasattr(callback_or_message, 'message'):
            # CallbackQuery
            user_id = callback_or_message.from_user.id
            # Получаем bot username через API
            try:
                bot_info = await callback_or_message.bot.get_me()
                bot_username = bot_info.username
            except:
                bot_username = None
        else:
            # Message
            user_id = callback_or_message.from_user.id
            # Получаем bot username через API
            try:
                bot_info = await callback_or_message.bot.get_me()
                bot_username = bot_info.username
            except:
                bot_username = None
        
        # Получаем бота по username (если удалось получить) или ищем по user_id
        bots = await db.get_user_bots(user_id)
        current_bot = None
        
        if bot_username:
            # Ищем по username
            for bot in bots:
                if bot.bot_username == bot_username:
                    current_bot = bot
                    break
        
        if not current_bot and bots:
            # Fallback - берем первый активный бот пользователя
            for bot in bots:
                if bot.status == 'active':
                    current_bot = bot
                    break
        
        if not current_bot and bots:
            # Последний fallback - берем любой бот
            current_bot = bots[0]
        
        if not current_bot:
            logger.error("❌ Bot not found", user_id=user_id, bot_username=bot_username)
            return None
        
        # Формируем конфигурацию
        bot_config = {
            'bot_id': current_bot.bot_id,
            'bot_username': current_bot.bot_username,
            'owner_user_id': current_bot.user_id,
            'ai_assistant_id': current_bot.openai_agent_id,
            'ai_assistant_settings': current_bot.openai_settings or {},
            'bot_manager': None,  # Заполнится при необходимости
            'user_bot': None      # Заполнится при необходимости
        }
        
        logger.info("✅ Bot config retrieved", 
                   bot_id=current_bot.bot_id,
                   owner_id=current_bot.user_id,
                   has_ai_agent=bool(current_bot.openai_agent_id))
        
        return bot_config
        
    except Exception as e:
        logger.error("💥 Failed to get bot config", 
                    error=str(e),
                    error_type=type(e).__name__)
        return None

def is_owner_check_factory(owner_user_id: int):
    """Фабрика для создания функции проверки владельца"""
    def is_owner_check(user_id: int) -> bool:
        return user_id == owner_user_id
    return is_owner_check

async def create_openai_handler(bot_config, db):
    """Создание экземпляра OpenAIHandler"""
    try:
        from .ai_openai_handler import OpenAIHandler
        
        # Создаем обработчик с полной конфигурацией
        openai_handler = OpenAIHandler(
            db=db,
            bot_config=bot_config,
            ai_assistant=None,  # Заполнится при необходимости
            user_bot=None       # Заполнится при необходимости
        )
        
        logger.info("✅ OpenAIHandler created", bot_id=bot_config['bot_id'])
        return openai_handler
        
    except Exception as e:
        logger.error("💥 Failed to create OpenAIHandler", 
                    error=str(e),
                    error_type=type(e).__name__)
        return None

# ===== КРИТИЧНЫЕ РОУТЕРЫ НАВИГАЦИИ =====

@router.callback_query(F.data.in_(["admin_panel", "admin_ai", "admin_main"]))
async def handle_navigation_callbacks(callback: CallbackQuery, state: FSMContext):
    """✅ НОВЫЙ: Обработчик критичных кнопок навигации"""
    logger.info("🧭 Navigation callback received", 
               user_id=callback.from_user.id,
               callback_data=callback.data)
    
    try:
        # Получаем db из контекста бота или создаем подключение
        from database.connection import DatabaseManager
        db = DatabaseManager()
        
        # Получаем конфигурацию бота
        bot_config = await get_bot_config(callback, db)
        if not bot_config:
            await callback.answer("❌ Ошибка: бот не найден", show_alert=True)
            return
        
        # Создаем функцию проверки владельца
        is_owner_check = is_owner_check_factory(bot_config['owner_user_id'])
        
        # Создаем обработчик OpenAI
        openai_handler = await create_openai_handler(bot_config, db)
        if not openai_handler:
            await callback.answer("❌ Ошибка создания обработчика", show_alert=True)
            return
        
        # Передаем обработку навигации
        await openai_handler.handle_navigation_action(callback, state, is_owner_check)
        
        logger.info("✅ Navigation handled successfully", 
                   callback_data=callback.data,
                   bot_id=bot_config['bot_id'])
        
    except Exception as e:
        logger.error("💥 Error in navigation handler", 
                    callback_data=callback.data,
                    error=str(e),
                    error_type=type(e).__name__)
        
        try:
            await callback.answer("❌ Произошла ошибка", show_alert=True)
        except:
            pass

# ===== ОТДЕЛЬНЫЙ ОБРАБОТЧИК ДЛЯ АДМИНСКОГО ЗАВЕРШЕНИЯ ДИАЛОГА =====

@router.callback_query(F.data == "ai_exit_conversation")
async def handle_admin_ai_exit_conversation(callback: CallbackQuery, state: FSMContext):
    """✅ НОВЫЙ: Завершение админского диалога с ИИ (отдельно от пользовательского)"""
    logger.info("🚪 Admin AI exit conversation", 
               user_id=callback.from_user.id)
    
    try:
        # Получаем db из контекста бота или создаем подключение
        from database.connection import DatabaseManager
        db = DatabaseManager()
        
        # Получаем конфигурацию бота
        bot_config = await get_bot_config(callback, db)
        if not bot_config:
            await callback.answer("❌ Ошибка: бот не найден", show_alert=True)
            return
        
        # Создаем функцию проверки владельца
        is_owner_check = is_owner_check_factory(bot_config['owner_user_id'])
        
        # Создаем обработчик OpenAI
        openai_handler = await create_openai_handler(bot_config, db)
        if not openai_handler:
            await callback.answer("❌ Ошибка создания обработчика", show_alert=True)
            return
        
        # Передаем обработку завершения диалога
        await openai_handler.handle_exit_conversation(callback, state)
        
        logger.info("✅ Admin AI conversation ended", 
                   callback_data=callback.data,
                   bot_id=bot_config['bot_id'])
        
    except Exception as e:
        logger.error("💥 Error in admin AI exit handler", 
                    error=str(e),
                    error_type=type(e).__name__)
        
        try:
            await callback.answer("❌ Произошла ошибка", show_alert=True)
        except:
            pass

# ===== РОУТЕРЫ OPENAI ДЕЙСТВИЙ =====

@router.callback_query(F.data.startswith("openai_"))
async def handle_openai_callbacks(callback: CallbackQuery, state: FSMContext):
    """✅ ОБНОВЛЕННЫЙ: Обработчик OpenAI действий + поддержка confirm_delete"""
    logger.info("🎨 OpenAI callback received", 
               user_id=callback.from_user.id,
               callback_data=callback.data)
    
    try:
        # Получаем db из контекста бота или создаем подключение
        from database.connection import DatabaseManager
        db = DatabaseManager()
        
        # Получаем конфигурацию бота
        bot_config = await get_bot_config(callback, db)
        if not bot_config:
            await callback.answer("❌ Ошибка: бот не найден", show_alert=True)
            return
        
        # Создаем функцию проверки владельца
        is_owner_check = is_owner_check_factory(bot_config['owner_user_id'])
        
        # Создаем обработчик OpenAI
        openai_handler = await create_openai_handler(bot_config, db)
        if not openai_handler:
            await callback.answer("❌ Ошибка создания обработчика", show_alert=True)
            return
        
        # ✅ СПЕЦИАЛЬНАЯ ОБРАБОТКА confirm_delete
        if callback.data == "openai_confirm_delete":
            await openai_handler.handle_confirm_delete(callback, is_owner_check)
        else:
            # Обычные OpenAI действия
            await openai_handler.handle_openai_action(callback, state, is_owner_check)
        
        logger.info("✅ OpenAI action handled successfully", 
                   callback_data=callback.data,
                   bot_id=bot_config['bot_id'])
        
    except Exception as e:
        logger.error("💥 Error in OpenAI handler", 
                    callback_data=callback.data,
                    error=str(e),
                    error_type=type(e).__name__)
        
        try:
            await callback.answer("❌ Произошла ошибка", show_alert=True)
        except:
            pass

# ===== ОСНОВНЫЕ AI ОБРАБОТЧИКИ =====

@router.callback_query(F.data == "admin_ai")
async def handle_ai_settings(callback: CallbackQuery, state: FSMContext):
    """Показ настроек ИИ (дублирует навигационный обработчик для совместимости)"""
    logger.info("🤖 AI settings callback", 
               user_id=callback.from_user.id)
    
    # Перенаправляем в навигационный обработчик
    await handle_navigation_callbacks(callback, state)

@router.callback_query(F.data == "ai_create_assistant")
async def handle_create_assistant(callback: CallbackQuery, state: FSMContext):
    """Создание ИИ ассистента (общий интерфейс)"""
    logger.info("🎨 Create assistant callback", 
               user_id=callback.from_user.id)
    
    try:
        from database.connection import DatabaseManager
        db = DatabaseManager()
        
        bot_config = await get_bot_config(callback, db)
        if not bot_config:
            await callback.answer("❌ Ошибка: бот не найден", show_alert=True)
            return
        
        is_owner_check = is_owner_check_factory(bot_config['owner_user_id'])
        
        if not is_owner_check(callback.from_user.id):
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return
        
        # Показываем выбор типа ассистента (пока только OpenAI)
        text = """
🎨 <b>Создание ИИ ассистента</b>

Выберите тип ассистента для вашего бота:
"""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧠 OpenAI GPT-4o (Responses API)", callback_data="openai_create")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_ai")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error("💥 Error in create assistant", error=str(e))
        await callback.answer("❌ Произошла ошибка", show_alert=True)

# ===== ОБРАБОТЧИКИ FSM СОСТОЯНИЙ =====

@router.message(StateFilter(AISettingsStates.waiting_for_openai_name))
async def handle_openai_name_input(message: Message, state: FSMContext):
    """Обработка ввода имени OpenAI агента"""
    logger.info("📝 OpenAI name input received", 
               user_id=message.from_user.id,
               input_length=len(message.text))
    
    try:
        from database.connection import DatabaseManager
        db = DatabaseManager()
        
        bot_config = await get_bot_config(message, db)
        if not bot_config:
            await message.answer("❌ Ошибка: бот не найден")
            return
        
        is_owner_check = is_owner_check_factory(bot_config['owner_user_id'])
        
        openai_handler = await create_openai_handler(bot_config, db)
        if not openai_handler:
            await message.answer("❌ Ошибка создания обработчика")
            return
        
        await openai_handler.handle_name_input(message, state, is_owner_check)
        
    except Exception as e:
        logger.error("💥 Error in name input handler", error=str(e))
        await message.answer("❌ Произошла ошибка при обработке имени")

@router.message(StateFilter(AISettingsStates.waiting_for_openai_role))
async def handle_openai_role_input(message: Message, state: FSMContext):
    """Обработка ввода роли OpenAI агента"""
    logger.info("📝 OpenAI role input received", 
               user_id=message.from_user.id,
               input_length=len(message.text))
    
    try:
        from database.connection import DatabaseManager
        db = DatabaseManager()
        
        bot_config = await get_bot_config(message, db)
        if not bot_config:
            await message.answer("❌ Ошибка: бот не найден")
            return
        
        is_owner_check = is_owner_check_factory(bot_config['owner_user_id'])
        
        openai_handler = await create_openai_handler(bot_config, db)
        if not openai_handler:
            await message.answer("❌ Ошибка создания обработчика")
            return
        
        await openai_handler.handle_role_input(message, state, is_owner_check)
        
    except Exception as e:
        logger.error("💥 Error in role input handler", error=str(e))
        await message.answer("❌ Произошла ошибка при обработке роли")

@router.message(StateFilter(AISettingsStates.editing_agent_name))
async def handle_agent_name_edit(message: Message, state: FSMContext):
    """Обработка редактирования имени агента"""
    logger.info("✏️ Agent name edit received", 
               user_id=message.from_user.id,
               input_length=len(message.text))
    
    try:
        from database.connection import DatabaseManager
        db = DatabaseManager()
        
        bot_config = await get_bot_config(message, db)
        if not bot_config:
            await message.answer("❌ Ошибка: бот не найден")
            return
        
        is_owner_check = is_owner_check_factory(bot_config['owner_user_id'])
        
        openai_handler = await create_openai_handler(bot_config, db)
        if not openai_handler:
            await message.answer("❌ Ошибка создания обработчика")
            return
        
        await openai_handler.handle_name_edit_input(message, state, is_owner_check)
        
    except Exception as e:
        logger.error("💥 Error in name edit handler", error=str(e))
        await message.answer("❌ Произошла ошибка при редактировании имени")

@router.message(StateFilter(AISettingsStates.editing_agent_prompt))
async def handle_agent_prompt_edit(message: Message, state: FSMContext):
    """Обработка редактирования промпта агента"""
    logger.info("🎭 Agent prompt edit received", 
               user_id=message.from_user.id,
               input_length=len(message.text))
    
    try:
        from database.connection import DatabaseManager
        db = DatabaseManager()
        
        bot_config = await get_bot_config(message, db)
        if not bot_config:
            await message.answer("❌ Ошибка: бот не найден")
            return
        
        is_owner_check = is_owner_check_factory(bot_config['owner_user_id'])
        
        openai_handler = await create_openai_handler(bot_config, db)
        if not openai_handler:
            await message.answer("❌ Ошибка создания обработчика")
            return
        
        await openai_handler.handle_prompt_edit_input(message, state, is_owner_check)
        
    except Exception as e:
        logger.error("💥 Error in prompt edit handler", error=str(e))
        await message.answer("❌ Произошла ошибка при редактировании промпта")

@router.message(StateFilter(AISettingsStates.in_ai_conversation))
async def handle_ai_conversation(message: Message, state: FSMContext):
    """Обработка диалога с ИИ агентом"""
    logger.info("💬 AI conversation message received", 
               user_id=message.from_user.id,
               message_length=len(message.text))
    
    try:
        # Проверяем команды выхода
        if message.text in ['/exit', '/stop', '/cancel']:
            await state.clear()
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="admin_main")]
            ])
            
            await message.answer(
                "🚪 Диалог с ИИ завершен",
                reply_markup=keyboard
            )
            return
        
        from database.connection import DatabaseManager
        db = DatabaseManager()
        
        bot_config = await get_bot_config(message, db)
        if not bot_config:
            await message.answer("❌ Ошибка: бот не найден")
            return
        
        is_owner_check = is_owner_check_factory(bot_config['owner_user_id'])
        
        if not is_owner_check(message.from_user.id):
            await message.answer("❌ Доступ запрещен")
            return
        
        # Получаем данные состояния
        data = await state.get_data()
        agent_type = data.get('agent_type', 'openai')
        
        if agent_type == 'openai':
            openai_handler = await create_openai_handler(bot_config, db)
            if not openai_handler:
                await message.answer("❌ Ошибка создания обработчика OpenAI")
                return
            
            # Показываем индикатор набора текста
            await message.bot.send_chat_action(message.chat.id, "typing")
            
            # Получаем ответ от OpenAI
            response = await openai_handler.handle_openai_conversation(message, data)
            
            if response:
                # Отправляем ответ с кнопками управления (БЕЗ очистки контекста)
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🚪 Завершить диалог", callback_data="ai_exit_conversation")]
                ])
                
                await message.answer(response, reply_markup=keyboard)
            else:
                await message.answer("❌ Не удалось получить ответ от ИИ")
        else:
            await message.answer("❌ Неподдерживаемый тип агента")
            
    except Exception as e:
        logger.error("💥 Error in AI conversation", 
                    error=str(e),
                    error_type=type(e).__name__)
        await message.answer("❌ Произошла ошибка при общении с ИИ")

# ===== ОБЩИЕ AI ОБРАБОТЧИКИ =====

@router.callback_query(F.data == "ai_toggle_status")
async def handle_toggle_ai_status(callback: CallbackQuery, state: FSMContext):
    """Переключение статуса ИИ"""
    logger.info("🔄 Toggle AI status", user_id=callback.from_user.id)
    
    try:
        from database.connection import DatabaseManager
        db = DatabaseManager()
        
        bot_config = await get_bot_config(callback, db)
        if not bot_config:
            await callback.answer("❌ Ошибка: бот не найден", show_alert=True)
            return
        
        is_owner_check = is_owner_check_factory(bot_config['owner_user_id'])
        
        if not is_owner_check(callback.from_user.id):
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return
        
        # Получаем текущий статус AI
        fresh_bot = await db.get_bot_by_id(bot_config['bot_id'], fresh=True)
        if not fresh_bot:
            await callback.answer("❌ Бот не найден", show_alert=True)
            return
        
        # Переключаем статус
        new_status = not fresh_bot.ai_assistant_enabled
        
        success = await db.update_ai_assistant(
            bot_config['bot_id'],
            enabled=new_status
        )
        
        if success:
            status_text = "включен" if new_status else "отключен"
            await callback.answer(f"✅ ИИ {status_text}")
            
            # Обновляем интерфейс
            openai_handler = await create_openai_handler(bot_config, db)
            if openai_handler:
                await openai_handler.show_settings(callback, has_ai_agent=new_status)
        else:
            await callback.answer("❌ Ошибка при изменении статуса", show_alert=True)
            
    except Exception as e:
        logger.error("💥 Error toggling AI status", error=str(e))
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@router.callback_query(F.data == "ai_stats")
async def handle_ai_stats(callback: CallbackQuery, state: FSMContext):
    """Показ статистики ИИ"""
    logger.info("📊 AI stats requested", user_id=callback.from_user.id)
    
    try:
        from database.connection import DatabaseManager
        db = DatabaseManager()
        
        bot_config = await get_bot_config(callback, db)
        if not bot_config:
            await callback.answer("❌ Ошибка: бот не найден", show_alert=True)
            return
        
        is_owner_check = is_owner_check_factory(bot_config['owner_user_id'])
        
        if not is_owner_check(callback.from_user.id):
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return
        
        # Получаем статистику
        fresh_bot = await db.get_bot_by_id(bot_config['bot_id'], fresh=True)
        if not fresh_bot:
            await callback.answer("❌ Бот не найден", show_alert=True)
            return
        
        # Формируем статистику
        input_tokens = fresh_bot.tokens_used_input or 0
        output_tokens = fresh_bot.tokens_used_output or 0
        total_tokens = fresh_bot.tokens_used_total or 0
        
        # Проверяем лимиты пользователя
        has_tokens, user_tokens_used, user_tokens_limit = await db.check_token_limit(fresh_bot.user_id)
        
        text = f"""
📊 <b>Статистика использования ИИ</b>

<b>🤖 Бот:</b> @{fresh_bot.bot_username}
<b>🧠 Тип ИИ:</b> {fresh_bot.ai_assistant_type or 'Не настроен'}
<b>🔄 Статус:</b> {'Включен' if fresh_bot.ai_assistant_enabled else 'Выключен'}

<b>📈 Токены бота:</b>
• Входящие: {input_tokens:,}
• Исходящие: {output_tokens:,}
• Всего: {total_tokens:,}

<b>👤 Лимиты пользователя:</b>
• Использовано: {user_tokens_used:,}
• Лимит: {user_tokens_limit:,}
• Осталось: {user_tokens_limit - user_tokens_used:,}
• Статус: {'✅ В пределах лимита' if has_tokens else '❌ Лимит превышен'}
"""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="ai_stats")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_ai")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error("💥 Error showing AI stats", error=str(e))
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@router.callback_query(F.data == "ai_diagnosis")
async def handle_ai_diagnosis(callback: CallbackQuery, state: FSMContext):
    """Диагностика состояния ИИ"""
    logger.info("🔍 AI diagnosis requested", user_id=callback.from_user.id)
    
    try:
        from database.connection import DatabaseManager
        db = DatabaseManager()
        
        bot_config = await get_bot_config(callback, db)
        if not bot_config:
            await callback.answer("❌ Ошибка: бот не найден", show_alert=True)
            return
        
        is_owner_check = is_owner_check_factory(bot_config['owner_user_id'])
        
        if not is_owner_check(callback.from_user.id):
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return
        
        # Выполняем диагностику
        diagnosis = await db.diagnose_ai_config(bot_config['bot_id'])
        
        status_emoji = {
            'configured': '✅',
            'disabled': '⚠️',
            'incomplete': '🔧',
            'misconfigured': '❌',
            'not_configured': '❓'
        }
        
        text = f"""
🔍 <b>Диагностика ИИ конфигурации</b>

<b>🎯 Статус:</b> {status_emoji.get(diagnosis['status'], '❓')} {diagnosis['status']}
<b>🤖 Бот ID:</b> {diagnosis['bot_id']}

<b>📊 Основные параметры:</b>
• AI включен: {'✅' if diagnosis['ai_assistant_enabled'] else '❌'}
• Тип AI: {diagnosis['ai_assistant_type'] or 'Не установлен'}

<b>🧠 OpenAI:</b>
• Agent ID: {'✅' if diagnosis['fields']['openai']['agent_id'] else '❌'}
• Имя агента: {'✅' if diagnosis['fields']['openai']['agent_name'] else '❌'}
• Модель: {diagnosis['fields']['openai']['model'] or 'Не установлена'}

<b>🔧 Внешний AI:</b>
• API токен: {'✅' if diagnosis['fields']['external']['api_token'] else '❌'}
• Платформа: {diagnosis['fields']['external']['platform'] or 'Не установлена'}
"""
        
        if diagnosis['issues']:
            text += f"\n<b>⚠️ Обнаруженные проблемы:</b>\n"
            for issue in diagnosis['issues']:
                text += f"• {issue}\n"
        
        if diagnosis['config_result']:
            result_emoji = '✅' if diagnosis['config_result'] == 'success' else '❌'
            text += f"\n<b>🔍 Результат загрузки конфигурации:</b> {result_emoji} {diagnosis['config_result']}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Повторить диагностику", callback_data="ai_diagnosis")],
            [InlineKeyboardButton(text="🔧 Синхронизировать данные", callback_data="openai_sync_data")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_ai")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error("💥 Error in AI diagnosis", error=str(e))
        await callback.answer("❌ Произошла ошибка", show_alert=True)

# ===== ФУНКЦИЯ РЕГИСТРАЦИИ ОБРАБОТЧИКОВ =====

def register_ai_handlers(dp, **kwargs):
    """Регистрация AI обработчиков с поддержкой навигации"""
    logger.info("🔧 Registering AI handlers", 
               extra_kwargs=list(kwargs.keys()))
    
    # Регистрируем роутер
    dp.include_router(router)
    
    logger.info("✅ AI handlers registered with full navigation support")
    
    # Логируем зарегистрированные обработчики
    logger.info("📋 Registered AI callback handlers", 
               callback_handlers=[
                   "navigation: admin_panel, admin_ai, admin_main",
                   "ai_exit_conversation: separate admin exit handler",
                   "openai_*: all OpenAI actions including confirm_delete",
                   "ai_create_assistant: assistant creation",
                   "ai_toggle_status: enable/disable AI",
                   "ai_stats: usage statistics",
                   "ai_diagnosis: configuration diagnosis"
               ])
    
    logger.info("📋 Registered AI message handlers",
               message_handlers=[
                   "waiting_for_openai_name: agent name input",
                   "waiting_for_openai_role: agent role input", 
                   "editing_agent_name: agent name editing",
                   "editing_agent_prompt: agent prompt editing",
                   "in_ai_conversation: AI conversation handling"
               ])
