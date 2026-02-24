FROM meldproject/meld_graph:v2.2.4

LABEL maintainer="NeuroInsight Research"
LABEL description="MELD Graph lesion detection adapter for Pennsieve"
LABEL org.pennsieve.processor="true"

COPY shared/detect_inputs.sh /shared/detect_inputs.sh
RUN chmod +x /shared/detect_inputs.sh

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
