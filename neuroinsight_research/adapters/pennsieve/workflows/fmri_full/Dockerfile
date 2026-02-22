FROM nipreps/fmriprep:23.2.1 AS fmriprep

FROM pennlinc/xcp_d:0.6.1

LABEL maintainer="NeuroInsight Research"
LABEL description="fMRI Full Pipeline workflow for Pennsieve (fMRIPrep + XCP-D)"
LABEL org.pennsieve.processor="true"

# Copy fMRIPrep from the fmriprep image
COPY --from=fmriprep /opt/conda /opt/fmriprep-conda
COPY --from=fmriprep /usr/local/miniconda /usr/local/fmriprep-miniconda 2>/dev/null || true

# fMRIPrep wrapper script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
