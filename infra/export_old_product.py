#!/usr/bin/env python3
"""Turn `aws dynamodb query` output from the OLD product table into a
products.json list for infra/seed.sh.  Read-only on the old side:

  AWS_PROFILE=default aws dynamodb query --region ap-southeast-1 \
    --table-name product-table-dev-manual \
    --key-condition-expression 'iprcode = :i' \
    --expression-attribute-values '{":i": {"N": "171670"}}' > old.json
  python3 infra/export_old_product.py old.json > products.json

The old table (villaProductDatabase.schema.KeySchema) keeps product fields
as a JSON string in `data`, keyed by iprcode/cprcode numbers.
"""

import json
import sys


def attr(value):
    """Decode one DynamoDB-JSON attribute value."""
    (kind, raw), = value.items()
    if kind == "S":
        return raw
    if kind == "N":
        number = float(raw)
        return int(number) if number.is_integer() else number
    if kind == "BOOL":
        return raw
    if kind == "NULL":
        return None
    if kind == "M":
        return {k: attr(v) for k, v in raw.items()}
    if kind == "L":
        return [attr(v) for v in raw]
    raise ValueError(f"unsupported attribute type {kind}")


def old_item_to_product(item):
    decoded = {k: attr(v) for k, v in item.items()}
    data = decoded.get("data") or {}
    if isinstance(data, str):
        data = json.loads(data)
    product = dict(data)
    product["iprcode"] = int(decoded["iprcode"])
    product["cprcode"] = int(decoded["cprcode"])
    return product


def main(argv):
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    with open(argv[1]) as f:
        result = json.load(f)
    products = [old_item_to_product(i) for i in result.get("Items", [])]
    json.dump(products, sys.stdout, ensure_ascii=False, indent=1)
    print()
    return 0 if products else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
