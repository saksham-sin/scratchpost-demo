#!/usr/bin/env python3
"""Fail if two migrations claim the same sequence number.

This is the check a real CI pipeline runs. It is deliberately simple: it only
looks at the merged tree, exactly like a post-merge build would.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
failures = []


def check_liquibase(path: Path) -> None:
    ids = re.findall(r'<changeSet\s+id="([^"]+)"', path.read_text())
    seen = {}
    for cid in ids:
        if cid in seen:
            failures.append(
                f"{path.relative_to(ROOT)}: duplicate changeSet id={cid} "
                f"(claimed twice)"
            )
        seen[cid] = True


def check_flyway(directory: Path) -> None:
    versions = {}
    for sql in sorted(directory.glob("V*__*.sql")):
        match = re.match(r"V(\d+)__", sql.name)
        if not match:
            continue
        version = match.group(1)
        if version in versions:
            failures.append(
                f"{sql.relative_to(ROOT)}: duplicate Flyway version V{version} "
                f"(also {versions[version]})"
            )
        versions[version] = sql.name


def main() -> int:
    liquibase = ROOT / "auth-service/src/main/resources/db/dbchangelog.xml"
    if liquibase.exists():
        check_liquibase(liquibase)
    flyway = ROOT / "payment-service/src/main/resources/db/migration"
    if flyway.is_dir():
        check_flyway(flyway)

    if failures:
        print("MIGRATION VALIDATION FAILED")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("migration validation passed: all sequence numbers unique")
    return 0


if __name__ == "__main__":
    sys.exit(main())
