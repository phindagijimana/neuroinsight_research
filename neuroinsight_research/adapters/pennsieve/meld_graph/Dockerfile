FROM meldproject/meld_graph:v2.2.4

LABEL maintainer="NeuroInsight Research"
LABEL description="MELD Graph lesion detection adapter for Pennsieve"
LABEL org.pennsieve.processor="true"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
