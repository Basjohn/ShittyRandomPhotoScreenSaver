"""Imgur Widget Module.

Displays curated image galleries from Imgur in a grid layout.
Uses web scraping since Imgur API is closed to new registrations.
"""
from widgets.imgur.widget import ImgurWidget
from widgets.imgur.scraper import ImgurScraper
from widgets.imgur.image_cache import ImgurImageCache

__all__ = ["ImgurWidget", "ImgurScraper", "ImgurImageCache"]
