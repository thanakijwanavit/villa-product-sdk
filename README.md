# villaProductSdk
> read and write product information in real time


## Install

`pip install villaProductSdk`

## How to use

Uploading a large amount of data using s3

## generate dummy data for testing

```python
#Dummy Data
sampleProducts = [{'cprcode': '0171670', 'iprcode': '0171670', 'oprcode': '0171670', 'ordertype': 'Y', 'pr_abb': 'JIRAPAT YOUNG KALE 2', 'pr_active': 'Y', 'pr_cgcode': '05', 'pr_code': '0171670', 'pr_dpcode': '19', 'pr_engname': 'IRAPAT YOUNG KALE 200 G.', 'pr_ggcode': '057', 'pr_market': 'JIRAPAT ยอดคะน้า 200 G.', 'pr_name': 'JIRAPAT ยอดคะน้า 200 G.', 'pr_puqty': '1', 'pr_sa_method': '1', 'pr_sucode1': 'CM845     ', 'pr_suref3': 'A', 'prtype': 'I', 'psqty': '1', 'pstype': '1'}, {'cprcode': '0235141', 'iprcode': '0235141', 'oprcode': '0235141', 'ordertype': 'Y', 'pr_abb': 'EEBOO-PZCT3-PUZZLE', 'pr_active': 'Y', 'pr_cgcode': '08', 'pr_code': '0235141', 'pr_dpcode': '19', 'pr_engname': 'EEBOO,ANIMAL COUNTING PUZZLE_3ED,PZCT3', 'pr_ggcode': '113', 'pr_market': 'eeboo,PUZZLE-PZCT3', 'pr_name': 'EEBOO-PZCT3-ตัวต่อนับเลข ANIMAL COUNTING_3ED', 'pr_puqty': '1', 'pr_sa_method': '1', 'pr_sucode1': 'CM1979    ', 'pr_suref3': 'A', 'prtype': 'I', 'psqty': '1', 'pstype': '1'}, {'cprcode': '0217153', 'iprcode': '0217153', 'oprcode': '0217153', 'ordertype': 'Y', 'pr_abb': 'COCOA LOCO MILK CHOC', 'pr_active': 'Y', 'pr_cgcode': '98', 'pr_code': '0217153', 'pr_dpcode': '28', 'pr_engname': 'COCOA LOCO MILK CHOCOLATE OWL LOLLY 26G.', 'pr_ggcode': '003', 'pr_market': 'COCOA LOCO MILK CHOCOLATE OWL', 'pr_name': 'COCOA LOCO MILK CHOCOLATE OWL LOLLY 26G.', 'pr_puqty': '24', 'pr_sa_method': '1', 'pr_sucode1': 'F1222     ', 'pr_suref3': 'S', 'prtype': 'I', 'psqty': '1', 'pstype': '1'}, {'cprcode': '0182223', 'iprcode': '0182223', 'oprcode': '0182223', 'ordertype': 'Y', 'pr_abb': 'CIRIO PIZZASSIMO 400', 'pr_active': 'Y', 'pr_cgcode': '06', 'pr_code': '0182223', 'pr_dpcode': '06', 'pr_engname': 'CIRIO PIZZASSIMO 400G.', 'pr_ggcode': '004', 'pr_market': 'CIRIO ซอสทำพิซซ่า 400 G.', 'pr_name': 'CIRIO ซอสทำพิซซ่า 400 G.', 'pr_puqty': '12', 'pr_sa_method': '1', 'pr_sucode1': '2589      ', 'pr_suref3': 'C', 'prtype': 'I', 'psqty': '1', 'pstype': '1'}, {'cprcode': '0124461', 'iprcode': '0124461', 'oprcode': '0124461', 'ordertype': 'Y', 'pr_abb': 'NEW CHOICE LYCHEE', 'pr_active': 'Y', 'pr_cgcode': '02', 'pr_code': '0124461', 'pr_dpcode': '02', 'pr_engname': 'NEW CHOICE LYCHEE', 'pr_ggcode': '003', 'pr_market': 'NEW CHOICE กลิ่นลิ้นจี่', 'pr_name': 'NEW CHOICE กลิ่นลิ้นจี่', 'pr_puqty': '12', 'pr_sa_method': '1', 'pr_sucode1': '695       ', 'pr_suref3': 'A', 'prtype': 'I', 'psqty': '1', 'pstype': '1'}]

```

## Create main class object

```python
sdk = ProductSdk(branch = 'dev-manual', user=USER, pw=PW)
```

## Upload lots of data using s3 

