FROM freesurfer/freesurfer:7.4.1

LABEL maintainer="NeuroInsight Research"
LABEL description="FreeSurfer SegmentHA_T2 adapter for Pennsieve"
LABEL org.pennsieve.processor="true"

COPY shared/detect_inputs.sh /shared/detect_inputs.sh
RUN chmod +x /shared/detect_inputs.sh

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
