"""Static checks on infra/ (vps-52s): template guardrails, change-set guard,
old-table export.  No AWS calls."""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]
INFRA = ROOT / "infra"
sys.path.insert(0, str(INFRA))

import check_changeset  # noqa: E402
import export_old_product  # noqa: E402


class CfnLoader(yaml.SafeLoader):
    pass


def _tag(loader, suffix, node):
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node, deep=True)
    else:
        value = loader.construct_mapping(node, deep=True)
    return {suffix: value}


CfnLoader.add_multi_constructor("!", _tag)


@pytest.fixture(scope="module")
def template():
    return yaml.load((INFRA / "template.yaml").read_text(), Loader=CfnLoader)


def resources(template, rtype):
    return {k: v for k, v in template["Resources"].items() if v["Type"] == rtype}


def test_stage_is_dev_only(template):
    assert template["Parameters"]["Stage"]["AllowedValues"] == ["dev"]


def test_no_server_resources_and_no_vpc(template):
    for name, res in template["Resources"].items():
        assert not check_changeset.forbidden(res["Type"]), name
        assert "VpcConfig" not in res.get("Properties", {}), name
    assert "VpcConfig" not in template["Globals"]["Function"]


def test_buckets_block_public_access_encrypt_and_force_tls(template):
    buckets = resources(template, "AWS::S3::Bucket")
    assert set(buckets) == {"InputBucket", "ProductBucket"}
    policies = resources(template, "AWS::S3::BucketPolicy")
    tls_buckets = set()
    for pol in policies.values():
        stmt = pol["Properties"]["PolicyDocument"]["Statement"][0]
        assert stmt["Effect"] == "Deny" and stmt["Condition"]["Bool"]["aws:SecureTransport"] == "false"
        tls_buckets.add(pol["Properties"]["Bucket"]["Ref"])
    for name, bucket in buckets.items():
        props = bucket["Properties"]
        assert props["PublicAccessBlockConfiguration"] == {
            "BlockPublicAcls": True,
            "BlockPublicPolicy": True,
            "IgnorePublicAcls": True,
            "RestrictPublicBuckets": True,
        }, name
        sse = props["BucketEncryption"]["ServerSideEncryptionConfiguration"][0]
        assert sse["ServerSideEncryptionByDefault"]["SSEAlgorithm"] in ("AES256", "aws:kms")
        assert props["OwnershipControls"]["Rules"][0]["ObjectOwnership"] == "BucketOwnerEnforced"
        assert name in tls_buckets


def test_uploaded_input_files_expire(template):
    rules = template["Resources"]["InputBucket"]["Properties"]["LifecycleConfiguration"]["Rules"]
    expire = [r for r in rules if r.get("Prefix") == "uploads/" and "ExpirationInDays" in r]
    assert expire and expire[0]["Status"] == "Enabled"


def test_api_requires_key_with_throttled_usage_plan(template):
    api = template["Resources"]["ProductApi"]["Properties"]
    assert api["Auth"]["ApiKeyRequired"] is True
    plan = api["Auth"]["UsagePlan"]
    assert plan["CreateUsagePlan"] == "PER_API"
    assert set(plan["Throttle"]) == {"RateLimit", "BurstLimit"}
    assert plan["Quota"]["Period"] == "DAY"


def test_routes_match_acceptance(template):
    routes = set()
    for res in resources(template, "AWS::Serverless::Function").values():
        for ev in res["Properties"].get("Events", {}).values():
            if ev["Type"] == "Api":
                routes.add((ev["Properties"]["Method"], ev["Properties"]["Path"]))
                assert ev["Properties"]["RestApiId"] == {"Ref": "ProductApi"}
    assert routes == {
        ("GET", "/product"),
        ("POST", "/products/list"),
        ("GET", "/products/all-url"),
        ("POST", "/upload-request"),
        ("POST", "/ingest"),
    }


def test_handlers_exist(template):
    sys.path.insert(0, str(INFRA / "handlers"))
    import product_api

    for res in resources(template, "AWS::Serverless::Function").values():
        module, func = res["Properties"]["Handler"].split(".")
        assert module == "product_api" and callable(getattr(product_api, func))


def test_function_names_do_not_reuse_old_product_names(template):
    for res in resources(template, "AWS::Serverless::Function").values():
        name = res["Properties"]["FunctionName"]["Sub"]
        assert name.startswith("product-api-"), name


def test_no_secrets_in_infra():
    pattern = re.compile(r"hooks\.slack\.com|LINE_TOKEN|AKIA[0-9A-Z]{16}|aws_secret_access_key", re.I)
    for path in INFRA.rglob("*"):
        if path.is_file() and ".aws-sam" not in path.parts:
            assert not pattern.search(path.read_text(errors="ignore")), path


# ------------------------------------------------------------ change-set guard


def _cs(*types):
    return {
        "ChangeSetName": "t",
        "StackName": "villa-product-api-dev",
        "Changes": [
            {"ResourceChange": {"Action": "Add", "LogicalResourceId": f"R{i}", "ResourceType": t}}
            for i, t in enumerate(types)
        ],
    }


@pytest.mark.parametrize(
    "rtype", ["AWS::ECS::Service", "AWS::ECS::TaskDefinition", "AWS::EC2::Instance", "AWS::EKS::Cluster", "Custom::FargateThing"]
)
def test_changeset_guard_refuses_servers(tmp_path, rtype):
    f = tmp_path / "cs.json"
    f.write_text(json.dumps(_cs("AWS::Lambda::Function", rtype)))
    run = subprocess.run([sys.executable, str(INFRA / "check_changeset.py"), str(f)], capture_output=True, text=True)
    assert run.returncode == 1
    assert "FORBIDDEN" in run.stderr


def test_changeset_guard_passes_serverless(tmp_path):
    f = tmp_path / "cs.json"
    f.write_text(json.dumps(_cs("AWS::Lambda::Function", "AWS::ApiGateway::RestApi", "AWS::S3::Bucket", "AWS::EC2::SecurityGroup")))
    run = subprocess.run([sys.executable, str(INFRA / "check_changeset.py"), str(f)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert "AWS::ApiGateway::RestApi" in run.stdout


def test_changeset_guard_bad_input(tmp_path):
    run = subprocess.run([sys.executable, str(INFRA / "check_changeset.py"), str(tmp_path / "missing")], capture_output=True)
    assert run.returncode == 2


# ------------------------------------------------------------ scripts


def test_scripts_guard_account_and_parse():
    lib = (INFRA / "lib.sh").read_text()
    assert "EXPECTED_ACCOUNT=917866274866" in lib
    for script in ("deploy.sh", "smoke.sh", "seed.sh", "teardown.sh"):
        text = (INFRA / script).read_text()
        assert "require_villaai2" in text, script
        assert subprocess.run(["bash", "-n", str(INFRA / script)]).returncode == 0, script
    assert "echo \"$API_KEY\"" not in lib


def test_export_old_item_decodes_json_data():
    item = {
        "iprcode": {"N": "171670"},
        "cprcode": {"N": "171670"},
        "needsUpdate": {"S": "N"},
        "data": {"S": json.dumps({"hema_name_en": "Milk", "sellingPrice": 55, "iprcode": 171670})},
    }
    assert export_old_product.old_item_to_product(item) == {
        "hema_name_en": "Milk",
        "sellingPrice": 55,
        "iprcode": 171670,
        "cprcode": 171670,
    }
