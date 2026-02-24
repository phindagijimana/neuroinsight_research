#!/bin/bash
# Shared BIDS-aware input detection for Pennsieve adapters.
# Source this file in entrypoint.sh:  source /shared/detect_inputs.sh
#
# Provides:
#   find_t1w DIR   -> prints first T1w NIfTI path (or empty)
#   find_flair DIR -> prints first FLAIR NIfTI path (or empty)
#   find_t2w DIR   -> prints first T2w NIfTI path (or empty)
#   find_all_t1w DIR -> prints all T1w NIfTI paths (for longitudinal)
#
# Search strategy (per function):
#   1. Flat: DIR/*pattern*.nii.gz
#   2. Anat subfolder: DIR/anat/*pattern*.nii.gz
#   3. BIDS sessions: DIR/ses-*/anat/*pattern*.nii.gz
#
# Excludes lesion ROIs (*label-lesion*, *_roi.*) from all results.

_is_excluded() {
    local fname="$1"
    echo "$fname" | grep -qiE "label-lesion|_roi\." && return 0
    return 1
}

_search_nifti() {
    local dir="$1"
    shift
    local patterns=("$@")
    for pattern in "${patterns[@]}"; do
        for f in "$dir"/$pattern; do
            [ -f "$f" ] || continue
            _is_excluded "$(basename "$f")" && continue
            echo "$f"
            return 0
        done
    done
    return 1
}

_search_nifti_all() {
    local dir="$1"
    shift
    local patterns=("$@")
    for pattern in "${patterns[@]}"; do
        for f in "$dir"/$pattern; do
            [ -f "$f" ] || continue
            _is_excluded "$(basename "$f")" && continue
            echo "$f"
        done
    done
}

find_t1w() {
    local input_dir="$1"
    local patterns=("*T1w*.nii.gz" "*T1w*.nii")

    # 1. Flat
    _search_nifti "$input_dir" "${patterns[@]}" && return 0

    # 2. anat/ subfolder
    if [ -d "$input_dir/anat" ]; then
        _search_nifti "$input_dir/anat" "${patterns[@]}" && return 0
    fi

    # 3. BIDS ses-*/anat/
    for ses_dir in "$input_dir"/ses-*/; do
        [ -d "$ses_dir" ] || continue
        local anat="${ses_dir}anat"
        [ -d "$anat" ] || anat="$ses_dir"
        _search_nifti "$anat" "${patterns[@]}" && return 0
    done

    return 1
}

find_flair() {
    local input_dir="$1"
    local patterns=("*FLAIR*.nii.gz" "*flair*.nii.gz" "*FLAIR*.nii" "*flair*.nii")

    _search_nifti "$input_dir" "${patterns[@]}" && return 0

    if [ -d "$input_dir/anat" ]; then
        _search_nifti "$input_dir/anat" "${patterns[@]}" && return 0
    fi

    for ses_dir in "$input_dir"/ses-*/; do
        [ -d "$ses_dir" ] || continue
        local anat="${ses_dir}anat"
        [ -d "$anat" ] || anat="$ses_dir"
        _search_nifti "$anat" "${patterns[@]}" && return 0
    done

    return 1
}

find_t2w() {
    local input_dir="$1"
    local patterns=("*T2w*.nii.gz" "*T2w*.nii")

    _search_t2w_filtered() {
        local dir="$1"
        for f in "$dir"/*T2w*.nii.gz "$dir"/*T2w*.nii; do
            [ -f "$f" ] || continue
            local fname=$(basename "$f")
            _is_excluded "$fname" && continue
            # Exclude T2starw
            echo "$fname" | grep -qi "T2starw" && continue
            echo "$f"
            return 0
        done
        return 1
    }

    _search_t2w_filtered "$input_dir" && return 0

    if [ -d "$input_dir/anat" ]; then
        _search_t2w_filtered "$input_dir/anat" && return 0
    fi

    for ses_dir in "$input_dir"/ses-*/; do
        [ -d "$ses_dir" ] || continue
        local anat="${ses_dir}anat"
        [ -d "$anat" ] || anat="$ses_dir"
        _search_t2w_filtered "$anat" && return 0
    done

    return 1
}

find_all_t1w() {
    local input_dir="$1"
    local patterns=("*T1w*.nii.gz" "*T1w*.nii")
    local found=0

    # 1. Flat
    while IFS= read -r f; do
        [ -n "$f" ] && echo "$f" && found=1
    done < <(_search_nifti_all "$input_dir" "${patterns[@]}")

    # 2. BIDS ses-*/anat/ (only if flat found < 2)
    if [ "$found" -eq 0 ] || [ $(find_all_t1w_count "$input_dir" 2>/dev/null) -lt 2 ]; then
        for ses_dir in "$input_dir"/ses-*/; do
            [ -d "$ses_dir" ] || continue
            local anat="${ses_dir}anat"
            [ -d "$anat" ] || anat="$ses_dir"
            _search_nifti_all "$anat" "${patterns[@]}"
        done
    fi
}

# Helper: extract timepoint ID from T1w filename
# e.g. "sub-01_ses-2WK_acq-3D_T1w.nii.gz" -> "sub-01_ses-2WK_acq-3D"
extract_tp_id() {
    local fname=$(basename "$1")
    local tp_id="${fname%%_T1w*}"
    [ -z "$tp_id" ] && tp_id="${fname%%.nii*}"
    echo "$tp_id"
}
