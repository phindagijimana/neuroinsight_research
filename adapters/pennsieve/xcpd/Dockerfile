FROM pennlinc/xcp_d:0.6.1

LABEL maintainer="NeuroInsight Research"
LABEL description="XCP-D post-processing adapter for Pennsieve"
LABEL org.pennsieve.processor="true"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
