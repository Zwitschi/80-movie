"""External system adapters for Discord and syndication."""

from .syndication_adapter import SyndicationAdapter
from .youtube import YouTubeSyndicationAdapter

__all__ = ["SyndicationAdapter", "YouTubeSyndicationAdapter"]
