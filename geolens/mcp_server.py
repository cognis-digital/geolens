"""GEOLENS MCP server — exposes scan as an MCP tool for Cognis.Studio."""
from cognis_core.mcp import build_mcp_server
from geolens.core import scan, TOOL_NAME

run_mcp_server = build_mcp_server(
    tool_name=TOOL_NAME,
    description="Image geolocation toolkit — EXIF, sun-shadow, OCR, reverse-search",
    scan_fn=scan,
)

if __name__ == "__main__":
    run_mcp_server()
