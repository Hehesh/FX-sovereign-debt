# FX Sovereign Debt

This repository contains work relevant to ECON 181 Fintech Practicum.


To run the regression script, the following files need to be present in the `nz_bond_flows/regression` directory:

* Controls - Regression Control Panel.csv
* FX.csv
* nz_daily_flows.csv
* US_Share_of_New_Zealand_Debt.xlsx - Regression Series.csv

They can be found in the regression folder in shared Google Drive and must be placed manually.

If it's your first time running python, then you'll need to set things up.
You can have AI guide you through your desired setup.
The packages needed for this project are:
* numpy 
* pandas 
* scipy 
* statsmodels 
* matplotlib

You may also see a prompt requiring you to install `pdflatex`. This system package renders the LaTeX output from the script.


Now that you're done with setup, run the script.

```bash
python nz_bond_flows/code/run_regressions.py
```
