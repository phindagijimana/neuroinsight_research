FROM phindagijimana321/hs-postprocess:1.0.0

LABEL maintainer="NeuroInsight Research"
LABEL description="HS Detection Postprocess utility adapter for Pennsieve"
LABEL org.pennsieve.processor="true"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
