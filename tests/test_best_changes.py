from dataclasses import replace
import pytest
from nocturne.core.game import Game
from nocturne_battle.model import Limit
from nocturne_battle.runtime import Search


@pytest.mark.parametrize('multipv,enabled',[(1,True),(3,True),(1,False)])
def test_capture_best_changes_between_checkpoints_and_same_depth(qtbot,db,profile,multipv,enabled):
    p=replace(profile,arguments=profile.arguments+['--silent'])
    search=Search(db)
    try:
        search.start(Game(),p,Limit('nodes',1000),multipv,save_best_changes=enabled)
        qtbot.waitUntil(lambda:search.engine.connection.phase=='search',timeout=10000)
        sid=search.context['id']
        def update(pv,nodes,depth=12):
            search.observe(search.generation,dict(multipv=1,depth=depth,nodes=nodes,score_type='cp',score_value=24,score=.24,pv=pv))
        update(['e2e4'],100)
        update(['e2e4','e7e5'],200)
        update(['d2d4'],300)
        update(['e2e4'],400)
        update(['g1f3'],50) # Older observations cannot generate a change.
        search.cancel()
        saved=db.search_run(sid)['final_result']['best_changes']
        if enabled:
            assert [r['lines']['1']['pv'][0] for r in saved]==['e2e4','d2d4']
            assert saved[0]['lines']['1']['pv']==['e2e4','e7e5']
            assert saved[0]['lines']['1']['depth']==12
            assert saved[0]['lines']['1']['nodes']==200
            assert saved[0]['lines']['1']['score_value']==24
        else:assert saved==[]
        assert db.records(Game(),p)==[]
    finally:search.close()
