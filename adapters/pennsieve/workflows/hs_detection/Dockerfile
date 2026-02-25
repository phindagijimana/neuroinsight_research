FROM freesurfer/freesurfer:7.4.1 AS freesurfer

FROM phindagijimana321/hs-postprocess:1.0.0

LABEL maintainer="NeuroInsight Research"
LABEL description="Hippocampal Sclerosis Detection workflow for Pennsieve (FreeSurfer VolOnly + HS Postprocess)"
LABEL org.pennsieve.processor="true"

# Copy FreeSurfer binaries and data from the FreeSurfer image
COPY --from=freesurfer /usr/local/freesurfer /usr/local/freesurfer

ENV FREESURFER_HOME=/usr/local/freesurfer
ENV PATH="${FREESURFER_HOME}/bin:${PATH}"

COPY shared/detect_inputs.sh /shared/detect_inputs.sh
RUN chmod +x /shared/detect_inputs.sh

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
