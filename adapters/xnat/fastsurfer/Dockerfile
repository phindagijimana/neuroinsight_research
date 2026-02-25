FROM deepmi/fastsurfer:v2.4.2

LABEL maintainer="NeuroInsight Research"
LABEL description="FastSurfer adapter for XNAT Container Service"
LABEL org.nrg.commands="[{\"command-line\": \"/entrypoint.sh\"}]"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
