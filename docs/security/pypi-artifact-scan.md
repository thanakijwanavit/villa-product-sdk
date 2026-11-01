# PyPI artifact secret scan

<!-- written by tools/scan_pypi_artifacts.py (vps-eht); a re-run replaces this file, Triage included -->

- Scanned: 2026-11-01 06:19 UTC with gitleaks 8.30.1, default rules (`gitleaks dir --redact`).
- Source: every file of every release on PyPI of villaProductSdk, lambdasdk, s3bz, nicHelper, awsSchema.
- Result: 412 files (10283 files inside them), 208 findings, 0 errors. A finding is shown as path:line [rule] only; secret values are never written here.
- Each file was checked against its sha256, unpacked without running anything and scanned in full: `*.dist-info/` (wheel METADATA) and archives inside the package included, `gitleaks:allow` comments and any `.gitleaks.toml` or `.gitleaksignore` shipped in the package ignored.

## Triage

villaProductSdk and lambdasdk are clean, and no secret value (password, secret key, token) is in any published file of
the five packages. The 208 findings come from two README patterns:

| package | findings | verdict | bead |
|---|---|---|---|
| s3bz | 100 in 34 files: README.md, PKG-INFO and egg-info/PKG-INFO of the sdist and METADATA of the wheel, for 0.0.3-0.1.5 and 0.1.19-0.1.27 (17 versions; the other 14 are clean) | **Real, low risk.** nbdev renders notebook output into the README, and that output prints presigned S3 links for bucket pybz-test with 3 different AWS access key IDs. These are key IDs only, with no secret access key, and the links expired in 2020-2021. | vps-f69: confirm in IAM that the 3 keys are inactive, and keep presigned output out of future READMEs |
| nicHelper | 4 in 2 files (0.0.1 only) | **Real, low risk.** It is the same README output, and the key ID is the one in s3bz 0.1.1-0.1.5. | vps-agm (closes with vps-f69) |
| awsSchema | 104 in all 42 files | **False positive.** The `generic-api-key` hit is `"Postman-Token": "<uuid>"` in the sample API Gateway event in the README: a per-request nonce that Postman adds, not a credential. The same event has a private `sourceIp` and an 11-digit `accountId` (real AWS account IDs have 12 digits), and neither is a credential. | none |

How the verdicts were checked (values were never printed):

- Every one of the 10283 files inside the 412 archives is text: .py, .txt, .md, .cfg, .ini, PKG-INFO, METADATA, RECORD,
  WHEEL, LICENSE. There are no binaries, .pyc files, notebooks or nested archives, so nothing sat outside what gitleaks reads.
- A separate AWS key-ID regex, run without gitleaks' word boundaries, matches exactly the 36 files that gitleaks flagged.
- No secret-shaped 40-character token sits near any key ID. No .py file (parsed with AST) and no README, PKG-INFO or
  METADATA has a string literal assigned to a credential name (password, pw, secret, token, api_key, access_key, ...),
  and no URL has user:password@. This was checked separately because gitleaks' generic rule skips low-entropy values.
- nicHelper ships `nicHelper/secrets.py`. It is a `getSecret()` helper that reads AWS Secrets Manager through boto3 and
  holds no credentials.
- The PyPI JSON API and the Simple API (PEP 691) list the same 412 files, and none is yanked.

Re-run with `tools/scan_pypi_artifacts.sh villaProductSdk lambdasdk s3bz nicHelper awsSchema --markdown
docs/security/pypi-artifact-scan.md`; it needs network access and gitleaks 8.19 or later. It exits 1 for as long as the
files above stay on PyPI. `tools/scan_pypi_artifacts.sh villaProductSdk` alone exits 0. Before uploading a release, run
`tools/scan_pypi_artifacts.sh --local dist`.

## Totals

| package | versions | files | findings | errors |
|---|---|---|---|---|
| villaProductSdk | 19 | 38 | 0 | 0 |
| lambdasdk | 20 | 40 | 0 | 0 |
| s3bz | 31 | 62 | 100 | 0 |
| nicHelper | 115 | 230 | 4 | 0 |
| awsSchema | 21 | 42 | 104 | 0 |

## Every file scanned

