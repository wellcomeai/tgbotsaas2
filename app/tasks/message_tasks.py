"""
Message Processing Tasks
"""

import logging
import asyncio
from typing import List, Dict, Any
from celery import current_task
from app.tasks.celery_app import celery_app
from app.core.database import get_db
from app.services.message_service import message_service
from app.services.bot_service import bot_service
from app.utils.telegram import send_telegram_message
from app.telegram.bot_manager import bot_manager

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="message_tasks.send_broadcast")
def send_broadcast_task(self, broadcast_id: int):
    """Send broadcast to all recipients"""
    try:
        current_task.update_state(
            state='PROGRESS',
            meta={'message': f'Processing broadcast {broadcast_id}...'}
        )
        
        async def _send_broadcast():
            async for db in get_db():
                # Get broadcast data
                broadcast_info = await message_service.send_broadcast(db, broadcast_id)
                
                recipients = broadcast_info['recipients']
                content = broadcast_info['content']
                bot_token = None
                
                # Get bot token
                bot_instance = bot_manager.get_bot_instance(broadcast_info['broadcast_id'])
                if bot_instance:
                    bot_token = bot_instance.bot_token
                
                if not bot_token:
                    raise Exception("Bot not found in manager")
                
                successful_sends = 0
                failed_sends = 0
                
                total_recipients = len(recipients)
                
                for i, recipient in enumerate(recipients):
                    try:
                        # Update progress
                        progress = (i + 1) / total_recipients * 100
                        current_task.update_state(
                            state='PROGRESS',
                            meta={
                                'message': f'Sending to recipient {i+1}/{total_recipients}',
                                'progress': progress
                            }
                        )
                        
                        # Send message
                        await send_telegram_message(
                            bot_token,
                            recipient.user_id,
                            content,
                            parse_mode='Markdown'
                        )
                        
                        successful_sends += 1
                        
                        # Delay between messages
                        await asyncio.sleep(broadcast_info.get('send_delay', 1))
                        
                    except Exception as e:
                        logger.warning(f"Failed to send to {recipient.user_id}: {e}")
                        failed_sends += 1
                
                # Update broadcast statistics
                await message_service.update_broadcast_stats(
                    db, broadcast_id, successful_sends, failed_sends
                )
                await db.commit()
                
                return {
                    'total_recipients': total_recipients,
                    'successful_sends': successful_sends,
                    'failed_sends': failed_sends,
                    'success_rate': (successful_sends / total_recipients * 100) if total_recipients > 0 else 0
                }
        
        result = asyncio.run(_send_broadcast())
        
        logger.info(f"Broadcast {broadcast_id} completed: {result}")
        return {
            'status': 'success',
            'data': result
        }
        
    except Exception as e:
        logger.error(f"Error sending broadcast {broadcast_id}: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


@celery_app.task(bind=True, name="message_tasks.send_welcome_messages")
def send_welcome_messages_task(self, bot_id: int, user_ids: List[int]):
    """Send welcome messages to new users"""
    try:
        current_task.update_state(
            state='PROGRESS',
            meta={'message': f'Sending welcome messages to {len(user_ids)} users...'}
        )
        
        async def _send_welcome():
            async for db in get_db():
                bot = await bot_service.get_bot(db, bot_id)
                
                if not bot.welcome_message_enabled or not bot.welcome_message:
                    return {'skipped': len(user_ids), 'reason': 'Welcome messages disabled'}
                
                bot_instance = bot_manager.get_bot_instance(bot_id)
                if not bot_instance:
                    raise Exception("Bot not found in manager")
                
                successful_sends = 0
                failed_sends = 0
                
                for i, user_id in enumerate(user_ids):
                    try:
                        # Update progress
                        progress = (i + 1) / len(user_ids) * 100
                        current_task.update_state(
                            state='PROGRESS',
                            meta={
                                'message': f'Sending welcome message {i+1}/{len(user_ids)}',
                                'progress': progress
                            }
                        )
                        
                        # Send welcome message
                        await send_telegram_message(
                            bot_instance.bot_token,
                            user_id,
                            bot.welcome_message,
                            parse_mode='Markdown'
                        )
                        
                        successful_sends += 1
                        
                        # Small delay
                        await asyncio.sleep(0.5)
                        
                    except Exception as e:
                        logger.warning(f"Failed to send welcome to {user_id}: {e}")
                        failed_sends += 1
                
                return {
                    'total_users': len(user_ids),
                    'successful_sends': successful_sends,
                    'failed_sends': failed_sends
                }
        
        result = asyncio.run(_send_welcome())
        
        logger.info(f"Welcome messages for bot {bot_id} completed: {result}")
        return {
            'status': 'success',
            'data': result
        }
        
    except Exception as e:
        logger.error(f"Error sending welcome messages: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


@celery_app.task(name="message_tasks.process_scheduled_messages")
def process_scheduled_messages_task():
    """Process scheduled messages and broadcasts"""
    try:
        async def _process_scheduled():
            async for db in get_db():
                # Get scheduled broadcasts
                scheduled_broadcasts = await message_service.get_scheduled_broadcasts(db)
                
                processed_count = 0
                
                for broadcast in scheduled_broadcasts:
                    try:
                        # Queue broadcast for sending
                        send_broadcast_task.delay(broadcast.id)
                        processed_count += 1
                        
                    except Exception as e:
                        logger.error(f"Error queuing broadcast {broadcast.id}: {e}")
                
                return processed_count
        
        processed_count = asyncio.run(_process_scheduled())
        
        logger.info(f"Processed {processed_count} scheduled messages")
        return {
            'status': 'success',
            'processed': processed_count
        }
        
    except Exception as e:
        logger.error(f"Error processing scheduled messages: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


@celery_app.task(bind=True, name="message_tasks.bulk_message_send")
def bulk_message_send_task(self, bot_id: int, message_data: Dict[str, Any], recipient_ids: List[int]):
    """Send bulk messages to specific recipients"""
    try:
        current_task.update_state(
            state='PROGRESS',
            meta={'message': f'Sending bulk message to {len(recipient_ids)} recipients...'}
        )
        
        async def _bulk_send():
            bot_instance = bot_manager.get_bot_instance(bot_id)
            if not bot_instance:
                raise Exception("Bot not found in manager")
            
            successful_sends = 0
            failed_sends = 0
            
            content = message_data.get('content', '')
            parse_mode = message_data.get('parse_mode', 'Markdown')
            
            for i, recipient_id in enumerate(recipient_ids):
                try:
                    # Update progress
                    progress = (i + 1) / len(recipient_ids) * 100
                    current_task.update_state(
                        state='PROGRESS',
                        meta={
                            'message': f'Sending message {i+1}/{len(recipient_ids)}',
                            'progress': progress
                        }
                    )
                    
                    # Send message
                    await send_telegram_message(
                        bot_instance.bot_token,
                        recipient_id,
                        content,
                        parse_mode=parse_mode
                    )
                    
                    successful_sends += 1
                    
                    # Delay between messages
                    await asyncio.sleep(message_data.get('delay', 1))
                    
                except Exception as e:
                    logger.warning(f"Failed to send to {recipient_id}: {e}")
                    failed_sends += 1
            
            return {
                'total_recipients': len(recipient_ids),
                'successful_sends': successful_sends,
                'failed_sends': failed_sends
            }
        
        result = asyncio.run(_bulk_send())
        
        logger.info(f"Bulk message for bot {bot_id} completed: {result}")
        return {
            'status': 'success',
            'data': result
        }
        
    except Exception as e:
        logger.error(f"Error sending bulk message: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }
