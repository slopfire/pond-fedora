#!/bin/sh
# Keep the shell command stable while libpm handles each distribution.
exec /usr/libexec/pond/pm "$@"
