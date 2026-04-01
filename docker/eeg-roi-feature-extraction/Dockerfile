# NIR plugin: roi_feature_extraction (NiBabel + NumPy)

FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.title="NIR eeg-roi-feature-extraction"
LABEL org.opencontainers.image.description="Fuse source NIfTI + segmentation labels into ROI JSON features"
LABEL org.opencontainers.image.source="NeuroInsight Research Tool"

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY app/roi_merge_prep.py /app/roi_merge_prep.py
COPY app/run.py /app/run.py

ENV NIR_INPUT_ROOT=/data/input NIR_OUTPUT_ROOT=/data/output
ENTRYPOINT ["python", "/app/run.py"]
