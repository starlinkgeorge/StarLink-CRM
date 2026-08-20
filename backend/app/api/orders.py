from functools import wraps
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.order import OrderPaymentStatus, OrderProductionStatus, OrderShippingStatus
from app.models.user import User
from app.schemas.order import OrderCreate, OrderPage, OrderProfitAnalytics, OrderProfitPeriod, OrderRead, OrderUpdate, WonOrderBackfillPreview, WonOrderBackfillRequest, WonOrderBackfillResult
from app.services import opportunity_service, order_profit_service, order_service
from app.services.errors import ConflictError, ForbiddenError, NotFoundError
router=APIRouter(prefix="/orders",tags=["orders"])
def guard(fn):
 @wraps(fn)
 def wrapped(*args,**kwargs):
  try:return fn(*args,**kwargs)
  except NotFoundError as e: raise HTTPException(404,detail=str(e)) from e
  except ForbiddenError as e: raise HTTPException(403,detail=str(e)) from e
  except ConflictError as e: raise HTTPException(409,detail=str(e)) from e
 return wrapped
@router.get("",response_model=OrderPage)
@guard
def list_orders(limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0),q:str|None=None,customer_id:int|None=Query(None,gt=0),start_date:date|None=None,end_date:date|None=None,payment_status:OrderPaymentStatus|None=None,production_status:OrderProductionStatus|None=None,shipping_status:OrderShippingStatus|None=None,session:Session=Depends(get_db_session),current_user:User=Depends(get_current_user)):
 items,total=order_service.list_orders(session,current_user,limit,offset,q,customer_id,start_date,end_date,payment_status,production_status,shipping_status); return OrderPage(items=items,total=total,limit=limit,offset=offset)
@router.post("",response_model=OrderRead,status_code=status.HTTP_201_CREATED)
@guard
def create_order(payload:OrderCreate,session:Session=Depends(get_db_session),current_user:User=Depends(get_current_user)): return order_service.create_order(session,payload,current_user)
@router.get("/analytics/profit", response_model=OrderProfitAnalytics)
@guard
def order_profit_analytics(
    period: OrderProfitPeriod = OrderProfitPeriod.MONTH,
    start_date: date | None = None,
    end_date: date | None = None,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    try:
        return order_profit_service.get_profit_analytics(
            session, current_user, period, start_date, end_date
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
@router.get("/by-quotation/{quotation_id}",response_model=OrderRead|None)
@guard
def by_quote(quotation_id:int,session:Session=Depends(get_db_session),current_user:User=Depends(get_current_user)): return order_service.quotation_order(session,current_user,quotation_id)
@router.get("/won-backfill/preview", response_model=WonOrderBackfillPreview)
@guard
def won_backfill_preview(session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)):
 return opportunity_service.preview_historical_won_order_backfill(session, current_user)
@router.post("/won-backfill", response_model=WonOrderBackfillResult)
@guard
def won_backfill(payload: WonOrderBackfillRequest, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)):
 return opportunity_service.backfill_historical_won_orders(session, current_user, fallback_order_date=payload.fallback_order_date)
@router.get("/{order_id}",response_model=OrderRead)
@guard
def get_order(order_id:int,session:Session=Depends(get_db_session),current_user:User=Depends(get_current_user)): return order_service.get_order(session,current_user,order_id)
@router.put("/{order_id}",response_model=OrderRead)
@guard
def update_order(order_id:int,payload:OrderUpdate,session:Session=Depends(get_db_session),current_user:User=Depends(get_current_user)): return order_service.update_order(session,order_id,payload,current_user)
@router.delete("/{order_id}",status_code=204)
@guard
def delete_order(order_id:int,session:Session=Depends(get_db_session),current_user:User=Depends(get_current_user)): order_service.delete_order(session,order_id,current_user)
