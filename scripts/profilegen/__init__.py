"""Generators for the animated SVG assets embedded in the profile README.

Every asset here is a standalone ``.svg`` file published to the ``output`` branch and
referenced from ``README.md`` through ``<img>``/``<picture>``.  That delivery path imposes
the constraints the whole package is shaped around:

* GitHub's markdown sanitiser **deletes** inline ``<svg>``, escapes ``<style>`` and strips
  ``style=`` attributes, so styling and motion have to live inside the ``.svg`` file.
* An SVG loaded through ``<img>`` runs in the browser's *secure static mode*: no scripts and
  no external resources at all.  Fonts are therefore embedded as base64 ``@font-face``
  sources, never fetched, and there is no JavaScript anywhere.
* Animation is CSS ``@keyframes`` with one shared duration per document.  SMIL is banned --
  ``tests`` asserts its absence so the migration away from it cannot regress.

``ASSET_VERSION`` is the ``?v=`` cache-buster in every README URL.  Camo keys its cache on
the full URL including the query string, so a visual change is only guaranteed to reach
readers if this number moves in the same commit.
"""

from __future__ import annotations

ASSET_VERSION = 8

__all__ = ["ASSET_VERSION"]
