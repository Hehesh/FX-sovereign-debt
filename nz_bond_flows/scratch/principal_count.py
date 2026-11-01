import sys, warnings; warnings.filterwarnings('ignore')
from pathlib import Path
sys.path.insert(0, 'code')
import numpy as np, pandas as pd
import attempt1r as a
f = a.settlements()
f['P'] = f.principal
p = f[(f.P.fillna(0) != 0)]
print('all nonzero principal dates in flow file:', len(p), p.date.min().date(), p.date.max().date())
print('  with us_share>0:', int((p.us_share > 0).sum()), '| us_share NaN:', int(p.us_share.isna().sum()))
q = p[p.date.between(*a.SAMPLE)]
print('inside 2014-01-02..2025-02-07:', len(q), '| with share>0:', int((q.us_share > 0).sum()))
print(q[['date','P','us_share']].assign(US_bn=lambda d: d.P*d.us_share/1000).to_string())
e, fix = a.fixings('h10'); 
from timing import window_index
f['j'] = window_index(pd.DatetimeIndex(f.settle_utc), fix)
print('principal dates mapped to a window j>=0 inside sample:', int((f.loc[q.index,'j']>=0).sum()))
print('--- pre-2014 principal dates (share NaN):'); print(p[p.date < '2014-01-02'][['date','P','us_share']].to_string())
print('share first valid:', f.dropna(subset=['us_share']).date.min())
print('nominal-only vs IIB-null principal in sample:', f.loc[q.index, ['nom_principal','iib_principal']].to_string())
