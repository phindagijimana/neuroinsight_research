# NIR plugin: biomarker_scoring (NumPy + PyYAML)

FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.title="NIR eeg-biomarker-scoring"
LABEL org.opencontainers.image.description="Score ROI features → laterality, concordance, viewer_summary"
LABEL org.opencontainers.image.source="NeuroInsight Research Tool"

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY app/run.py /app/run.py

ENV NIR_INPUT_ROOT=/data/input NIR_OUTPUT_ROOT=/data/output
ENTRYPOINT ["python", "/app/run.py"]
