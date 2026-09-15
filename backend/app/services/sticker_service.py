from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sticker import Sticker, StickerEvent

# Only these forward transitions are allowed - prevents skipping steps
# (e.g. straight from "pending" to "dispatched") which is the
# fraud-prevention control spec §12 asks for. "cancelled" and "replaced"
# are reachable from most states, handled separately below.
ALLOWED_TRANSITIONS = {
    "pending": {"validated", "cancelled"},
    "validated": {"payment_confirmed", "cancelled"},
    "payment_confirmed": {"generating", "cancelled"},
    "generating": {"generated"},
    "generated": {"ready_for_collection"},
    "ready_for_collection": {"dispatched"},
    "dispatched": {"delivered", "replaced"},
    "delivered": {"replaced"},
}


async def advance_sticker(db: AsyncSession, sticker_id: str, to_status: str, actor_user_id: str | None, notes: str | None) -> Sticker:
    sticker = await db.get(Sticker, sticker_id)
    if not sticker:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sticker not found")

    allowed = ALLOWED_TRANSITIONS.get(sticker.status, set())
    if to_status not in allowed:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot move sticker from '{sticker.status}' to '{to_status}' - allowed next steps: {sorted(allowed) or 'none'}",
        )

    db.add(StickerEvent(sticker_id=sticker.id, from_status=sticker.status, to_status=to_status, actor_user_id=actor_user_id, notes=notes))
    sticker.status = to_status

    await db.commit()
    await db.refresh(sticker)
    return sticker
