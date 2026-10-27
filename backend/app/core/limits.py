from collections import defaultdict
from time import time
from fastapi import HTTPException
from app.core.config import settings
_local=defaultdict(list)
def enforce_rate_limit(key:str,limit:int,window_seconds:int)->None:
    try:
        from redis import Redis
        client=Redis.from_url(settings.redis_url,socket_connect_timeout=.2,socket_timeout=.2)
        k='resumeiq:ratelimit:'+key
        count=client.incr(k)
        if count==1: client.expire(k,window_seconds)
        if count>limit: raise HTTPException(429,'Too many requests. Please wait before trying again.')
        return
    except HTTPException: raise
    except Exception:
        # Development fallback only; use Redis/edge rate limiting for multi-instance deployments.
        now=time();_local[key]=[x for x in _local[key] if now-x<window_seconds]
        if len(_local[key])>=limit: raise HTTPException(429,'Too many requests. Please wait before trying again.')
        _local[key].append(now)
