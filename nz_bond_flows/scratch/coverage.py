import sys, warnings; warnings.filterwarnings('ignore')
sys.path.insert(0, 'code')
import pandas as pd, attempt1r as a
f = a.settlements()
f['yr'] = f.date.dt.year
g = f.groupby('yr').agg(rows=('date','size'), net_nan=('net', lambda s: int(s.isna().sum())), nonzero=('net', lambda s: int((s.fillna(0)!=0).sum())),
                         princ=('principal', lambda s: int((s.fillna(0)!=0).sum())), princ_nan=('principal', lambda s: int(s.isna().sum())))
print(g.to_string())
e, fix = a.fixings('h10'); print('FX first/last', e.index.min().date(), e.index.max().date())
