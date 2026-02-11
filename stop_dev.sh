#!/bin/bash
# Legacy wrapper -- use ./research-dev stop instead
exec "$(dirname "$0")/research-dev" stop "$@"
