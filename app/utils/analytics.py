# app/utils/analytics.py
import logging
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import AnalyticsEvent, Dialogue, JobContext

logger = logging.getLogger(__name__)

async def log_event(
    db: AsyncSession, 
    dialogue: Dialogue, 
    event_type: str, 
    event_data: dict = None,
    check_duplicates: bool = False
):
    """
    Универсальная функция записи события аналитики.
    """
    try:
        if check_duplicates:
            stmt = select(AnalyticsEvent.id).filter_by(
                dialogue_id=dialogue.id,
                event_type=event_type
            ).limit(1)
            res = await db.execute(stmt)
            if res.scalar():
                return

        city_val = "Не определен"
        if dialogue.vacancy:
            city_val = dialogue.vacancy.city or "Не определен"
        
        interview_dt = None
        meta = dialogue.metadata_json or {}
        date_str = meta.get("interview_date") # Формат 'YYYY-MM-DD'
        if date_str:
            try:
                from datetime import datetime
                interview_dt = datetime.strptime(date_str, '%Y-%m-%d').date()
            except:
                pass

        event = AnalyticsEvent(
            account_id=dialogue.account_id,
            job_context_id=dialogue.vacancy_id,
            dialogue_id=dialogue.id,
            event_type=event_type,
            city=city_val,
            interview_date=interview_dt,
            mode='standard',
            event_data=event_data or {}
        )
        db.add(event)

    except Exception as e:
        logger.error(f"❌ Ошибка записи аналитики {event_type}: {e}")