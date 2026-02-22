FROM pennlinc/qsirecon:1.1.1

LABEL maintainer="NeuroInsight Research"
LABEL description="QSIRecon adapter for Pennsieve"
LABEL org.pennsieve.processor="true"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
