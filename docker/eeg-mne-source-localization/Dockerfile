# NIR plugin: EEG source localization (MNE-Python inverse)
# Tutorial basis: https://mne.tools/stable/auto_tutorials/inverse/30_mne_dspm_loreta.html

FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.title="NIR eeg-source-localization-mne"
LABEL org.opencontainers.image.description="dSPM-style inverse from cleaned EEG + forward solution"
LABEL org.opencontainers.image.source="NeuroInsight Research Tool"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app/run.py /app/run.py

ENV NIR_INPUT_ROOT=/data/input \
    NIR_OUTPUT_ROOT=/data/output

ENTRYPOINT ["python", "/app/run.py"]
