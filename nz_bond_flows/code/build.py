"""Steps 2-6: raw tables -> bond-level payments and events -> daily net flows. Writes the workbook."""
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, sys.argv[1])
import load as L

OUT = sys.argv[2]
START, END = pd.Timestamp("2000-02-01"), pd.Timestamp("2026-09-30")
TENDER_LAG = 3                      # NZ business days from tender date to settlement (see checks)

bdays, hol = L.nz_business_days()
bdays = pd.DatetimeIndex(bdays)
def next_bd(d):                     # same day if business day, else next business day
    return bdays[bdays.searchsorted(pd.Timestamp(d))]
def add_bd(d, k):                   # k business days after d
    return bdays[bdays.searchsorted(pd.Timestamp(d), side="right") + k - 1]

# ---------- Step 2: holdings by bond and month-end ----------
o = L.onissue()
tend, synd, rep, lsap, nmk = L.tenders(), L.syndications(), L.repurchases(), L.lsap_repurchases(), L.nonmarket()
tend["settle_date"] = [add_bd(d, TENDER_LAG) for d in tend.trade_date]
rep["settle_date"] = [add_bd(d, TENDER_LAG) for d in rep.trade_date]

# drop month-end rows dated before a bond's first issue settles (one pre-launch row: GB0532, May-2021)
first = pd.concat([tend[["bond", "settle_date"]], synd[["bond", "settle_date"]]]).groupby("bond").settle_date.min()
o["first_settle"] = o.bond.map(first)
prelaunch = o[o.first_settle.notna() & (o.month_end < o.first_settle + pd.offsets.MonthEnd(0))]
o = o.drop(prelaunch.index)

d31 = L.d31()
h = o.merge(d31, on=["month_end", "bond"], how="left")
h["private"] = np.where(h.private_d31.notna(), h.private_d31, h.market_nzdm)
h["rbnz_secondary"] = np.where(h.private_d31.notna(), h.market_nzdm - h.private_d31, 0.0)
h["nonres"] = h.nonres_d31
h["holder_source"] = np.where(h.private_d31.notna(), "RBNZ D31", "NZDM market bonds")
bonds = o.groupby("bond").agg(type=("type", "first"), coupon=("coupon", "first"), maturity=("maturity", "first"),
                              first_month_end=("month_end", "min"), last_month_end=("month_end", "max")).reset_index()

# ---------- Step 3: inflation index factor Kt for IIBs ----------
kt = L.iib_factors()[["bond", "coupon_date", "p", "kt", "kt_source"]]
# IIB0216 (4.5% Feb-2016) is not in the NZDM factors file: rebuild Kt from CPI with the same formula,
# K(t) = K(t-1) * (1 + p/100), p = mean % change in CPI over the 2 quarters ending 2 quarters before payment.
cpi = L.cpi().set_index("date").cpi
cpi.index = cpi.index.to_period("Q")
chg = cpi.pct_change() * 100
dates, k, rows = [pd.Timestamp("1995-11-15") + pd.DateOffset(months=3 * i) for i in range(82)], 100.0, []
for i, d in enumerate(dates):
    pq = d.to_period("Q") - 2
    p = 0.0 if i == 0 else round((chg[pq] + chg[pq - 1]) / 2, 2)
    k = 100.0 if i == 0 else round(k * (1 + p / 100), 2)
    rows.append(("IIB0216", d, p, k, "Estimated from CPI (OECD via FRED); base 100 at 15-Nov-1995 assumed"))
kt = pd.concat([kt, pd.DataFrame(rows, columns=kt.columns)]).sort_values(["bond", "coupon_date"]).reset_index(drop=True)

def kt_at(bond, d, on_or_before=False):
    g = kt[kt.bond == bond]
    if on_or_before:
        g = g[g.coupon_date <= d]
        return g.iloc[-1] if len(g) else None
    g = g[g.coupon_date == d]
    return g.iloc[0] if len(g) else None

