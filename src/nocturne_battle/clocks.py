"""Integer-nanosecond match clocks. Preparation is excluded; search receipt is charged."""
import time
from dataclasses import dataclass


@dataclass
class MatchClock:
    remaining: dict
    increments: dict
    active: int | None = None
    anchor: int | None = None
    wall_anchor: int | None = None

    @classmethod
    def create(cls, limits, a_white):
        white = 0 if a_white else 1
        return cls({1:limits[white].value*1_000_000,-1:limits[1-white].value*1_000_000},
                   {1:limits[white].increment_ms*1_000_000,-1:limits[1-white].increment_ms*1_000_000})

    @classmethod
    def restore(cls, payload, wall_now=None):
        clock=cls({int(k):v for k,v in payload['remaining_ns'].items()},
                  {int(k):v for k,v in payload['increment_ns'].items()})
        active=payload.get('active')
        if active is not None:
            elapsed=max(0,(time.time_ns() if wall_now is None else wall_now)-payload['wall_anchor_ns'])
            clock.remaining[active]=max(0,clock.remaining[active]-elapsed)
        return clock

    def start(self,color,now=None,wall_now=None):
        if self.active is not None:raise ValueError('Clock already running')
        self.active=color
        self.anchor=time.monotonic_ns() if now is None else now
        self.wall_anchor=time.time_ns() if wall_now is None else wall_now

    def left(self,color,now=None):
        elapsed=0 if self.active != color else max(0,(time.monotonic_ns() if now is None else now)-self.anchor)
        return max(0,self.remaining[color]-elapsed)

    def stop(self,now=None,add_increment=False,buffer_ns=0):
        if self.active is None:return None,0
        color=self.active
        elapsed=max(0,(time.monotonic_ns() if now is None else now)-self.anchor)
        charged=max(0,elapsed-max(0,buffer_ns))
        self.remaining[color]=max(0,self.remaining[color]-charged)
        flagged=self.remaining[color] == 0
        if add_increment and not flagged:self.remaining[color]+=self.increments[color]
        self.active=self.anchor=self.wall_anchor=None
        return color if flagged else None,charged

    def uci(self):
        return 'go '+ ' '.join(f'{name} {value}' for name,value in (
            ('wtime',max(1,self.left(1)//1_000_000)),('btime',max(1,self.left(-1)//1_000_000)),
            ('winc',self.increments[1]//1_000_000),('binc',self.increments[-1]//1_000_000)))

    def payload(self):
        return dict(remaining_ns=dict(self.remaining),increment_ns=dict(self.increments),
                    active=self.active,wall_anchor_ns=self.wall_anchor,
                    policy='charge from UCI go until receipt; unclean recovery charges wall time including downtime')
