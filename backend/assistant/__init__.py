"""Job-drafting assistant.

The assistant is a proposer: it fills the same job form a user would, explains
the pipeline, and runs read-only checks (SciCap invoke, SciGuard validate).
Nothing in this package submits or executes a job. Submission happens only in
``backend.routes.assistant.approve`` after a human clicks Approve, and goes
through the same submit endpoints the manual form uses.
"""

from backend.assistant.drafting import Draft, draft_job, infer_instance
from backend.assistant.gates import run_checks, gate_status
from backend.assistant.explain import explain_target

__all__ = [
    "Draft",
    "draft_job",
    "infer_instance",
    "run_checks",
    "gate_status",
    "explain_target",
]
