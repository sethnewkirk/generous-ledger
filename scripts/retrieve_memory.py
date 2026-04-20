#!/usr/bin/env python3

import argparse
import json

from scripts.steward_memory.retrieval import retrieve_context


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieve steward memory context for a workflow.")
    parser.add_argument("--vault", required=True, help="Path to the target vault")
    parser.add_argument("--workflow", required=True, help="Workflow name, such as daily-briefing or meeting-prep")
    parser.add_argument("--subject", action="append", default=[], help="Subject title to expand from")
    parser.add_argument("--since-days", type=int, default=30, help="Only consider recent documents from the last N days")
    args = parser.parse_args()

    result = retrieve_context(
        args.vault,
        args.workflow,
        subject_titles=args.subject,
        since_days=args.since_days,
    )
    print(
        json.dumps(
            {
                "workflow": result.workflow,
                "subject_titles": result.subject_titles,
                "used_search_fallback": result.used_search_fallback,
                "documents": [
                    {
                        "path": document.path,
                        "doc_type": document.doc_type,
                        "title": document.title,
                        "summary": document.summary,
                        "subjects": document.subjects,
                        "wikilinks": document.wikilinks,
                        "occurred_at": document.occurred_at,
                        "claim_type": document.claim_type,
                        "status": document.status,
                        "source_type": document.source_type,
                        "sensitivity": document.sensitivity,
                        "score": document.score,
                    }
                    for document in result.documents
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
