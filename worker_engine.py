# worker_engine.py
import asyncio
import json
import logging
import signal
from aio_pika import IncomingMessage
from app.core.rabbitmq import mq
from app.core.engine import dispatcher
from app.db.session import engine
from app.services.llm import cleanup_llm

from app.utils.logger import logger, set_log_context, log_context
from app.core.exceptions import DialogueLockedError

async def on_engine_task(message: IncomingMessage):
    """
    Обработка задачи ИИ.
    Используем ignore_processed=True, чтобы задача не удалялась из очереди при возникновении ошибки.
    """
    async with message.process(ignore_processed=True):
        log_context.set({})
        try:
            body_raw = message.body.decode()
            task_data = json.loads(body_raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.error("❌ Критическая ошибка: Не удалось распарсить JSON в engine_tasks. Сообщение удалено.")
            await message.reject(requeue=False)
            return

        set_log_context(
            dialogue_id=task_data.get('dialogue_id'),
            account_id=task_data.get('account_id'),
            candidate_id=task_data.get('candidate_id'),
            platform=task_data.get('platform', 'unknown'),
            step="engine_start"
        )
        diag_id = task_data.get('dialogue_id', 'unknown')
        platform = task_data.get('platform', 'unknown')
        processed_successfully = False
        try:
            logger.info(f"🧠 [Engine] Обработка ИИ-логики диалога ID: {diag_id} (Платформа: {platform})")
            
            await dispatcher.process_engine_task(task_data)
            await message.ack()
            processed_successfully = True
            
        except DialogueLockedError:
            logger.warning(f"⚠️ [Engine] Диалог {diag_id} заблокирован другим воркером. Пропуск и повтор...")
        except Exception as e:
            error_msg = f"❌ Ошибка в Движке (Engine):\nДиалог ID: `{diag_id}`\nТекст ошибки: {str(e)}"
            logger.exception("❌ Ошибка в Движке (Engine)")
            try:
                await mq.publish("tg_alerts", {
                    "type": "system",
                    "text": error_msg,
                    "alert_type": "admin_only"
                })
            except Exception as mq_err:
                logger.error(f"Не удалось отправить системный алерт из Engine: {mq_err}")
        if not processed_successfully:
            logger.info(f"♻️ Возвращаем задачу диалога {diag_id} в очередь для повторной попытки...")
            await asyncio.sleep(2)
            await message.nack(requeue=True)

async def main():
    await mq.connect()
    channel = mq.channel
    await channel.set_qos(prefetch_count=10)

    engine_queue = await channel.get_queue("engine_tasks")
    await engine_queue.consume(on_engine_task)

    logger.info("👷 [worker_engine] (Brain) запущен", extra={"prefetch_count": 10})
    
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: stop_event.set())

    await stop_event.wait()
    await mq.close()
    await engine.dispose()
    await cleanup_llm()
    logger.info("👋 [worker_engine] остановлен.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass