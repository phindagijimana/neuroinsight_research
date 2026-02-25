FROM freesurfer/freesurfer:7.4.1 AS freesurfer

FROM meldproject/meld_graph:v2.2.4

LABEL maintainer="NeuroInsight Research"
LABEL description="Cortical Lesion Detection workflow for Pennsieve (FreeSurfer recon-all + MELD Graph)"
LABEL org.pennsieve.processor="true"

# Copy FreeSurfer binaries and data from the FreeSurfer image
COPY --from=freesurfer /usr/local/freesurfer /usr/local/freesurfer

ENV FREESURFER_HOME=/usr/local/freesurfer
ENV PATH="${FREESURFER_HOME}/bin:${PATH}"
ENV SUBJECTS_DIR=/data/output/subjects

COPY shared/detect_inputs.sh /shared/detect_inputs.sh
RUN chmod +x /shared/detect_inputs.sh

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
