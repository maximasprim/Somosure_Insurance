"""Audit trail: who did what, when, to which record, and why.

Three cooperating pieces (see docs/AUDIT_TRAIL.md for the overview):

  context.py     - the per-request "who/where/why" carried through a request
  capture.py     - SQLAlchemy listeners that record every create/update/delete
                   of a tracked record, INSIDE the same database transaction as
                   the change itself (so a change can never exist without its
                   audit row, and a rolled-back change leaves none)
  middleware.py  - records each mutating (and sensitive read) HTTP request with
                   its outcome, including refused and failed attempts, and
                   extracts the staff member's stated reason

Everything here is written to NEVER break the request it observes: any failure
is logged and swallowed.
"""
