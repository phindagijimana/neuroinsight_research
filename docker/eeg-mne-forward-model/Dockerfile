# NIR plugin: forward_model (MNE make_forward_solution)

FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.title="NIR eeg-forward-model-mne"
LABEL org.opencontainers.image.description="Lead field / forward solution from trans, src, BEM"
LABEL org.opencontainers.image.source="NeuroInsight Research Tool"
LABEL org.opencontainers.image.version="1.0.10"

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY app/run.py /app/run.py

ENV NIR_INPUT_ROOT=/data/input NIR_OUTPUT_ROOT=/data/output
ENTRYPOINT ["python", "/app/run.py"]
