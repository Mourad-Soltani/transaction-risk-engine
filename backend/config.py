"""Runtime configuration constants for the HTTP surface.

Domain rules and thresholds live in aml_engine.py.

Author: Mourad.Soltani
"""

PROJECT_NAME = "Transaction Risk Assessment Engine"
VERSION = "1.0.0"
AUTHOR = "Mourad.Soltani"
SIGNATURE = "Mourad.Soltani"

# Enterprise transaction histories are large. 512 KB holds ~2,000 records.
MAX_CONTENT_LENGTH = 512 * 1024

# Upper bound on history records per request.
MAX_HISTORY_RECORDS = 2000
