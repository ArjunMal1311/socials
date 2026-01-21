from typing import Optional
from .base_storage import BaseStorage
from .platforms.twitter import TwitterActionStorage
from .platforms.linkedin import LinkedInConnectionStorage
from services.support.logger_util import _log as log

def get_storage(platform: str, profile_name: str, feature: str = 'action', verbose: bool = False) -> Optional[BaseStorage]:
    platform = platform.lower().strip()
    feature = feature.lower().strip()

    if platform in ['x', 'twitter']:
        if feature == 'action':
            log(f"Creating Twitter action storage for profile: {profile_name}", verbose, log_caller_file="storage_factory.py")
            return TwitterActionStorage(profile_name)
        else:
            log(f"Unsupported Twitter feature: {feature}. Supported: action", verbose, is_error=True, log_caller_file="storage_factory.py")
            return None
    elif platform == 'linkedin':
        if feature == 'connection':
            log(f"Creating LinkedIn connection storage for profile: {profile_name}", verbose, log_caller_file="storage_factory.py")
            return LinkedInConnectionStorage(profile_name)
        else:
            log(f"Unsupported LinkedIn feature: {feature}. Supported: connection", verbose, is_error=True, log_caller_file="storage_factory.py")
            return None
    else:
        log(f"Unsupported platform: {platform}", verbose, is_error=True, log_caller_file="storage_factory.py")
        return None

def get_supported_platforms() -> list[str]:
    return ['x', 'twitter', 'linkedin']

def get_supported_features(platform: str) -> list[str]:
    platform = platform.lower().strip()

    if platform in ['x', 'twitter']:
        return ['action']
    elif platform == 'linkedin':
        return ['connection']
    else:
        return []

def validate_platform(platform: str) -> bool:
    return platform.lower().strip() in get_supported_platforms()

def validate_feature(platform: str, feature: str) -> bool:
    return feature.lower().strip() in get_supported_features(platform)

