# FX Sovereign Debt

Work for ECON 181 Fintech Practicum.

## Layout

```
data/                         Cross-country raw data (IMF SBHI, Arslanalp-Tsuda, issuance/flow indicators)
nz_bond_flows/                NZ government bond flow pipeline + regressions
  raw/                        Source files for the flow builder
  code/                       build.py, load.py, write.py, run_regressions.py, tests
  regression/                 Regression inputs (placed manually, see below)
  output/                     Generated: flows workbook, tables, hypothesis tests, intermediate/
  docs/                       METHODOLOGY.md, method PDF, RUN.txt (build instructions)
  scratch/                    Experimental scripts, not part of the pipeline
reference/
  papers/                     Background literature
  braeuer_hau_replication/    Third-party replication package (read-only reference)
```

## Running the regressions

These files must be present in `nz_bond_flows/regression/` (from the shared Google Drive, placed manually):

* Controls - Regression Control Panel.csv
* FX.csv
* nz_daily_flows.csv
* US_Share_of_New_Zealand_Debt.xlsx - Regression Series.csv

Python packages: numpy, pandas, scipy, statsmodels, matplotlib (plus `openpyxl`, `holidays` for the flow builder).
`pdflatex` is needed to render the LaTeX output.

```bash
python nz_bond_flows/code/run_regressions.py
python -m unittest discover -s nz_bond_flows/code -p 'test_*.py'
```

Building the daily flows workbook is described in `nz_bond_flows/docs/RUN.txt`.
