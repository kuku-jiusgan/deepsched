from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models import Instrument, InstrumentCapability, MaintenanceWindow, InstrumentFault
from app.schemas.schemas import (
    InstrumentCreate, InstrumentOut, CapabilityCreate, CapabilityOut,
    MaintenanceCreate, MaintenanceOut, FaultCreate, FaultOut
)

router = APIRouter(prefix="/api/v1/instruments", tags=["instruments"])

@router.post("", response_model=InstrumentOut)
def create_instrument(data: InstrumentCreate, db: Session = Depends(get_db)):
    inst = Instrument(
        name=data.name, brand=data.brand, model=data.model,
        location=data.location, buffer_rate=data.buffer_rate,
        switchover_base_hours=data.switchover_base_hours
    )
    db.add(inst)
    db.flush()
    for cap in data.capabilities:
        db.add(InstrumentCapability(instrument_id=inst.id, tag_name=cap.tag_name, tag_value=cap.tag_value))
    db.commit()
    db.refresh(inst)
    return inst

@router.get("", response_model=List[InstrumentOut])
def list_instruments(db: Session = Depends(get_db)):
    return db.query(Instrument).all()

@router.get("/{inst_id}", response_model=InstrumentOut)
def get_instrument(inst_id: int, db: Session = Depends(get_db)):
    inst = db.query(Instrument).filter(Instrument.id == inst_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="仪器不存在")
    return inst

@router.put("/{inst_id}", response_model=InstrumentOut)
def update_instrument(inst_id: int, data: InstrumentCreate, db: Session = Depends(get_db)):
    inst = db.query(Instrument).filter(Instrument.id == inst_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="仪器不存在")
    inst.name = data.name
    inst.brand = data.brand
    inst.model = data.model
    inst.location = data.location
    inst.buffer_rate = data.buffer_rate
    inst.switchover_base_hours = data.switchover_base_hours
    # Replace capabilities
    db.query(InstrumentCapability).filter(InstrumentCapability.instrument_id == inst_id).delete()
    for cap in data.capabilities:
        db.add(InstrumentCapability(instrument_id=inst_id, tag_name=cap.tag_name, tag_value=cap.tag_value))
    db.commit()
    db.refresh(inst)
    return inst

@router.post("/{inst_id}/capabilities", response_model=CapabilityOut)
def add_capability(inst_id: int, data: CapabilityCreate, db: Session = Depends(get_db)):
    cap = InstrumentCapability(instrument_id=inst_id, tag_name=data.tag_name, tag_value=data.tag_value)
    db.add(cap)
    db.commit()
    db.refresh(cap)
    return cap

@router.post("/{inst_id}/maintenance", response_model=MaintenanceOut)
def add_maintenance(inst_id: int, data: MaintenanceCreate, db: Session = Depends(get_db)):
    mw = MaintenanceWindow(
        instrument_id=inst_id, start_time=data.start_time,
        end_time=data.end_time, mw_type=data.mw_type, description=data.description
    )
    db.add(mw)
    db.commit()
    db.refresh(mw)
    return mw

@router.get("/{inst_id}/maintenance", response_model=List[MaintenanceOut])
def list_maintenance(inst_id: int, db: Session = Depends(get_db)):
    return db.query(MaintenanceWindow).filter(MaintenanceWindow.instrument_id == inst_id).all()

@router.post("/{inst_id}/fault", response_model=FaultOut)
def report_fault(inst_id: int, data: FaultCreate, db: Session = Depends(get_db)):
    inst = db.query(Instrument).filter(Instrument.id == inst_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="仪器不存在")
    inst.status = "fault"
    fault = InstrumentFault(instrument_id=inst_id, description=data.description)
    db.add(fault)
    db.commit()
    db.refresh(fault)
    return fault

@router.put("/{inst_id}/fault/{fault_id}/resolve", response_model=FaultOut)
def resolve_fault(inst_id: int, fault_id: int, db: Session = Depends(get_db)):
    fault = db.query(InstrumentFault).filter(
        InstrumentFault.id == fault_id, InstrumentFault.instrument_id == inst_id
    ).first()
    if not fault:
        raise HTTPException(status_code=404, detail="故障记录不存在")
    from datetime import datetime
    fault.resolved_at = datetime.now()
    fault.status = "resolved"
    inst = db.query(Instrument).filter(Instrument.id == inst_id).first()
    inst.status = "active"
    db.commit()
    return fault
