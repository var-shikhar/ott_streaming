from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.billing_client import get_razorpay_client
from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.entitlement import active_subscription
from app.errors import ApiError

router = APIRouter(prefix="/api/v1", tags=["billing"])


class SubscribeIn(BaseModel):
    plan_id: int


def sub_out(sub: models.Subscription) -> dict:
    return {
        "status": sub.status,
        "plan": {"id": sub.plan.id, "name": sub.plan.name,
                 "price_inr": sub.plan.price_inr, "interval": sub.plan.interval},
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
    }


@router.get("/plans")
def list_plans(db: Session = Depends(get_db)):
    rows = (db.query(models.Plan).filter(models.Plan.is_active.is_(True))
              .order_by(models.Plan.price_inr).all())
    return [{"id": p.id, "name": p.name, "price_inr": p.price_inr, "interval": p.interval}
            for p in rows]


@router.post("/subscriptions", status_code=201)
def create_subscription(body: SubscribeIn, db: Session = Depends(get_db),
                        user=Depends(get_current_user)):
    plan = db.get(models.Plan, body.plan_id)
    if not plan or not plan.is_active:
        raise ApiError(404, "not_found", "Plan not found")
    if active_subscription(db, user) is not None:
        raise ApiError(409, "already_subscribed", "You already have an active subscription")
    total_count = {"weekly": 52, "monthly": 12, "yearly": 5}.get(plan.interval, 12)
    rzp = get_razorpay_client().subscription.create({
        "plan_id": plan.razorpay_plan_id, "total_count": total_count, "customer_notify": 1,
        "notes": {"user_id": str(user.id)},
    })
    db.add(models.Subscription(user_id=user.id, plan_id=plan.id,
                               razorpay_subscription_id=rzp["id"], status="created"))
    db.commit()
    return {"razorpay_subscription_id": rzp["id"], "razorpay_key_id": settings.razorpay_key_id}


@router.post("/subscriptions/cancel")
def cancel_subscription(db: Session = Depends(get_db), user=Depends(get_current_user)):
    sub = active_subscription(db, user)
    if sub is None:
        raise ApiError(404, "no_subscription", "No active subscription to cancel")
    get_razorpay_client().subscription.cancel(sub.razorpay_subscription_id,
                                              {"cancel_at_cycle_end": 1})
    return {"status": "ok", "message": "Subscription will end at the current period"}


@router.get("/subscriptions/current")
def current_subscription(db: Session = Depends(get_db), user=Depends(get_current_user)):
    sub = active_subscription(db, user)
    return sub_out(sub) if sub else None
