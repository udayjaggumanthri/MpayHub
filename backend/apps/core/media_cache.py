"""HTTP cache headers for immutable UUID-named media files."""

# Filenames are UUID-based (content-addressed); safe to cache aggressively.
MEDIA_CACHE_CONTROL = 'public, max-age=86400, immutable'
