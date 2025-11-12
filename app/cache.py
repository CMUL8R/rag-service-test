import json
import hashlib
import time
from typing import Optional

import structlog

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover - redis is optional for tests
    redis = None

from app.config import settings

logger = structlog.get_logger()


class CacheManager:
    def __init__(self):
        self.ttl = settings.cache_ttl
        self._memory_cache = {}
        self.redis_client = None

        if redis:
            try:
                self.redis_client = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2
                )
                logger.info("redis_connected")
            except Exception as e:
                logger.warning("redis_connection_failed", error=str(e))

    def _get_cache_key(self, question: str) -> str:
        """Generate cache key from question"""
        return f"question:{hashlib.md5(question.lower().strip().encode()).hexdigest()}"
    
    def get(self, question: str) -> Optional[dict]:
        """Get cached response"""
        key = self._get_cache_key(question)

        if not self.redis_client:
            payload = self._memory_cache.get(key)
            if payload and payload["expires_at"] > time.time():
                logger.info("cache_hit", question=question[:50], backend="memory")
                return payload["value"]
            if payload:
                self._memory_cache.pop(key, None)
            return None

        try:
            cached = self.redis_client.get(key)
            if cached:
                logger.info("cache_hit", question=question[:50], backend="redis")
                return json.loads(cached)
            return None
        except Exception as e:
            logger.error("cache_get_error", error=str(e))
            return None
    
    def set(self, question: str, response: dict):
        """Cache response"""
        key = self._get_cache_key(question)

        if not self.redis_client:
            self._memory_cache[key] = {
                "value": response,
                "expires_at": time.time() + self.ttl
            }
            return

        try:
            self.redis_client.setex(
                key,
                self.ttl,
                json.dumps(response)
            )
            logger.info("cache_set", question=question[:50])
        except Exception as e:
            logger.error("cache_set_error", error=str(e))
    
    def health_check(self) -> bool:
        """Check if Redis is healthy"""
        if not self.redis_client:
            return False
        try:
            return self.redis_client.ping()
        except Exception:
            return False


cache_manager = CacheManager()
