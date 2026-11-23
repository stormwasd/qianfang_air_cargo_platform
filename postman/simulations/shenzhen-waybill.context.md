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
2026-11-02: Below-45kg chargeable-weight cabin policy passed 57 related regression
tests, followed by all five policy test methods after adding explicit C-cabin
suggestions. Across both runs KingGo served 407 requests; all 71 below-45
check/submit bodies sent F/F舱. The 45kg boundary, metadata/config precedence,
snapshot execution, rejection and unknown-submit protections were covered.
At/above-45 original cabin adjustment remained available. These are local caller
observations; real airline acceptance and final display still need business verification.
2026-11-02: 52 storage-note, direct-waybill, cabin, diagnostic, void and
post-processing tests passed. KingGo served 210 HTTP requests; all 82
check/submit form bodies kept transNote separate from goodsName. Empty notes,
old pending snapshots, CRLF/LF and special characters were covered. The local
port was used to reuse existing test wiring; no production origin or proxy
configuration changed. The simulation was stopped after verification.
Current evidence and remaining live-provider uncertainty are recorded in
shenzhen-waybill.context.yaml. No live waybill was created or changed.
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
