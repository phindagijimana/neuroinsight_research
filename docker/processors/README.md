# Processor Image Mirror

Use this folder to track and publish tested processor images under `phindagijimana321/*`.

See `required-images.yaml` for the complete plugin/workflow image mapping.

## Custom MELD image

`meld_graph` now uses a NeuroInsight-managed tag:

- `phindagijimana321/meld_graph:v2.2.4-nir2`

`nir2` bakes MELD params/models into the image for deterministic runtime.

The Dockerfile upgrades **NumPy** and **h5py** in the upstream **`meld_graph`** conda env (`/opt/conda/envs/meld_graph/bin/python -m pip`, pins `numpy>=1.26.4,<2.3`, `h5py>=3.11.0`) so HDF5 wheels match the runtime interpreter. Pennsieve MELD Dockerfiles under `adapters/pennsieve/` use the same step.

Build and push it with:

```bash
MELD_CACHE_SRC=/absolute/path/to/meld_cache ./docker/processors/build_and_push_meld_graph_nir.sh
```

`MELD_CACHE_SRC` must contain:

- `meld_params/fsaverage_sym/surf/lh.inflated`
- `meld_params/fsaverage_sym/surf/rh.inflated`
- `models/` (non-empty)

To populate a cache directory on a machine that can download from Figshare (browser or
unblocked network), run `./docker/scripts/bootstrap_meld_cache.sh /path/to/meld_cache`.
Some networks return AWS WAF challenges to unattended `curl`; if the script fails, download
the MELD parameter and model archives from the MELD Graph project documentation or by
running `get_meld_params()` / `get_model()` inside the upstream `meldproject/meld_graph`
container on a workstation, then point `MELD_CACHE_SRC` at the resulting tree.
