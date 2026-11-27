"""CLI entry point for Datagenix.

Run the end-to-end multi-agent pipeline directly from the command line.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys

from backend.orchestrator import run_pipeline
from backend.state import ProjectState
from config.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-25s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("datagenix-cli")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Datagenix - Multi-Agent AI Data Engineering & dbt Platform"
    )
    parser.add_argument(
        "--name",
        type=str,
        required=True,
        help="Project name (e.g. ecommerce_analytics)",
    )
    parser.add_argument(
        "--requirements",
        type=str,
        help="Path to requirements text file or inline text string",
    )
    parser.add_argument(
        "--description",
        type=str,
        default="",
        help="Optional high-level description of the project",
    )
    parser.add_argument(
        "--metadata",
        type=str,
        help="Optional path to source metadata CSV/JSON/YAML file",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Override output root directory",
    )

    args = parser.parse_args()

    # Load requirements text
    req_text = ""
    if args.requirements:
        req_path = Path(args.requirements)
        if req_path.is_file():
            req_text = req_path.read_text(encoding="utf-8")
        else:
            req_text = args.requirements

    if not req_text.strip():
        logger.error("No requirements provided. Use --requirements <file_or_text>")
        sys.exit(1)

    # Optional metadata
    manual_meta = {}
    if args.metadata:
        meta_path = Path(args.metadata)
        if meta_path.is_file():
            manual_meta = {meta_path.name: meta_path.read_text(encoding="utf-8")}

    settings = get_settings()
    if args.output_dir:
        settings.project_output_dir = args.output_dir

    logger.info("Initializing Datagenix for project: %s", args.name)
    initial_state = ProjectState(
        project_name=args.name,
        project_description=args.description or f"dbt project for {args.name}",
        business_requirements=req_text,
        source_metadata_manual=manual_meta,
    )

    result_state = run_pipeline(initial_state)

    logger.info("=== Execution Finished ===")
    out_path = result_state.get("project_output_path", "")
    if out_path:
        logger.info("Generated project path: %s", out_path)
    
    qa = result_state.get("qa_report", {})
    logger.info("QA Status: %s (Issues: %d)", qa.get("status", "unknown"), len(qa.get("issues", [])))
    
    pkg = result_state.get("packaging_result", {})
    if pkg.get("zip_archive"):
        logger.info("Packaged ZIP: %s", pkg["zip_archive"])


if __name__ == "__main__":
    main()

