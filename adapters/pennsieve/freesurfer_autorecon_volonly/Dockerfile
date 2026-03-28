FROM freesurfer/freesurfer:7.4.1

LABEL maintainer="NeuroInsight Research"
LABEL description="FreeSurfer Volumetric (autorecon1 + autorecon2-volonly) adapter for Pennsieve"
LABEL org.pennsieve.processor="true"

COPY shared/detect_inputs.sh /shared/detect_inputs.sh
RUN chmod +x /shared/detect_inputs.sh

# Build from repo root: `docker build -f adapters/pennsieve/freesurfer_autorecon_volonly/Dockerfile -t … adapters/pennsieve`
COPY freesurfer_autorecon_volonly/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
