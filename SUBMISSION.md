# Submission answers: Code for a Billion · Bharat Agentic-AI Hackathon 2026

Ready-to-paste answers for the official form, one section per field.

---

## Team / Project name

Jal Parakh (Clean Water)

## Team members

Rida Kalam (@ridakalam52-design)

## Problem statement

Millions of Indian households drink groundwater with fluoride, arsenic or nitrate that they cannot see, smell or taste. CGWB data shows fluoride above permissible limits in parts of 370 districts and arsenic in parts of 152 districts, and nearly 1 in 5 groundwater samples over the nitrate limit. Labs are far, slow and unfamiliar, so most families never test, and the usual fix, boiling, removes none of these chemicals. Cheap home test strips exist, but reading tiny colour pads against a chart and knowing what the numbers mean is hard, especially for non-English speakers. Jal Parakh turns a phone photo of a cheap strip into a clear verdict and a fix that works, in Hindi and English.

## What you built

Jal Parakh is a free, open-source, mobile-first web app (Hindi-first, with English) that works as a pipeline of agents:

- **Strip reader (Gemini vision):** reads every pad of a multi-parameter strip against the colour chart in the same photo and returns a value, the two nearest swatches and a confidence for each. Code enforces safety-biased rounding: a pad between two swatches is given the riskier value.
- **Deterministic rules engine:** checks readings against BIS IS 10500:2012 (WHO for nitrite) and gives Safe / Use with caution / Unsafe, with a reason per parameter. The AI cannot change the verdict.
- **Fail-safe retake:** a blurry photo, missing chart or any pad below 0.6 confidence gives "please retake", never "safe". A confident danger reading still shows as unsafe.
- **District risk lookup:** official CGWB data (fluoride/arsenic districts, state nitrate/iron/salinity) and pincode lookup say what else to test for, even without a strip.
- **Advice agent (Gemini text):** grounded on the verdict and a verified treatment knowledge base. It gives the cheapest effective fix, health warnings and when to see a doctor, with on-device text-to-speech. Guards replace any summary that calls unsafe water safe and discard advice claiming boiling removes chemicals.
- **Complaint drafter:** a ready-to-copy Hindi/English complaint to PHED / Jal Jeevan Mission with CPGRAMS links. The app never sends anything.
- **Anonymous impact map:** every real test is logged at district level only (no photo, name, phone, IP or exact location) to a public dashboard with CSV export. Demo tests are excluded.

**How AgentFoundry was used:** on 28 Oct 2026, in the AgentFoundry desktop IDE (v0.1.80), its coding agent SMART-Code built the new `GET /api/strip-chart` endpoint (every strip parameter with its BIS/WHO limits, sources and the demo colour-chart swatches). It read the codebase, planned the change and wrote the endpoint, a shared colour-chart module, a refactor of the demo-strip generator to use it, and the tests. It then applied a second round of review feedback. The final review and two simplifications were done by hand, and the test suite was run in AgentFoundry's terminal (100 passed at the time). Write-up and screenshots: https://github.com/ridakalam52-design/jal-parakh/blob/main/docs/agentfoundry/README.md

## GitHub repository URL

https://github.com/ridakalam52-design/jal-parakh

## Demo URL

https://jal-parakh.onrender.com (demo video: VIDEO_URL_PLACEHOLDER)

## Scale & severity

- About **2 lakh deaths a year** in India due to inadequate access to safe water, and **600 million people** facing high-to-extreme water stress. Source: NITI Aayog, Composite Water Management Index (2018), https://www.niti.gov.in/sites/default/files/2023-03/CompositeWaterManagementIndex-CWMI.pdf
- **Fluoride** above permissible limits in parts of **370 districts across 23 States**; **arsenic** in parts of **152 districts across 21 States**. Source: CGWB data via Ministry of Jal Shakti, PIB 24 Mar 2022, https://www.pib.gov.in/PressReleasePage.aspx?PRID=1809264
- **Nitrate** above the limit in **19.8% of 15,259** CGWB groundwater samples, in parts of **443 districts in 23 States/UTs** (fluoride high in 9.04%, arsenic in 3.1%). Source: CGWB Annual Ground Water Quality Report 2024, PIB 10 Mar 2025, https://www.pib.gov.in/PressReleasePage.aspx?PRID=2109942
- These contaminants cause dental and skeletal fluorosis, arsenic skin lesions and cancers, and "blue baby" syndrome in infants. Boiling, the most common household response, removes none of them.

## Deployment & impact data

- **Live since 27 Oct 2026** at https://jal-parakh.onrender.com on Render's free tier, running Gemini `gemini-3.5-flash`.
- **Public impact dashboard:** https://jal-parakh.onrender.com/impact. It shows **0 real tests so far**, because all testing has used the synthetic demo strips, which are deliberately excluded from public numbers. We have not padded the map with fake data.
- **Live accuracy check (28 Oct 2026, gemini-3.5-flash, synthetic strips):**
  - High nitrate/iron strip (true nitrate 100, nitrite 1, iron 3, hardness 120) → read nitrate 50, nitrite 0.5, iron 1.0, hardness 120 → **UNSAFE (correct)**
  - High fluoride strip (true fluoride 2.0, hardness 250) → read fluoride 4.0, hardness 250 → **UNSAFE (correct)**
  - Safe strip (true fluoride 0.5, hardness 120) → read fluoride 0, hardness 120 → **SAFE (correct)**
  - Verdicts were 3/3 correct, but individual pads can still be off by one swatch.
- **Safety fix found through testing:** with the earlier flash-lite model, the high-nitrate strip was read low enough to be called **safe**. We added safety-biased swatch rounding enforced in code, a stricter reader prompt and a stronger default model. The same strip is now correctly flagged unsafe.
- **No field pilot yet.** Real phone photos of commercial strips are not yet validated.
- **Pilot plan:** partner with an NGO, self-help group or school in Kanpur. We will test real household and handpump water with commercial strips and compare against district-lab results to measure real-world accuracy. Real, anonymous district-level results will be published on the public map. Next come a WhatsApp bot, offline mode, more strip brands, a persistent database and a Hindi native-speaker review.

## Track

Other

## Contact email

ridakalam52@gmail.com
