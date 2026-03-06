# Processor Image Mirror

Use this folder to track and publish tested processor images under `phindagijimana321/*`.

See `required-images.yaml` for the complete plugin/workflow image mapping.

## Custom MELD image

`meld_graph` now uses a NeuroInsight-managed tag:

- `phindagijimana321/meld_graph:v2.2.4-nir2`

`nir2` bakes MELD params/models into the image for deterministic runtime.

Build and push it with:

```bash
MELD_CACHE_SRC=/absolute/path/to/meld_cache ./docker/processors/build_and_push_meld_graph_nir.sh
```

`MELD_CACHE_SRC` must contain:

- `meld_params/fsaverage_sym/surf/lh.inflated`
- `meld_params/fsaverage_sym/surf/rh.inflated`
- `models/` (non-empty)
