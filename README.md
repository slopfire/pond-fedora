# Pond on Fedora

This directory keeps the installed Pond components in separate repositories.
It is for this Fedora port. It does not configure a new desktop session or
install the niri configuration, fonts, cursor theme, or desktop dependencies.

- `pond-interface` tracks upstream on the `fedora` branch. The local commit
  adds Codexbar. The upstream tray is used instead of the old custom tray.
- `vicinae` tracks the Butterfly fork of the launcher.
- `package-manager` is the upstream source for reference. Its package manager
  targets Arch. `fedora-tools/pm` is the existing Fedora replacement.
- `fedora-tools` has the commands below and the Fedora replacement for `pm`.

Run commands from `~/Projects/pond-fedora`.

## Update

```sh
./pond status
./pond update
./pond build
./pond install-shell
./pond install-system
```

`update` fetches all three repositories. It rebases the local Pond commits onto
upstream and fast-forwards the other repositories. It stops for uncommitted or
untracked files. If a rebase has a conflict, resolve it in `pond-interface`,
then run `git rebase --continue`. Run `./pond update` again after the rebase.
The update does not install files until you run the install commands.

`install-shell` writes tracked shell files into
`~/.config/quickshell/pond-shell`. It records their hashes under
`~/.local/state/pond-fedora` and refuses to overwrite local changes. On its
first run it only adopts files that already match. Move edits into the Git
checkout before installing. It leaves extra files and user settings in place.
It also leaves files that upstream removed in place and reports their names.
The shell reloads after changes. Check `qs log -c pond-shell -t 30` if it fails
to load. This repository does not contain the local Codexbar configuration or
real usage snapshots. The existing files stay on this machine.

`build` needs CMake, a C++ compiler, Qt 6.11 development files,
KF6 NetworkManagerQt development files, Wayland development files and
`patchelf`. The packages are already installed on this machine. `install-system`
uses `sudo` to install the built QML modules, Pond source files, and the
Fedora `pm` replacement. It does not delete files. Use
`POND_DRY_RUN=1 ./pond install-system` to see the proposed file changes.
The system files are not tracked by RPM. This is an update workflow for the
existing port, not a complete installer for a fresh Fedora system.

## Launcher

```sh
./pond build-launcher
./pond install-launcher
systemctl --user restart vicinae.service
```

The launcher build requires the development dependencies used by the upstream
Vicinae CMake project. CMake reports any missing dependencies. The install
uses `sudo`, installs the launcher under `/usr`, and restores the input
server's existing `cap_dac_override` capability. Restarting the user service
is separate so it does not interrupt the launcher during the install.

Use `JOBS=8 ./pond build` or `JOBS=8 ./pond build-launcher` to set parallelism.
The default is four jobs. Build files are in `fedora-tools/.build`.
