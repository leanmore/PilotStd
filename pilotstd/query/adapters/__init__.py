# pilotstd/query/adapters/__init__.py
from .base import BaseAdapter
from .csres import CsresAdapter
from .std_gov import StdGovAdapter
from .njbz365 import Njbz365Adapter
from .hbba import HbbaAdapter
from .iso_gov import IsoGovAdapter
from .dbba import DbbaAdapter

try:
    from .mock import MockQueryAdapter
except ImportError:
    MockQueryAdapter = None

__all__ = ["BaseAdapter", "CsresAdapter", "DbbaAdapter",
           "StdGovAdapter", "Njbz365Adapter", "HbbaAdapter", "IsoGovAdapter"]
if MockQueryAdapter is not None:
    __all__.append("MockQueryAdapter")
