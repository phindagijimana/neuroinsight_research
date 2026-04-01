# NIR plugin: bem_source_space — MNE BEM + volume source space (FreeSurfer watershed)

FROM freesurfer/freesurfer:7.4.1

USER root

# Python + pip without dnf/yum: CentOS Stream 8 mirrorlists often fail in CI and
# minimal networks. Miniforge provides a current Python + pip on PATH.
RUN curl -fsSL https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh -o /tmp/miniforge.sh \
    && bash /tmp/miniforge.sh -b -p /opt/conda \
    && rm -f /tmp/miniforge.sh \
    && /opt/conda/bin/conda install -y -c conda-forge "python=3.11" pip \
    && /opt/conda/bin/conda clean -afy

ENV PATH="/opt/conda/bin:${PATH}"

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY app/run.py /app/run.py

ENV FREESURFER_HOME=/usr/local/freesurfer \
    NIR_INPUT_ROOT=/data/input \
    NIR_OUTPUT_ROOT=/data/output

ENTRYPOINT ["python", "/app/run.py"]
