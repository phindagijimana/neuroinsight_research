"""
Bundled completed demo jobs with tiny EEG (+ T1) files for Viewer onboarding.

Seeded on API startup when MNE (and nibabel for the source-localization job) are installed.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

SAMPLE_EEG_PREP_JOB_ID = "00000000-0000-4000-8000-0000000ee101"
SAMPLE_EEG_SOURCE_JOB_ID = "00000000-0000-4000-8000-0000000ee102"

SAMPLE_JOB_IDS = frozenset({SAMPLE_EEG_PREP_JOB_ID, SAMPLE_EEG_SOURCE_JOB_ID})

SAMPLE_JOB_DISPLAY: dict[str, str] = {
    SAMPLE_EEG_PREP_JOB_ID: "Sample: EEG preprocessing",
    SAMPLE_EEG_SOURCE_JOB_ID: "Sample: EEG source localization (EEG + MRI)",
}

EEG_REL_PATH = "eeg/rest_demo_raw.fif"
T1_REL_PATH = "anatomy/t1w.nii.gz"


def _write_demo_fif(target: Path) -> bool:
    try:
        import mne
        import numpy as np
    except ImportError:
        return False

    target.parent.mkdir(parents=True, exist_ok=True)
    sfreq = 250.0
    duration_s = 8.0
    n_times = int(duration_s * sfreq)
    ch_names = ["Fp1", "Fp2", "Cz", "C3", "C4", "Oz", "P3", "P4"]
    info = mne.create_info(ch_names, sfreq, ch_types="eeg")
    rng = np.random.default_rng(42)
    t = np.arange(n_times, dtype=np.float64) / sfreq
    data = np.zeros((len(ch_names), n_times), dtype=np.float64)
    for i in range(len(ch_names)):
        data[i] = 1e-5 * (
            np.sin(2 * np.pi * 10.0 * t)
            + 0.35 * np.sin(2 * np.pi * 50.0 * t)
            + 0.45 * rng.standard_normal(n_times)
        )
    raw = mne.io.RawArray(data, info, verbose=False)
    raw.save(str(target), overwrite=True, verbose=False)
    return True


def _write_demo_t1w(target: Path) -> bool:
    try:
        import nibabel as nib
        import numpy as np
    except ImportError:
        return False

    target.parent.mkdir(parents=True, exist_ok=True)
    shape = (40, 48, 40)
    data = np.zeros(shape, dtype=np.float32)
    center = np.array([s / 2.0 for s in shape], dtype=np.float32)
    ii, jj, kk = np.indices(shape)
    r = np.sqrt((ii - center[0]) ** 2 + (jj - center[1]) ** 2 + (kk - center[2]) ** 2)
    data[r < 14] = 1.0
    data[r < 12] = 0.85
    img = nib.Nifti1Image(data, np.eye(4, dtype=np.float32))
    nib.save(img, str(target))
    return True


def _readme(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_sample_eeg_jobs() -> None:
    """Create output files and DB rows for demo jobs (idempotent)."""
    try:
        import mne  # noqa: F401
        import numpy  # noqa: F401
    except ImportError:
        logger.warning("MNE/numpy unavailable — sample EEG demo jobs not installed")
        return

    from backend.core.config import get_settings
    from backend.core.database import get_db_context
    from backend.models.job import Job

    settings = get_settings()
    completed = datetime.utcnow() - timedelta(days=1)
    base_outputs = Path(settings.data_dir) / "outputs"

    prep_dir = base_outputs / SAMPLE_EEG_PREP_JOB_ID
    if not _write_demo_fif(prep_dir / EEG_REL_PATH):
        logger.warning("Could not write sample FIF — skipping sample jobs")
        return
    _readme(
        prep_dir / "README_SAMPLE.txt",
        [
            "NeuroInsight Research — sample EEG preprocessing output",
            f"- {EEG_REL_PATH}: synthetic 8-channel resting EEG (demo)",
            "Open the app Viewer → Signal View and pick this file from job outputs.",
        ],
    )

    source_dir = base_outputs / SAMPLE_EEG_SOURCE_JOB_ID
    if not _write_demo_fif(source_dir / EEG_REL_PATH):
        logger.warning("Could not write sample FIF for source-localization job")
        return
    if not _write_demo_t1w(source_dir / T1_REL_PATH):
        logger.warning(
            "nibabel unavailable — sample source-localization job skipped "
            "(EEG preprocessing sample still available)"
        )
        with get_db_context() as db:
            stale = db.query(Job).filter(Job.id == SAMPLE_EEG_SOURCE_JOB_ID).first()
            if stale:
                stale.soft_delete()
            db.commit()
        _upsert_job_row(
            job_id=SAMPLE_EEG_PREP_JOB_ID,
            out_dir=prep_dir,
            pipeline_name="eeg_preprocessing",
            plugin_id="eeg_preprocessing",
            viewer_tab="eeg",
            completed=completed,
        )
        return

    _readme(
        source_dir / "README_SAMPLE.txt",
        [
            "NeuroInsight Research — sample EEG + MRI (source localization) demo",
            f"- {EEG_REL_PATH}: synthetic EEG",
            f"- {T1_REL_PATH}: toy T1-like volume for Niivue",
            "- source/demo_cortex.npz + nir_multimodal_manifest.json: linked cortical demo mesh",
            "Viewer → Multimodal View: signal time slider drives cortical coloring when manifest is present.",
        ],
    )

    try:
        from backend.services.multimodal_bundle import write_demo_cortex_bundle

        write_demo_cortex_bundle(
            source_dir,
            eeg_rel=EEG_REL_PATH,
            mri_rel=T1_REL_PATH,
            sfreq=250.0,
            duration_s=4.0,
            n_time_points=400,
        )
    except Exception as e:
        logger.warning("Could not write multimodal demo bundle: %s", e)

    _upsert_job_row(
        job_id=SAMPLE_EEG_PREP_JOB_ID,
        out_dir=prep_dir,
        pipeline_name="eeg_preprocessing",
        plugin_id="eeg_preprocessing",
        viewer_tab="eeg",
        completed=completed,
    )
    _upsert_job_row(
        job_id=SAMPLE_EEG_SOURCE_JOB_ID,
        out_dir=source_dir,
        pipeline_name="source_localization",
        plugin_id="source_localization",
        viewer_tab="eeg-brain",
        completed=completed,
    )


def _upsert_job_row(
    *,
    job_id: str,
    out_dir: Path,
    pipeline_name: str,
    plugin_id: str,
    viewer_tab: str,
    completed: datetime,
) -> None:
    from backend.core.database import get_db_context
    from backend.models.job import Job, JobStatusEnum

    out_dir.mkdir(parents=True, exist_ok=True)
    out_resolved = str(out_dir.resolve())

    with get_db_context() as db:
        row = db.query(Job).filter(Job.id == job_id).first()
        params = {
            "plugin_id": plugin_id,
            "execution_mode": "plugin",
            "_sample_job": True,
            "_sample_viewer_tab": viewer_tab,
        }
        if row is None:
            db.add(
                Job(
                    id=job_id,
                    backend_type="local_docker",
                    pipeline_name=pipeline_name,
                    container_image="sample/bundled-eeg-demo",
                    input_files=[],
                    parameters=params,
                    resources={
                        "memory_gb": 0,
                        "cpus": 0,
                        "time_hours": 0,
                        "gpu": False,
                    },
                    output_dir=out_resolved,
                    status=JobStatusEnum.COMPLETED.value,
                    progress=100,
                    current_phase="Sample data ready",
                    submitted_at=completed,
                    started_at=completed,
                    completed_at=completed,
                    exit_code=0,
                )
            )
        else:
            row.deleted = False
            row.deleted_at = None
            row.output_dir = out_resolved
            row.status = JobStatusEnum.COMPLETED.value
            row.progress = 100
            row.pipeline_name = pipeline_name
            row.parameters = params
            row.exit_code = 0
            row.error_message = None
        db.commit()

    logger.info("Sample EEG job ready: %s (%s)", job_id[:13], pipeline_name)
