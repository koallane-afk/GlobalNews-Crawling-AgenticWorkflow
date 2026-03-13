#!/usr/bin/env python3
"""Check crawl progress from background task output and data files.

Distinguishes between sites that actually collected articles vs sites
that "completed" with 0 articles (deadline expired, extraction failed, etc.).
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path


def main():
    project = Path(__file__).resolve().parent.parent
    output_file = sys.argv[1] if len(sys.argv) > 1 else None
    date_str = datetime.now().strftime("%Y-%m-%d")

    print(f"=== CRAWL PROGRESS {datetime.now().strftime('%H:%M:%S')} ===\n")

    # 1. Check articles in JSONL
    jsonl = project / "data" / "raw" / date_str / "all_articles.jsonl"
    article_count = 0
    sources: dict[str, int] = {}
    if jsonl.exists():
        with open(jsonl) as f:
            for line in f:
                article_count += 1
                try:
                    d = json.loads(line)
                    sid = d.get("source_id", "unknown")
                    sources[sid] = sources.get(sid, 0) + 1
                except json.JSONDecodeError:
                    pass

    # 2. Parse background task output for site completions
    completed_with_articles: dict[str, int] = {}
    completed_zero: list[str] = []
    deadline_expired: list[str] = []
    started_sites: set[str] = set()
    skipped_sites: set[str] = set()

    if output_file and Path(output_file).exists():
        with open(output_file) as f:
            for line in f:
                # crawl_site_complete
                m = re.search(r'crawl_site_complete\s+site=(\S+)\s+articles=(\d+)', line)
                if m:
                    site, count = m.group(1), int(m.group(2))
                    if count > 0:
                        completed_with_articles[site] = max(
                            completed_with_articles.get(site, 0), count
                        )
                    else:
                        if site not in completed_zero:
                            completed_zero.append(site)
                    continue
                # site_already_complete
                m = re.search(r'site_already_complete\s+site_id=(\S+)', line)
                if m:
                    site = m.group(1)
                    skipped_sites.add(site)
                    cnt = sources.get(site, 0)
                    if cnt > 0:
                        completed_with_articles[site] = cnt
                    continue
                # deadline expired
                if 'site_deadline_expired' in line:
                    m = re.search(r'site_id=(\S+)', line)
                    if m and m.group(1) not in deadline_expired:
                        deadline_expired.append(m.group(1))
                    continue
                # crawl_site_start
                m = re.search(r'crawl_site_start\s+site=(\S+)', line)
                if m:
                    started_sites.add(m.group(1))

    all_done = set(completed_with_articles) | set(completed_zero) | skipped_sites
    in_progress = started_sites - all_done

    # Unique deadline-expired sites not in completed_with_articles
    truly_skipped = [s for s in deadline_expired if s not in completed_with_articles]

    success_count = len(completed_with_articles)
    zero_count = len([s for s in completed_zero if s not in completed_with_articles])

    print(f"Sites with articles:    {success_count} / 121")
    print(f"Sites with 0 articles:  {zero_count} (deadline expired or extraction failed)")
    print(f"Sites in progress:      {len(in_progress)}")
    print(f"Deadline-skipped:       {len(truly_skipped)}")
    print(f"Total articles (JSONL): {article_count}")
    print()

    # Top sites by articles
    if sources:
        print("Top sites by articles:")
        for sid, cnt in sorted(sources.items(), key=lambda x: -x[1])[:15]:
            print(f"  {sid:25s} {cnt:4d} articles")
        print()

    # In progress
    if in_progress:
        print(f"Currently crawling ({len(in_progress)}):")
        for s in sorted(in_progress)[:10]:
            print(f"  {s}")
        if len(in_progress) > 10:
            print(f"  ... and {len(in_progress) - 10} more")
        print()

    # Deadline-expired summary
    if truly_skipped:
        print(f"Never crawled (deadline expired before execution): {len(truly_skipped)}")
        for s in truly_skipped[:5]:
            print(f"  {s}")
        if len(truly_skipped) > 5:
            print(f"  ... and {len(truly_skipped) - 5} more")
        print()

    # Elapsed
    if output_file and Path(output_file).exists():
        stat = Path(output_file).stat()
        elapsed = datetime.now().timestamp() - stat.st_birthtime
        print(f"Elapsed: {elapsed/60:.1f} minutes")


if __name__ == "__main__":
    main()
