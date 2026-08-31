from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.followup import FollowUp
from app.models.order import Order
from app.models.quotation import Quotation
from app.models.user import User, UserRole
from app.models.workbench import DailyWorkNote, Task
from app.schemas.workbench import DailyWorkNoteRead, DailyWorkNoteUpdate, TaskCreate, TaskRead, WorkbenchToday
from app.services.errors import ForbiddenError, NotFoundError
from app.services.followup_reminder_service import CHINA_TIMEZONE, list_customer_followup_reminders, shanghai_today


def _ensure_admin(user: User) -> None:
    if user.role is not UserRole.ADMIN:
        raise ForbiddenError("Only Admin accounts can use the daily workbench.")


def _day_window(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=CHINA_TIMEZONE).astimezone(timezone.utc)
    return start, start + timedelta(days=1)


def _task_read(task: Task, customer_name: str | None) -> TaskRead:
    return TaskRead(
        id=task.id, title=task.title, due_date=task.due_date, priority=task.priority,
        status=task.status, customer_id=task.customer_id, customer_name=customer_name,
        created_by_id=task.created_by_id, created_at=task.created_at, completed_at=task.completed_at,
    )


def _tasks_for_today(session: Session, user: User, today: date) -> list[TaskRead]:
    priority_order = {"high": 0, "medium": 1, "low": 2}
    rows = session.execute(
        select(Task, Customer.company_name)
        .outerjoin(Customer, Customer.id == Task.customer_id)
        .where(Task.created_by_id == user.id, Task.status == "pending", Task.due_date <= today)
        .order_by(Task.due_date.asc(), Task.id.asc())
    ).all()
    result = [_task_read(task, company_name) for task, company_name in rows]
    return sorted(result, key=lambda task: (task.due_date >= today, priority_order[task.priority], task.due_date, task.id))


def get_today(session: Session, user: User) -> WorkbenchToday:
    _ensure_admin(user)
    today = shanghai_today()
    summary, _ = list_customer_followup_reminders(session, user, today=today)
    start, end = _day_window(today)
    note = session.scalar(select(DailyWorkNote).where(DailyWorkNote.user_id == user.id, DailyWorkNote.work_date == today))
    metrics = {
        "overdue_customers": summary["overdue_count"],
        "due_today_customers": summary["today_count"],
        "new_customers": session.scalar(select(func.count()).select_from(Customer).where(Customer.customer_acquired_at == today)) or 0,
        "new_quotations": session.scalar(select(func.count()).select_from(Quotation).where(Quotation.created_at >= start, Quotation.created_at < end)) or 0,
        "new_orders": session.scalar(select(func.count()).select_from(Order).where(Order.order_date == today)) or 0,
        "new_followups": session.scalar(select(func.count()).select_from(FollowUp).where(FollowUp.followup_date == today)) or 0,
        "completed_tasks": session.scalar(select(func.count()).select_from(Task).where(Task.created_by_id == user.id, Task.completed_at >= start, Task.completed_at < end)) or 0,
    }
    return WorkbenchToday(
        today=today, metrics=metrics, tasks=_tasks_for_today(session, user, today),
        daily_note=DailyWorkNoteRead(work_date=note.work_date, content=note.content, updated_at=note.updated_at) if note else None,
    )


def create_task(session: Session, payload: TaskCreate, user: User) -> TaskRead:
    _ensure_admin(user)
    if payload.customer_id is not None and session.get(Customer, payload.customer_id) is None:
        raise NotFoundError("Customer not found.")
    task = Task(**payload.model_dump(), created_by_id=user.id, status="pending")
    session.add(task); session.commit(); session.refresh(task)
    customer = session.get(Customer, task.customer_id) if task.customer_id else None
    return _task_read(task, customer.company_name if customer else None)


def complete_task(session: Session, task_id: int, user: User) -> TaskRead:
    _ensure_admin(user)
    task = session.scalar(select(Task).where(Task.id == task_id, Task.created_by_id == user.id))
    if task is None: raise NotFoundError("Task not found.")
    task.status = "completed"; task.completed_at = datetime.now(timezone.utc)
    session.commit(); session.refresh(task)
    customer = session.get(Customer, task.customer_id) if task.customer_id else None
    return _task_read(task, customer.company_name if customer else None)


def delete_task(session: Session, task_id: int, user: User) -> None:
    _ensure_admin(user)
    task = session.scalar(select(Task).where(Task.id == task_id, Task.created_by_id == user.id))
    if task is None: raise NotFoundError("Task not found.")
    session.delete(task); session.commit()


def save_daily_note(session: Session, payload: DailyWorkNoteUpdate, user: User) -> DailyWorkNoteRead:
    _ensure_admin(user)
    today = shanghai_today()
    note = session.scalar(select(DailyWorkNote).where(DailyWorkNote.user_id == user.id, DailyWorkNote.work_date == today))
    if note is None:
        note = DailyWorkNote(user_id=user.id, work_date=today, content=payload.content)
        session.add(note)
    else:
        note.content = payload.content
    session.commit(); session.refresh(note)
    return DailyWorkNoteRead(work_date=note.work_date, content=note.content, updated_at=note.updated_at)
