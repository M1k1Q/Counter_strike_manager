from enum import Enum


class NegotiationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"
    COLLAPSED = "collapsed"

class MatchFormats(str, Enum):
    Bo1 = "Bo1"
    Bo3 = "Bo3"
    Bo5 = "Bo5"