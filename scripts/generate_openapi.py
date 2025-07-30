#!/usr/bin/env python3
"""Generate OpenAPI documentation from FastAPI server"""

import argparse
import json
import sys
from pathlib import Path

import yaml

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import the FastAPI app
from backend.server import app


def generate_openapi(output_format: str = "yaml", output_file: str = "openapi"):
    """Generate OpenAPI documentation from FastAPI app

    Args:
        output_format: 'json' or 'yaml'
        output_file: Output filename without extension
    """
    # Get the OpenAPI schema from FastAPI
    openapi_schema = app.openapi()

    # Add more metadata if needed
    openapi_schema["info"]["version"] = "1.0.0"
    openapi_schema["info"]["description"] = "Backend API with Supabase Authentication"

    # Write the schema to file
    print(output_format)
    if output_format == "yaml":
        output_path = f"{output_file}.yaml"
        with open(output_path, "w") as f:
            yaml.dump(openapi_schema, f, default_flow_style=False, sort_keys=False)
    else:
        output_path = f"{output_file}.json"
        with open(output_path, "w") as f:
            json.dump(openapi_schema, f, indent=2)

    print(f"OpenAPI documentation generated: {output_path}")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate OpenAPI documentation")
    parser.add_argument(
        "--format",
        choices=["json", "yaml"],
        default="yaml",
        help="Output format (default: yaml)",
    )
    parser.add_argument(
        "--output",
        default="openapi",
        help="Output filename without extension (default: openapi)",
    )

    args = parser.parse_args()
    generate_openapi(args.format, args.output)
