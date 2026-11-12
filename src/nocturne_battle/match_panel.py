"""Short display previews retain the complete underlying engine data."""
from nocturne.gui.candidates import CandidatePanel


class MatchCandidates(CandidatePanel):
    move_limit = 6

    def update_line(self, info, turn, light=False, detailed=False):
        super().update_line(info,turn,light=False,detailed=detailed)

    def _paint_line(self, rank, info, turn, light, detailed, previous=None, historical=False):
        shown = dict(info, san=info['san'][:self.move_limit]) if self.move_limit else info
        super()._paint_line(rank,shown,turn,False,detailed,previous,historical)

    def set_full(self, full):
        self.move_limit = None if full else 6
        for rank,info in list(self.lines.items()):
            self._paint_line(rank,info,self.turn,False,self.show_details)
