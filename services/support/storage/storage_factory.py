from typing import Optional

from services.support.logger_util import _log as log

from services.support.storage.base_storage import BaseStorage
from services.support.storage.platforms.twitter import TwitterActionStorage
from services.support.storage.platforms.linkedin.action import LinkedInActionStorage
from services.support.storage.platforms.producthunt.action import ProductHuntActionStorage
from services.support.storage.platforms.ycombinator.action import YCombinatorActionStorage
from services.support.storage.platforms.connections.connection_storage import ConnectionStorage

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
    elif platform == 'producthunt':
        if feature == 'action':
            log(f"Creating Product Hunt action storage for profile: {profile_name}", verbose, log_caller_file="storage_factory.py")
            return ProductHuntActionStorage(profile_name)
        else:
            log(f"Unsupported Product Hunt feature: {feature}. Supported: action", verbose, is_error=True, log_caller_file="storage_factory.py")
            return None
    elif platform == 'ycombinator':
        if feature == 'action':
            log(f"Creating Y Combinator action storage for profile: {profile_name}", verbose, log_caller_file="storage_factory.py")
            return YCombinatorActionStorage(profile_name)
        else:
            log(f"Unsupported Y Combinator feature: {feature}. Supported: action", verbose, is_error=True, log_caller_file="storage_factory.py")
            return None
    elif platform == 'linkedin':
        if feature == 'action':
            log(f"Creating LinkedIn action storage for profile: {profile_name}", verbose, log_caller_file="storage_factory.py")
            return LinkedInActionStorage(profile_name)
        else:
            log(f"Unsupported LinkedIn feature: {feature}. Supported: action", verbose, is_error=True, log_caller_file="storage_factory.py")
            return None
    elif platform == 'connections':
        if feature == 'connection':
            log(f"Creating Connection storage for profile: {profile_name}", verbose, log_caller_file="storage_factory.py")
            return ConnectionStorage(profile_name)
        else:
            log(f"Unsupported Connection feature: {feature}. Supported: connection", verbose, is_error=True, log_caller_file="storage_factory.py")
            return None
    else:
        log(f"Unsupported platform: {platform}", verbose, is_error=True, log_caller_file="storage_factory.py")
        return None

def get_supported_platforms() -> list[str]:
    return ['x', 'twitter', 'linkedin', 'producthunt', 'ycombinator', 'connections']

def get_supported_features(platform: str) -> list[str]:
    platform = platform.lower().strip()

    if platform in ['x', 'twitter']:
        return ['action']
    elif platform == 'linkedin':
        return ['action', 'connection']
    elif platform == 'producthunt':
        return ['action']
    elif platform == 'ycombinator':
        return ['action']
    elif platform == 'connections':
        return ['connection']
    else:
        return []

def validate_platform(platform: str) -> bool:
    return platform.lower().strip() in get_supported_platforms()

def validate_feature(platform: str, feature: str) -> bool:
    return feature.lower().strip() in get_supported_features(platform)

