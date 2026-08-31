from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.user import User, UserRole
from app.models.workbench import DailyWorkNote, Task, WorkbenchDailyMetric
from app.schemas.workbench import DailyWorkNoteRead, DailyWorkNoteUpdate, TaskCreate, TaskRead, WorkbenchMetricRead, WorkbenchMetricUpdate, WorkbenchToday
from app.services.errors import ForbiddenError, NotFoundError
from app.services.followup_reminder_service import shanghai_today

WorkbenchPeriod = Literal["today", "week", "month"]


def _ensure_admin(user: User) -> None:
    if user.role is not UserRole.ADMIN:
        raise ForbiddenError("Only Admin accounts can use the daily workbench.")


def _period_start(today: date, period: WorkbenchPeriod) -> date:
    if period == "week":
        return date.fromordinal(today.toordinal() - today.weekday())
    if period == "month":
        return today.replace(day=1)
    return today


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


def _metric_reads(session: Session, user: User, start: date, today: date) -> list[WorkbenchMetricRead]:
    rows = session.scalars(
        select(WorkbenchDailyMetric)
        .where(
            WorkbenchDailyMetric.user_id == user.id,
            WorkbenchDailyMetric.work_date >= start,
            WorkbenchDailyMetric.work_date <= today,
        )
        .order_by(WorkbenchDailyMetric.metric_group, WorkbenchDailyMetric.metric_key)
    ).all()
    totals: dict[tuple[str, str], tuple[Decimal, Decimal]] = {}
    for row in rows:
        key = (row.metric_group, row.metric_key)
        completed, target = totals.get(key, (Decimal("0"), Decimal("0")))
        totals[key] = (completed + row.completed_value, target + row.target_value)
    return [
        WorkbenchMetricRead(metric_group=group, metric_key=key, completed_value=completed, target_value=target)
        for (group, key), (completed, target) in totals.items()
    ]


def get_workbench(session: Session, user: User, period: WorkbenchPeriod = "today") -> WorkbenchToday:
    _ensure_admin(user)
    today = shanghai_today()
    start = _period_start(today, period)
    note = None
    if period == "today":
        note = session.scalar(select(DailyWorkNote).where(DailyWorkNote.user_id == user.id, DailyWorkNote.work_date == today))
    return WorkbenchToday(
        today=today,
        period=period,
        tasks=_tasks_for_today(session, user, today) if period == "today" else [],
        daily_note=DailyWorkNoteRead(work_date=note.work_date, content=note.content, updated_at=note.updated_at) if note else None,
        metrics=_metric_reads(session, user, start, today),
    )


def update_metric(session: Session, payload: WorkbenchMetricUpdate, user: User) -> WorkbenchMetricRead:
    _ensure_admin(user)
    today = shanghai_today()
    metric = session.scalar(
        select(WorkbenchDailyMetric).where(
            WorkbenchDailyMetric.user_id == user.id,
            WorkbenchDailyMetric.work_date == today,
            WorkbenchDailyMetric.metric_group == payload.metric_group,
            WorkbenchDailyMetric.metric_key == payload.metric_key,
        )
    )
    if metric is None:
        metric = WorkbenchDailyMetric(
            user_id=user.id, work_date=today, metric_group=payload.metric_group, metric_key=payload.metric_key,
            completed_value=payload.completed_value, target_value=payload.target_value,
        )
        session.add(metric)
    else:
        metric.completed_value = payload.completed_value
        metric.target_value = payload.target_value
    session.commit(); session.refresh(metric)
    return WorkbenchMetricRead(metric_group=metric.metric_group, metric_key=metric.metric_key, completed_value=metric.completed_value, target_value=metric.target_value)


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
