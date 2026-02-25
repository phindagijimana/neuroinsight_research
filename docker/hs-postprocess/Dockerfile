FROM python:3.11-slim

RUN pip install --no-cache-dir nibabel numpy matplotlib scipy

COPY neuroinsight_hs /app/neuroinsight_hs
WORKDIR /app

ENTRYPOINT ["python", "-m", "neuroinsight_hs.postprocess"]
