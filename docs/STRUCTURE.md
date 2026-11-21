# NanOs repository structure

The active 0.0.1-alpha build is a Kali live-build variant. Only the paths below feed it:

```text
VERSION
BUILD_ISO.txt
nanos/kali-config/
  common/
    hooks/live/                 build-time live setup
    includes.chroot/            OS identity, tty autologin, Hyprland + Waybar config
  variant-nanos/
    package-lists/nanos.list.chroot
scripts/
  build-kali-iso.sh             clones official Kali kali-live, overlays config, builds amd64 ISO
  check-nanos-config.py         static validation
.github/workflows/
  ci.yml                        static checks
  iso.yml                       privileged Kali Rolling container and ISO artifact
```

The old `profile/`, `groups/` and FlyArchOs scripts are not read by the NanOs workflow. They remain temporarily only while the first NanOs live image is being validated; the old build and release workflows are disabled.
