"""Redis state manager for user sessions"""
import redis
import json
from typing import Any, Optional
from core.config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD


class StateManager:
    """Manage user states in Redis"""

    def __init__(self):
        self.redis = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD if REDIS_PASSWORD else None,
            decode_responses=True
        )

    def set_state(self, user_id: int, state: str, ttl: int = 3600):
        """Set user state"""
        key = f"state:{user_id}"
        self.redis.setex(key, ttl, state)

    def get_state(self, user_id: int) -> Optional[str]:
        """Get user state"""
        key = f"state:{user_id}"
        return self.redis.get(key)

    def clear_state(self, user_id: int):
        """Clear user state"""
        key = f"state:{user_id}"
        self.redis.delete(key)

    def set_data(self, user_id: int, key: str, value: Any, ttl: int = 3600):
        """Set user data"""
        redis_key = f"data:{user_id}:{key}"
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        self.redis.setex(redis_key, ttl, value)

    def get_data(self, user_id: int, key: str) -> Optional[Any]:
        """Get user data"""
        redis_key = f"data:{user_id}:{key}"
        value = self.redis.get(redis_key)

        if value:
            try:
                return json.loads(value)
            except:
                return value
        return None

    def delete_data(self, user_id: int, key: str):
        """Delete user data"""
        redis_key = f"data:{user_id}:{key}"
        self.redis.delete(redis_key)

    def clear_user_data(self, user_id: int):
        """Clear all user data"""
        pattern = f"data:{user_id}:*"
        for key in self.redis.scan_iter(pattern):
            self.redis.delete(key)

    def set_task_id(self, user_id: int, task_id: str, ttl: int = 600):
        """Save task ID for user"""
        key = f"task:{user_id}"
        self.redis.setex(key, ttl, task_id)

    def get_task_id(self, user_id: int) -> Optional[str]:
        """Get task ID for user"""
        key = f"task:{user_id}"
        return self.redis.get(key)

    def clear_task_id(self, user_id: int):
        """Clear task ID"""
        key = f"task:{user_id}"
        self.redis.delete(key)


# Global instance
state_manager = StateManager()
