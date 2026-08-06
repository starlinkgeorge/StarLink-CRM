from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.user import User, UserRole
from app.services.errors import ForbiddenError


def customer_scope(user: User):
    """Return a customer owner filter for sales users, or no filter for wider roles."""
    if user.role is UserRole.SALES:
        return Customer.owner_id == user.id
    return None


def ensure_customer_read_access(user: User, customer: Customer) -> None:
    if user.role is UserRole.SALES and customer.owner_id != user.id:
        raise ForbiddenError("You may only access customers assigned to you.")


def ensure_customer_manage_access(user: User, customer: Customer) -> None:
    if user.role is UserRole.VIEWER:
        raise ForbiddenError("Viewer accounts have read-only access.")
    ensure_customer_read_access(user, customer)


def ensure_user_management_access(user: User) -> None:
    if user.role is not UserRole.ADMIN:
        raise ForbiddenError("Only administrators may manage users.")
