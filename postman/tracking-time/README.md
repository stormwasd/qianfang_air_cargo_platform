# Tracking list acquisition-time contract

The existing `data_update_time` response field remains nullable text in
`YYYY-MM-DD HH:mm` format, in Asia/Shanghai time. Its scope is the acquisition
type, not the current page, flight-date filter, or a particular waybill.

- Shenzhen approvals: last successful direct report download, separately for
  standard and wide-body; in RPA mode, the matched run's successful `endTime`.
- Shenzhen departures: last successful transit-loading main-table export
  download (`AwbQueryExport`); in RPA mode, the matched transit-loading run's
  successful `endTime`. Select the source using
  `SHENZHEN_AIR_TRANSIT_LOADING_EXECUTION_MODE`, independently of the
  billing/container detail mode. Detail requests never refresh this field.
- Southern approvals: last successful approval-data RPA run's `endTime`.
- Southern departures: last successful on-site product + cargo RPA run's
  `endTime`, never an approval-data run.

All successful RPA times are keyed separately from legacy data-completion
timestamps in `rpa_task_last_success`, with `_RPA_RUN` keys. Subsequent queue
processing/complete_task calls do not overwrite them. Existing direct approval
keys are retained; direct billing and transit-loading each use their own
`_DIRECT` key. No DDL is needed.

Naive RPA times are China local, as in the supplied RPA response; explicit UTC
or offset values are converted. Missing/malformed endTime falls back to the
time the backend confirmed success, with a warning. Older run reports cannot
move a newer success time backward. A failed run/request does not refresh time.

The field remains available for an empty result page. Without an acquisition
success record it is null: neither legacy completion times nor manually edited
business rows, approval imports, or detail creation times are substitutes.
New RPA/direct transit-loading keys populate on the first success after deployment;
this change does not fabricate or backdate historical execution records.

This is **not** a data-completeness guarantee. Existing queue consumption,
validation, completion flags and retries are unchanged. Timestamp writes use
their own short transaction; a write failure is logged and must not fail the
business task. No runtime query or RPA trigger is added to list requests.

Local regression: run the existing `rpa-departure.sim.yaml` on port 4912, set
`RPA_DEPARTURE_SIMULATION_URL=http://127.0.0.1:4912/rpa`, then run
`tests.test_csa_departure_rpa_success` and `tests.test_tracking_execution_time`.
The HTTP mock uses the repository client's contract and supplied logs, not a
published provider mock; it does not establish that production RPA wrote queues.