# ---------- Step 4: coupon and principal schedule ----------
P = []
for b in bonds.itertuples():
    step = 3 if b.type == "IIB" else 6
    n = 0
    while True:
        d = b.maturity - pd.DateOffset(months=step * n)
        if d < START: break
        if d <= END:
            P.append((b.bond, d, "Coupon"))
            if n == 0:
                P.append((b.bond, d, "Principal"))
        n += 1
P = pd.DataFrame(P, columns=["bond", "scheduled_date", "flow"]).merge(bonds, on="bond")
P["holdings_month_end"] = P.scheduled_date - pd.offsets.MonthEnd(1)       # last month-end before payment
P = P.merge(h[["month_end", "bond", "total", "crown_direct", "rbnz_secondary", "private", "nonres", "holder_source"]],
            left_on=["holdings_month_end", "bond"], right_on=["month_end", "bond"], how="inner").drop(columns="month_end")
P = P[P.total > 0]
P["pay_date"] = P.scheduled_date.map(next_bd)
P["rate_per_payment"] = np.where(P.flow == "Coupon", P.coupon / np.where(P.type == "IIB", 4, 2), 1.0)
kk = [kt_at(b, d) if t == "IIB" else None for b, d, t in zip(P.bond, P.scheduled_date, P.type)]
P["kt"] = [x.kt if x is not None else (np.nan) for x in kk]
P["kt_source"] = [x.kt_source if x is not None else "" for x in kk]
P["index_ratio"] = np.where(P.type == "IIB", P.kt / 100, 1.0)
for grp in ["private", "crown", "nonres"]:
    base = P.crown_direct + P.rbnz_secondary if grp == "crown" else P[grp]
    P[f"{grp}_face"] = base * P.rate_per_payment
    P[f"{grp}_cash"] = P[f"{grp}_face"] * P.index_ratio
P = P.sort_values(["pay_date", "bond", "flow"]).reset_index(drop=True)

# ---------- Step 5: issuance, buybacks and intra-Crown events ----------
def ev(df, source, category, holder, sign, settle_rule):
    e = df[["bond", "trade_date", "settle_date", "amount"]].copy() if "trade_date" in df else df[["bond", "settle_date", "amount"]].assign(trade_date=pd.NaT)
    e["source"], e["category"], e["holder"], e["settle_rule"] = source, category, holder, settle_rule
    e["face_signed"] = sign * e.amount.abs() if sign else e.amount        # non-market file: negative = issued to Crown (Govt receives cash)
    return e
E = pd.concat([
    ev(tend, "govtbonds-tender-history", "Issuance", "private", -1, f"tender date + {TENDER_LAG} NZ business days"),
    ev(synd, "Government Bonds - Syndication", "Issuance", "private", -1, "settlement date in file"),
    ev(rep, "Repurchase-history: Tender", "Buyback", "private", +1, f"tender date + {TENDER_LAG} NZ business days"),
    ev(lsap, "Repurchase-history: LSAP Repurchase", "LSAP repurchase (from RBNZ)", "crown", +1, "settlement date in file"),
    ev(nmk, "Non market issuance history", "Non-market issuance (to/from Crown entity)", "crown", 0, "settlement date in file"),
])
E["settle_date"] = pd.to_datetime(E.settle_date)
E = E[(E.settle_date >= START) & (E.settle_date <= END)].merge(bonds[["bond", "type"]], on="bond", how="left")
E["type"] = E.type.fillna(E.bond.str[:3].map({"IIB": "IIB"}).fillna("Nominal"))
kk = [kt_at(b, d, True) if t == "IIB" else None for b, d, t in zip(E.bond, E.settle_date, E.type)]
E["kt"] = [x.kt if x is not None else np.nan for x in kk]
E["index_ratio"] = np.where(E.type == "IIB", E.kt.fillna(100) / 100, 1.0)
E["cash_signed"] = E.face_signed * E.index_ratio
E = E[["settle_date", "trade_date", "bond", "type", "category", "holder", "source", "settle_rule",
       "amount", "face_signed", "kt", "index_ratio", "cash_signed"]].sort_values(["settle_date", "bond"]).reset_index(drop=True)

