#!/usr/bin/env bash
# entrypoint.sh - universal wrapper with command and extension handling

if [[ "${1:0:1}" == "-" ]]; then
    exec python /app/pipeline.py "${@}"
fi

script="$1"
shift

if [[ "$script" != *.* ]]; then
    exec "$script" "$@"
fi

if [[ "$script" == *.py ]]; then
    exec python "/app/${script}" "$@"
fi

exec "/app/${script}" "$@"