"""Unit tests for remote-Docker status polling in the /api/jobs/progress path.

Covers the pure logic of ``_poll_remote_docker_status_batch`` with a mocked
backend (no SSH / remote host required): JobStatus->DB-status mapping, the
"unknown" skip, the non-remote-backend guard, and per-job error tolerance.
"""
from unittest.mock import patch

from backend.core.execution import JobStatus
import backend.main as m


class FakeJob:
    def __init__(self, jid):
        self.id = jid


class FakeBackend:
    def __init__(self, backend_type="remote_docker", statuses=None, raise_ids=None):
        self._bt = backend_type
        self._statuses = statuses or {}
        self._raise_ids = raise_ids or set()

    @property
    def backend_type(self):
        return self._bt

    def get_job_status(self, job_id):
        if job_id in self._raise_ids:
            raise RuntimeError("ssh down")
        return self._statuses[job_id]


def test_empty_jobs_returns_empty():
    assert m._poll_remote_docker_status_batch([]) == {}


def test_non_remote_backend_is_skipped():
    fb = FakeBackend(backend_type="slurm")
    with patch.object(m, "get_backend", return_value=fb):
        assert m._poll_remote_docker_status_batch([FakeJob("a")]) == {}


def test_maps_statuses_and_skips_unknown():
    jobs = [FakeJob("a"), FakeJob("b"), FakeJob("c")]
    fb = FakeBackend(
        statuses={
            "a": JobStatus.RUNNING,
            "b": JobStatus.COMPLETED,
            "c": JobStatus.UNKNOWN,
        }
    )
    with patch.object(m, "get_backend", return_value=fb):
        out = m._poll_remote_docker_status_batch(jobs)
    # unknown is intentionally omitted so the caller leaves the status unchanged
    assert out == {"a": "running", "b": "completed"}


def test_failed_status_maps_through():
    jobs = [FakeJob("x")]
    fb = FakeBackend(statuses={"x": JobStatus.FAILED})
    with patch.object(m, "get_backend", return_value=fb):
        assert m._poll_remote_docker_status_batch(jobs) == {"x": "failed"}


def test_per_job_exception_is_tolerated():
    jobs = [FakeJob("a"), FakeJob("b")]
    fb = FakeBackend(statuses={"b": JobStatus.COMPLETED}, raise_ids={"a"})
    with patch.object(m, "get_backend", return_value=fb):
        out = m._poll_remote_docker_status_batch(jobs)
    # 'a' raised -> skipped; 'b' still resolved
    assert out == {"b": "completed"}


def test_backend_unavailable_returns_empty():
    with patch.object(m, "get_backend", side_effect=RuntimeError("no backend")):
        assert m._poll_remote_docker_status_batch([FakeJob("a")]) == {}
