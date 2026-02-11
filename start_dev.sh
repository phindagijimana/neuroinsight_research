#!/bin/bash
# Legacy wrapper -- use ./research-dev start instead
exec "$(dirname "$0")/research-dev" start "$@"
