#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

CHK="desktop-release-sha256-macos.txt"
if [[ ! -f "$CHK" ]]; then
  echo "Missing checksum file: $CHK" >&2
  exit 1
fi

echo "Verifying macOS installer checksums..."
mapfile -t files_to_check < <(awk '{print $2}' "$CHK" | sed 's/^\*//' | grep -E '\.(dmg|pkg|zip)$' || true)
if [[ "${#files_to_check[@]}" -eq 0 ]]; then
  echo "No macOS installer entries found in $CHK" >&2
  exit 1
fi
for f in "${files_to_check[@]}"; do
  expected="$(awk -v target="$f" '$2==target || $2=="*"target {print $1}' "$CHK" | head -n 1)"
  if [[ -z "$expected" ]]; then
    echo "Checksum entry missing for $f" >&2
    exit 1
  fi
  actual="$(shasum -a 256 "$f" | awk '{print $1}')"
  if [[ "$actual" != "$expected" ]]; then
    echo "Checksum mismatch for $f" >&2
    exit 1
  fi
done

dmg="$(ls -1 ./*.dmg 2>/dev/null | head -n 1 || true)"
zipf="$(ls -1 ./*.zip 2>/dev/null | head -n 1 || true)"

if [[ -n "$dmg" ]]; then
  echo "Opening DMG: $dmg"
  open "$dmg"
  exit 0
fi

if [[ -n "$zipf" ]]; then
  echo "Opening ZIP: $zipf"
  open "$zipf"
  exit 0
fi

echo "No macOS installer found (.dmg or .zip)." >&2
exit 1