| package | version | file | sha256 (first 12) | files inside | status | findings (path:line [rule]) |
|---|---|---|---|---|---|---|
| villaProductSdk | 0.0.1 | villaProductSdk-0.0.1-py3-none-any.whl | e280572309d9 | 13 | ok | none |
| villaProductSdk | 0.0.1 | villaProductSdk-0.0.1.tar.gz | 3797e7fc60bd | 22 | ok | none |
| villaProductSdk | 0.0.10 | villaProductSdk-0.0.10-py3-none-any.whl | 41ef62f001b0 | 18 | ok | none |
| villaProductSdk | 0.0.10 | villaProductSdk-0.0.10.tar.gz | 124ec7b91f54 | 27 | ok | none |
| villaProductSdk | 0.0.11 | villaProductSdk-0.0.11-py3-none-any.whl | 02f6d3fb1d6d | 18 | ok | none |
| villaProductSdk | 0.0.11 | villaProductSdk-0.0.11.tar.gz | 1476a5298282 | 27 | ok | none |
| villaProductSdk | 0.0.12 | villaProductSdk-0.0.12-py3-none-any.whl | aa93dbab3770 | 18 | ok | none |
| villaProductSdk | 0.0.12 | villaProductSdk-0.0.12.tar.gz | 9dea0881486b | 27 | ok | none |
| villaProductSdk | 0.0.13 | villaProductSdk-0.0.13-py3-none-any.whl | 17c4f620baab | 18 | ok | none |
| villaProductSdk | 0.0.13 | villaProductSdk-0.0.13.tar.gz | 53cff5ce3f40 | 27 | ok | none |
| villaProductSdk | 0.0.14 | villaProductSdk-0.0.14-py3-none-any.whl | 71794083ac80 | 18 | ok | none |
| villaProductSdk | 0.0.14 | villaProductSdk-0.0.14.tar.gz | ec6de434963a | 27 | ok | none |
| villaProductSdk | 0.0.15 | villaProductSdk-0.0.15-py3-none-any.whl | 3db246a843a0 | 18 | ok | none |
| villaProductSdk | 0.0.15 | villaProductSdk-0.0.15.tar.gz | 539848f796b0 | 27 | ok | none |
| villaProductSdk | 0.0.16 | villaProductSdk-0.0.16-py3-none-any.whl | 83a09a05510f | 18 | ok | none |
| villaProductSdk | 0.0.16 | villaProductSdk-0.0.16.tar.gz | 5f2e6f91c0d5 | 27 | ok | none |
| villaProductSdk | 0.0.17 | villaProductSdk-0.0.17-py3-none-any.whl | 5e40cd1ed9bd | 18 | ok | none |
| villaProductSdk | 0.0.17 | villaProductSdk-0.0.17.tar.gz | 920403c3744f | 27 | ok | none |
| villaProductSdk | 0.0.18 | villaProductSdk-0.0.18-py3-none-any.whl | 9180483379ca | 18 | ok | none |
| villaProductSdk | 0.0.18 | villaProductSdk-0.0.18.tar.gz | 689c829feed2 | 27 | ok | none |
| villaProductSdk | 0.0.19 | villaProductSdk-0.0.19-py3-none-any.whl | b71eb6322965 | 18 | ok | none |
| villaProductSdk | 0.0.19 | villaProductSdk-0.0.19.tar.gz | 5f270800ba95 | 27 | ok | none |
| villaProductSdk | 0.0.2 | villaProductSdk-0.0.2-py3-none-any.whl | b22e1e14b675 | 18 | ok | none |
| villaProductSdk | 0.0.2 | villaProductSdk-0.0.2.tar.gz | c8c30e72128e | 27 | ok | none |
| villaProductSdk | 0.0.20 | villaProductSdk-0.0.20-py3-none-any.whl | 367f39fcf3f7 | 18 | ok | none |
| villaProductSdk | 0.0.20 | villaProductSdk-0.0.20.tar.gz | afc4cf3564b6 | 27 | ok | none |
| villaProductSdk | 0.0.3 | villaProductSdk-0.0.3-py3-none-any.whl | b1dfdafb6aa1 | 18 | ok | none |
| villaProductSdk | 0.0.3 | villaProductSdk-0.0.3.tar.gz | aa134298a911 | 27 | ok | none |
| villaProductSdk | 0.0.5 | villaProductSdk-0.0.5-py3-none-any.whl | dd6834cc9a31 | 18 | ok | none |
| villaProductSdk | 0.0.5 | villaProductSdk-0.0.5.tar.gz | e0fb5a1edb00 | 27 | ok | none |
| villaProductSdk | 0.0.6 | villaProductSdk-0.0.6-py3-none-any.whl | 257da4dcddd0 | 18 | ok | none |
| villaProductSdk | 0.0.6 | villaProductSdk-0.0.6.tar.gz | 5643e8d16d40 | 27 | ok | none |
| villaProductSdk | 0.0.7 | villaProductSdk-0.0.7-py3-none-any.whl | 403475dca0ca | 18 | ok | none |
| villaProductSdk | 0.0.7 | villaProductSdk-0.0.7.tar.gz | 8585a5b836e5 | 27 | ok | none |
| villaProductSdk | 0.0.8 | villaProductSdk-0.0.8-py3-none-any.whl | 83675ff8cd46 | 18 | ok | none |
| villaProductSdk | 0.0.8 | villaProductSdk-0.0.8.tar.gz | 27bd6d3777ff | 27 | ok | none |
| villaProductSdk | 0.0.9 | villaProductSdk-0.0.9-py3-none-any.whl | 2f11e1fbb3cb | 18 | ok | none |
| villaProductSdk | 0.0.9 | villaProductSdk-0.0.9.tar.gz | 2368c0884b7e | 27 | ok | none |
| lambdasdk | 0.0.1 | lambdasdk-0.0.1-py3-none-any.whl | 578ffe23cb3c | 21 | ok | none |
| lambdasdk | 0.0.1 | lambdasdk-0.0.1.tar.gz | f9eece08cc22 | 16 | ok | none |
| lambdasdk | 0.0.10 | lambdasdk-0.0.10-py3-none-any.whl | f79bd91097fe | 22 | ok | none |
| lambdasdk | 0.0.10 | lambdasdk-0.0.10.tar.gz | fcfc75fd1b99 | 16 | ok | none |
| lambdasdk | 0.0.11 | lambdasdk-0.0.11-py3-none-any.whl | 2bccd186eee0 | 22 | ok | none |
| lambdasdk | 0.0.11 | lambdasdk-0.0.11.tar.gz | 41725c78b3ce | 16 | ok | none |
| lambdasdk | 0.0.12 | lambdasdk-0.0.12-py3-none-any.whl | 0a692371d491 | 9 | ok | none |
| lambdasdk | 0.0.12 | lambdasdk-0.0.12.tar.gz | 677c1d386ac9 | 18 | ok | none |
| lambdasdk | 0.0.13 | lambdasdk-0.0.13-py3-none-any.whl | d90872d80357 | 9 | ok | none |
| lambdasdk | 0.0.13 | lambdasdk-0.0.13.tar.gz | 54fce248d9f5 | 18 | ok | none |
| lambdasdk | 0.0.14 | lambdasdk-0.0.14-py3-none-any.whl | d41203cc4c08 | 9 | ok | none |
| lambdasdk | 0.0.14 | lambdasdk-0.0.14.tar.gz | fb6e5949f445 | 18 | ok | none |
| lambdasdk | 0.0.15 | lambdasdk-0.0.15-py3-none-any.whl | def61129eb97 | 9 | ok | none |
| lambdasdk | 0.0.15 | lambdasdk-0.0.15.tar.gz | e1647e177f13 | 18 | ok | none |
| lambdasdk | 0.0.16 | lambdasdk-0.0.16-py3-none-any.whl | 03ccbf92b686 | 9 | ok | none |
| lambdasdk | 0.0.16 | lambdasdk-0.0.16.tar.gz | 2e91ca012157 | 18 | ok | none |
| lambdasdk | 0.0.3 | lambdasdk-0.0.3-py3-none-any.whl | c81c3c7fd4c4 | 21 | ok | none |
| lambdasdk | 0.0.3 | lambdasdk-0.0.3.tar.gz | 605ab9f0ad5f | 15 | ok | none |
| lambdasdk | 0.0.4 | lambdasdk-0.0.4-py3-none-any.whl | fca7da44ef16 | 20 | ok | none |
| lambdasdk | 0.0.4 | lambdasdk-0.0.4.tar.gz | b7378b6c6f07 | 14 | ok | none |
| lambdasdk | 0.0.5 | lambdasdk-0.0.5-py3-none-any.whl | 2fda1c2382d4 | 21 | ok | none |
| lambdasdk | 0.0.5 | lambdasdk-0.0.5.tar.gz | 37411b9ced04 | 15 | ok | none |
| lambdasdk | 0.0.6 | lambdasdk-0.0.6-py3-none-any.whl | f806464e9292 | 22 | ok | none |
| lambdasdk | 0.0.6 | lambdasdk-0.0.6.tar.gz | 421450061df5 | 16 | ok | none |
| lambdasdk | 0.0.7 | lambdasdk-0.0.7-py3-none-any.whl | 4b767ad7a131 | 22 | ok | none |
| lambdasdk | 0.0.7 | lambdasdk-0.0.7.tar.gz | 79706e10b441 | 16 | ok | none |
| lambdasdk | 0.0.8 | lambdasdk-0.0.8-py3-none-any.whl | 39f92f4bb31d | 22 | ok | none |
| lambdasdk | 0.0.8 | lambdasdk-0.0.8.tar.gz | bb32da750f0a | 16 | ok | none |
| lambdasdk | 0.0.9 | lambdasdk-0.0.9-py3-none-any.whl | 114870f69990 | 22 | ok | none |
| lambdasdk | 0.0.9 | lambdasdk-0.0.9.tar.gz | 13ae72e20609 | 16 | ok | none |
| lambdasdk | 0.1.0 | lambdasdk-0.1.0-py3-none-any.whl | fbbc7a398aae | 9 | ok | none |
| lambdasdk | 0.1.0 | lambdasdk-0.1.0.tar.gz | 874f92ff8b28 | 18 | ok | none |
| lambdasdk | 0.1.1 | lambdasdk-0.1.1-py3-none-any.whl | 138ae0cd06ab | 9 | ok | none |
| lambdasdk | 0.1.1 | lambdasdk-0.1.1.tar.gz | 1fe5fb10a201 | 18 | ok | none |
| lambdasdk | 0.1.2 | lambdasdk-0.1.2-py3-none-any.whl | 30b2274cccfe | 9 | ok | none |
| lambdasdk | 0.1.2 | lambdasdk-0.1.2.tar.gz | 718896311751 | 18 | ok | none |
| lambdasdk | 0.1.3 | lambdasdk-0.1.3-py3-none-any.whl | 0319d7430621 | 9 | ok | none |
| lambdasdk | 0.1.3 | lambdasdk-0.1.3.tar.gz | 9e2d232539c6 | 17 | ok | none |
| lambdasdk | 0.1.4 | lambdasdk-0.1.4-py3-none-any.whl | 3fd5c0af0fa9 | 9 | ok | none |
| lambdasdk | 0.1.4 | lambdasdk-0.1.4.tar.gz | 35008a72b559 | 17 | ok | none |
| s3bz | 0.0.1 | s3bz-0.0.1-py3-none-any.whl | 102f172ceee0 | 12 | ok | none |
| s3bz | 0.0.1 | s3bz-0.0.1.tar.gz | c2eef146bd40 | 20 | ok | none |
| s3bz | 0.0.2 | s3bz-0.0.2-py3-none-any.whl | 17692c11db60 | 12 | ok | none |
| s3bz | 0.0.2 | s3bz-0.0.2.tar.gz | 6603e655fe10 | 20 | ok | none |
| s3bz | 0.0.3 | s3bz-0.0.3-py3-none-any.whl | 2d4525460d43 | 12 | ok | `s3bz-0.0.3.dist-info/METADATA:105` [aws-access-token] |
| s3bz | 0.0.3 | s3bz-0.0.3.tar.gz | ac9dffb98dbd | 21 | ok | `s3bz-0.0.3/PKG-INFO:92` [aws-access-token]<br>`s3bz-0.0.3/README.md:84` [aws-access-token]<br>`s3bz-0.0.3/s3bz.egg-info/PKG-INFO:92` [aws-access-token] |
| s3bz | 0.0.4 | s3bz-0.0.4-py3-none-any.whl | b7c83d1a8e19 | 12 | ok | `s3bz-0.0.4.dist-info/METADATA:106` [aws-access-token] |
| s3bz | 0.0.4 | s3bz-0.0.4.tar.gz | e9d050cb330a | 21 | ok | `s3bz-0.0.4/PKG-INFO:92` [aws-access-token]<br>`s3bz-0.0.4/README.md:84` [aws-access-token]<br>`s3bz-0.0.4/s3bz.egg-info/PKG-INFO:92` [aws-access-token] |
| s3bz | 0.0.5 | s3bz-0.0.5-py3-none-any.whl | f57da0a7c556 | 12 | ok | `s3bz-0.0.5.dist-info/METADATA:106` [aws-access-token] |
| s3bz | 0.0.5 | s3bz-0.0.5.tar.gz | 934f51a4ac8a | 21 | ok | `s3bz-0.0.5/PKG-INFO:92` [aws-access-token]<br>`s3bz-0.0.5/README.md:84` [aws-access-token]<br>`s3bz-0.0.5/s3bz.egg-info/PKG-INFO:92` [aws-access-token] |
| s3bz | 0.1.0 | s3bz-0.1.0-py3-none-any.whl | ee122a382d3f | 12 | ok | `s3bz-0.1.0.dist-info/METADATA:106` [aws-access-token] |
| s3bz | 0.1.0 | s3bz-0.1.0.tar.gz | 197f34dd25e6 | 21 | ok | `s3bz-0.1.0/PKG-INFO:92` [aws-access-token]<br>`s3bz-0.1.0/README.md:84` [aws-access-token]<br>`s3bz-0.1.0/s3bz.egg-info/PKG-INFO:92` [aws-access-token] |
| s3bz | 0.1.1 | s3bz-0.1.1-py3-none-any.whl | aec5a8c8d7c9 | 12 | ok | `s3bz-0.1.1.dist-info/METADATA:108` [aws-access-token] |
| s3bz | 0.1.1 | s3bz-0.1.1.tar.gz | 058a79023860 | 21 | ok | `s3bz-0.1.1/PKG-INFO:94` [aws-access-token]<br>`s3bz-0.1.1/README.md:86` [aws-access-token]<br>`s3bz-0.1.1/s3bz.egg-info/PKG-INFO:94` [aws-access-token] |
| s3bz | 0.1.10 | s3bz-0.1.10-py3-none-any.whl | 3a33e07a1e4a | 12 | ok | none |
| s3bz | 0.1.10 | s3bz-0.1.10.tar.gz | 3c7b40908e8e | 21 | ok | none |
| s3bz | 0.1.11 | s3bz-0.1.11-py3-none-any.whl | f59c15f304e2 | 12 | ok | none |
| s3bz | 0.1.11 | s3bz-0.1.11.tar.gz | 91dd908fce8b | 21 | ok | none |
| s3bz | 0.1.12 | s3bz-0.1.12-py3-none-any.whl | 517a33cdb19a | 12 | ok | none |
| s3bz | 0.1.12 | s3bz-0.1.12.tar.gz | a92493a761fb | 21 | ok | none |
| s3bz | 0.1.13 | s3bz-0.1.13-py3-none-any.whl | eb2bcf3fef1d | 12 | ok | none |
| s3bz | 0.1.13 | s3bz-0.1.13.tar.gz | 13f0564a470b | 21 | ok | none |
| s3bz | 0.1.14 | s3bz-0.1.14-py3-none-any.whl | 59588c50cf73 | 12 | ok | none |
| s3bz | 0.1.14 | s3bz-0.1.14.tar.gz | 815ff95d09af | 21 | ok | none |
| s3bz | 0.1.15 | s3bz-0.1.15-py3-none-any.whl | 6f5a1dabf8ee | 12 | ok | none |
| s3bz | 0.1.15 | s3bz-0.1.15.tar.gz | 6dae7c617309 | 21 | ok | none |
| s3bz | 0.1.17 | s3bz-0.1.17-py3-none-any.whl | d95ff6c52054 | 12 | ok | none |
| s3bz | 0.1.17 | s3bz-0.1.17.tar.gz | 07526bbb596a | 21 | ok | none |
| s3bz | 0.1.18 | s3bz-0.1.18-py3-none-any.whl | 2607cde71af8 | 12 | ok | none |
| s3bz | 0.1.18 | s3bz-0.1.18.tar.gz | 34fb7dcbafc4 | 21 | ok | none |
| s3bz | 0.1.19 | s3bz-0.1.19-py3-none-any.whl | c1f6c352ecff | 12 | ok | `s3bz-0.1.19.dist-info/METADATA:148` [aws-access-token]<br>`s3bz-0.1.19.dist-info/METADATA:255` [aws-access-token] |
| s3bz | 0.1.19 | s3bz-0.1.19.tar.gz | bef8e8aaa5ae | 21 | ok | `s3bz-0.1.19/PKG-INFO:133` [aws-access-token]<br>`s3bz-0.1.19/PKG-INFO:240` [aws-access-token]<br>`s3bz-0.1.19/README.md:125` [aws-access-token]<br>`s3bz-0.1.19/README.md:232` [aws-access-token]<br>`s3bz-0.1.19/s3bz.egg-info/PKG-INFO:133` [aws-access-token]<br>`s3bz-0.1.19/s3bz.egg-info/PKG-INFO:240` [aws-access-token] |
| s3bz | 0.1.2 | s3bz-0.1.2-py3-none-any.whl | 82e9bd08428c | 12 | ok | `s3bz-0.1.2.dist-info/METADATA:108` [aws-access-token] |
| s3bz | 0.1.2 | s3bz-0.1.2.tar.gz | c01ad9f2e3a2 | 21 | ok | `s3bz-0.1.2/PKG-INFO:94` [aws-access-token]<br>`s3bz-0.1.2/README.md:86` [aws-access-token]<br>`s3bz-0.1.2/s3bz.egg-info/PKG-INFO:94` [aws-access-token] |
| s3bz | 0.1.20 | s3bz-0.1.20-py3-none-any.whl | 85491c04d8d7 | 12 | ok | `s3bz-0.1.20.dist-info/METADATA:148` [aws-access-token]<br>`s3bz-0.1.20.dist-info/METADATA:306` [aws-access-token] |
| s3bz | 0.1.20 | s3bz-0.1.20.tar.gz | 27b47725d0b1 | 21 | ok | `s3bz-0.1.20/PKG-INFO:133` [aws-access-token]<br>`s3bz-0.1.20/PKG-INFO:291` [aws-access-token]<br>`s3bz-0.1.20/README.md:125` [aws-access-token]<br>`s3bz-0.1.20/README.md:283` [aws-access-token]<br>`s3bz-0.1.20/s3bz.egg-info/PKG-INFO:133` [aws-access-token]<br>`s3bz-0.1.20/s3bz.egg-info/PKG-INFO:291` [aws-access-token] |
| s3bz | 0.1.21 | s3bz-0.1.21-py3-none-any.whl | 1e2e8e12509f | 12 | ok | `s3bz-0.1.21.dist-info/METADATA:148` [aws-access-token]<br>`s3bz-0.1.21.dist-info/METADATA:306` [aws-access-token] |
| s3bz | 0.1.21 | s3bz-0.1.21.tar.gz | ad6b83d36f07 | 21 | ok | `s3bz-0.1.21/PKG-INFO:133` [aws-access-token]<br>`s3bz-0.1.21/PKG-INFO:291` [aws-access-token]<br>`s3bz-0.1.21/README.md:125` [aws-access-token]<br>`s3bz-0.1.21/README.md:283` [aws-access-token]<br>`s3bz-0.1.21/s3bz.egg-info/PKG-INFO:133` [aws-access-token]<br>`s3bz-0.1.21/s3bz.egg-info/PKG-INFO:291` [aws-access-token] |
| s3bz | 0.1.22 | s3bz-0.1.22-py3-none-any.whl | f13bc97a8c50 | 12 | ok | `s3bz-0.1.22.dist-info/METADATA:148` [aws-access-token]<br>`s3bz-0.1.22.dist-info/METADATA:306` [aws-access-token] |
| s3bz | 0.1.22 | s3bz-0.1.22.tar.gz | caeb0ce2616e | 21 | ok | `s3bz-0.1.22/PKG-INFO:133` [aws-access-token]<br>`s3bz-0.1.22/PKG-INFO:291` [aws-access-token]<br>`s3bz-0.1.22/README.md:125` [aws-access-token]<br>`s3bz-0.1.22/README.md:283` [aws-access-token]<br>`s3bz-0.1.22/s3bz.egg-info/PKG-INFO:133` [aws-access-token]<br>`s3bz-0.1.22/s3bz.egg-info/PKG-INFO:291` [aws-access-token] |
| s3bz | 0.1.23 | s3bz-0.1.23-py3-none-any.whl | 5c65812323d3 | 12 | ok | `s3bz-0.1.23.dist-info/METADATA:148` [aws-access-token]<br>`s3bz-0.1.23.dist-info/METADATA:306` [aws-access-token] |
| s3bz | 0.1.23 | s3bz-0.1.23.tar.gz | d8cdf9572534 | 21 | ok | `s3bz-0.1.23/PKG-INFO:133` [aws-access-token]<br>`s3bz-0.1.23/PKG-INFO:291` [aws-access-token]<br>`s3bz-0.1.23/README.md:125` [aws-access-token]<br>`s3bz-0.1.23/README.md:283` [aws-access-token]<br>`s3bz-0.1.23/s3bz.egg-info/PKG-INFO:133` [aws-access-token]<br>`s3bz-0.1.23/s3bz.egg-info/PKG-INFO:291` [aws-access-token] |
| s3bz | 0.1.25 | s3bz-0.1.25-py3-none-any.whl | 01437a97d8bf | 12 | ok | `s3bz-0.1.25.dist-info/METADATA:148` [aws-access-token]<br>`s3bz-0.1.25.dist-info/METADATA:306` [aws-access-token] |
| s3bz | 0.1.25 | s3bz-0.1.25.tar.gz | d9a9acbbf1a4 | 21 | ok | `s3bz-0.1.25/PKG-INFO:133` [aws-access-token]<br>`s3bz-0.1.25/PKG-INFO:291` [aws-access-token]<br>`s3bz-0.1.25/README.md:125` [aws-access-token]<br>`s3bz-0.1.25/README.md:283` [aws-access-token]<br>`s3bz-0.1.25/s3bz.egg-info/PKG-INFO:133` [aws-access-token]<br>`s3bz-0.1.25/s3bz.egg-info/PKG-INFO:291` [aws-access-token] |
| s3bz | 0.1.26 | s3bz-0.1.26-py3-none-any.whl | fcf6ba8337e2 | 12 | ok | `s3bz-0.1.26.dist-info/METADATA:148` [aws-access-token]<br>`s3bz-0.1.26.dist-info/METADATA:306` [aws-access-token] |
| s3bz | 0.1.26 | s3bz-0.1.26.tar.gz | 00689c860908 | 21 | ok | `s3bz-0.1.26/PKG-INFO:133` [aws-access-token]<br>`s3bz-0.1.26/PKG-INFO:291` [aws-access-token]<br>`s3bz-0.1.26/README.md:125` [aws-access-token]<br>`s3bz-0.1.26/README.md:283` [aws-access-token]<br>`s3bz-0.1.26/s3bz.egg-info/PKG-INFO:133` [aws-access-token]<br>`s3bz-0.1.26/s3bz.egg-info/PKG-INFO:291` [aws-access-token] |
| s3bz | 0.1.27 | s3bz-0.1.27-py3-none-any.whl | 3dd38675f1b4 | 12 | ok | `s3bz-0.1.27.dist-info/METADATA:148` [aws-access-token]<br>`s3bz-0.1.27.dist-info/METADATA:306` [aws-access-token] |
| s3bz | 0.1.27 | s3bz-0.1.27.tar.gz | 527310b574d9 | 21 | ok | `s3bz-0.1.27/PKG-INFO:133` [aws-access-token]<br>`s3bz-0.1.27/PKG-INFO:291` [aws-access-token]<br>`s3bz-0.1.27/README.md:125` [aws-access-token]<br>`s3bz-0.1.27/README.md:283` [aws-access-token]<br>`s3bz-0.1.27/s3bz.egg-info/PKG-INFO:133` [aws-access-token]<br>`s3bz-0.1.27/s3bz.egg-info/PKG-INFO:291` [aws-access-token] |
| s3bz | 0.1.3 | s3bz-0.1.3-py3-none-any.whl | f068544eca99 | 12 | ok | `s3bz-0.1.3.dist-info/METADATA:108` [aws-access-token] |
| s3bz | 0.1.3 | s3bz-0.1.3.tar.gz | 040071954b08 | 21 | ok | `s3bz-0.1.3/PKG-INFO:94` [aws-access-token]<br>`s3bz-0.1.3/README.md:86` [aws-access-token]<br>`s3bz-0.1.3/s3bz.egg-info/PKG-INFO:94` [aws-access-token] |
| s3bz | 0.1.4 | s3bz-0.1.4-py3-none-any.whl | b484c3cfd2de | 12 | ok | `s3bz-0.1.4.dist-info/METADATA:100` [aws-access-token] |
| s3bz | 0.1.4 | s3bz-0.1.4.tar.gz | 7804b08e5ed1 | 21 | ok | `s3bz-0.1.4/PKG-INFO:86` [aws-access-token]<br>`s3bz-0.1.4/README.md:78` [aws-access-token]<br>`s3bz-0.1.4/s3bz.egg-info/PKG-INFO:86` [aws-access-token] |
| s3bz | 0.1.5 | s3bz-0.1.5-py3-none-any.whl | d8e3dba4ea0a | 12 | ok | `s3bz-0.1.5.dist-info/METADATA:100` [aws-access-token] |
| s3bz | 0.1.5 | s3bz-0.1.5.tar.gz | e57ed6442896 | 21 | ok | `s3bz-0.1.5/PKG-INFO:86` [aws-access-token]<br>`s3bz-0.1.5/README.md:78` [aws-access-token]<br>`s3bz-0.1.5/s3bz.egg-info/PKG-INFO:86` [aws-access-token] |
| s3bz | 0.1.6 | s3bz-0.1.6-py3-none-any.whl | 12554396f0ed | 12 | ok | none |
| s3bz | 0.1.6 | s3bz-0.1.6.tar.gz | aa52bfd12537 | 21 | ok | none |
| s3bz | 0.1.7 | s3bz-0.1.7-py3-none-any.whl | c97ca0e2866b | 12 | ok | none |
| s3bz | 0.1.7 | s3bz-0.1.7.tar.gz | 335754b554be | 21 | ok | none |
| s3bz | 0.1.8 | s3bz-0.1.8-py3-none-any.whl | 37e17aa79e25 | 12 | ok | none |
| s3bz | 0.1.8 | s3bz-0.1.8.tar.gz | 5fadcf79daae | 21 | ok | none |
| s3bz | 0.1.9 | s3bz-0.1.9-py3-none-any.whl | 9d2297a3c66c | 12 | ok | none |
| s3bz | 0.1.9 | s3bz-0.1.9.tar.gz | bdcd00c02729 | 21 | ok | none |
| nicHelper | 0.0.1 | nicHelper-0.0.1-py3-none-any.whl | 3f05be6fbd93 | 15 | ok | `nicHelper-0.0.1.dist-info/METADATA:131` [aws-access-token] |
| nicHelper | 0.0.1 | nicHelper-0.0.1.tar.gz | 02b8a2490f7b | 21 | ok | `nicHelper-0.0.1/PKG-INFO:118` [aws-access-token]<br>`nicHelper-0.0.1/README.md:110` [aws-access-token]<br>`nicHelper-0.0.1/nicHelper.egg-info/PKG-INFO:118` [aws-access-token] |
| nicHelper | 0.0.10 | nicHelper-0.0.10-py3-none-any.whl | 6a143947f435 | 19 | ok | none |
| nicHelper | 0.0.10 | nicHelper-0.0.10.tar.gz | da92d74ec810 | 25 | ok | none |
| nicHelper | 0.0.100 | nicHelper-0.0.100-py3-none-any.whl | ca0848e014f8 | 33 | ok | none |
| nicHelper | 0.0.100 | nicHelper-0.0.100.tar.gz | d2c038ea0317 | 42 | ok | none |
| nicHelper | 0.0.101 | nicHelper-0.0.101-py3-none-any.whl | 7111f3badbbb | 33 | ok | none |
| nicHelper | 0.0.101 | nicHelper-0.0.101.tar.gz | 94eb41a62152 | 42 | ok | none |
| nicHelper | 0.0.102 | nicHelper-0.0.102-py3-none-any.whl | acc722e067d3 | 33 | ok | none |
| nicHelper | 0.0.102 | nicHelper-0.0.102.tar.gz | 0f55a0a2c435 | 42 | ok | none |
| nicHelper | 0.0.103 | nicHelper-0.0.103-py3-none-any.whl | 9cf380f46723 | 32 | ok | none |
| nicHelper | 0.0.103 | nicHelper-0.0.103.tar.gz | 5e8a50a4f42c | 41 | ok | none |
| nicHelper | 0.0.104 | nicHelper-0.0.104-py3-none-any.whl | ae51971d2897 | 33 | ok | none |
| nicHelper | 0.0.104 | nicHelper-0.0.104.tar.gz | defbc8575bc5 | 42 | ok | none |
| nicHelper | 0.0.105 | nicHelper-0.0.105-py3-none-any.whl | 381e264ca6e7 | 33 | ok | none |
| nicHelper | 0.0.105 | nicHelper-0.0.105.tar.gz | 5024774695c8 | 42 | ok | none |
| nicHelper | 0.0.107 | nicHelper-0.0.107-py3-none-any.whl | 70366ef666bf | 34 | ok | none |
| nicHelper | 0.0.107 | nicHelper-0.0.107.tar.gz | fcff5e5736ed | 43 | ok | none |
| nicHelper | 0.0.109 | nicHelper-0.0.109-py3-none-any.whl | 7fcd712039c6 | 34 | ok | none |
| nicHelper | 0.0.109 | nicHelper-0.0.109.tar.gz | 6a3e7ad77d69 | 43 | ok | none |
| nicHelper | 0.0.11 | nicHelper-0.0.11-py3-none-any.whl | d38b981e1057 | 20 | ok | none |
| nicHelper | 0.0.11 | nicHelper-0.0.11.tar.gz | 15342ab154f1 | 26 | ok | none |
| nicHelper | 0.0.110 | nicHelper-0.0.110-py3-none-any.whl | 59f4eeb2ae06 | 34 | ok | none |
| nicHelper | 0.0.110 | nicHelper-0.0.110.tar.gz | c4ac5f07d539 | 43 | ok | none |
| nicHelper | 0.0.115 | nicHelper-0.0.115-py3-none-any.whl | e14d8d60f93b | 34 | ok | none |
| nicHelper | 0.0.115 | nicHelper-0.0.115.tar.gz | ce165dc8240c | 43 | ok | none |
| nicHelper | 0.0.116 | nicHelper-0.0.116-py3-none-any.whl | e934882db9e3 | 34 | ok | none |
| nicHelper | 0.0.116 | nicHelper-0.0.116.tar.gz | 33a10d52241e | 43 | ok | none |
| nicHelper | 0.0.117 | nicHelper-0.0.117-py3-none-any.whl | eeafa4dd1ec9 | 34 | ok | none |
| nicHelper | 0.0.117 | nicHelper-0.0.117.tar.gz | 04fd63c6904e | 43 | ok | none |
| nicHelper | 0.0.118 | nicHelper-0.0.118-py3-none-any.whl | 2ae4f2ccddc2 | 35 | ok | none |
| nicHelper | 0.0.118 | nichelper-0.0.118.tar.gz | d17e8fc3e7ed | 44 | ok | none |
| nicHelper | 0.0.119 | nicHelper-0.0.119-py3-none-any.whl | ba12536e95d1 | 36 | ok | none |
| nicHelper | 0.0.119 | nichelper-0.0.119.tar.gz | 085bbc80b6e9 | 45 | ok | none |
| nicHelper | 0.0.12 | nicHelper-0.0.12-py3-none-any.whl | 2dd19d33101c | 20 | ok | none |
| nicHelper | 0.0.12 | nicHelper-0.0.12.tar.gz | 432ab5d997e1 | 26 | ok | none |
| nicHelper | 0.0.120 | nicHelper-0.0.120-py3-none-any.whl | 32545c316001 | 36 | ok | none |
| nicHelper | 0.0.120 | nichelper-0.0.120.tar.gz | 94ba643f43a6 | 45 | ok | none |
| nicHelper | 0.0.121 | nicHelper-0.0.121-py3-none-any.whl | d94b1f9f8721 | 39 | ok | none |
| nicHelper | 0.0.121 | nicHelper-0.0.121.tar.gz | 4d71274b28cc | 49 | ok | none |
| nicHelper | 0.0.122 | nicHelper-0.0.122-py3-none-any.whl | a395bc1c56f4 | 90 | ok | none |
| nicHelper | 0.0.122 | nicHelper-0.0.122.tar.gz | 234e2047563e | 99 | ok | none |
| nicHelper | 0.0.123 | nicHelper-0.0.123-py3-none-any.whl | eb3045e851b0 | 90 | ok | none |
| nicHelper | 0.0.123 | nicHelper-0.0.123.tar.gz | 0aeb34cedcc5 | 99 | ok | none |
| nicHelper | 0.0.13 | nicHelper-0.0.13-py3-none-any.whl | f671b1db4994 | 20 | ok | none |
| nicHelper | 0.0.13 | nicHelper-0.0.13.tar.gz | 5a9be64a3fc0 | 26 | ok | none |
| nicHelper | 0.0.14 | nicHelper-0.0.14-py3-none-any.whl | edaaac666929 | 20 | ok | none |
| nicHelper | 0.0.14 | nicHelper-0.0.14.tar.gz | 38fd137ea967 | 26 | ok | none |
| nicHelper | 0.0.15 | nicHelper-0.0.15-py3-none-any.whl | 66e9055d2232 | 20 | ok | none |
| nicHelper | 0.0.15 | nicHelper-0.0.15.tar.gz | a229ba7b648e | 26 | ok | none |
| nicHelper | 0.0.16 | nicHelper-0.0.16-py3-none-any.whl | 052a412c973b | 20 | ok | none |
| nicHelper | 0.0.16 | nicHelper-0.0.16.tar.gz | 5fcfc1642421 | 26 | ok | none |
| nicHelper | 0.0.17 | nicHelper-0.0.17-py3-none-any.whl | 43b9a1ad5f64 | 20 | ok | none |
| nicHelper | 0.0.17 | nicHelper-0.0.17.tar.gz | 3256b4e03c02 | 26 | ok | none |
| nicHelper | 0.0.18 | nicHelper-0.0.18-py3-none-any.whl | 6aae13ec98f9 | 20 | ok | none |
| nicHelper | 0.0.18 | nicHelper-0.0.18.tar.gz | 053128145f57 | 26 | ok | none |
| nicHelper | 0.0.19 | nicHelper-0.0.19-py3-none-any.whl | 9917682486ff | 21 | ok | none |
| nicHelper | 0.0.19 | nicHelper-0.0.19.tar.gz | 9f7abfce7848 | 27 | ok | none |
| nicHelper | 0.0.2 | nicHelper-0.0.2-py3-none-any.whl | 795e47857b0d | 16 | ok | none |
| nicHelper | 0.0.2 | nicHelper-0.0.2.tar.gz | 79a01720cb50 | 22 | ok | none |
| nicHelper | 0.0.20 | nicHelper-0.0.20-py3-none-any.whl | 131a8048532f | 21 | ok | none |
| nicHelper | 0.0.20 | nicHelper-0.0.20.tar.gz | 839210ee944e | 27 | ok | none |
| nicHelper | 0.0.21 | nicHelper-0.0.21-py3-none-any.whl | 54f178ad8a7b | 21 | ok | none |
| nicHelper | 0.0.21 | nicHelper-0.0.21.tar.gz | 3842dc291874 | 27 | ok | none |
| nicHelper | 0.0.22 | nicHelper-0.0.22-py3-none-any.whl | ed8b4d5c274d | 21 | ok | none |
| nicHelper | 0.0.22 | nicHelper-0.0.22.tar.gz | 689ecaec94fa | 27 | ok | none |
| nicHelper | 0.0.23 | nicHelper-0.0.23-py3-none-any.whl | 3c926881e554 | 21 | ok | none |
| nicHelper | 0.0.23 | nicHelper-0.0.23.tar.gz | c0841cdda19b | 27 | ok | none |
| nicHelper | 0.0.24 | nicHelper-0.0.24-py3-none-any.whl | bc99246d51da | 22 | ok | none |
| nicHelper | 0.0.24 | nicHelper-0.0.24.tar.gz | 0948863a9076 | 28 | ok | none |
| nicHelper | 0.0.25 | nicHelper-0.0.25-py3-none-any.whl | 5646127252a6 | 22 | ok | none |
| nicHelper | 0.0.25 | nicHelper-0.0.25.tar.gz | c9211e9bf726 | 28 | ok | none |
| nicHelper | 0.0.26 | nicHelper-0.0.26-py3-none-any.whl | 8435feb3c959 | 22 | ok | none |
| nicHelper | 0.0.26 | nicHelper-0.0.26.tar.gz | 0376bd46c4eb | 28 | ok | none |
| nicHelper | 0.0.27 | nicHelper-0.0.27-py3-none-any.whl | 13c9573fce78 | 22 | ok | none |
| nicHelper | 0.0.27 | nicHelper-0.0.27.tar.gz | d7457c373fa1 | 28 | ok | none |
| nicHelper | 0.0.28 | nicHelper-0.0.28-py3-none-any.whl | 3b4aeed17c9d | 22 | ok | none |
| nicHelper | 0.0.28 | nicHelper-0.0.28.tar.gz | d1793c71bfe4 | 28 | ok | none |
| nicHelper | 0.0.29 | nicHelper-0.0.29-py3-none-any.whl | edb647e90111 | 22 | ok | none |
| nicHelper | 0.0.29 | nicHelper-0.0.29.tar.gz | b7b628e528eb | 28 | ok | none |
| nicHelper | 0.0.3 | nicHelper-0.0.3-py3-none-any.whl | f7c171158a4a | 17 | ok | none |
| nicHelper | 0.0.3 | nicHelper-0.0.3.tar.gz | 75f6bc2ae673 | 23 | ok | none |
| nicHelper | 0.0.30 | nicHelper-0.0.30-py3-none-any.whl | 30475aa10ee8 | 22 | ok | none |
| nicHelper | 0.0.30 | nicHelper-0.0.30.tar.gz | 036495a8953b | 28 | ok | none |
| nicHelper | 0.0.31 | nicHelper-0.0.31-py3-none-any.whl | 3dba968cdb09 | 22 | ok | none |
| nicHelper | 0.0.31 | nicHelper-0.0.31.tar.gz | dea28b189f68 | 28 | ok | none |
| nicHelper | 0.0.32 | nicHelper-0.0.32-py3-none-any.whl | ca1bffd22fe3 | 22 | ok | none |
| nicHelper | 0.0.32 | nicHelper-0.0.32.tar.gz | 07ca4633e1fa | 28 | ok | none |
| nicHelper | 0.0.33 | nicHelper-0.0.33-py3-none-any.whl | 6bb321001af1 | 23 | ok | none |
| nicHelper | 0.0.33 | nicHelper-0.0.33.tar.gz | a86b11dfde73 | 29 | ok | none |
| nicHelper | 0.0.34 | nicHelper-0.0.34-py3-none-any.whl | 1dbb383acd36 | 23 | ok | none |
| nicHelper | 0.0.34 | nicHelper-0.0.34.tar.gz | 24a2f8b8dfad | 29 | ok | none |
| nicHelper | 0.0.35 | nicHelper-0.0.35-py3-none-any.whl | 2d6cf4da9e5e | 23 | ok | none |
| nicHelper | 0.0.35 | nicHelper-0.0.35.tar.gz | 5e59e3ce5221 | 29 | ok | none |
| nicHelper | 0.0.36 | nicHelper-0.0.36-py3-none-any.whl | 7cfe17afbffc | 23 | ok | none |
| nicHelper | 0.0.36 | nicHelper-0.0.36.tar.gz | 155cd1881f7b | 29 | ok | none |
| nicHelper | 0.0.37 | nicHelper-0.0.37-py3-none-any.whl | b8020e82d8b3 | 24 | ok | none |
| nicHelper | 0.0.37 | nicHelper-0.0.37.tar.gz | 04ca0c0d5071 | 30 | ok | none |
| nicHelper | 0.0.38 | nicHelper-0.0.38-py3-none-any.whl | 5511ef4d6b43 | 24 | ok | none |
| nicHelper | 0.0.38 | nicHelper-0.0.38.tar.gz | 641b348b266c | 30 | ok | none |
| nicHelper | 0.0.39 | nicHelper-0.0.39-py3-none-any.whl | ca041f46f5c7 | 24 | ok | none |
| nicHelper | 0.0.39 | nicHelper-0.0.39.tar.gz | 60da7c82cb32 | 30 | ok | none |
| nicHelper | 0.0.4 | nicHelper-0.0.4-py3-none-any.whl | 9483e57d89a0 | 18 | ok | none |
| nicHelper | 0.0.4 | nicHelper-0.0.4.tar.gz | 7c6e5ea3ff5a | 24 | ok | none |
| nicHelper | 0.0.40 | nicHelper-0.0.40-py3-none-any.whl | 6594bcb7f1f7 | 24 | ok | none |
| nicHelper | 0.0.40 | nicHelper-0.0.40.tar.gz | 3fe5fc2a78da | 30 | ok | none |
| nicHelper | 0.0.41 | nicHelper-0.0.41-py3-none-any.whl | 0ab6b59c3754 | 24 | ok | none |
| nicHelper | 0.0.41 | nicHelper-0.0.41.tar.gz | 6cc09dd1865a | 30 | ok | none |
| nicHelper | 0.0.42 | nicHelper-0.0.42-py3-none-any.whl | b0842b8fb003 | 24 | ok | none |
| nicHelper | 0.0.42 | nicHelper-0.0.42.tar.gz | 00112808fee8 | 30 | ok | none |
| nicHelper | 0.0.43 | nicHelper-0.0.43-py3-none-any.whl | 94f0f892b1e7 | 24 | ok | none |
| nicHelper | 0.0.43 | nicHelper-0.0.43.tar.gz | 8cfc1429f327 | 30 | ok | none |
| nicHelper | 0.0.44 | nicHelper-0.0.44-py3-none-any.whl | de8b199e6d42 | 21 | ok | none |
| nicHelper | 0.0.44 | nicHelper-0.0.44.tar.gz | fba9d2559241 | 30 | ok | none |
| nicHelper | 0.0.45 | nicHelper-0.0.45-py3-none-any.whl | 53eae2c10812 | 21 | ok | none |
| nicHelper | 0.0.45 | nicHelper-0.0.45.tar.gz | 117fa5d0b841 | 30 | ok | none |
| nicHelper | 0.0.46 | nicHelper-0.0.46-py3-none-any.whl | f051fbc64121 | 21 | ok | none |
| nicHelper | 0.0.46 | nicHelper-0.0.46.tar.gz | 7408eed8a7f2 | 30 | ok | none |
| nicHelper | 0.0.48 | nicHelper-0.0.48-py3-none-any.whl | 12f25afed038 | 21 | ok | none |
| nicHelper | 0.0.48 | nicHelper-0.0.48.tar.gz | a2a9c85aaeee | 30 | ok | none |
| nicHelper | 0.0.49 | nicHelper-0.0.49-py3-none-any.whl | f795b7795ff9 | 22 | ok | none |
| nicHelper | 0.0.49 | nicHelper-0.0.49.tar.gz | 4af29d38acdb | 31 | ok | none |
| nicHelper | 0.0.5 | nicHelper-0.0.5-py3-none-any.whl | 52c644631e0f | 19 | ok | none |
| nicHelper | 0.0.5 | nicHelper-0.0.5.tar.gz | 8290dbdb7552 | 25 | ok | none |
| nicHelper | 0.0.50 | nicHelper-0.0.50-py3-none-any.whl | 608b72333916 | 24 | ok | none |
| nicHelper | 0.0.50 | nicHelper-0.0.50.tar.gz | 042e5d398116 | 31 | ok | none |
| nicHelper | 0.0.51 | nicHelper-0.0.51-py3-none-any.whl | 4c7cb7a8172d | 24 | ok | none |
| nicHelper | 0.0.51 | nicHelper-0.0.51.tar.gz | c2907ff0dec0 | 31 | ok | none |
| nicHelper | 0.0.52 | nicHelper-0.0.52-py3-none-any.whl | 96a2889c5375 | 26 | ok | none |
| nicHelper | 0.0.52 | nicHelper-0.0.52.tar.gz | 4f11ca6e8ab4 | 33 | ok | none |
| nicHelper | 0.0.53 | nicHelper-0.0.53-py3-none-any.whl | 2fbfb9371a0a | 26 | ok | none |
| nicHelper | 0.0.53 | nicHelper-0.0.53.tar.gz | 9379d0810fa5 | 33 | ok | none |
| nicHelper | 0.0.54 | nicHelper-0.0.54-py3-none-any.whl | fbd56b8b273f | 26 | ok | none |
| nicHelper | 0.0.54 | nicHelper-0.0.54.tar.gz | 5fa44232a02d | 33 | ok | none |
| nicHelper | 0.0.55 | nicHelper-0.0.55-py3-none-any.whl | 68dcb59ac405 | 26 | ok | none |
| nicHelper | 0.0.55 | nicHelper-0.0.55.tar.gz | 8faef265ceea | 33 | ok | none |
| nicHelper | 0.0.56 | nicHelper-0.0.56-py3-none-any.whl | 05ce2059a7ca | 26 | ok | none |
| nicHelper | 0.0.56 | nicHelper-0.0.56.tar.gz | 341bdd91bb55 | 33 | ok | none |
| nicHelper | 0.0.57 | nicHelper-0.0.57-py3-none-any.whl | ac7d5a12a535 | 26 | ok | none |
| nicHelper | 0.0.57 | nicHelper-0.0.57.tar.gz | a775d9c7ac9b | 33 | ok | none |
| nicHelper | 0.0.58 | nicHelper-0.0.58-py3-none-any.whl | 29142b365be1 | 26 | ok | none |
| nicHelper | 0.0.58 | nicHelper-0.0.58.tar.gz | e58fe67b083c | 33 | ok | none |
| nicHelper | 0.0.59 | nicHelper-0.0.59-py3-none-any.whl | 2cea6a476ae9 | 26 | ok | none |
| nicHelper | 0.0.59 | nicHelper-0.0.59.tar.gz | b0bf6813c3c6 | 33 | ok | none |
| nicHelper | 0.0.6 | nicHelper-0.0.6-py3-none-any.whl | d1aa7d6234f5 | 19 | ok | none |
| nicHelper | 0.0.6 | nicHelper-0.0.6.tar.gz | c727fcd94e38 | 25 | ok | none |
| nicHelper | 0.0.60 | nicHelper-0.0.60-py3-none-any.whl | d51d75a1517d | 26 | ok | none |
| nicHelper | 0.0.60 | nicHelper-0.0.60.tar.gz | 653b09f8ceea | 33 | ok | none |
| nicHelper | 0.0.61 | nicHelper-0.0.61-py3-none-any.whl | 9869f8485f7f | 26 | ok | none |
| nicHelper | 0.0.61 | nicHelper-0.0.61.tar.gz | 0af29d74aceb | 33 | ok | none |
| nicHelper | 0.0.62 | nicHelper-0.0.62-py3-none-any.whl | 464fd80259ca | 26 | ok | none |
| nicHelper | 0.0.62 | nicHelper-0.0.62.tar.gz | 7302137c2968 | 33 | ok | none |
| nicHelper | 0.0.63 | nicHelper-0.0.63-py3-none-any.whl | f4af517ce2ef | 27 | ok | none |
| nicHelper | 0.0.63 | nicHelper-0.0.63.tar.gz | f7215db7861c | 34 | ok | none |
| nicHelper | 0.0.64 | nicHelper-0.0.64-py3-none-any.whl | 0afc2214cb7a | 27 | ok | none |
| nicHelper | 0.0.64 | nicHelper-0.0.64.tar.gz | 3ca16c7077e0 | 34 | ok | none |
| nicHelper | 0.0.65 | nicHelper-0.0.65-py3-none-any.whl | 0822f3347d3a | 27 | ok | none |
| nicHelper | 0.0.65 | nicHelper-0.0.65.tar.gz | be16ce8c76a2 | 34 | ok | none |
| nicHelper | 0.0.66 | nicHelper-0.0.66-py3-none-any.whl | ba78d8021ff0 | 28 | ok | none |
| nicHelper | 0.0.66 | nicHelper-0.0.66.tar.gz | 0cd46c80e175 | 35 | ok | none |
| nicHelper | 0.0.67 | nicHelper-0.0.67-py3-none-any.whl | 5d00062207b5 | 28 | ok | none |
| nicHelper | 0.0.67 | nicHelper-0.0.67.tar.gz | 8c4a3b88f3d9 | 35 | ok | none |
| nicHelper | 0.0.68 | nicHelper-0.0.68-py3-none-any.whl | 5721c7450844 | 28 | ok | none |
| nicHelper | 0.0.68 | nicHelper-0.0.68.tar.gz | e52e876a2ff6 | 35 | ok | none |
| nicHelper | 0.0.69 | nicHelper-0.0.69-py3-none-any.whl | cc60909a03b5 | 28 | ok | none |
| nicHelper | 0.0.69 | nicHelper-0.0.69.tar.gz | f39492862d60 | 35 | ok | none |
| nicHelper | 0.0.7 | nicHelper-0.0.7-py3-none-any.whl | 0dcac106b457 | 19 | ok | none |
| nicHelper | 0.0.7 | nicHelper-0.0.7.tar.gz | 163b3e909f89 | 25 | ok | none |
| nicHelper | 0.0.70 | nicHelper-0.0.70-py3-none-any.whl | 24dacdc9b95a | 28 | ok | none |
| nicHelper | 0.0.70 | nicHelper-0.0.70.tar.gz | 6c0b875d7c99 | 35 | ok | none |
| nicHelper | 0.0.71 | nicHelper-0.0.71-py3-none-any.whl | eca8f6701233 | 28 | ok | none |
| nicHelper | 0.0.71 | nicHelper-0.0.71.tar.gz | 2a5afff4d8e1 | 35 | ok | none |
| nicHelper | 0.0.72 | nicHelper-0.0.72-py3-none-any.whl | 9752e920e4aa | 28 | ok | none |
| nicHelper | 0.0.72 | nicHelper-0.0.72.tar.gz | b78037907f02 | 35 | ok | none |
| nicHelper | 0.0.73 | nicHelper-0.0.73-py3-none-any.whl | a2ff6ffd7c60 | 28 | ok | none |
| nicHelper | 0.0.73 | nicHelper-0.0.73.tar.gz | acf8492c05f9 | 35 | ok | none |
| nicHelper | 0.0.74 | nicHelper-0.0.74-py3-none-any.whl | 3ba5f1743795 | 28 | ok | none |
| nicHelper | 0.0.74 | nicHelper-0.0.74.tar.gz | 2ff7a58b9d83 | 35 | ok | none |
| nicHelper | 0.0.75 | nicHelper-0.0.75-py3-none-any.whl | 729f040c7f4d | 29 | ok | none |
| nicHelper | 0.0.75 | nicHelper-0.0.75.tar.gz | 63537c60efe7 | 36 | ok | none |
| nicHelper | 0.0.76 | nicHelper-0.0.76-py3-none-any.whl | f1d038de5f9e | 30 | ok | none |
| nicHelper | 0.0.76 | nicHelper-0.0.76.tar.gz | 6bbff0129033 | 37 | ok | none |
| nicHelper | 0.0.77 | nicHelper-0.0.77-py3-none-any.whl | be50f3f6fc4c | 30 | ok | none |
| nicHelper | 0.0.77 | nicHelper-0.0.77.tar.gz | bdf2932d6233 | 37 | ok | none |
| nicHelper | 0.0.78 | nicHelper-0.0.78-py3-none-any.whl | aaa7b515857d | 30 | ok | none |
| nicHelper | 0.0.78 | nicHelper-0.0.78.tar.gz | 2305cc09f842 | 37 | ok | none |
| nicHelper | 0.0.79 | nicHelper-0.0.79-py3-none-any.whl | 34ec3c545d23 | 31 | ok | none |
| nicHelper | 0.0.79 | nicHelper-0.0.79.tar.gz | e66d30ce64c5 | 38 | ok | none |
| nicHelper | 0.0.8 | nicHelper-0.0.8-py3-none-any.whl | 4d73ac25dfbb | 19 | ok | none |
| nicHelper | 0.0.8 | nicHelper-0.0.8.tar.gz | 06face06da42 | 25 | ok | none |
| nicHelper | 0.0.80 | nicHelper-0.0.80-py3-none-any.whl | 071100275a6b | 31 | ok | none |
| nicHelper | 0.0.80 | nicHelper-0.0.80.tar.gz | 0a3f9a3f2cfb | 38 | ok | none |
| nicHelper | 0.0.81 | nicHelper-0.0.81-py3-none-any.whl | 2c005d7915d8 | 31 | ok | none |
| nicHelper | 0.0.81 | nicHelper-0.0.81.tar.gz | d95315046a1d | 38 | ok | none |
| nicHelper | 0.0.82 | nicHelper-0.0.82-py3-none-any.whl | 00c7182aded1 | 31 | ok | none |
| nicHelper | 0.0.82 | nicHelper-0.0.82.tar.gz | f2ce2fde8c8e | 38 | ok | none |
| nicHelper | 0.0.83 | nicHelper-0.0.83-py3-none-any.whl | 363c038c890d | 31 | ok | none |
| nicHelper | 0.0.83 | nicHelper-0.0.83.tar.gz | 8a02c47e9670 | 38 | ok | none |
| nicHelper | 0.0.84 | nicHelper-0.0.84-py3-none-any.whl | 0939a32c566d | 29 | ok | none |
| nicHelper | 0.0.84 | nicHelper-0.0.84.tar.gz | 135c700bae90 | 38 | ok | none |
| nicHelper | 0.0.85 | nicHelper-0.0.85-py3-none-any.whl | dc3b61605039 | 30 | ok | none |
| nicHelper | 0.0.85 | nicHelper-0.0.85.tar.gz | 66d2fb2ac8d3 | 39 | ok | none |
| nicHelper | 0.0.86 | nicHelper-0.0.86-py3-none-any.whl | c3f5fb55e694 | 31 | ok | none |
| nicHelper | 0.0.86 | nicHelper-0.0.86.tar.gz | 85ebe5e69a87 | 40 | ok | none |
| nicHelper | 0.0.87 | nicHelper-0.0.87-py3-none-any.whl | 14e29a1fa2df | 31 | ok | none |
| nicHelper | 0.0.87 | nicHelper-0.0.87.tar.gz | 657ebccc6833 | 40 | ok | none |
| nicHelper | 0.0.88 | nicHelper-0.0.88-py3-none-any.whl | 662d30191224 | 31 | ok | none |
| nicHelper | 0.0.88 | nicHelper-0.0.88.tar.gz | 97de6e9cdbe5 | 40 | ok | none |
| nicHelper | 0.0.89 | nicHelper-0.0.89-py3-none-any.whl | f28f84d3a1bc | 31 | ok | none |
| nicHelper | 0.0.89 | nicHelper-0.0.89.tar.gz | f7acc04958e1 | 40 | ok | none |
| nicHelper | 0.0.9 | nicHelper-0.0.9-py3-none-any.whl | 9b9ee821958e | 19 | ok | none |
| nicHelper | 0.0.9 | nicHelper-0.0.9.tar.gz | 1235a1a49acf | 25 | ok | none |
| nicHelper | 0.0.90 | nicHelper-0.0.90-py3-none-any.whl | d32c7d1569ea | 31 | ok | none |
| nicHelper | 0.0.90 | nicHelper-0.0.90.tar.gz | beca99a20a66 | 40 | ok | none |
| nicHelper | 0.0.91 | nicHelper-0.0.91-py3-none-any.whl | dccdad4b73f8 | 32 | ok | none |
| nicHelper | 0.0.91 | nicHelper-0.0.91.tar.gz | 6ceb7a9e5d16 | 41 | ok | none |
| nicHelper | 0.0.92 | nicHelper-0.0.92-py3-none-any.whl | 13537ab6d388 | 32 | ok | none |
| nicHelper | 0.0.92 | nicHelper-0.0.92.tar.gz | 23f704689e0b | 41 | ok | none |
| nicHelper | 0.0.93 | nicHelper-0.0.93-py3-none-any.whl | 5639b294ca8d | 32 | ok | none |
| nicHelper | 0.0.93 | nicHelper-0.0.93.tar.gz | e28c2e5c7a9a | 41 | ok | none |
| nicHelper | 0.0.95 | nicHelper-0.0.95-py3-none-any.whl | a1f013d429bb | 32 | ok | none |
| nicHelper | 0.0.95 | nicHelper-0.0.95.tar.gz | db31c7e81723 | 41 | ok | none |
| nicHelper | 0.0.96 | nicHelper-0.0.96-py3-none-any.whl | 44c8a2db0cd6 | 32 | ok | none |
| nicHelper | 0.0.96 | nicHelper-0.0.96.tar.gz | 2d1b46ba856c | 41 | ok | none |
| nicHelper | 0.0.97 | nicHelper-0.0.97-py3-none-any.whl | 8079c3d121f9 | 33 | ok | none |
| nicHelper | 0.0.97 | nicHelper-0.0.97.tar.gz | b14af6493158 | 42 | ok | none |
| nicHelper | 0.0.98 | nicHelper-0.0.98-py3-none-any.whl | 224c4104cded | 33 | ok | none |
| nicHelper | 0.0.98 | nicHelper-0.0.98.tar.gz | 46f5698e21d7 | 42 | ok | none |
| nicHelper | 0.0.99 | nicHelper-0.0.99-py3-none-any.whl | a9a90ba423e8 | 33 | ok | none |
| nicHelper | 0.0.99 | nicHelper-0.0.99.tar.gz | 5cb5235b14c4 | 42 | ok | none |
| awsSchema | 0.0.1 | awsSchema-0.0.1-py3-none-any.whl | efa429ac5a0b | 9 | ok | `awsSchema-0.0.1.dist-info/METADATA:42` [generic-api-key] |
| awsSchema | 0.0.1 | awsSchema-0.0.1.tar.gz | 8cc54b76a760 | 18 | ok | `awsSchema-0.0.1/PKG-INFO:29` [generic-api-key]<br>`awsSchema-0.0.1/README.md:21` [generic-api-key]<br>`awsSchema-0.0.1/awsSchema.egg-info/PKG-INFO:29` [generic-api-key] |
| awsSchema | 0.0.10 | awsSchema-0.0.10-py3-none-any.whl | 8fdf3c8586b1 | 11 | ok | `awsSchema-0.0.10.dist-info/METADATA:47` [generic-api-key] |
| awsSchema | 0.0.10 | awsSchema-0.0.10.tar.gz | 5758b8f997da | 20 | ok | `awsSchema-0.0.10/PKG-INFO:33` [generic-api-key]<br>`awsSchema-0.0.10/README.md:25` [generic-api-key]<br>`awsSchema-0.0.10/awsSchema.egg-info/PKG-INFO:33` [generic-api-key] |
| awsSchema | 0.0.11 | awsSchema-0.0.11-py3-none-any.whl | 8f758427de35 | 11 | ok | `awsSchema-0.0.11.dist-info/METADATA:47` [generic-api-key] |
| awsSchema | 0.0.11 | awsSchema-0.0.11.tar.gz | e5d51845318e | 20 | ok | `awsSchema-0.0.11/PKG-INFO:33` [generic-api-key]<br>`awsSchema-0.0.11/README.md:25` [generic-api-key]<br>`awsSchema-0.0.11/awsSchema.egg-info/PKG-INFO:33` [generic-api-key] |
| awsSchema | 0.0.12 | awsSchema-0.0.12-py3-none-any.whl | 4e8cdbec7a9a | 11 | ok | `awsSchema-0.0.12.dist-info/METADATA:47` [generic-api-key] |
| awsSchema | 0.0.12 | awsSchema-0.0.12.tar.gz | 244cab0aaaee | 20 | ok | `awsSchema-0.0.12/PKG-INFO:33` [generic-api-key]<br>`awsSchema-0.0.12/README.md:25` [generic-api-key]<br>`awsSchema-0.0.12/awsSchema.egg-info/PKG-INFO:33` [generic-api-key] |
| awsSchema | 0.0.13 | awsSchema-0.0.13-py3-none-any.whl | 91ff7ad41cfb | 12 | ok | `awsSchema-0.0.13.dist-info/METADATA:47` [generic-api-key] |
| awsSchema | 0.0.13 | awsSchema-0.0.13.tar.gz | 4e5696c8b567 | 21 | ok | `awsSchema-0.0.13/PKG-INFO:33` [generic-api-key]<br>`awsSchema-0.0.13/README.md:25` [generic-api-key]<br>`awsSchema-0.0.13/awsSchema.egg-info/PKG-INFO:33` [generic-api-key] |
| awsSchema | 0.0.14 | awsSchema-0.0.14-py3-none-any.whl | 96c7e1295981 | 12 | ok | `awsSchema-0.0.14.dist-info/METADATA:47` [generic-api-key] |
| awsSchema | 0.0.14 | awsSchema-0.0.14.tar.gz | efeecd7cd4cc | 21 | ok | `awsSchema-0.0.14/PKG-INFO:33` [generic-api-key]<br>`awsSchema-0.0.14/README.md:25` [generic-api-key]<br>`awsSchema-0.0.14/awsSchema.egg-info/PKG-INFO:33` [generic-api-key] |
| awsSchema | 0.0.15 | awsSchema-0.0.15-py3-none-any.whl | 2e199f27737c | 12 | ok | `awsSchema-0.0.15.dist-info/METADATA:47` [generic-api-key] |
| awsSchema | 0.0.15 | awsSchema-0.0.15.tar.gz | 145d86255323 | 21 | ok | `awsSchema-0.0.15/PKG-INFO:33` [generic-api-key]<br>`awsSchema-0.0.15/README.md:25` [generic-api-key]<br>`awsSchema-0.0.15/awsSchema.egg-info/PKG-INFO:33` [generic-api-key] |
| awsSchema | 0.0.18 | awsSchema-0.0.18-py3-none-any.whl | 6c8ef1bd52b5 | 12 | ok | `awsSchema-0.0.18.dist-info/METADATA:47` [generic-api-key] |
| awsSchema | 0.0.18 | awsSchema-0.0.18.tar.gz | 91175783fbf9 | 21 | ok | `awsSchema-0.0.18/PKG-INFO:33` [generic-api-key]<br>`awsSchema-0.0.18/README.md:25` [generic-api-key]<br>`awsSchema-0.0.18/awsSchema.egg-info/PKG-INFO:33` [generic-api-key] |
| awsSchema | 0.0.2 | awsSchema-0.0.2-py3-none-any.whl | d3fa12c3e09a | 9 | ok | `awsSchema-0.0.2.dist-info/METADATA:44` [generic-api-key] |
| awsSchema | 0.0.2 | awsSchema-0.0.2.tar.gz | 95ef3f4aedbc | 18 | ok | `awsSchema-0.0.2/PKG-INFO:31` [generic-api-key]<br>`awsSchema-0.0.2/README.md:23` [generic-api-key]<br>`awsSchema-0.0.2/awsSchema.egg-info/PKG-INFO:31` [generic-api-key] |
| awsSchema | 0.0.22 | awsSchema-0.0.22-py3-none-any.whl | 606b6eafbbac | 12 | ok | `awsSchema-0.0.22.dist-info/METADATA:47` [generic-api-key] |
| awsSchema | 0.0.22 | awsSchema-0.0.22.tar.gz | 233fc40fe4a4 | 21 | ok | `awsSchema-0.0.22/PKG-INFO:33` [generic-api-key]<br>`awsSchema-0.0.22/README.md:25` [generic-api-key]<br>`awsSchema-0.0.22/awsSchema.egg-info/PKG-INFO:33` [generic-api-key] |
| awsSchema | 0.0.23 | awsSchema-0.0.23-py3-none-any.whl | e838244ab496 | 11 | ok | `awsSchema-0.0.23.dist-info/METADATA:48` [generic-api-key] |
| awsSchema | 0.0.23 | awsSchema-0.0.23.tar.gz | 7bd1b5d064b5 | 20 | ok | `awsSchema-0.0.23/PKG-INFO:34` [generic-api-key]<br>`awsSchema-0.0.23/README.md:26` [generic-api-key]<br>`awsSchema-0.0.23/awsSchema.egg-info/PKG-INFO:34` [generic-api-key] |
| awsSchema | 0.0.24 | awsSchema-0.0.24-py3-none-any.whl | ffba06d48a6f | 11 | ok | `awsSchema-0.0.24.dist-info/METADATA:47` [generic-api-key] |
| awsSchema | 0.0.24 | awsSchema-0.0.24.tar.gz | 64d2bd947e59 | 20 | ok | `awsSchema-0.0.24/PKG-INFO:33` [generic-api-key]<br>`awsSchema-0.0.24/README.md:25` [generic-api-key]<br>`awsSchema-0.0.24/awsSchema.egg-info/PKG-INFO:33` [generic-api-key] |
| awsSchema | 0.0.25 | awsSchema-0.0.25-py3-none-any.whl | 51eb1252cec8 | 12 | ok | `awsSchema-0.0.25.dist-info/METADATA:47` [generic-api-key] |
| awsSchema | 0.0.25 | awsSchema-0.0.25.tar.gz | 6ee88eae8353 | 21 | ok | `awsSchema-0.0.25/PKG-INFO:33` [generic-api-key]<br>`awsSchema-0.0.25/README.md:25` [generic-api-key]<br>`awsSchema-0.0.25/awsSchema.egg-info/PKG-INFO:33` [generic-api-key] |
| awsSchema | 0.0.26 | awsSchema-0.0.26-py3-none-any.whl | 16f575202d44 | 13 | ok | `awsSchema-0.0.26.dist-info/METADATA:47` [generic-api-key] |
| awsSchema | 0.0.26 | awsSchema-0.0.26.tar.gz | 78abf0c72a44 | 22 | ok | `awsSchema-0.0.26/PKG-INFO:33` [generic-api-key]<br>`awsSchema-0.0.26/README.md:25` [generic-api-key]<br>`awsSchema-0.0.26/awsSchema.egg-info/PKG-INFO:33` [generic-api-key] |
| awsSchema | 0.0.27 | awsSchema-0.0.27-py3-none-any.whl | 0132d290e5c6 | 13 | ok | `awsSchema-0.0.27.dist-info/METADATA:47` [generic-api-key] |
| awsSchema | 0.0.27 | awsSchema-0.0.27.tar.gz | e8931a6c0226 | 22 | ok | `awsSchema-0.0.27/PKG-INFO:33` [generic-api-key]<br>`awsSchema-0.0.27/README.md:25` [generic-api-key]<br>`awsSchema-0.0.27/awsSchema.egg-info/PKG-INFO:33` [generic-api-key] |
| awsSchema | 0.0.3 | awsSchema-0.0.3-py3-none-any.whl | a82f8977d346 | 9 | ok | `awsSchema-0.0.3.dist-info/METADATA:44` [generic-api-key] |
| awsSchema | 0.0.3 | awsSchema-0.0.3.tar.gz | c1aeeca5de2c | 18 | ok | `awsSchema-0.0.3/PKG-INFO:31` [generic-api-key]<br>`awsSchema-0.0.3/README.md:23` [generic-api-key]<br>`awsSchema-0.0.3/awsSchema.egg-info/PKG-INFO:31` [generic-api-key] |
| awsSchema | 0.0.4 | awsSchema-0.0.4-py3-none-any.whl | 076139fb9e9a | 9 | ok | `awsSchema-0.0.4.dist-info/METADATA:45` [generic-api-key]<br>`awsSchema-0.0.4.dist-info/METADATA:64` [generic-api-key] |
| awsSchema | 0.0.4 | awsSchema-0.0.4.tar.gz | 412013341ed5 | 18 | ok | `awsSchema-0.0.4/PKG-INFO:31` [generic-api-key]<br>`awsSchema-0.0.4/PKG-INFO:50` [generic-api-key]<br>`awsSchema-0.0.4/README.md:23` [generic-api-key]<br>`awsSchema-0.0.4/README.md:42` [generic-api-key]<br>`awsSchema-0.0.4/awsSchema.egg-info/PKG-INFO:31` [generic-api-key]<br>`awsSchema-0.0.4/awsSchema.egg-info/PKG-INFO:50` [generic-api-key] |
| awsSchema | 0.0.5 | awsSchema-0.0.5-py3-none-any.whl | e7d653834bf3 | 9 | ok | `awsSchema-0.0.5.dist-info/METADATA:45` [generic-api-key]<br>`awsSchema-0.0.5.dist-info/METADATA:64` [generic-api-key] |
| awsSchema | 0.0.5 | awsSchema-0.0.5.tar.gz | 7e8efa5d4e7e | 18 | ok | `awsSchema-0.0.5/PKG-INFO:31` [generic-api-key]<br>`awsSchema-0.0.5/PKG-INFO:50` [generic-api-key]<br>`awsSchema-0.0.5/README.md:23` [generic-api-key]<br>`awsSchema-0.0.5/README.md:42` [generic-api-key]<br>`awsSchema-0.0.5/awsSchema.egg-info/PKG-INFO:31` [generic-api-key]<br>`awsSchema-0.0.5/awsSchema.egg-info/PKG-INFO:50` [generic-api-key] |
| awsSchema | 0.0.6 | awsSchema-0.0.6-py3-none-any.whl | 85aed518cb23 | 9 | ok | `awsSchema-0.0.6.dist-info/METADATA:45` [generic-api-key]<br>`awsSchema-0.0.6.dist-info/METADATA:64` [generic-api-key] |
| awsSchema | 0.0.6 | awsSchema-0.0.6.tar.gz | 3c13288ef237 | 18 | ok | `awsSchema-0.0.6/PKG-INFO:31` [generic-api-key]<br>`awsSchema-0.0.6/PKG-INFO:50` [generic-api-key]<br>`awsSchema-0.0.6/README.md:23` [generic-api-key]<br>`awsSchema-0.0.6/README.md:42` [generic-api-key]<br>`awsSchema-0.0.6/awsSchema.egg-info/PKG-INFO:31` [generic-api-key]<br>`awsSchema-0.0.6/awsSchema.egg-info/PKG-INFO:50` [generic-api-key] |
| awsSchema | 0.0.7 | awsSchema-0.0.7-py3-none-any.whl | b80536a09e84 | 9 | ok | `awsSchema-0.0.7.dist-info/METADATA:45` [generic-api-key]<br>`awsSchema-0.0.7.dist-info/METADATA:64` [generic-api-key] |
| awsSchema | 0.0.7 | awsSchema-0.0.7.tar.gz | 1924973b8415 | 18 | ok | `awsSchema-0.0.7/PKG-INFO:31` [generic-api-key]<br>`awsSchema-0.0.7/PKG-INFO:50` [generic-api-key]<br>`awsSchema-0.0.7/README.md:23` [generic-api-key]<br>`awsSchema-0.0.7/README.md:42` [generic-api-key]<br>`awsSchema-0.0.7/awsSchema.egg-info/PKG-INFO:31` [generic-api-key]<br>`awsSchema-0.0.7/awsSchema.egg-info/PKG-INFO:50` [generic-api-key] |
| awsSchema | 0.0.8 | awsSchema-0.0.8-py3-none-any.whl | da2c2a7104bd | 9 | ok | `awsSchema-0.0.8.dist-info/METADATA:45` [generic-api-key]<br>`awsSchema-0.0.8.dist-info/METADATA:53` [generic-api-key] |
| awsSchema | 0.0.8 | awsSchema-0.0.8.tar.gz | 99db7f2f5d90 | 18 | ok | `awsSchema-0.0.8/PKG-INFO:31` [generic-api-key]<br>`awsSchema-0.0.8/PKG-INFO:39` [generic-api-key]<br>`awsSchema-0.0.8/README.md:23` [generic-api-key]<br>`awsSchema-0.0.8/README.md:31` [generic-api-key]<br>`awsSchema-0.0.8/awsSchema.egg-info/PKG-INFO:31` [generic-api-key]<br>`awsSchema-0.0.8/awsSchema.egg-info/PKG-INFO:39` [generic-api-key] |
