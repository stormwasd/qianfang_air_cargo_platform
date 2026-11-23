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
    if not booking_export_id:
        # The model requires an export association. Reject malformed legacy
        # tasks before looking up times or replacing any existing details.
        raise ValueError("深航走货明细缺少导出记录ID")
    scope = ShenzhenAirBillingTimeContainer.booking_export_id == booking_export_id

    # Refreshes replace container rows, but must not erase an already resolved
    # flight's actual time when an upstream lookup is temporarily unavailable.
    def flight_key(flight, day, origin, destination):
        return (str(flight or "").strip().upper(), str(day or "").strip().replace("/", "-")[:10],
                str(origin or "").strip(), str(destination or "").strip())

    records = []
    has_invalid_flight = False
    times_by_flight = {}
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
        key = flight_key(flight_number, row[2], row[4], row[5])
        actual_time = None
        if flight_number:
            try:
                if key not in times_by_flight:
                    times_by_flight[key] = await shenzhen_air_flight_times.get_flight_times(
                        flight_number,
                        str(row[2]).strip(),
                        f"{str(row[4]).strip()}-{str(row[5]).strip()}",
                        required_times=("planned_time", "actual_time"),
                    )
                flight_times = times_by_flight[key] or {}
                planned_time = flight_times.get("planned_time")
                actual_time = flight_times.get("actual_time") or actual_time
            except Exception as exc:
                # A missing Ctrip value must not discard otherwise valid
                # KingGo data; the existing actual-time sync can retry later.
                times_by_flight[key] = None
                print(f"获取深航航班时间失败: waybill={waybill_number}, flight={flight_number}, error={exc}")

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
            actual_time=actual_time,
            actual_time_attempts="0",
        ))

    # Keep the write transaction short: finish all external lookups first.
    # Re-read here so a background sync during those lookups is preserved too.
    existing = db.query(ShenzhenAirBillingTimeContainer).filter(
        scope
    ).populate_existing().with_for_update().all()
    known_times = {
        flight_key(row.flight_number, row.flight_date, row.origin, row.destination): row.actual_time
        for row in existing if row.actual_time
    }
    for row in records:
        if not row.actual_time:
            row.actual_time = known_times.get(
                flight_key(row.flight_number, row.flight_date, row.origin, row.destination)
            )
    db.query(ShenzhenAirBillingTimeContainer).filter(scope).delete(synchronize_session=False)
    if records:
        db.add_all(records)
    # Commit the delete as well as inserts.  This is important for direct
    # mode, which has no RPA task whose later commit would flush the session.
    actual_time_count = sum(bool(row.actual_time) for row in records)
    db.commit()
    print(
        "[ShenzhenAirBilling] 明细入库完成: "
        f"waybill={waybill_number}, export_id={booking_export_id}, rows={len(records)}, "
        f"actual_time_rows={actual_time_count}"
    )
    return BillingRowsPersistenceResult(len(records), has_invalid_flight)


def mark_shenzhen_air_export_completed(db, booking_export_id: int) -> None:
    """Mark a source Excel row complete after all returned rows are valid."""
    export_record = db.query(ShenzhenAirBookingExport).filter(
        ShenzhenAirBookingExport.id == booking_export_id
    ).first()
    if export_record:
        export_record.departure_tracking_completed = "1"
        db.commit()
