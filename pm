#!/bin/sh
# pm - Fedora replacement for Pond's Arch package manager shim.
#
# Pond's shell calls two forms only:
#   pm -a   print "true" when updates are available, "false" otherwise
#   pm -u   apply updates; exit 0 = complete, 2 = restart required, else failed
#
# The Arch original shells out to checkupdates (pacman) and paru. This version
# uses dnf, which is what Fedora 44 ships.
#
# stdin is redirected from /dev/null in both branches: dnf reads stdin when it
# is not a terminal and hangs forever when the caller (Quickshell Process) gives
# it an inherited pipe. That hang left the shell's update badge blank.

set -u

case "${1:-}" in
-a)
    # dnf check-update exits 100 when updates exist, 0 when none, 1 on error.
    dnf -q check-update </dev/null >/dev/null 2>&1
    case $? in
    100) echo true ;;
    *) echo false ;;
    esac
    ;;
-u)
    dnf -y upgrade --refresh </dev/null >/dev/null 2>&1 || exit 1
    # A kernel or glibc update needs a reboot; report the same "restart"
    # code that Pond's Arch shim uses for paru's post-upgrade signal.
    if needs-restarting -r </dev/null >/dev/null 2>&1; then
        exit 0
    fi
    exit 2
    ;;
*)
    echo "usage: pm -a | pm -u" >&2
    exit 64
    ;;
esac
