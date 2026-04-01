# NIR plugin: bem_source_space — MNE BEM + volume source space (FreeSurfer watershed)

FROM freesurfer/freesurfer:7.4.1

USER root

# Base image is CentOS Stream 8 (no apt); FreeSurfer is under /usr/local/freesurfer
RUN dnf install -y python3 python3-pip \
    && dnf clean all

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt
COPY app/run.py /app/run.py

ENV FREESURFER_HOME=/usr/local/freesurfer \
    NIR_INPUT_ROOT=/data/input \
    NIR_OUTPUT_ROOT=/data/output

ENTRYPOINT ["python3", "/app/run.py"]
