# rpa-departure local verification

## Purpose

Exercise the repository's real RPA, KingGo and Ctrip clients against the local
examples in `../mocks/rpa-departure/default.js`, `../mocks/kinggo/default.js` and
`../mocks/ctrip-times/default.js`. These are repository fixtures, not published
provider mocks. The Ctrip fixture is synthetic, derived from the existing
client's JSON contract and regression tests.

## Execution

Run `postman simulation run postman/simulations/rpa-departure.sim.yaml --port 4912 --output ndjson --no-history`.
Wait for `listening`, set `RPA_DEPARTURE_SIMULATION_URL=http://127.0.0.1:4912/rpa`,
then run `python -m unittest tests.test_shenzhen_air_flight_info_logging tests.test_shenzhen_air_detail_actual_times tests.test_departure_tracking_schedule tests.test_shenzhen_air_flight_info tests.test_shenzhen_air_direct_billing_time_container tests.test_ctrip_client tests.test_csa_departure_rpa_success tests.test_tracking_execution_time tests.test_shenzhen_air_direct_transit_loading tests.test_shenzhen_air_direct_approval -q`.
Inspect the simulation's request events, then stop it with Ctrl+C.

## Assumptions

- The October 27, 2026 run used temporary SQLite databases and patched signing
  with synthetic credentials. It verifies HTTP parsing, persistence and response
  mapping, not live KingGo authentication or today's upstream HTML. (observed 2026-10-27)
- The Excel regression requires the repository's pandas 2.2.3-compatible runtime.
  The local environment had pandas 3.0.6 with openpyxl 3.1.2; the successful run
  used pandas 2.2.3 and pytz from a temporary directory via PYTHONPATH, without
  changing project dependencies. (observed 2026-10-27)
- Ctrip tests route the real client's HTTP requests to the local simulation
  using a request hook. GUID handling, payload construction, time parsing and
  retries execute locally; this does not verify live Ctrip availability or proxy
  behavior. No production service or database is changed. (observed 2026-10-27)

## Observations

<!-- begin:observations -->
2026-10-27 mixed identifiers: All 113 selected tests passed; KingGo, Ctrip and
RPA members all served requests. Three HTTP pages containing ZH9883, ZHT2F8 and
ZH30CU synchronized together; complete identifiers remained queryable, blank
actual departures stayed blank, and local detail backfill matched the full
identifier/date/segment. Before the fix, the added cases reproduced both the
parser rejection and the skipped local backfill. Live upstream was not called.

2026-10-27 diagnostics: All 109 selected tests passed; all three members served
requests. The real KingGo client logged the intentional HTTP 400 with its page
and status, and a one-page test limit logged the expected/collected totals.
Failure-log tests also checked HTML, pagination, transport, auth and persistence
errors, retained stored rows/retry throttling, and omitted synthetic secrets
from raw cells, responses, signed URLs and exception causes.

2026-10-27 review: All 102 selected tests passed; KingGo, RPA and Ctrip members
all served requests. Three added database interleaving tests (four scenarios)
first reproduced stale local/HTTP results overwriting another session's saved
times, then passed with conditional SQL updates. This checks deterministic
interleavings in SQLite, not concurrent-load behavior of production MySQL.

2026-10-27: All 99 selected tests passed in the final run, including real-client
HTTP requests to the local KingGo, RPA and Ctrip members. Scheduling requested
the parent's billing flight ZH8985; detail lookups requested ZH9203 and converted
the destination city to XIY. Duplicate container rows shared one Ctrip lookup
per sync round while retaining independent attempt state. Disabling fallback
made no Ctrip request; simulated 503 retries preserved KingGo planned time and
previously saved actual time. Missing export IDs were rejected without changing
existing details. These observations establish local contract/persistence
behavior, not availability or authentication of the live providers.

<!-- end:observations -->
