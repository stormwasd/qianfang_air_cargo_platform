# CSA cargo-type defaults verification

## Purpose

Verify saved default name/code pairs through real order/booking payload builders
and the HTTP calculateCharge/createOrder client. The local fixture is based on
the repository client contract; provider mock discovery was not performed.

## Execution

Run `postman simulation run postman/simulations/csa-cargo-defaults.sim.yaml --port 4914 --output ndjson --no-history`.
After listening, set `CSA_CARGO_SIM_ORIGIN=http://127.0.0.1:4914/csa` and run
`python -m unittest tests.test_csa_cargo_type_defaults -q`.
Inspect request events and stop the simulation with Ctrl+C.

## Assumptions

Temporary SQLite holds configuration and dictionaries. Responses are synthetic;
`observedCargoType` is a test echo, not a real CSA response field. Credentials
and waybill numbers are synthetic. No live upstream is called and no stock is used.

## Observations

2026-10-29: All 80 selected tests passed, with no skips, including configuration
HTTP round trips, SQLite persistence, legacy defaults, order/booking requests,
CSA sync/volume/special-code/template regressions, postprocessing guards and
Shenzhen waybill/cabin/void regressions. The latter used the existing KingGo
simulation on port 4913 with KINGGO_SIM_ORIGIN set. CSA request events recorded
ordinary and lithium cargo independently with code 3006, and dangerous cargo
with code 3002, through both calculateCharge and createOrder. No live upstream
was called. This does not establish live authentication, fare availability or
successful real waybill creation.
