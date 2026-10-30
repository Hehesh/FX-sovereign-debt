"""Step 1: read each raw NZDM / RBNZ file into a tidy table. No transformations beyond cleaning."""
import os
import re
import pandas as pd
import holidays

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "raw") + "/"   # put the 8 source files in ../raw


def bond_id(typ, mat):
    """One key per bond: GB0427 = nominal maturing Apr-2027, IIB0930 = inflation-indexed Sep-2030 (RBNZ D31 style)."""
    t = str(typ).strip().lower()
    return ("IIB" if t.startswith("inf") or t == "iib" else "GB") + pd.Timestamp(mat).strftime("%m%y")


def pct(x):
    """Coupons are stored both as 0.045 and as the text '4.50%'."""
    if isinstance(x, str):
        return float(x.strip().rstrip("%")) / 100
    return float(x)


def onissue():
    o = pd.read_excel(RAW + "onissue.xlsx", sheet_name="Month_end", header=5).iloc[:, :11]
    o.columns = ["month_end", "first_issued", "prefix", "coupon", "maturity", "type",
                 "total", "rbnz", "eqc", "sresl", "market_nzdm"]
    o = o[o.month_end != "-"].dropna(subset=["total"]).copy()   # drop separator rows and blank rows
    o["month_end"] = pd.to_datetime(o.month_end)
    o["maturity"] = pd.to_datetime(o.maturity)
    o["row"] = range(len(o))
    # Fix 1: Aug-2000, Feb-2001, Nov-2002 blocks repeat the previous month's date. A second row with the
    # same (date, loan prefix) is the next month's snapshot.
    o["rep"] = o.groupby(["month_end", "prefix"]).cumcount()
    o.loc[o.rep == 1, "month_end"] = o.loc[o.rep == 1, "month_end"] + pd.offsets.MonthEnd(1)
    # Fix 2: dates are business month-ends (e.g. 29-Mar-2019) and Aug-2009 / Aug-2010 carry extra mid-month
    # snapshots. Label by calendar month-end and keep the last snapshot in each month.
    o["month_end"] = o.month_end + pd.offsets.MonthEnd(0)
    o = o.sort_values("row").groupby(["month_end", "prefix"], as_index=False).last()
    o["type"] = o.type.str.strip().map(lambda t: "IIB" if t.lower().startswith("inf") else "Nominal")
    o["coupon"] = o.coupon.map(pct)
    for c in ["total", "rbnz", "eqc", "sresl", "market_nzdm"]:
        o[c] = o[c].astype(float)
    o["bond"] = [bond_id(t, m) for t, m in zip(o.type, o.maturity)]
    # Fix: Jul-Aug 2021 rows carry another bond's coupon (column shift in source). Use each bond's most common coupon.
    o["coupon"] = o.groupby("bond").coupon.transform(lambda s: s.round(5).mode().iloc[0])
    # Two tiny 4.55% Sep-2001 loans (XL08, 0008) share a maturity: sum them into one bond.
    o = (o.groupby(["month_end", "bond", "type", "coupon", "maturity"], as_index=False)
           [["total", "rbnz", "eqc", "sresl", "market_nzdm"]].sum())
    o["crown_direct"] = o.rbnz + o.eqc + o.sresl
    return o


def d31():
    d = pd.read_excel(RAW + "hd31.xlsx", sheet_name="Data", header=None)
    names, kinds = d.iloc[0].tolist(), [str(k).strip() for k in d.iloc[1].tolist()]
    rows = d.iloc[5:]
    rows = rows[rows[0].map(lambda x: hasattr(x, "year"))]
    recs = []
    for j in range(1, d.shape[1]):
        m = re.search(r"\((\w+)\)", str(names[j]))
        if not m or kinds[j] not in ("Total in the market", "Non-residents"):
            continue
        for dt, v in zip(rows[0], rows[j]):
            recs.append((pd.Timestamp(dt), m.group(1), kinds[j], v))
    out = (pd.DataFrame(recs, columns=["month_end", "bond", "kind", "v"])
             .pivot_table(index=["month_end", "bond"], columns="kind", values="v").reset_index())
    out.columns = ["month_end", "bond", "nonres_d31", "private_d31"]
    return out.dropna(subset=["private_d31"])


