FROM meldproject/meld_graph:v2.2.4

LABEL maintainer="NeuroInsight Research"
LABEL description="MELD Graph lesion detection adapter for Pennsieve"
LABEL org.pennsieve.processor="true"

RUN python3 -m pip install --no-cache-dir --upgrade \
    "numpy>=1.26.4,<2.3" \
    "h5py>=3.11.0"

COPY shared/detect_inputs.sh /shared/detect_inputs.sh
RUN chmod +x /shared/detect_inputs.sh

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
