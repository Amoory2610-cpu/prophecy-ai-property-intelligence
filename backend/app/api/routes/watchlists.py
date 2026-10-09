from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DB, CurrentUser
from app.api.routes.properties import _out as property_out
from app.models import Property, Watchlist, WatchlistItem
from app.schemas import WatchlistCreate, WatchlistItemIn, WatchlistOut, WatchlistUpdate
from app.services import deals

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


def _out(w: Watchlist) -> dict:
    return WatchlistOut(
        id=w.id,
        name=w.name,
        description=w.description,
        created_at=w.created_at,
        items=[
            {
                "id": i.id,
                "property_id": i.property_id,
                "note": i.note,
                "added_at": i.added_at,
                "property": property_out(i.property),
            }
            for i in w.items
        ],
    ).model_dump(mode="json")


@router.get("")
def list_watchlists(user: CurrentUser, db: DB):
    rows = db.scalars(select(Watchlist).where(Watchlist.owner_id == user.id).order_by(Watchlist.created_at))
    return [_out(w) for w in rows]


@router.post("", status_code=201)
def create_watchlist(body: WatchlistCreate, user: CurrentUser, db: DB):
    w = Watchlist(owner_id=user.id, name=body.name.strip(), description=body.description)
    db.add(w)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A watchlist with this name already exists") from None
    db.refresh(w)
    return _out(w)


@router.get("/{watchlist_id}")
def get_watchlist(watchlist_id: uuid.UUID, user: CurrentUser, db: DB):
    return _out(deals.get_owned(db, Watchlist, watchlist_id, user))


@router.patch("/{watchlist_id}")
def update_watchlist(watchlist_id: uuid.UUID, body: WatchlistUpdate, user: CurrentUser, db: DB):
    w = deals.get_owned(db, Watchlist, watchlist_id, user)
    if body.name is not None:
        w.name = body.name.strip()
    if body.description is not None:
        w.description = body.description
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A watchlist with this name already exists") from None
    db.refresh(w)
    return _out(w)


@router.delete("/{watchlist_id}", status_code=204)
def delete_watchlist(watchlist_id: uuid.UUID, user: CurrentUser, db: DB):
    db.delete(deals.get_owned(db, Watchlist, watchlist_id, user))
    db.commit()


@router.post("/{watchlist_id}/items", status_code=201)
def add_item(watchlist_id: uuid.UUID, body: WatchlistItemIn, user: CurrentUser, db: DB):
    w = deals.get_owned(db, Watchlist, watchlist_id, user)
    deals.get_owned(db, Property, body.property_id, user)
    if any(i.property_id == body.property_id for i in w.items):
        raise HTTPException(status_code=409, detail="Property is already on this watchlist")
    w.items.append(WatchlistItem(property_id=body.property_id, note=body.note))
    db.commit()
    db.refresh(w)
    return _out(w)


@router.delete("/{watchlist_id}/items/{property_id}", status_code=204)
def remove_item(watchlist_id: uuid.UUID, property_id: uuid.UUID, user: CurrentUser, db: DB):
    w = deals.get_owned(db, Watchlist, watchlist_id, user)
    item = next((i for i in w.items if i.property_id == property_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Property is not on this watchlist")
    w.items.remove(item)
    db.commit()
