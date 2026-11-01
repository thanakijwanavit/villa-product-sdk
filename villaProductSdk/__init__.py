__version__ = "0.0.17"

import logging

# vps-53u: the SDK logs to its own logger and configures nothing; the application decides where logs go.
logging.getLogger(__name__).addHandler(logging.NullHandler())
