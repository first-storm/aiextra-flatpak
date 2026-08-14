#!/bin/bash

env TMPDIR="${XDG_CACHE_HOME}" zypak-wrapper /app/extra/claude-desktop "$@"
