# villaInventorySdk
> read and write inventory in real time


## Install

`pip install villaInventorySdk`

## How to use

Uploading a large amount of data

## sample input

```python
input = [
    {'ib_brcode': '1023',
     'ib_cf_qty': '835',
     'ib_prcode': '84621',
     'new_ib_vs_stock_cv': '839'},
    {'ib_brcode': '1022',
     'ib_cf_qty': '24',
     'ib_prcode': '12424',
     'new_ib_vs_stock_cv': '21'}
]
```

## Upload data

```python
from villaInventorySdk.inventory import InventorySdk
from random import randrange
import boto3
from dataclasses import dataclass
from dataclasses_json import dataclass_json
from datetime import datetime
t0 = datetime.now()
print(f'uploading {len(input)} items')
sdk = InventorySdk(user=USER, pw=PW)
result = sdk.updateWithS3(
    input,
    inputBucketName= 'input-bucket-dev-manual', 
    functionName= 'update-inventory-s3-dev-manual',
    invocationType = 'RequestResponse'
  )
dt = datetime.now()-t0
print(f'it took {dt.seconds} s')
```

    uploading 2 items
    data was saved to s3
    data is saved to s3, invoking ingestion function
    input to lambda is {'inputBucketName': 'input-bucket-dev-manual', 'inputKeyName': 'input-data-name'}
    it took 1 s


## Query single product

```python
import json
sdk = InventorySdk(user=USER, pw=PW)
result = sdk.querySingleProduct(ib_prcode = '84621')
json.loads(result)
```




    {'statusCode': 200,
     'inventory': '{"1023": {"ib_cf_qty": 835, "new_ib_bs_stock_cv": 839, "lastUpdate": 1601394614.340882}, "lastUpdate": 1601394614.340882, "ib_prcode": "84621"}'}


