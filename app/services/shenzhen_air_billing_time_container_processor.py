"""Persist KingGo/RPA billing-time and container rows using one mapping."""
from __future__ import annotations

from dataclasses import dataclass

from app.models.billing_time_container import ShenzhenAirBillingTimeContainer
from app.models.transit_loading import ShenzhenAirBookingExport
from app.services.shenzhen_air_flight_times import shenzhen_air_flight_times


@dataclass(frozen=True)
class BillingRowsPersistenceResult:
    """Outcome used by both the direct scheduler and the legacy RPA worker."""

    inserted_count: int
    has_invalid_flight: bool


async def persist_shenzhen_air_billing_rows(
    db,
    billing_data: list,
    waybill_number: str,
    booking_export_id: int,
) -> BillingRowsPersistenceResult:
    """Map and persist the nine-column KingGo/RPA table rows.

    The caller decides whether an empty/invalid result should be retried and
    when the source export can be marked complete.  Keeping those decisions
    outside this helper allows direct mode to avoid creating an RPA task.
    """
    db.query(ShenzhenAirBillingTimeContainer).filter(
        ShenzhenAirBillingTimeContainer.booking_export_id == booking_export_id
    ).delete()

    records = []
    has_invalid_flight = False
    for row in billing_data:
        if not isinstance(row, list) or len(row) < 9:
            continue
        sequence = str(row[0]).strip()
        if not sequence or sequence == "序号" or "合计" in str(row[1]):
            continue

        flight_number = str(row[1]).strip() if row[1] else ""
        if not flight_number:
            has_invalid_flight = True
        planned_time = None
        if flight_number:
            try:
                ctrip_times = await shenzhen_air_flight_times.get_flight_times(
                    flight_number,
                    str(row[2]).strip(),
                    f"{str(row[4]).strip()}-{str(row[5]).strip()}",
                    required_times=("planned_time",),
                )
                planned_time = (ctrip_times or {}).get("planned_time")
            except Exception as exc:
                # A missing Ctrip value must not discard otherwise valid
                # KingGo data; the existing actual-time sync can retry later.
                print(f"获取深航计飞时间失败: {exc}")

        records.append(ShenzhenAirBillingTimeContainer(
            booking_export_id=booking_export_id,
            waybill_number_8=waybill_number,
            sequence=sequence,
            flight_number=flight_number or None,
            flight_date=str(row[2]).strip(),
            billing_time=str(row[3]).strip(),
            origin=str(row[4]).strip(),
            destination=str(row[5]).strip(),
            quantity=str(row[6]).strip(),
            weight=str(row[7]).strip(),
            container=str(row[8]).strip(),
            planned_time=planned_time,
            actual_time=None,
            actual_time_attempts="0",
        ))

    if records:
        db.add_all(records)
    # Commit the delete as well as inserts.  This is important for direct
    # mode, which has no RPA task whose later commit would flush the session.
    db.commit()
    return BillingRowsPersistenceResult(len(records), has_invalid_flight)


def mark_shenzhen_air_export_completed(db, booking_export_id: int) -> None:
    """Mark a source Excel row complete after all returned rows are valid."""
    export_record = db.query(ShenzhenAirBookingExport).filter(
        ShenzhenAirBookingExport.id == booking_export_id
    ).first()
    if export_record:
        export_record.departure_tracking_completed = "1"
        db.commit()
