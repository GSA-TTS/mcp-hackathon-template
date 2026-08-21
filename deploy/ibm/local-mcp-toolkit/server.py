#!/usr/bin/env python
"""Local MCP toolkit entrypoint for watsonx Orchestrate (stdio transport).

watsonx Orchestrate runs a LOCAL MCP toolkit by starting this script inside its
own runtime and speaking MCP over stdio. This entrypoint reuses the EXISTING
FastMCP server defined in the `example_server` package and runs it over stdio —
no HTTP, no Code Engine, no container.

The register script stages this file NEXT TO the `example_server` package
(flattened out of the repo's src/ layout), so `example_server` is importable
from this script's own directory. We add that directory to sys.path defensively
in case Orchestrate runs the command from a different working directory.

Orchestrate invokes:  python server.py
"""

import os
import sys

# Ensure the directory containing this file (which also contains the
# `example_server` package after staging) is importable, regardless of CWD.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from example_server.app import mcp  # noqa: E402

if __name__ == "__main__":
    # stdio is the transport watsonx Orchestrate uses for local MCP toolkits.
    mcp.run(transport="stdio")
