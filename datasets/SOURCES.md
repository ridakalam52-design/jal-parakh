# Bundled data and where it comes from

All files are rebuilt by `python scripts/build_dataset.py`. The script holds the official annexure text verbatim (typos included) and every cleaning step, so the CSVs can be audited line by line.

| File | What it is | Source | Licence / status |
|---|---|---|---|
| `district_risks.csv` | 442 districts with fluoride > 1.5 mg/L (370) and/or arsenic > 0.01 mg/L (152) found in **parts** of their groundwater | Central Ground Water Board data tabled in Lok Sabha, Ministry of Jal Shakti. PIB, 24 Mar 2022, *Contamination of Ground Water*, Annexure-I. <https://www.pib.gov.in/PressReleasePage.aspx?PRID=1809264> | Government of India public information |
| `state_risks.csv` | Number of partly affected districts per state for salinity (EC > 3000 µS/cm), nitrate (> 45 mg/L) and iron (> 1 mg/L) | CGWB data tabled in Rajya Sabha. PIB, 29 Nov 2021, *Contamination of Groundwater*, Annexure-I. <https://www.pib.gov.in/PressReleasePage.aspx?PRID=1776171> | Government of India public information |
| `district_aliases.csv` | Old / alternate district names (Allahabad → Prayagraj, Gurgaon → Gurugram, …) used only for lookup | Hand-written in `scripts/build_dataset.py` | MIT (this repo) |
| `district_centroids.csv` | Map coordinates for districts (map only, never used for a verdict) | Polygon centroids computed from the geohacker/india district GeoJSON (<https://github.com/geohacker/india>, MIT). Gaps filled from Goyal, Bhatia & Kumar (2024), Zenodo, `district_centroids_lat_long.csv`, <https://doi.org/10.5281/zenodo.12662782> | MIT / CC BY 4.0 |
| `raw_district_centroids_zenodo.csv` | Unmodified Zenodo file (input to the script) | as above | CC BY 4.0 |

## Cleaning steps (in the script)

1. Split names the PDF table ran together (for example `Chittoor Kadapa`, `Darrang&Baksha`, `Varanasi and Unnao`).
2. Fix spellings and use current names (`Uajjain` → Ujjain, `Jahanabd` → Jehanabad, `Allahabad` → Prayagraj, `Mewat` → Nuh, `Gulburga` → Kalaburagi, …). State-specific fixes where two states share a name (Bijapur, Karnataka → Vijayapura; Bijapur, Chhattisgarh unchanged).
3. One row per (state, district) with `fluoride` and `arsenic` flags.
4. Check: the cleaned file has exactly **370 fluoride** and **152 arsenic** districts, the totals PIB states (also asserted in `tests/test_risk_and_advice.py`).

## Limits of this data

- "Partly affected" means contamination was found at **some** monitoring points in the district, not everywhere. A household source can be safe in a listed district, or unsafe in an unlisted one. The app says this every time it shows a risk.
- The district list reflects district names and boundaries as reported in 2022.
- Newer data: the CGWB *Annual Ground Water Quality Report 2024* (PIB, 10 Mar 2025, <https://www.pib.gov.in/PressReleasePage.aspx?PRID=2109942>) gives state-wise counts for 2023 (nitrate in parts of 443 districts, fluoride 263, arsenic 118, uranium 132). Its district lists are in the CGWB PDF annexures; adding them is on the roadmap.
