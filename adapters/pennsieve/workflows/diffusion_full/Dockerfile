FROM pennbbl/qsiprep:0.20.0 AS qsiprep

FROM pennlinc/qsirecon:1.1.1

LABEL maintainer="NeuroInsight Research"
LABEL description="Diffusion Full Pipeline workflow for Pennsieve (QSIPrep + QSIRecon)"
LABEL org.pennsieve.processor="true"

# Copy QSIPrep from the qsiprep image
COPY --from=qsiprep /opt/conda /opt/qsiprep-conda
COPY --from=qsiprep /usr/local/miniconda /usr/local/qsiprep-miniconda 2>/dev/null || true

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
