from enum import Enum


class NegotiationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"
    COLLAPSED = "collapsed"
