# NIR plugin: legacy EEG → BIDS (MNE + MNE-BIDS)
# See: https://mne.tools/mne-bids/stable/use.html

FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.title="NIR eeg-legacy-to-bids-mne"
LABEL org.opencontainers.image.description="Convert flat EEG files (EDF/BDF/BrainVision/FIF) to BIDS"
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
