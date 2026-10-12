"""EchoProof: finite, task-aware sonification collision auditing."""
from .model import Mapping, Render, Event, encode
from .audit import audit, verify_witness, verify_audit

__version__ = "0.1.0"
__all__ = ["Mapping", "Render", "Event", "encode", "audit", "verify_witness", "verify_audit"]
