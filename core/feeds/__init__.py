"""Durable feed ingestion/presentation primitives.

The package root intentionally performs no eager parser/network imports.
Individual consumers import the narrow module they need so merely registering
feed-related settings or presentation contracts cannot wake requests/feedparser
or create hidden startup cost while the family is dormant.
"""
