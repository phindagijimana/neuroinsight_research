FROM meldproject/meld_graph:v2.2.4

LABEL org.opencontainers.image.title="NeuroInsight MELD Graph"
LABEL org.opencontainers.image.description="NeuroInsight-managed MELD Graph image with deterministic baked cache"
LABEL org.opencontainers.image.source="https://github.com/MELDProject/meld_graph"
LABEL org.opencontainers.image.vendor="NeuroInsight"
LABEL org.opencontainers.image.version="v2.2.4-nir2"

# Install util-linux (flock) and bake MELD cache data into image so runtime
# execution is deterministic and does not depend on network/downloads.
RUN apt-get update \
    && apt-get install -y --no-install-recommends util-linux \
    && rm -rf /var/lib/apt/lists/*

# Copy deterministic cache prepared by build script.
COPY build_meld_cache/meld_params /data/meld_params
COPY build_meld_cache/models /data/models

RUN test -f /data/meld_params/fsaverage_sym/surf/lh.inflated \
    && test -f /data/meld_params/fsaverage_sym/surf/rh.inflated \
    && test -d /data/models \
    && test -n "$(ls -A /data/models)"
