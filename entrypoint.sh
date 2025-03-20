#!/bin/sh

# Execute application
exec python3 -m src.main --host 0.0.0.0 --port 8765 --certfile "${CERT_FILE}" --keyfile "${KEY_FILE}" "$@"
