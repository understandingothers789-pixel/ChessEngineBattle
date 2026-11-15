"""Normalized pentanomial GSPRT using Fishtest's published mathematical model.

Independent implementation of normalized_elo_practical.pdf. No upstream code is
bundled. The numerical result is compared against upstream in regression work.
"""
import math
from scipy.optimize import brentq

FACTOR=800/math.log(10)


def pair_results(state):
    groups={}
    for game in state['games']:
        if game['result']=='*':continue
        value=.5 if game['result']=='1/2-1/2' else int((game['result']=='1-0')==game['a_white'])
        groups.setdefault(game['pair'],[]).append(value)
    return [(key,round(2*sum(values))) for key,values in sorted(groups.items()) if len(values)==2]


def normalized_elo(counts):
    n=sum(counts)
    if not n:return None
    p=[c/n for c in counts];mean=sum(i/4*p[i] for i in range(5))
    variance=sum(p[i]*(i/4-mean)**2 for i in range(5))
    return FACTOR*(mean-.5)/math.sqrt(2*variance) if variance>0 else None


def constrained_fit(observed,target):
    fitted=[.2]*5
    for _ in range(10):
        mean=sum(i/4*fitted[i] for i in range(5))
        variance=sum(fitted[i]*(i/4-mean)**2 for i in range(5))
        sd=math.sqrt(variance)
        offsets=[i/4-.5-target*sd*(1+((mean-i/4)/sd)**2)/2 for i in range(5)]
        lo=-1/max(offsets)+1e-9;hi=-1/min(offsets)-1e-9
        root=brentq(lambda x:sum(p*d/(1+x*d) for p,d in zip(observed,offsets)),lo,hi)
        new=[p/(1+root*d) for p,d in zip(observed,offsets)]
        change=max(abs(a-b) for a,b in zip(new,fitted));fitted=new
        if change<1e-9:break
    mean=sum(i/4*fitted[i] for i in range(5))
    var=sum(fitted[i]*(i/4-mean)**2 for i in range(5))
    if abs(sum(fitted)-1)>1e-3 or abs((mean-.5)/math.sqrt(var)-target)>1e-5:
        raise ValueError('Normalized likelihood fit did not converge')
    return fitted


def log_likelihood(counts,h0,h1):
    # Fishtest's 0.001 regularization permits unseen result categories.
    counts=[c if c else .001 for c in counts];n=sum(counts)
    observed=[c/n for c in counts]
    fits=[constrained_fit(observed,h*math.sqrt(2)/FACTOR) for h in (h0,h1)]
    return sum(c*math.log(b/a) for c,a,b in zip(counts,*fits))


def start_test(h0=0,h1=5,alpha=.05,beta=.05):
    if not -20<=h0<h1<=20 or not .001<=alpha<=.2 or not .001<=beta<=.2:
        raise ValueError('SPRT requires -20 ≤ H0 < H1 ≤ 20 nElo and error rates between 0.001 and 0.20')
    return dict(h0=h0,h1=h1,alpha=alpha,beta=beta,counts=[0]*5,seen=[],llr=0,decision='',
                lower=math.log(beta/(1-alpha)),upper=math.log((1-beta)/alpha),
                low=0,high=0,down_sum=0,down_sq=0,up_sum=0,up_sq=0)


def update_test(state):
    test=state.get('sprt')
    if not test or test['decision']:return
    for key,category in pair_results(state):
        if key in test['seen']:continue
        counts=list(test['counts']);counts[category]+=1
        try:llr=log_likelihood(counts,test['h0'],test['h1'])
        except (ValueError,ArithmeticError) as exc:
            test['error']=str(exc);return
        test.pop('error',None);test['counts']=counts;test['seen'].append(key);test['llr']=llr
        if llr<test['low']:
            step=llr-test['low'];test['down_sum']+=step;test['down_sq']+=step*step;test['low']=llr
        if llr>test['high']:
            step=llr-test['high'];test['up_sum']+=step;test['up_sq']+=step*step;test['high']=llr
        down=-test['down_sq']/test['down_sum']/2 if test['down_sum'] else 0
        up=test['up_sq']/test['up_sum']/2 if test['up_sum'] else 0
        test['effective_lower']=test['lower']+down;test['effective_upper']=test['upper']-up
        if llr<test['effective_lower']:test['decision']='H0 accepted'
        elif llr>test['effective_upper']:test['decision']='H1 accepted'
        if test['decision']:break


def report(state):
    counts=[0]*5
    for _,category in pair_results(state):counts[category]+=1
    value=normalized_elo(counts)
    text='NORMALIZED ELO / SPRT · A minus B\n'
    text+=f'Normalized Elo: {value:+.2f}\n' if value is not None else 'Normalized Elo unavailable: no pairs or zero pair variance.\n'
    if value is not None:
        from statistics import NormalDist
        results=pair_results(state);n=len(results)
        mean=sum(category/4 for _,category in results)/n
        variance=sum((category/4-mean)**2 for _,category in results)/n
        identities={g['pair']:(g.get('fen',str(g['pair'])),tuple(g.get('moves',[])[:g.get('opening_plies',0)])) for g in state['games']}
        clusters={}
        for key,category in results:
            x=category/4;influence=FACTOR/math.sqrt(2)*((x-mean)/math.sqrt(variance)-(mean-.5)*((x-mean)**2-variance)/(2*variance**1.5))
            identity=identities[key];clusters[identity]=clusters.get(identity,0)+influence
        k=len(clusters)
        if k>=10:
            se=math.sqrt(k/(k-1)*sum(v*v for v in clusters.values())/n**2)
            if se>0:
                for level in (.8,.9,.95,.99):
                    radius=NormalDist().inv_cdf((1+level)/2)*se
                    text+=f'{level:.0%} normalized Elo interval: {value-radius:+.2f} to {value+radius:+.2f}\n'
                text+='Normalized intervals: fixed-sample cluster delta-method approximation; not sequentially adjusted.\n'
            else:text+='Normalized intervals unavailable: zero estimated uncertainty.\n'
        else:text+='Normalized intervals need at least 10 distinct opening groups.\n'
    test=state.get('sprt')
    if not test:return text+'No preconfigured SPRT for this match. Enable SPRT before starting a new match.\n'
    text+=f"Normalized hypotheses: H0 {test['h0']:+g}, H1 {test['h1']:+g} · α {test['alpha']:.1%}, β {test['beta']:.1%}\n"
    text+=f"LLR {test['llr']:+.4f} · boundaries [{test.get('effective_lower',test['lower']):+.4f}, {test.get('effective_upper',test['upper']):+.4f}]\n"
    text+=f"Decision: {test['decision'] or 'continuing'} · {sum(test['counts'])} tested pairs\n"
    if test.get('error'):text+='Numerical error: '+test['error']+'\n'
    return text+'Normalized pentanomial generalized SPRT with overshoot correction. Decision freezes at the first boundary; the match schedule continues. Assumes independent opening pairs; repeated openings or tuning during a test undermine error guarantees. Normalized Elo and logistic Elo are different scales.'