def iib_factors():
    xl = pd.ExcelFile(RAW + "iib.xlsx")
    out = []
    for sh in xl.sheet_names:              # sheet 'Sep-2030 IIB Factors' -> IIB0930
        mat = pd.to_datetime("20-" + sh.split()[0])
        f = pd.read_excel(xl, sheet_name=sh, header=3).iloc[:, :3].dropna()
        f.columns = ["coupon_date", "p", "kt"]
        f["bond"] = "IIB" + mat.strftime("%m%y")
        out.append(f)
    f = pd.concat(out)
    f["coupon_date"] = pd.to_datetime(f.coupon_date)
    f["kt_source"] = "NZDM IIB factors file"
    return f


def tenders():
    n = pd.read_excel(RAW + "tender.xlsx", sheet_name="Nominals", header=4)
    i = pd.read_excel(RAW + "tender.xlsx", sheet_name="IIBs", header=4)
    n = n.assign(type="Nominal")[["Tender Date", "Maturity Date", "type", "Volume Accepted ($m)"]]
    i = i.assign(type="IIB")[["Tender Date", "Maturity Date", "type", "Volume Accepted ($m)"]]
    t = pd.concat([n, i]).dropna()
    t.columns = ["trade_date", "maturity", "type", "amount"]
    t = t[t.trade_date.map(lambda x: hasattr(x, "year"))].copy()   # IIB sheet repeats its header mid-sheet
    t["trade_date"] = pd.to_datetime(t.trade_date)
    t["maturity"] = pd.to_datetime(t.maturity)
    t["amount"] = t.amount.astype(float)
    t = t[t.amount > 0]
    t["bond"] = [bond_id(a, b) for a, b in zip(t.type, t.maturity)]
    return t


def syndications():
    out = []
    for sh in ["Syndication", "Syndicated Tap"]:
        s = pd.read_excel(RAW + "syndication.xlsx", sheet_name=sh, header=5).iloc[:, :6].dropna(subset=["Settlement Date"])
        out.append(s)
    s = pd.concat(out).drop_duplicates()
    s.columns = ["trade_date", "settle_date", "maturity", "coupon", "type", "amount"]
    s["bond"] = [bond_id(a, b) for a, b in zip(s.type, s.maturity)]
    return s


def repurchases():
    r = pd.read_excel(RAW + "repurchase.xlsx", sheet_name="Tender", header=4)
    r = r[["Tender Date", "Maturity Date", "Type", "Volume accepted ($m)"]].dropna()
    r.columns = ["trade_date", "maturity", "type", "amount"]
    r["bond"] = [bond_id(a, b) for a, b in zip(r.type, r.maturity)]
    return r[r.amount > 0]


def lsap_repurchases():
    l = pd.read_excel(RAW + "repurchase.xlsx", sheet_name="LSAP Repurchase", header=7)
    l = l[["Deal Date", "Settlement Date", "Maturity Date", "Type", "Volume accepted ($m)"]].dropna()
    l.columns = ["trade_date", "settle_date", "maturity", "type", "amount"]
    l["bond"] = [bond_id(a, b) for a, b in zip(l.type, l.maturity)]
    return l


def nonmarket():
    n = pd.read_excel(RAW + "nonmarket.xlsx", header=None, skiprows=9).iloc[:, :5]
    n.columns = ["settle_date", "maturity", "instrument", "institution", "amount"]
    n = n[n.settle_date.map(lambda x: hasattr(x, "year"))]
    n = n[n.instrument.str.contains("Bond")].copy()          # T-bills are out of scope
    n["settle_date"] = pd.to_datetime(n.settle_date)
    n["type"] = n.instrument.map(lambda s: "IIB" if s.startswith("Inf") else "Nominal")
    n["bond"] = [bond_id(a, b) for a, b in zip(n.type, n.maturity)]
    n["amount"] = n.amount.astype(float)
    return n


def cpi():
    c = pd.read_csv(RAW + "cpi_oecd_fred.csv", parse_dates=["date"])
    return c


def nz_business_days(start="1995-01-01", end="2027-12-31"):
    """Wellington business days: weekdays that are not NZ national holidays or Wellington Anniversary Day."""
    hol = holidays.NZ(subdiv="WGN", years=range(1995, 2028))
    days = pd.bdate_range(start, end)
    return days[~days.isin(pd.to_datetime(list(hol.keys())))], hol
