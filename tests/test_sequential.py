import math
import pytest
from nocturne_battle.sequential import log_likelihood, normalized_elo, start_test, update_test


@pytest.mark.parametrize('counts,expected',[
    ([10,20,100,25,15],0.2954390532101659),
    ([1,0,0,0,0],-0.02056854226703698),
    ([0,0,100,0,0],-0.03753988283646515),
    ([0,0,0,0,20],0.4028835633542902)])
def test_likelihood_matches_fishtest_reference(counts,expected):
    # official-stockfish/fishtest f7af98f81f0c740a4de3d9a3721854709dcdc2bb
    assert log_likelihood(counts,0,5)==pytest.approx(expected,abs=1e-9)


def test_normalized_estimate_and_degenerate_data():
    assert normalized_elo([10,20,40,20,10])==pytest.approx(0)
    assert normalized_elo([0,0,50,0,0]) is None
    assert normalized_elo([1,2,4,8,16])>0


def test_monitor_does_not_double_count_and_freezes_first_decision():
    state={'games':[],'sprt':start_test()}
    for pair in range(500):
        state['games'] += [dict(pair=pair,result='1-0',a_white=True)]*2
        update_test(state)
        if state['sprt']['decision']:break
    assert state['sprt']['decision']=='H1 accepted'
    counts=state['sprt']['counts'][:]
    state['games'] += [dict(pair=1000,result='0-1',a_white=True)]*2
    update_test(state)
    assert state['sprt']['counts']==counts


def test_invalid_test_hypotheses():
    with pytest.raises(ValueError):start_test(5,0)
