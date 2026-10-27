import os, uuid, hashlib
from pathlib import Path
from app.core.config import settings

def ensure_dirs():
 Path(settings.upload_dir).mkdir(parents=True,exist_ok=True,mode=0o700); Path(settings.output_dir).mkdir(parents=True,exist_ok=True,mode=0o700); os.chmod(settings.upload_dir,0o700); os.chmod(settings.output_dir,0o700)
def store_upload(content: bytes, filename: str, user_id: int) -> tuple[str,str]:
 ensure_dirs(); digest=hashlib.sha256(content).hexdigest()
 # Opaque storage name; original filename is metadata only, never used as a path.
 suffix=Path(filename).suffix.lower(); key=f"u{user_id}_{uuid.uuid4().hex}{suffix}"
 if settings.storage_backend.lower()=="s3":
  import boto3
  if not all([settings.s3_bucket,settings.s3_access_key_id,settings.s3_secret_access_key]): raise RuntimeError("S3 storage is not fully configured.")
  client=boto3.client("s3",endpoint_url=settings.s3_endpoint_url or None,region_name=settings.s3_region,aws_access_key_id=settings.s3_access_key_id,aws_secret_access_key=settings.s3_secret_access_key)
  client.put_object(Bucket=settings.s3_bucket,Key=f"uploads/{key}",Body=content)
  return f"s3://{settings.s3_bucket}/uploads/{key}",digest
 path=Path(settings.upload_dir)/key; path.write_bytes(content); os.chmod(path,0o600)
 return str(path.resolve()),digest

def read_private(path: str) -> bytes:
 if path.startswith("s3://"):
  import boto3
  _,rest=path.split("s3://",1); bucket,key=rest.split("/",1)
  client=boto3.client("s3",endpoint_url=settings.s3_endpoint_url or None,region_name=settings.s3_region,aws_access_key_id=settings.s3_access_key_id,aws_secret_access_key=settings.s3_secret_access_key)
  return client.get_object(Bucket=bucket,Key=key)["Body"].read()
 return Path(path).read_bytes()

def delete_private(path: str) -> None:
 try:
  if path.startswith("s3://"):
   import boto3
   _,rest=path.split("s3://",1); bucket,key=rest.split("/",1)
   boto3.client("s3",endpoint_url=settings.s3_endpoint_url or None,region_name=settings.s3_region,aws_access_key_id=settings.s3_access_key_id,aws_secret_access_key=settings.s3_secret_access_key).delete_object(Bucket=bucket,Key=key)
  else: Path(path).unlink(missing_ok=True)
 except Exception: pass


def store_output_file(local_path: str, user_id: int) -> str:
    """Persist a generated file locally or to the configured private S3 bucket."""
    source=Path(local_path)
    if settings.storage_backend.lower()!='s3':
        os.chmod(source,0o600)
        return str(source.resolve())
    import boto3, mimetypes, uuid
    if not all([settings.s3_bucket,settings.s3_access_key_id,settings.s3_secret_access_key]): raise RuntimeError('S3 storage is not fully configured.')
    key=f"outputs/u{user_id}/{uuid.uuid4().hex}{source.suffix.lower()}"
    client=boto3.client('s3',endpoint_url=settings.s3_endpoint_url or None,region_name=settings.s3_region,aws_access_key_id=settings.s3_access_key_id,aws_secret_access_key=settings.s3_secret_access_key)
    client.upload_file(str(source),settings.s3_bucket,key,ExtraArgs={'ContentType':mimetypes.guess_type(source.name)[0] or 'application/octet-stream'})
    return f"s3://{settings.s3_bucket}/{key}"

def signed_download_url(path: str) -> str:
    if not path.startswith('s3://'): raise ValueError('Expected S3 object URI.')
    import boto3
    bucket_key=path[5:];bucket,key=bucket_key.split('/',1)
    client=boto3.client('s3',endpoint_url=settings.s3_endpoint_url or None,region_name=settings.s3_region,aws_access_key_id=settings.s3_access_key_id,aws_secret_access_key=settings.s3_secret_access_key)
    return client.generate_presigned_url('get_object',Params={'Bucket':bucket,'Key':key},ExpiresIn=settings.s3_presigned_url_seconds)
