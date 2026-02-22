FROM nipy/heudiconv:1.3.4

LABEL maintainer="NeuroInsight Research"
LABEL description="dcm2niix DICOM-to-NIfTI adapter for Pennsieve"
LABEL org.pennsieve.processor="true"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
