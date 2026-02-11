
__doc__ = '\nLocal Docker Backend\n\nExecutes jobs locally using Docker containers.\nMimics HPC behavior for development and testing.\n'
import json
import logging
import os
import re
importshutil
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
# WARNING: Decompyle incomplete
