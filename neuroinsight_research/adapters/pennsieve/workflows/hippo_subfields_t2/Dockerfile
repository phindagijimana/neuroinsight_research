FROM phindagijimana321/freesurfer-mcr:7.4.1

LABEL maintainer="NeuroInsight Research"
LABEL description="Hippocampal Subfields T1+T2 workflow adapter for Pennsieve (recon-all + segmentHA_T2)"
LABEL org.pennsieve.processor="true"

COPY shared/detect_inputs.sh /shared/detect_inputs.sh
RUN chmod +x /shared/detect_inputs.sh

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
