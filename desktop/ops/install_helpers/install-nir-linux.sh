#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

CHK="desktop-release-sha256-linux.txt"
if [[ ! -f "$CHK" ]]; then
  echo "Missing checksum file: $CHK" >&2
  exit 1
fi

echo "Verifying Linux installer checksums..."
mapfile -t files_to_check < <(awk '{print $2}' "$CHK" | sed 's/^\*//' | grep -E '\.(AppImage|deb)$' || true)
if [[ "${#files_to_check[@]}" -eq 0 ]]; then
  echo "No Linux installer entries found in $CHK" >&2
  exit 1
fi
for f in "${files_to_check[@]}"; do
  expected="$(awk -v target="$f" '$2==target || $2=="*"target {print $1}' "$CHK" | head -n 1)"
  if [[ -z "$expected" ]]; then
    echo "Checksum entry missing for $f" >&2
    exit 1
  fi
  actual="$(sha256sum "$f" | awk '{print $1}')"
  if [[ "$actual" != "$expected" ]]; then
    echo "Checksum mismatch for $f" >&2
    exit 1
  fi
done

appimage="$(ls -1 ./*.AppImage 2>/dev/null | head -n 1 || true)"
deb="$(ls -1 ./*.deb 2>/dev/null | head -n 1 || true)"

if [[ -n "$appimage" ]]; then
  chmod +x "$appimage"
  echo "Launching AppImage: $appimage"
  "$appimage"
  exit 0
fi

if [[ -n "$deb" ]]; then
  echo "Opening DEB package: $deb"
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$deb"
  else
    echo "xdg-open not found. Install manually with: sudo dpkg -i \"$deb\""
  fi
  exit 0
fi

echo "No Linux installer found (.AppImage or .deb)." >&2
exit 1
