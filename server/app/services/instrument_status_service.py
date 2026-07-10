from typing import Optional

from app.models import Instrument, TimeSlot


PROTECTED_STATUSES = {"fault", "maintenance"}


def list_instruments_with_effective_status(db, include_unavailable: bool = False):
    query = db.query(Instrument)
    if not include_unavailable:
        query = query.filter(Instrument.availability_status == "available")
    instruments = query.all()
    for instrument in instruments:
        instrument.status = effective_instrument_status(db, instrument)
    return instruments


def effective_instrument_status(db, instrument: Instrument) -> str:
    if instrument.status in PROTECTED_STATUSES:
        return instrument.status
    if _has_running_slot(db, instrument.id):
        return "running"
    return "idle"


def mark_instrument_running(db, instrument_id: Optional[int]) -> None:
    if not instrument_id:
        return
    instrument = db.query(Instrument).filter(Instrument.id == instrument_id).first()
    if instrument and instrument.status not in PROTECTED_STATUSES:
        instrument.status = "running"


def refresh_instrument_status(db, instrument_id: Optional[int]) -> None:
    if not instrument_id:
        return
    instrument = db.query(Instrument).filter(Instrument.id == instrument_id).first()
    if instrument:
        instrument.status = effective_instrument_status(db, instrument)


def _has_running_slot(db, instrument_id: int) -> bool:
    return db.query(TimeSlot.id).filter(
        TimeSlot.instrument_id == instrument_id,
        TimeSlot.status == "running",
    ).first() is not None
