__version__ = "0.1.0"

import logging

# vps-53u: the SDK logs to its own logger and configures nothing; the application decides where logs go.
logging.getLogger(__name__).addHandler(logging.NullHandler())
