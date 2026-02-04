from typing import Optional

from services.support.logger_util import _log as log
from services.support.storage.base_storage import BaseStorage

from services.support.storage.platforms.profiles.profile_storage import ProfilesStorage
from services.support.storage.platforms.producthunt.action import ProductHuntActionStorage
from services.support.storage.platforms.ycombinator.action import YCombinatorActionStorage
from services.support.storage.platforms.connections.connection_storage import ConnectionStorage

from services.support.storage.platforms.twitter import TwitterActionStorage
from services.support.storage.platforms.x.suggestions_new import XSuggestionsNewStorage
from services.support.storage.platforms.x.suggestions_generated import XSuggestionsGeneratedStorage

from services.support.storage.platforms.linkedin.action import LinkedInActionStorage
from services.support.storage.platforms.linkedin.suggestions_new import LinkedInSuggestionsNewStorage
from services.support.storage.platforms.linkedin.suggestions_generated import LinkedInSuggestionsGeneratedStorage

from services.support.storage.platforms.reddit.trends import RedditTrendsStorage
from services.support.storage.platforms.reddit.suggestions_new import RedditSuggestionsNewStorage
from services.support.storage.platforms.reddit.suggestions_generated import RedditSuggestionsGeneratedStorage

def get_storage(platform: str, profile_name: str, feature: str = 'action', verbose: bool = False) -> Optional[BaseStorage]:
    platform = platform.lower().strip()
    feature = feature.lower().strip()

    if platform in ['x', 'twitter']:
        if feature == 'action':
            log(f"Creating Twitter action storage for profile: {profile_name}", verbose, log_caller_file="storage_factory.py")
            return TwitterActionStorage(profile_name)
        elif feature == 'suggestions_generated':
            log(f"Creating X suggestions (generated) storage for profile: {profile_name}", verbose, log_caller_file="storage_factory.py")
            return XSuggestionsGeneratedStorage(profile_name)
        elif feature == 'suggestions_new':
            log(f"Creating X suggestions (new) storage for profile: {profile_name}", verbose, log_caller_file="storage_factory.py")
            return XSuggestionsNewStorage(profile_name)
        else:
            log(f"Unsupported Twitter feature: {feature}. Supported: action, suggestions_generated, suggestions_new", verbose, is_error=True, log_caller_file="storage_factory.py")
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
        elif feature == 'suggestions_generated':
            log(f"Creating LinkedIn suggestions (generated) storage for profile: {profile_name}", verbose, log_caller_file="storage_factory.py")
            return LinkedInSuggestionsGeneratedStorage(profile_name)
        elif feature == 'suggestions_new':
            log(f"Creating LinkedIn suggestions (new) storage for profile: {profile_name}", verbose, log_caller_file="storage_factory.py")
            return LinkedInSuggestionsNewStorage(profile_name)
        else:
            log(f"Unsupported LinkedIn feature: {feature}. Supported: action, connection, suggestions_generated, suggestions_new", verbose, is_error=True, log_caller_file="storage_factory.py")
            return None
    elif platform == 'connections':
        if feature == 'connection':
            log(f"Creating Connection storage for profile: {profile_name}", verbose, log_caller_file="storage_factory.py")
            return ConnectionStorage(profile_name)
        else:
            log(f"Unsupported Connection feature: {feature}. Supported: connection", verbose, is_error=True, log_caller_file="storage_factory.py")
            return None
    elif platform == 'profiles':
        if feature == 'sync':
            log(f"Creating Profiles sync storage for profile: {profile_name}", verbose, log_caller_file="storage_factory.py")
            return ProfilesStorage(profile_name)
        else:
            log(f"Unsupported Profiles feature: {feature}. Supported: sync", verbose, is_error=True, log_caller_file="storage_factory.py")
            return None
    elif platform == 'reddit':
        if feature == 'suggestions_generated':
            log(f"Creating Reddit suggestions (generated) storage for profile: {profile_name}", verbose, log_caller_file="storage_factory.py")
            return RedditSuggestionsGeneratedStorage(profile_name)
        elif feature == 'suggestions_new':
            log(f"Creating Reddit suggestions (new) storage for profile: {profile_name}", verbose, log_caller_file="storage_factory.py")
            return RedditSuggestionsNewStorage(profile_name)
        elif feature == 'trends':
            log(f"Creating Reddit trends storage for profile: {profile_name}", verbose, log_caller_file="storage_factory.py")
            return RedditTrendsStorage(profile_name)
        else:
            log(f"Unsupported Reddit feature: {feature}. Supported: suggestions_generated, suggestions_new, trends", verbose, is_error=True, log_caller_file="storage_factory.py")
            return None
    else:
        log(f"Unsupported platform: {platform}", verbose, is_error=True, log_caller_file="storage_factory.py")
        return None

def get_supported_platforms() -> list[str]:
    return ['x', 'twitter', 'linkedin', 'reddit', 'producthunt', 'ycombinator', 'connections', 'profiles']

def get_supported_features(platform: str) -> list[str]:
    platform = platform.lower().strip()

    if platform in ['x', 'twitter']:
        return ['action', 'suggestions_generated', 'suggestions_new']
    elif platform == 'linkedin':
        return ['action', 'connection', 'suggestions_generated', 'suggestions_new']
    elif platform == 'reddit':
        return ['suggestions_generated', 'suggestions_new', 'trends']
    elif platform == 'producthunt':
        return ['action']
    elif platform == 'ycombinator':
        return ['action']
    elif platform == 'connections':
        return ['connection']
    elif platform == 'profiles':
        return ['sync']
    else:
        return []

def validate_platform(platform: str) -> bool:
    return platform.lower().strip() in get_supported_platforms()

def validate_feature(platform: str, feature: str) -> bool:
    return feature.lower().strip() in get_supported_features(platform)

