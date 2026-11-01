# Pond on Fedora

This directory keeps the installed Pond components in separate repositories.
It is for this Fedora port. It does not configure a new desktop session or
install the niri configuration, fonts, cursor theme, or desktop dependencies.

- `pond-interface` tracks upstream on the `fedora` branch. The local commit
  adds Codexbar. The upstream tray is used instead of the old custom tray.
- `vicinae` tracks the Butterfly fork of the launcher.
- `package-manager` tracks upstream on the `fedora` branch. It adds a DNF5
  backend to `libpm` and keeps the upstream launcher extension and Flatpak backend.
- `fedora-tools` has the build, update, and install commands below. Its `pm`
  command forwards to the built upstream CLI.

Run commands from `~/Projects/pond-fedora`.

## Update

```sh
./pond status
./pond update --check
./pond update
./pond build
./pond install-shell
./pond install-system
```

`update --check` fetches all three repositories and shows incoming commits and
changed file counts. It does not change source branches or install files. It
also works with local edits, so you can inspect upstream before saving work.

`update` fetches all three repositories. It rebases the local Pond and package
manager commits onto upstream and fast-forwards the launcher. It stops for
uncommitted or untracked files, detached checkouts, and unfinished Git operations.
It checks the launcher for local commits before it changes any source branch.
If a rebase has a conflict, resolve it in `pond-interface` or `package-manager`,
then run `git rebase --continue`. Run `./pond update` again after the rebase.
The update does not install files until you run the install commands.

`install-shell` writes tracked shell files into
`$XDG_CONFIG_HOME/quickshell/pond-shell`, or `~/.config/quickshell/pond-shell`
when `XDG_CONFIG_HOME` is unset. It records their hashes under
`$XDG_STATE_HOME/pond-fedora`, or `~/.local/state/pond-fedora` when
`XDG_STATE_HOME` is unset. Each install target has a separate manifest.
The installer refuses to overwrite local changes. On its
first run it only adopts files that already match. It refuses symbolic links
at the target or within its directory tree. Move edits into the Git
checkout before installing. It leaves extra files and user settings in place.
It also leaves files that upstream removed in place and reports their names.
The shell reloads after changes. Check `qs log -c pond-shell -t 30` if it fails
to load. This repository does not contain the local Codexbar configuration or
real usage snapshots. The existing files stay on this machine.

`build` builds the native shell modules and package manager. It needs CMake,
a C++ compiler, Qt 6.11 development files,
KF6 NetworkManagerQt development files, Wayland development files and
`patchelf`. The packages are already installed on this machine. `install-system`
uses `sudo` to install the built QML modules, Pond source files, and the
upstream `pm` CLI with Fedora support. It also installs the app installer in
the current user's Vicinae extensions. It does not delete shell or system files. Use
`POND_DRY_RUN=1 ./pond install-system` to see the proposed file changes.
The system files are not tracked by RPM. This is an update workflow for the
existing port, not a complete installer for a fresh Fedora system.

## App installer and updates

```sh
./pond build-package-manager
POND_DRY_RUN=1 ./pond install-package-manager
./pond install-package-manager
```

These commands work with the existing launcher. They do not rebuild or restart
Vicinae. Open `Install apps` in the launcher after installation. If Vicinae does
not detect the new bundle, restart `vicinae.service` when convenient.

The build uses Cargo with the upstream lockfile and the extension's existing
`npm ci` and build script. It needs Rust, Node.js, npm, `pkg-config`, and
`flatpak-devel`. It uses the same Cargo target directory for the CLI and
extension bridge under `fedora-tools/.build/package-manager`.

The installer places the CLI at `/usr/libexec/pond/pm` and a forwarding command
at `/usr/local/bin/pm`. It copies upstream catalog icons to
`/usr/share/pond-pm/icons`. It installs the upstream bundle at
`$XDG_DATA_HOME/vicinae/extensions/pond-pm-extension`, or under
`~/.local/share` when `XDG_DATA_HOME` is unset. It checks the previous bundle's
hashes before replacement and refuses local edits. Bundle replacement removes
obsolete generated files and causes Vicinae to scan the new bundle.

On Fedora, `libpm` reuses upstream catalog entries and searches configured DNF
repository metadata for native package names. It maps known renamed packages
and hides native entries without an available Fedora package. Flatpak entries
keep the upstream Flathub source. Native search uses cached metadata. Run
`dnf5 makecache` if DNF reports that its cache is missing. The existing Flatpak
backend needs a system Flathub remote to install Flatpak apps.

`pm -a` checks DNF and Flatpak updates. It prints `true` or `false` only after a
successful check and returns a nonzero status on errors. `pm -u` updates native
packages through `pkexec /usr/bin/dnf5` and keeps the upstream Flatpak update
path. The desktop's Polkit agent handles authentication. No authorization rule
is added. The CLI returns 0 after success, 2 when DNF recommends a reboot, and
1 on failure. A failed reboot check is an error, not a reboot recommendation.

## Launcher

```sh
./pond build-launcher
./pond install-launcher
systemctl --user restart vicinae.service
```

The launcher commands also build and install the package manager and extension.
The launcher build requires the development dependencies used by the upstream
Vicinae CMake project. CMake reports any missing dependencies. The install
uses `sudo`, installs the launcher under `/usr`, and restores the input
server's existing `cap_dac_override` capability. Restarting the user service
is separate so it does not interrupt the launcher during the install.

Use `JOBS=8 ./pond build` or `JOBS=8 ./pond build-launcher` to set parallelism.
The default is four jobs. Build files are in `fedora-tools/.build`.

## Workflow tests

```sh
cd fedora-tools
python3 -m unittest discover -s tests -v
```

The tests use temporary homes and local Git repositories. They do not contact
upstream, install system files, or restart the shell.
