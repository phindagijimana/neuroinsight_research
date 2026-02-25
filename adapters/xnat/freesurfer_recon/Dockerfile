FROM freesurfer/freesurfer:7.4.1

LABEL maintainer="NeuroInsight Research"
LABEL description="FreeSurfer recon-all adapter for XNAT Container Service"
LABEL org.nrg.commands="[{\"command-line\": \"/entrypoint.sh\"}]"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
