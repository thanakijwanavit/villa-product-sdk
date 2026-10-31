#!/usr/bin/env python3
"""Print a CloudFormation change set as a table and refuse server resources.

Usage: check_changeset.py <describe-change-set.json>
Exit 0 = safe to execute, 1 = forbidden resource found, 2 = bad input.
Only resource actions, logical ids and types are printed (no parameter
values, no outputs), so the table is safe to paste into a bead note.
"""

import json
import sys

FORBIDDEN_PREFIXES = (
    "AWS::ECS::",
    "AWS::EKS::",
    "AWS::Batch::",
    "AWS::AppRunner::",
    "AWS::ElasticBeanstalk::",
    "AWS::Lightsail::",
    "AWS::AutoScaling::",
    "AWS::CodeBuild::",
)
FORBIDDEN_TYPES = {
    "AWS::EC2::Instance",
    "AWS::EC2::LaunchTemplate",
    "AWS::EC2::SpotFleet",
    "AWS::EC2::EC2Fleet",
    "AWS::EC2::NatGateway",
}


def forbidden(resource_type):
    return (
        resource_type in FORBIDDEN_TYPES
        or resource_type.startswith(FORBIDDEN_PREFIXES)
        or "fargate" in resource_type.lower()
    )


def rows(change_set):
    for change in change_set.get("Changes", []):
        rc = change.get("ResourceChange", {})
        yield rc.get("Action", "?"), rc.get("LogicalResourceId", "?"), rc.get("ResourceType", "?"), rc.get(
            "Replacement", ""
        )


def check(change_set):
    """Return (table_lines, bad_rows)."""
    table, bad = [], []
    table.append(f"change set {change_set.get('ChangeSetName', '?')} on stack {change_set.get('StackName', '?')}")
    table.append(f"{'Action':<8} {'LogicalId':<36} {'Type':<40} Replacement")
    for action, logical, rtype, repl in rows(change_set):
        table.append(f"{action:<8} {logical:<36} {rtype:<40} {repl}")
        if forbidden(rtype):
            bad.append((logical, rtype))
    return table, bad


def main(argv):
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        with open(argv[1]) as f:
            change_set = json.load(f)
    except (OSError, ValueError) as e:
        print(f"cannot read change set: {e}", file=sys.stderr)
        return 2
    table, bad = check(change_set)
    print("\n".join(table))
    if bad:
        for logical, rtype in bad:
            print(f"FORBIDDEN: {logical} {rtype}", file=sys.stderr)
        return 1
    print("OK: no ECS/Fargate/EC2 instance or other server resources")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
