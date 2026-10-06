#!/usr/bin/env python3
"""Bounded recurring scheduler contract: computes due/not-due only."""
from __future__ import annotations
from typing import Any
MIN_INTERVAL=60
def due(schedule:dict[str,Any],epoch:int)->dict[str,Any]:
 interval=int(schedule.get("interval_seconds",0))
 if interval<MIN_INTERVAL:return {"due":False,"reason":"interval_below_minimum","authority_effect":"none","execution_authorized":False}
 last=schedule.get("last_completed_epoch")
 if last is None:return {"due":True,"reason":"never_completed","authority_effect":"none","execution_authorized":False}
 if epoch<int(last):return {"due":False,"reason":"clock_regression","authority_effect":"none","execution_authorized":False}
 return {"due":epoch-int(last)>=interval,"reason":"interval_elapsed" if epoch-int(last)>=interval else "not_due","authority_effect":"none","execution_authorized":False}
