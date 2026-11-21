#!/usr/bin/env bash
# Build the NanOs live ISO using Kali's official kali-live/live-build scripts.
set -Eeuo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${NANOS_VERSION:-$(<"$REPO_ROOT/VERSION")}"
KALI_LIVE_URL="${KALI_LIVE_URL:-https://gitlab.com/kalilinux/build-scripts/kali-live.git}"
WORK_ROOT="${NANOS_WORK_ROOT:-$REPO_ROOT/work/nanos}"
KALI_LIVE_DIR="$WORK_ROOT/kali-live"
OUT_DIR="${NANOS_OUT_DIR:-$REPO_ROOT/out}"

log() { printf '\n[%s] %s\n' "$(date -u +%FT%TZ)" "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

[[ "$VERSION" == "0.0.1-alpha" ]] || die "VERSION must be 0.0.1-alpha for this pre-release (got: $VERSION)"
[[ "$EUID" -eq 0 ]] || die "Run this only inside the privileged Kali Rolling container from GitHub Actions."
for tool in git python3; do
    command -v "$tool" >/dev/null 2>&1 || die "Required host tool missing: $tool"
done
python3 "$REPO_ROOT/scripts/check-nanos-config.py"

mkdir -p "$WORK_ROOT" "$OUT_DIR"
rm -f "$OUT_DIR"/nanos-*.iso "$OUT_DIR"/nanos-*.iso.sha256 \
    "$OUT_DIR/build-manifest.txt" "$OUT_DIR/kali-live.log"
rm -rf "$KALI_LIVE_DIR"
log "Clone Kali live-build scripts: $KALI_LIVE_URL"
git clone --depth 1 "$KALI_LIVE_URL" "$KALI_LIVE_DIR"
KALI_LIVE_COMMIT="$(git -C "$KALI_LIVE_DIR" rev-parse HEAD)"
printf 'kali-live commit: %s\n' "$KALI_LIVE_COMMIT" | tee "$OUT_DIR/kali-live.log"

[[ -x "$KALI_LIVE_DIR/build.sh" ]] || die "Upstream Kali repository has no executable build.sh"
[[ -d "$KALI_LIVE_DIR/kali-config/common" ]] || die "Upstream Kali repository has no kali-config/common"

# Kali's wrapper expects a variant-* configuration directory. Create a clean
# NanOs variant; no Kali desktop variant is copied or inherited.
rm -rf "$KALI_LIVE_DIR/kali-config/variant-nanos"
mkdir -p "$KALI_LIVE_DIR/kali-config/variant-nanos"
cp -a "$REPO_ROOT/nanos/kali-config/variant-nanos/." \
    "$KALI_LIVE_DIR/kali-config/variant-nanos/"
cp -a "$REPO_ROOT/nanos/kali-config/common/." \
    "$KALI_LIVE_DIR/kali-config/common/"

log "Build Kali Rolling / amd64 / variant-nanos"
cd "$KALI_LIVE_DIR"
# tee is paired with pipefail so a failed live-build cannot look like success.
./build.sh --variant nanos --arch amd64 --verbose \
    2>&1 | tee -a "$OUT_DIR/kali-live.log"

mapfile -d '' -t images < <(find "$KALI_LIVE_DIR/images" -maxdepth 1 -type f -name '*.iso' -print0 2>/dev/null)
[[ "${#images[@]}" -eq 1 ]] || die "Expected exactly one ISO in images/, found ${#images[@]}"

mkdir -p "$OUT_DIR"
ISO="$OUT_DIR/nanos-$VERSION-amd64.iso"
install -m 0644 "${images[0]}" "$ISO"
sha256sum "$ISO" > "$ISO.sha256"

HYPRLAND_VERSION="not-recorded"
DPKG_ADMIN="$KALI_LIVE_DIR/chroot/var/lib/dpkg"
if [[ -f "$DPKG_ADMIN/status" ]] && command -v dpkg-query >/dev/null 2>&1; then
    HYPRLAND_VERSION="$(dpkg-query --admindir="$DPKG_ADMIN" -W -f='${Version}' hyprland 2>/dev/null || printf 'unknown')"
fi

cat > "$OUT_DIR/build-manifest.txt" <<EOF
os=NanOs
version=$VERSION
base=Kali Linux Rolling
desktop=Hyprland
architecture=amd64
kali_live_url=$KALI_LIVE_URL
kali_live_commit=$KALI_LIVE_COMMIT
hyprland_version=$HYPRLAND_VERSION
build_time_utc=$(date -u +%FT%TZ)
iso_file=$(basename "$ISO")
sha256=$(cut -d' ' -f1 < "$ISO.sha256")
EOF

log "NanOs ISO ready: $ISO"
ls -lh "$ISO" "$ISO.sha256" "$OUT_DIR/build-manifest.txt"
