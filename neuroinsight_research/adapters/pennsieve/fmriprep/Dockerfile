FROM nipreps/fmriprep:23.2.1

LABEL maintainer="NeuroInsight Research"
LABEL description="fMRIPrep adapter for Pennsieve"
LABEL org.pennsieve.processor="true"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
