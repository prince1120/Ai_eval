"""Background job workers.

Transcription and evaluation run here rather than inside the HTTP request, so
that a slow provider, a rate limit, or a redeploy cannot lose a user's upload.
"""
