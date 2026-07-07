"""Endpoint-level test for remote-Docker status transitions in /api/jobs/progress.

Uses a real in-memory SQLite DB (no remote host / SSH): insert a remote_docker
job as 'pending', mock the backend to report a live status, hit the endpoint,
and assert both the response and the persisted DB row transition correctly.
"""
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool



@pytest.fixture
def Session():
    """In-memory SQLite shared across connections (StaticPool)."""
    from backend.core.database import Base

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    yield maker
    Base.metadata.drop_all(engine)


def _insert_remote_job(maker, jid="job-remote-1", status="pending"):
    from backend.models.job import Job

    db = maker()
    db.add(
        Job(
            id=jid,
            backend_type="remote_docker",
            backend_job_id=None,
            pipeline_name="freesurfer",
            pipeline_version="7.4.1",
            container_image="test/image:latest",
            input_files=["/data/sub-01/t1w.nii.gz"],
            parameters={},
            resources={},
            status=status,
            progress=0,
            output_dir="/tmp/out",
            deleted=False,
        )
    )
    db.commit()
    db.close()
    return jid


def _run_progress(maker, mapped_status):
    """Call GET /api/jobs/progress with get_db bound to the test DB.

    ``_poll_remote_docker_status_batch`` (the SSH poller, unit-tested separately)
    is stubbed to report ``mapped_status`` for the remote jobs — so this test
    exercises the endpoint's status-transition handling, not the SSH round-trip.
    ``mapped_status=None`` simulates the poller returning nothing (e.g. UNKNOWN).
    """
    from fastapi.testclient import TestClient
    import backend.main as m
    from backend.core.database import get_db

    def override_get_db():
        db = maker()
        try:
            yield db
        finally:
            db.close()

    def fake_poll(jobs):
        return {j.id: mapped_status for j in jobs} if mapped_status else {}

    m.app.dependency_overrides[get_db] = override_get_db
    try:
        with patch.object(m, "_poll_remote_docker_status_batch", side_effect=fake_poll), \
             patch.object(m, "_poll_slurm_progress", return_value=None):
            client = TestClient(m.app)
            resp = client.get("/api/jobs/progress")
        assert resp.status_code == 200, resp.text
        return {j["id"]: j for j in resp.json()["jobs"]}
    finally:
        m.app.dependency_overrides.pop(get_db, None)


def test_remote_job_transitions_to_completed(Session):
    jid = _insert_remote_job(Session, status="pending")
    jobs = _run_progress(Session, "completed")

    assert jid in jobs
    assert jobs[jid]["status"] == "completed"
    assert jobs[jid]["progress"] == 100

    # persisted to the DB
    from backend.models.job import Job

    db = Session()
    row = db.query(Job).filter(Job.id == jid).first()
    assert row.status == "completed"
    assert row.completed_at is not None
    assert row.exit_code == 0
    db.close()


def test_remote_job_transitions_to_running(Session):
    jid = _insert_remote_job(Session, status="pending")
    jobs = _run_progress(Session, "running")

    assert jobs[jid]["status"] == "running"

    from backend.models.job import Job

    db = Session()
    row = db.query(Job).filter(Job.id == jid).first()
    assert row.status == "running"
    assert row.started_at is not None
    assert row.current_phase == "Running on remote server"
    db.close()


def test_remote_job_unchanged_when_status_unknown(Session):
    jid = _insert_remote_job(Session, status="running")
    jobs = _run_progress(Session, None)  # poller reports nothing for UNKNOWN

    # UNKNOWN must not change the job's status
    assert jobs[jid]["status"] == "running"

    from backend.models.job import Job

    db = Session()
    row = db.query(Job).filter(Job.id == jid).first()
    assert row.status == "running"
    assert row.completed_at is None
    db.close()
