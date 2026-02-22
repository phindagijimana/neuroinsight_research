FROM freesurfer/freesurfer:7.4.1

LABEL maintainer="NeuroInsight Research"
LABEL description="FreeSurfer SegmentHA_T1 adapter for Pennsieve"
LABEL org.pennsieve.processor="true"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
