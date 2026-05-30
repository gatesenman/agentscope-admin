"""Per-user persistence for the vue-vben-admin frontend preferences.

vben stores its UI preferences (theme, layout, locale, sidebar state, ...) in
``localStorage`` by default. This module persists them server-side keyed by the
``X-User-ID`` header so settings follow the user across browsers/devices.
"""
