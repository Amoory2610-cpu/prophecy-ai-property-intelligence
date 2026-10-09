# Sample data

`pp-2024-demo-districts.csv` is an unmodified extract of HM Land Registry Price Paid Data
for 2024, filtered to seven postcode districts (M1, M14, LS6, NG7, L15, CF24, NE6) that the
demo portfolio uses. It is in the official no-header 16-column format and imports with:

    python -m app.cli import-ppd ../data/samples/pp-2024-demo-districts.csv

Contains HM Land Registry data © Crown copyright and database right 2024. This data is
licensed under the Open Government Licence v3.0.
https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads

The sample is real sales data, but it is not complete or current: download the yearly or
monthly files from GOV.UK for full coverage.
