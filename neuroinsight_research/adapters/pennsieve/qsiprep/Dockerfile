FROM pennbbl/qsiprep:0.20.0

LABEL maintainer="NeuroInsight Research"
LABEL description="QSIPrep adapter for Pennsieve"
LABEL org.pennsieve.processor="true"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