```python
%%time
result = sdk.updateWithS3(
    sampleProducts,
    invocationType = 'RequestResponse'
  )
result
```

    ERROR:root:error parsing body, perhaps there is no body in response
    Traceback (most recent call last):
      File "/Users/nic/pip/villa-product-sdk/villaProductSdk/products.py", line 47, in returnLambdaResponse
        return Response.fromDict(lambdaResponse).body
      File "/Users/nic/pip/villa-product-sdk/villaProductSdk/schema.py", line 27, in fromDict
        body = dictInput.pop('body')
    KeyError: 'body'
    ERROR:root:{'errorMessage': "invalid literal for int() with base 10: ''", 'errorType': 'ValueError', 'stackTrace': ['  File "/var/task/villaProductDatabase/database.py", line 144, in lambdaUpdateS3\n    updateResult = ProductDatabase.updateS3Input(\n', '  File "/var/task/villaProductDatabase/update.py", line 81, in updateS3Input\n    updateResult = cls.valueUpdate(s3Result)\n', '  File "/var/task/villaProductDatabase/update.py", line 62, in valueUpdate\n    itemsUpdated[\'timetaken\'] = (datetime.now()- t0).total_seconds()*1000\n', '  File "/opt/python/pynamodb/models.py", line 113, in __exit__\n    return self.commit()\n', '  File "/opt/python/pynamodb/models.py", line 131, in commit\n    data = self.model._get_connection().batch_write_item(\n', '  File "/opt/python/pynamodb/connection/table.py", line 173, in batch_write_item\n    return self.connection.batch_write_item(\n', '  File "/opt/python/pynamodb/connection/base.py", line 1159, in batch_write_item\n    return self.dispatch(BATCH_WRITE_ITEM, operation_kwargs)\n', '  File "/opt/python/pynamodb/connection/base.py", line 349, in dispatch\n    data = self._make_api_call(operation_name, operation_kwargs)\n', '  File "/opt/python/pynamodb/connection/base.py", line 379, in _make_api_call\n    return self.dax_write_client.dispatch(operation_name, operation_kwargs)\n', '  File "/opt/python/pynamodb/connection/base.py", line 559, in dax_write_client\n    self._dax_write_client = DaxClient(\n', '  File "/opt/python/pynamodb/connection/dax.py", line 30, in __init__\n    self.connection = AmazonDaxClient(\n', '  File "/opt/python/amazondax/AmazonDaxClient.py", line 177, in __init__\n    self._cluster = Cluster(self._region_name,\n', '  File "/opt/python/amazondax/Cluster.py", line 30, in __init__\n    self._discovery_endpoints = [_parse_host_ports(endpoint) for endpoint in discovery_endpoints]\n', '  File "/opt/python/amazondax/Cluster.py", line 30, in <listcomp>\n    self._discovery_endpoints = [_parse_host_ports(endpoint) for endpoint in discovery_endpoints]\n', '  File "/opt/python/amazondax/Cluster.py", line 116, in _parse_host_ports\n    return parts[0].strip(), int(parts[1].strip())\n']}


    CPU times: user 58.7 ms, sys: 15.4 ms, total: 74.2 ms
    Wall time: 838 ms


## Query Single Product

```python
%%time
result = sdk.querySingleProduct('0171670')
result
```

    CPU times: user 3.14 ms, sys: 1.14 ms, total: 4.28 ms
    Wall time: 123 ms





    {'cprcode': '0171670',
     'iprcode': '0171670',
     'oprcode': '0171670',
     'ordertype': 'Y',
     'pr_abb': 'JIRAPAT YOUNG KALE 2',
     'pr_active': 'Y',
     'pr_cgcode': '05',
     'pr_code': '0171670',
     'pr_dpcode': '19',
     'pr_engname': 'JIRAPAT YOUNG KALE 200 G.',
     'pr_ggcode': '057',
     'pr_market': 'JIRAPAT ยอดคะน้า 200 G.',
     'pr_name': 'JIRAPAT ยอดคะน้า 200 G.',
     'pr_puqty': '1',
     'pr_sa_method': '1',
     'pr_sucode1': 'CM845',
     'pr_suref3': 'A',
     'prtype': 'I',
     'psqty': '1',
     'pstype': '1'}



## All Query

```python
result = sdk.allQuery()
sdk.printFirst(result)
```




    ('0217153',
     {'0217153': {'cprcode': '0217153',
       'iprcode': '0217153',
       'oprcode': '0217153',
       'ordertype': 'Y',
       'pr_abb': 'COCOA LOCO MILK CHOC',
       'pr_active': 'Y',
       'pr_cgcode': '98',
       'pr_code': '0217153',
       'pr_dpcode': '28',
       'pr_engname': 'COCOA LOCO MILK CHOCOLATE OWL LOLLY 26G.',
       'pr_ggcode': '003',
       'pr_market': 'COCOA LOCO MILK CHOCOLATE OWL',
       'pr_name': 'COCOA LOCO MILK CHOCOLATE OWL LOLLY 26G.',
       'pr_puqty': '24',
       'pr_sa_method': '1',
       'pr_sucode1': 'F1222',
       'pr_suref3': 'S',
       'prtype': 'I',
       'psqty': '1',
       'pstype': '1'}})



## Trigger s3 sync

```python
%%time
response = sdk.syncS3()
response
```

    CPU times: user 3.05 ms, sys: 902 µs, total: 3.95 ms
    Wall time: 329 ms





    {'result': 'saved 5 products'}


