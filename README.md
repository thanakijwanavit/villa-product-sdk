# villaProductSdk



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

    INFO:root:bucket is input-product-bucket-dev-manual
    INFO:root:using accelerate endpoint
    INFO:root:data was saved to s3
    INFO:root:data is saved to s3, invoking ingestion function
    INFO:root:input to lambda is {'body': '{"key":"input-data-name"}', 'header': {}}
    INFO:root:lambdaResponse is {'body': '{"success": 1, "failure": 0, "skipped": 4, "failureMessage": [], "timetaken": 64.086}', 'statusCode': 200, 'header': {}}


    CPU times: user 53.8 ms, sys: 8.23 ms, total: 62 ms
    Wall time: 625 ms





    {'success': 1,
     'failure': 0,
     'skipped': 4,
     'failureMessage': [],
     'timetaken': 64.086}



## Query Single Product

```python
%%time
result = sdk.querySingleProduct('0171670')
result
```

    INFO:root:{'body': '{"iprcode":"0171670"}', 'header': {}}


    CPU times: user 4.91 ms, sys: 123 µs, total: 5.04 ms
    Wall time: 74.6 ms





    {'cprcode': '0171670',
     'iprcode': '0171670',
     'oprcode': '0171670',
     'ordertype': 'Y',
     'pr_abb': 'JIRAPAT YOUNG KALE 2',
     'pr_active': 'Y',
     'pr_cgcode': '05',
     'pr_code': '0171670',
     'pr_dpcode': '19',
     'pr_engname': 'IRAPAT YOUNG KALE 200 G.',
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

    CPU times: user 3.97 ms, sys: 0 ns, total: 3.97 ms
    Wall time: 739 ms





    {'result': 'saved 3351 products'}