# ---------- Step 6: daily aggregation ----------
days = pd.DataFrame({"date": pd.date_range(START, END)})
days["nz_business_day"] = days.date.isin(bdays)
def daily(df, datecol, mask, col):
    return df[mask].groupby(datecol)[col].sum()
cols = {}
for t, pre in [("Nominal", "nom"), ("IIB", "iib")]:
    pt, et = P.type == t, E.type == t
    cols[f"{pre}_coupon"] = daily(P, "pay_date", pt & (P.flow == "Coupon"), "private_cash")
    cols[f"{pre}_principal"] = daily(P, "pay_date", pt & (P.flow == "Principal"), "private_cash")
    cols[f"{pre}_issuance"] = daily(E, "settle_date", et & (E.category == "Issuance"), "cash_signed")
    cols[f"{pre}_buyback"] = daily(E, "settle_date", et & (E.category == "Buyback"), "cash_signed")
D = days.set_index("date")
order = ["nom_coupon", "nom_principal", "nom_issuance", "nom_buyback",
         "iib_coupon", "iib_principal", "iib_issuance", "iib_buyback"]
for c in order:
    D[c] = cols[c].reindex(D.index).fillna(0.0)
D["net_flow_private"] = D[order].sum(axis=1)
# memo: IIB at face value (before indexation)
D["iib_coupon_face"] = daily(P, "pay_date", (P.type == "IIB") & (P.flow == "Coupon"), "private_face").reindex(D.index).fillna(0.0)
D["iib_principal_face"] = daily(P, "pay_date", (P.type == "IIB") & (P.flow == "Principal"), "private_face").reindex(D.index).fillna(0.0)
D["iib_issuance_face"] = daily(E, "settle_date", (E.type == "IIB") & (E.category == "Issuance"), "face_signed").reindex(D.index).fillna(0.0)
D["iib_buyback_face"] = daily(E, "settle_date", (E.type == "IIB") & (E.category == "Buyback"), "face_signed").reindex(D.index).fillna(0.0)
# memo: non-resident share of coupon+principal (only where RBNZ D31 exists, Jul-2015 on)
nr = P[P.nonres.notna()].groupby("pay_date").nonres_cash.sum()
D["nonres_payments"] = nr.reindex(D.index)
D.loc[D.index >= pd.Timestamp("2015-08-01"), "nonres_payments"] = D.loc[D.index >= pd.Timestamp("2015-08-01"), "nonres_payments"].fillna(0.0)
# memo: intra-Crown flows (excluded from the target)
D["crown_payments"] = P.groupby("pay_date").crown_cash.sum().reindex(D.index).fillna(0.0)
D["crown_nonmarket_issuance"] = daily(E, "settle_date", E.category.str.startswith("Non-market"), "cash_signed").reindex(D.index).fillna(0.0)
D["crown_lsap_repurchase"] = daily(E, "settle_date", E.category.str.startswith("LSAP"), "cash_signed").reindex(D.index).fillna(0.0)
D = D.round(4).reset_index()

# ---------- holdings sheet ----------
H = h[["month_end", "bond", "type", "coupon", "maturity", "total", "rbnz", "eqc", "sresl", "crown_direct",
       "market_nzdm", "private_d31", "rbnz_secondary", "private", "nonres", "holder_source"]].sort_values(["month_end", "bond"])

# save intermediate for writer
pd.to_pickle(dict(D=D, P=P, E=E, H=H, bonds=bonds, kt=kt, prelaunch=prelaunch, hol=hol, bdays=bdays,
                  TENDER_LAG=TENDER_LAG, START=START, END=END), OUT)
print("days", len(D), "payments", len(P), "events", len(E))
print(D[order + ["net_flow_private"]].sum().round(0))
