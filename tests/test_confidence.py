from nocturne_battle.statistics import confidence_report


def match(results):
    games=[]
    for pair,result in enumerate(results):
        for score in result:
            games.append(dict(pair=pair,fen=str(pair),moves=[],result={0:'0-1',0.5:'1/2-1/2',1:'1-0'}[score],a_white=True))
    return {'games':games}


def test_confidence_reports_multiple_levels_and_pair_distribution():
    text=confidence_report(match([(1,1),(0,0),(1,0),(.5,.5)]*5))
    assert '[5, 0, 10, 0, 5]' in text
    for level in ('80%','90%','95%','99%'):assert level+' Elo interval:' in text
    assert '50.00%' in text and 'Not Fishtest SPRT' in text


def test_degenerate_and_repeated_openings_do_not_claim_precision():
    assert 'no variation' in confidence_report(match([(.5,.5)]*20))
    state=match([(1,1),(0,0)]*10)
    for game in state['games']:game['fen']='same'
    assert 'need at least 10' in confidence_report(state)
