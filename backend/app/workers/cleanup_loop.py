import time
from app.workers.cleanup import cleanup_expired
def main():
 while True:
  try: print({'retention_cleanup':cleanup_expired()},flush=True)
  except Exception as exc: print({'retention_cleanup_error':type(exc).__name__},flush=True)
  time.sleep(3600)
if __name__=='__main__':main()
