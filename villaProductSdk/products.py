# AUTOGENERATED! DO NOT EDIT! File to edit: product-sdk.ipynb (unless otherwise specified).

__all__ = ['FunctionNames', 'ProductSdk']

# Cell
from botocore.config import Config
from s3bz.s3bz import S3, Requests
from lambdasdk.lambdasdk import Lambda
from .schema import Event, Response
import bz2, json, boto3, base64, logging
logging.basicConfig(level=logging.INFO)

# Cell
class FunctionNames:
  '''determine function and resources name based on branchName'''
  def __init__(self, branchName = 'dev-manual'):
    self.branchName = branchName
  dumpToS3 = lambda self: f'product-dump-s3-{self.branchName}'
  updateProduct = lambda self: f'product-update-{self.branchName}'
  updateS3 = lambda self: f'product-update-s3-{self.branchName}'
  singleQuery = lambda self: f'product-get-{self.branchName}'
  allQuery = lambda self: f'product-get-all-{self.branchName}'
  inputBucket = lambda self: f'input-product-bucket-{self.branchName}'
  inventoryBucket = lambda self: f'product-bucket-{self.branchName}'


# Cell
class ProductSdk:

  def __init__(self, branch = 'dev-manual', user = None, pw = None, region = 'ap-southeast-1'):
    self.branchName = branch
    self.functionNames = FunctionNames(branchName = branch)
    self.lambdaClient = Lambda(user =user, pw=pw, region = region)
    self.user = user; self.pw = pw; self.region = region

  @staticmethod
  def returnLambdaResponse(lambdaResponse:dict):
    try:
      return Response.fromDict(lambdaResponse).body
    except:
      logging.exception('error parsing body, perhaps there is no body in response')
      logging.error(lambdaResponse)
  @staticmethod
  def printFirst(inputDict:dict):
    return next(iter(inputDict.items()))

  def updateWithS3(self, data,
                   inputKeyName = 'input-data-name',
                   invocationType = 'RequestResponse',
                   user= None, pw= None):
    # put users if not specified
    user = user or self.user; pw = pw or self.pw

    # extract function name and inputbucket name
    inputBucketName = self.functionNames.inputBucket()
    functionName = self.functionNames.updateS3()
    logging.info(f'bucket is {inputBucketName}')

    # save data to s3
    S3.save(key = inputKeyName,
            objectToSave = data ,
            bucket = inputBucketName,
            user=user, pw=pw)
    logging.info(f'data is saved to s3, invoking ingestion function')

    # call lambda function
    inputValue = Event(body = json.dumps({ 'key': inputKeyName })).to_dict()
    logging.info(f'input to lambda is {inputValue}')
    lambdaResponse = self.lambdaClient.invoke(
      functionName= functionName ,
      input=inputValue,
      invocationType= invocationType )
    return self.returnLambdaResponse(lambdaResponse)

  def querySingleProduct(self, iprcode = '0171670', user=None, pw=None):
    '''query a single product'''
    #extract function name
    functionName = self.functionNames.singleQuery()
    query = {'iprcode': iprcode}
    inputValue = Event(body = json.dumps(query)).to_dict()
    logging.info(inputValue)
    lambdaResponse = self.lambdaClient.invoke(
        functionName = functionName , input = inputValue )
    return self.returnLambdaResponse(lambdaResponse)

  def allQuery(self):
    functionName = self.functionNames.allQuery()
    lambdaResponse = self.lambdaClient.invoke(
      functionName = functionName, input = {}
    )
    url = Response.fromDict(lambdaResponse).body['url']
    result = Requests.getContentFromUrl(url)
    return result
  def syncS3(self):
    '''force s3 to sync with the newly input data'''
    functionName = self.functionNames.dumpToS3()
    lambdaResponse = self.lambdaClient.invoke(
      functionName = functionName, input = {}
    )
    return lambdaResponse