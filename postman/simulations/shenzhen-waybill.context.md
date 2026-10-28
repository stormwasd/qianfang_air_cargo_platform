# shenzhen-waybill local verification

## Purpose

Run the real Shenzhen direct waybill client, persistent worker and task query
against the repository's KingGo fixture in `../mocks/kinggo/default.js`.

## Execution

Run `postman simulation run postman/simulations/shenzhen-waybill.sim.yaml --port 4913 --output ndjson --no-history`.
After `listening`, set `KINGGO_SIM_ORIGIN=http://127.0.0.1:4913/kinggo` and
`RPA_DEPARTURE_SIMULATION_URL=http://127.0.0.1:4913/rpa` (the latter only derives
the sibling KingGo URL for flight-table tests).
Run `python -m unittest tests.test_shenzhen_air_direct_waybill_cabin tests.test_shenzhen_air_direct_waybill_logging tests.test_shenzhen_air_direct_waybill tests.test_shenzhen_air_direct_waybill_void tests.test_post_waybill_automation_guard tests.test_shenzhen_air_flight_info tests.test_china_southern_air_booking_volume -q`.
Inspect request events and stop the simulation with Ctrl+C.

## Assumptions

- Synthetic signing and temporary SQLite replace live credentials and business
  storage. The `BUSINESS_REJECT` example deliberately rejects weight 35 / charge
  weight 45 at submit; this does not establish KingGo's real validation rule.
  No real waybill is created. (observed 2026-10-28)
- The local Excel runtime needs the pandas 2.2.3 compatibility setup documented
  in `rpa-departure.context.md`. (observed 2026-10-28)
- The cabin rejection wording comes from the supplied real failure; `CABIN_*`
  follow-up responses are synthetic. Acceptance of synchronizing
  `cabinTypeName` and `cabinType` still needs real KingGo verification.
  (observed 2026-10-29)

## Observations

<!-- begin:observations -->
2026-10-29: KingGo served the real worker's cabin-correction traffic. Z/A retries
aligned name and code, retained the original oldCabinType and one candidate,
and confirmed once. Explicit repeat rejections and recheck/signing failures
before any next submit became failed and allowed manual execution; another
submit with HTTP/non-JSON/timeout or unconfirmed results stayed unknown.
No RPA or Ctrip member is configured for this run.
2026-10-28: KingGo served all simulation traffic. The actual HTTP submit rejection
reached the worker log and persisted task error with the upstream code/messages,
task identifiers and distinct weights. Check succeeded, submit was not retried,
the task remained unknown, and querying the waybill preserved both weights.
Client tests also checked redaction, malformed messages, auth, HTTP, non-JSON
and network failures. No RPA or Ctrip member is configured in this simulation.
<!-- end:observations -->
