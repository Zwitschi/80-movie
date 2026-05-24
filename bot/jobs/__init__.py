"""Scheduled jobs and polling tasks."""

from .syndication_polling import SyndicationPollingJob, SyndicationPollingRunResult

__all__ = ["SyndicationPollingJob", "SyndicationPollingRunResult"]
