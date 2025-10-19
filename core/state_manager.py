"""Redis state manager for user sessions"""
import redis
import json
from typing import Any, Optional
from core.config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD


class StateManager:
    """Manage user states in Redis"""

    def __init__(self):
        # Create connection pool with retry logic
        self.pool = redis.ConnectionPool(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD if REDIS_PASSWORD else None,
            decode_responses=True,
            max_connections=50,
            socket_keepalive=True,
            socket_connect_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30
        )
        self.redis = redis.Redis(connection_pool=self.pool)

    def _execute_with_retry(self, func, *args, **kwargs):
        """Execute Redis command with automatic retry on connection error"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except (redis.ConnectionError, redis.TimeoutError, ConnectionResetError) as e:
                if attempt == max_retries - 1:
                    # Last attempt failed, raise the error
                    raise
                # Recreate connection on error
                try:
                    self.redis = redis.Redis(connection_pool=self.pool)
                except Exception:
                    pass
                continue
            except Exception as e:
                # Other errors - don't retry
                raise

    def set_state(self, user_id: int, state: str, ttl: int = 3600):
        """Set user state"""
        key = f"state:{user_id}"
        return self._execute_with_retry(self.redis.setex, key, ttl, state)

    def get_state(self, user_id: int) -> Optional[str]:
        """Get user state"""
        key = f"state:{user_id}"
        return self._execute_with_retry(self.redis.get, key)

    def clear_state(self, user_id: int):
        """Clear user state"""
        key = f"state:{user_id}"
        return self._execute_with_retry(self.redis.delete, key)

    def set_data(self, user_id: int, key: str, value: Any, ttl: int = 3600):
        """Set user data"""
        redis_key = f"data:{user_id}:{key}"
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        return self._execute_with_retry(self.redis.setex, redis_key, ttl, value)

    def get_data(self, user_id: int, key: str) -> Optional[Any]:
        """Get user data"""
        redis_key = f"data:{user_id}:{key}"
        value = self._execute_with_retry(self.redis.get, redis_key)

        if value:
            try:
                return json.loads(value)
            except:
                return value
        return None

    def delete_data(self, user_id: int, key: str):
        """Delete user data"""
        redis_key = f"data:{user_id}:{key}"
        return self._execute_with_retry(self.redis.delete, redis_key)

    def clear_user_data(self, user_id: int):
        """Clear all user data"""
        pattern = f"data:{user_id}:*"
        try:
            keys = list(self._execute_with_retry(self.redis.scan_iter, pattern))
            if keys:
                self._execute_with_retry(self.redis.delete, *keys)
        except Exception as e:
            # If scanning fails, just log and continue
            print(f"Warning: Failed to clear user data: {e}")

    def set_task_id(self, user_id: int, task_id: str, ttl: int = 600):
        """Save task ID for user"""
        key = f"task:{user_id}"
        return self._execute_with_retry(self.redis.setex, key, ttl, task_id)

    def get_task_id(self, user_id: int) -> Optional[str]:
        """Get task ID for user"""
        key = f"task:{user_id}"
        return self._execute_with_retry(self.redis.get, key)

    def clear_task_id(self, user_id: int):
        """Clear task ID"""
        key = f"task:{user_id}"
        return self._execute_with_retry(self.redis.delete, key)


# Global instance
state_manager = StateManager()
