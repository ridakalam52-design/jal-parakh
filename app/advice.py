"""Action knowledge base: what actually fixes each problem, health warnings, and the complaint draft.

This is the deterministic ground truth the Gemini action agent is grounded on. It is also the complete
fallback: with no API key (or if the model fails or says something unsafe) users get exactly this text.

Key honesty rules (repeated in the UI and the model prompt):
  * Boiling kills germs. It does NOT remove fluoride, arsenic, nitrate, lead or iron; boiling
    concentrates them slightly as water evaporates.
  * RO (reverse osmosis) removes fluoride, arsenic, nitrate, lead and salts, but wastes water and needs
    regular service. It is not needed for hard-but-safe water.
  * Activated alumina is a low-cost proven filter for fluoride (and arsenic); the medium needs regeneration.
  * Community water purification plants (CWPP) under Jal Jeevan Mission give treated water in
    fluoride/arsenic villages - ask the Gram Panchayat / PHED.
  * Chlorine tablets / bleaching powder kill germs only.
Sources for the treatment facts: WHO GDWQ 4th ed.; BIS IS 10500:2012; Ministry of Jal Shakti guidance on
community water purification plants (PIB PRID=1809264).
"""
from __future__ import annotations

import re

from .standards import LIMITS

FIXES: dict[str, dict] = {
    "fluoride": {
        "en": ["Stop drinking and cooking with this water; use a safe source for children first.",
               "Works: RO filter, activated alumina filter, or a Jal Jeevan Mission community plant.",
               "Boiling does NOT remove fluoride.",
               "Eat calcium-rich food (milk, curd, green leaves) - it lowers fluoride harm."],
        "hi": ["इस पानी को पीना और खाना पकाना बंद करें; बच्चों को पहले सुरक्षित पानी दें।",
               "असरदार: RO फ़िल्टर, एक्टिवेटेड एलुमिना फ़िल्टर, या जल जीवन मिशन का सामुदायिक प्लांट।",
               "उबालने से फ्लोराइड नहीं निकलता।",
               "दूध, दही, हरी सब्ज़ियाँ खाएँ - कैल्शियम फ्लोराइड का असर कम करता है।"],
        "cheapest_en": "Ask the Gram Panchayat or PHED for the nearest community water plant; at home, an activated alumina filter is cheaper than RO.",
        "cheapest_hi": "ग्राम पंचायत या PHED से नज़दीकी सामुदायिक जल संयंत्र पूछें; घर पर एक्टिवेटेड एलुमिना फ़िल्टर RO से सस्ता है।",
        "health_en": "Long use causes yellow-brown stained teeth, joint pain and stiff bones (fluorosis).",
        "health_hi": "लंबे समय तक पीने से दाँतों पर पीले-भूरे दाग, जोड़ों में दर्द और हड्डियाँ अकड़ना (फ्लोरोसिस)।",
        "doctor_en": "See a doctor if children have stained teeth or anyone has joint pain or stiffness.",
        "doctor_hi": "बच्चों के दाँतों पर दाग हों या किसी को जोड़ों में दर्द/अकड़न हो तो डॉक्टर को दिखाएँ।",
    },
    "arsenic": {
        "en": ["Do not drink or cook with this water. Do not use it for babies' food.",
               "Works: RO, arsenic-removal (iron-based or activated alumina) filters, or a community plant.",
               "Boiling does NOT remove arsenic.",
               "Get a lab test at the district water lab to confirm - strips are rough for arsenic."],
        "hi": ["इस पानी को पीने या खाना पकाने में इस्तेमाल न करें, बच्चों के खाने में भी नहीं।",
               "असरदार: RO, आर्सेनिक हटाने वाले फ़िल्टर, या सामुदायिक प्लांट।",
               "उबालने से आर्सेनिक नहीं निकलता।",
               "ज़िला जल प्रयोगशाला में जाँच कराएँ - स्ट्रिप आर्सेनिक के लिए मोटा अंदाज़ा ही देती है।"],
        "cheapest_en": "Switch to a tested safe source (community plant or a tested deep tube well) while you get a lab test.",
        "cheapest_hi": "लैब जाँच होने तक किसी जाँचे हुए सुरक्षित स्रोत (सामुदायिक प्लांट या जाँचा हुआ गहरा नलकूप) का पानी लें।",
        "health_en": "Years of exposure cause dark spots and hard skin on palms and soles, and cancers.",
        "health_hi": "सालों तक पीने से हथेलियों-तलवों पर काले धब्बे, सख्त त्वचा और कैंसर हो सकता है।",
        "doctor_en": "See a doctor if you notice dark spots or hard patches on palms or soles.",
        "doctor_hi": "हथेलियों या तलवों पर काले धब्बे या सख्त चकत्ते दिखें तो डॉक्टर को दिखाएँ।",
    },
    "nitrate": {
        "en": ["Never use this water for babies' milk or food - use bottled or tested safe water.",
               "Works: RO or ion-exchange filters.",
               "Boiling does NOT remove nitrate; it makes it slightly stronger.",
               "Keep latrines, cattle sheds and fertiliser away from the well; check the well cover."],
        "hi": ["इस पानी से शिशु का दूध या खाना कभी न बनाएँ - बोतलबंद या जाँचा हुआ पानी लें।",
               "असरदार: RO या आयन-एक्सचेंज फ़िल्टर।",
               "उबालने से नाइट्रेट नहीं निकलता, बल्कि थोड़ा बढ़ जाता है।",
               "शौचालय, पशुशाला और खाद को कुएँ से दूर रखें; कुएँ का ढक्कन देखें।"],
        "cheapest_en": "Use a different tested source for infants and pregnant women right away; RO for the household if it stays high.",
        "cheapest_hi": "शिशुओं और गर्भवती महिलाओं के लिए तुरंत दूसरा जाँचा हुआ स्रोत लें; लगातार ज़्यादा रहे तो घर के लिए RO।",
        "health_en": "Dangerous for babies under 6 months: it stops blood carrying oxygen (blue baby syndrome).",
        "health_hi": "6 महीने से छोटे बच्चों के लिए खतरनाक: खून में ऑक्सीजन कम हो जाती है (ब्लू बेबी)।",
        "doctor_en": "Go to a doctor IMMEDIATELY if a baby's lips, skin or nails look bluish, or the baby is unusually sleepy.",
        "doctor_hi": "अगर शिशु के होंठ, त्वचा या नाखून नीले दिखें या बच्चा बहुत सुस्त हो तो तुरंत डॉक्टर के पास जाएँ।",
    },
    "nitrite": {
        "en": ["Do not give to babies. Nitrite means fresh sewage or fertiliser is getting in.",
               "Works: RO; fix the source (sealed well, distance from latrines).",
               "Boiling does NOT remove nitrite."],
        "hi": ["शिशुओं को न दें। नाइट्राइट का मतलब है ताज़ा गंदगी या खाद पानी में मिल रही है।",
               "असरदार: RO; स्रोत ठीक करें (कुआँ ढकें, शौचालय से दूरी)।",
               "उबालने से नाइट्राइट नहीं निकलता।"],
        "cheapest_en": "Use another source and report it so the supply can be checked for sewage.",
        "cheapest_hi": "दूसरा स्रोत इस्तेमाल करें और शिकायत करें ताकि सप्लाई में गंदगी की जाँच हो।",
        "health_en": "Like nitrate, harmful for infants (blue baby syndrome).",
        "health_hi": "नाइट्रेट की तरह शिशुओं के लिए हानिकारक (ब्लू बेबी)।",
        "doctor_en": "Go to a doctor immediately if a baby looks bluish or very sleepy.",
        "doctor_hi": "शिशु नीला या बहुत सुस्त दिखे तो तुरंत डॉक्टर के पास जाएँ।",
    },
    "lead": {
        "en": ["Do not drink or cook with this water, especially children and pregnant women.",
               "Works: RO or a certified lead-removal filter; check old pipes and fittings.",
               "Boiling does NOT remove lead.",
               "Let the tap run for a minute before use if pipes are old; confirm with a lab test."],
        "hi": ["इस पानी को न पिएँ, न खाना पकाएँ, खासकर बच्चे और गर्भवती महिलाएँ।",
               "असरदार: RO या लेड हटाने वाला प्रमाणित फ़िल्टर; पुराने पाइप देखें।",
               "उबालने से लेड नहीं निकलता।",
               "पुराने पाइप हों तो इस्तेमाल से पहले नल एक मिनट चलाएँ; लैब जाँच कराएँ।"],
        "cheapest_en": "Use another source for drinking and cooking now; get a lab test and check old pipes.",
        "cheapest_hi": "अभी पीने-पकाने के लिए दूसरा स्रोत लें; लैब जाँच कराएँ और पुराने पाइप देखें।",
        "health_en": "No safe level. Harms children's brain development and causes anaemia.",
        "health_hi": "कोई सुरक्षित मात्रा नहीं। बच्चों के दिमागी विकास को नुकसान और खून की कमी।",
        "doctor_en": "Ask a doctor about a blood lead test for young children and pregnant women.",
        "doctor_hi": "छोटे बच्चों और गर्भवती महिलाओं के खून में लेड की जाँच के लिए डॉक्टर से पूछें।",
    },
    "copper": {
        "en": ["Use another source for drinking until it is checked.", "Works: RO.",
               "Boiling does NOT remove copper."],
        "hi": ["जाँच होने तक पीने के लिए दूसरा स्रोत लें।", "असरदार: RO।", "उबालने से ताँबा नहीं निकलता।"],
        "cheapest_en": "Check for corroding copper pipes or tanks; use another source meanwhile.",
        "cheapest_hi": "ताँबे के पाइप/टंकी में जंग देखें; तब तक दूसरा स्रोत लें।",
        "health_en": "Causes stomach pain, nausea and vomiting.", "health_hi": "पेट दर्द, जी मिचलाना और उल्टी।",
        "doctor_en": "See a doctor if vomiting or stomach pain continues.",
        "doctor_hi": "उल्टी या पेट दर्द बना रहे तो डॉक्टर को दिखाएँ।",
    },
    "iron": {
        "en": ["Let water stand in a covered vessel overnight and pour off the clear top, or use a sand/iron-removal filter.",
               "RO is not needed just for iron.", "Boiling does not remove iron."],
        "hi": ["पानी को रात भर ढककर रखें और ऊपर का साफ़ पानी निकालें, या रेत/आयरन हटाने वाला फ़िल्टर लगाएँ।",
               "सिर्फ़ आयरन के लिए RO ज़रूरी नहीं।", "उबालने से आयरन नहीं निकलता।"],
        "cheapest_en": "Settle overnight and decant, or a simple sand-gravel iron-removal filter.",
        "cheapest_hi": "रात भर रखकर ऊपर का पानी निकालें, या साधारण रेत-बजरी फ़िल्टर।",
        "health_en": "Mostly taste, colour and stains; high iron can also hide germs.",
        "health_hi": "मुख्यतः स्वाद, रंग और दाग; ज़्यादा आयरन में कीटाणु भी पनप सकते हैं।",
        "doctor_en": "", "doctor_hi": "",
    },
    "free_chlorine": {
        "en": ["Too much chlorine: fill water in an open vessel for 1-2 hours before drinking.",
               "Tell the water supplier the dose is too high."],
        "hi": ["क्लोरीन ज़्यादा: पीने से पहले पानी को 1-2 घंटे खुले बर्तन में रखें।", "सप्लाई विभाग को बताएँ कि मात्रा ज़्यादा है।"],
        "cheapest_en": "Let it stand open for an hour or two.", "cheapest_hi": "एक-दो घंटे खुला रखें।",
        "health_en": "Strong taste; very high levels irritate the stomach.", "health_hi": "तेज़ स्वाद; बहुत ज़्यादा हो तो पेट में जलन।",
        "doctor_en": "", "doctor_hi": "",
    },
    "ph": {
        "en": ["pH outside 6.5-8.5 often means another problem - test again and get a lab test.",
               "Very low pH can dissolve metals from pipes."],
        "hi": ["pH 6.5-8.5 से बाहर हो तो अक्सर कोई और गड़बड़ी होती है - फिर जाँचें और लैब टेस्ट कराएँ।",
               "बहुत कम pH पाइप से धातु घोल सकता है।"],
        "cheapest_en": "Retest and get a lab test from the district water lab.",
        "cheapest_hi": "दोबारा जाँचें और ज़िला जल प्रयोगशाला से जाँच कराएँ।",
        "health_en": "Not directly harmful at mild levels.", "health_hi": "हल्का अंतर सीधे नुकसानदेह नहीं।",
        "doctor_en": "", "doctor_hi": "",
    },
}
for _k in ("total_hardness", "total_alkalinity", "tds", "chloride", "sulphate", "manganese"):
    FIXES[_k] = {
        "en": ["This is mainly a taste and scaling problem, not an immediate health risk.",
               "If the taste is bad or the level is very high, RO or a community plant helps. Boiling does not fix it."],
        "hi": ["यह मुख्यतः स्वाद और परत जमने की समस्या है, तुरंत स्वास्थ्य खतरा नहीं।",
               "स्वाद बहुत खराब हो या मात्रा बहुत ज़्यादा हो तो RO या सामुदायिक प्लांट मदद करता है। उबालने से ठीक नहीं होता।"],
        "cheapest_en": "No urgent action; use a community plant if the taste is bad.",
        "cheapest_hi": "तुरंत कुछ ज़रूरी नहीं; स्वाद खराब हो तो सामुदायिक प्लांट।",
        "health_en": "", "health_hi": "", "doctor_en": "", "doctor_hi": "",
    }

GERMS_EN = ("A strip cannot see germs. If the water comes from a well, handpump, tank or a broken pipe, boil it "
            "(rolling boil for 1 minute) or use chlorine tablets. This kills germs but does not remove chemicals.")
GERMS_HI = ("स्ट्रिप कीटाणु नहीं देख सकती। अगर पानी कुएँ, हैंडपंप, टंकी या टूटे पाइप से है तो उबालें (1 मिनट तेज़ उबाल) "
            "या क्लोरीन की गोली डालें। इससे कीटाणु मरते हैं, रसायन नहीं निकलते।")
DOCTOR_GENERAL_EN = "See a doctor for diarrhoea with blood, signs of dehydration, or fever after drinking the water."
DOCTOR_GENERAL_HI = "पानी पीने के बाद खून वाले दस्त, पानी की कमी के लक्षण या बुखार हो तो डॉक्टर को दिखाएँ।"

GRIEVANCE = {
    "cpgrams": "https://pgportal.gov.in/",
    "ddws": "https://jalshakti-ddws.gov.in/connect/grievance-redressal",
    "jjm_citizen": "https://ejalshakti.gov.in/jjmreport/JJMIndia.aspx",
    "up_jal_samadhan": "https://jalsamadhan.in/ (UP toll-free 1800 121 2164)",
    "mh_jal_samadhan": "https://mahajalsamadhan.in/",
}

VERDICT_TEXT = {
    "safe": ("Safe to drink on the tested parameters.", "जाँचे गए मानकों पर पानी पीने लायक है।"),
    "caution": ("Use with caution.", "सावधानी से इस्तेमाल करें।"),
    "unsafe": ("Unsafe to drink.", "यह पानी पीने लायक नहीं है।"),
    "retake": ("Not sure yet - please retake the photo.", "अभी पक्का नहीं - कृपया फिर से फोटो लें।"),
}
RETAKE_TIPS_EN = {
    "blurry": "The photo is blurry. Hold the phone steady, 20-30 cm away, and tap to focus.",
    "no_chart": "The colour chart is not in the photo. Put the strip right next to the chart on the bottle.",
    "no_strip": "No test strip found. Dip the strip, wait the time printed on the pack, then photograph it on the chart.",
    "not_a_strip": "This does not look like a water test strip.",
    "glare": "There is glare. Move away from direct light or tilt the phone.",
    "too_dark": "The photo is too dark. Use daylight near a window, no flash.",
    "some_pads_uncertain": "Some pads could not be read with confidence.",
    "low_overall_confidence": "The reader was not confident overall.",
    "too_few_pads": "Too few pads could be read.",
    "bad_photo": "The photo could not be used.",
}
RETAKE_TIPS_HI = {
    "blurry": "फोटो धुंधली है। फोन स्थिर रखें, 20-30 सेमी दूर से, और फोकस के लिए टैप करें।",
    "no_chart": "रंग चार्ट फोटो में नहीं है। स्ट्रिप को बोतल पर बने चार्ट के ठीक बगल में रखें।",
    "no_strip": "टेस्ट स्ट्रिप नहीं मिली। स्ट्रिप डुबोएँ, पैक पर लिखा समय रुकें, फिर चार्ट के साथ फोटो लें।",
    "not_a_strip": "यह पानी की टेस्ट स्ट्रिप नहीं लगती।",
    "glare": "चमक आ रही है। सीधी रोशनी से हटें या फोन थोड़ा तिरछा करें।",
    "too_dark": "फोटो बहुत अंधेरी है। खिड़की के पास दिन की रोशनी में, बिना फ्लैश के लें।",
    "some_pads_uncertain": "कुछ पैड भरोसे से नहीं पढ़े जा सके।",
    "low_overall_confidence": "पढ़ने में कुल भरोसा कम था।",
    "too_few_pads": "बहुत कम पैड पढ़े जा सके।",
    "bad_photo": "फोटो इस्तेमाल नहीं हो सकी।",
}


def template_advice(evaluation: dict, risk: dict | None = None) -> dict:
    """Deterministic, bilingual, voice-friendly advice for a rules-engine result."""
    v = evaluation["verdict"]
    by = {r["param"]: r for r in evaluation["results"]}
    bad = evaluation["unsafe_params"] + evaluation["caution_params"]
    head_en, head_hi = VERDICT_TEXT[v]
    steps_en: list[str] = []
    steps_hi: list[str] = []
    health_en: list[str] = []
    health_hi: list[str] = []
    doctor_en: list[str] = []
    doctor_hi: list[str] = []
    cheapest_en = cheapest_hi = ""
    if v == "retake":
        for reason in evaluation.get("retake_reasons", []):
            steps_en.append(RETAKE_TIPS_EN.get(reason, RETAKE_TIPS_EN["bad_photo"]))
            steps_hi.append(RETAKE_TIPS_HI.get(reason, RETAKE_TIPS_HI["bad_photo"]))
        steps_en.append("Until then, treat the water as unsafe: use a known safe source, and boil it to kill germs.")
        steps_hi.append("तब तक पानी को असुरक्षित मानें: जाना-पहचाना सुरक्षित स्रोत लें और कीटाणुओं के लिए उबालें।")
    for p in bad:
        fx = FIXES.get(p)
        if not fx:
            continue
        for s in fx["en"]:
            if s not in steps_en:
                steps_en.append(s)
        for s in fx["hi"]:
            if s not in steps_hi:
                steps_hi.append(s)
        if not cheapest_en:
            cheapest_en, cheapest_hi = fx["cheapest_en"], fx["cheapest_hi"]
        if fx["health_en"]:
            health_en.append(f"{by[p]['name_en']}: {fx['health_en']}")
            health_hi.append(f"{by[p]['name_hi']}: {fx['health_hi']}")
        if fx["doctor_en"]:
            doctor_en.append(fx["doctor_en"])
            doctor_hi.append(fx["doctor_hi"])
    if by.get("free_chlorine", {}).get("status") == "low":
        steps_en.append("No chlorine left in the water: boil it or add a chlorine tablet before drinking.")
        steps_hi.append("पानी में क्लोरीन नहीं बची: पीने से पहले उबालें या क्लोरीन की गोली डालें।")
    if v == "safe":
        steps_en.append("Keep stored water covered and use a clean ladle. Test again every 3-6 months and after floods.")
        steps_hi.append("रखे पानी को ढककर रखें और साफ़ बर्तन से निकालें। हर 3-6 महीने और बाढ़ के बाद फिर जाँचें।")
    gaps = evaluation.get("untested_district_risks") or []
    if gaps:
        names_en = ", ".join(LIMITS[g].name_en.lower() for g in gaps if g in LIMITS)
        names_hi = ", ".join(LIMITS[g].name_hi for g in gaps if g in LIMITS)
        steps_en.append(f"Your district has official reports of {names_en}, which this test did not measure. "
                        f"Get it checked at the district water testing lab.")
        steps_hi.append(f"आपके ज़िले में {names_hi} की सरकारी रिपोर्ट है, जो इस जाँच में नहीं मापा गया। "
                        f"इसकी जाँच ज़िला जल प्रयोगशाला में कराएँ।")
    doctor_en.append(DOCTOR_GENERAL_EN)
    doctor_hi.append(DOCTOR_GENERAL_HI)

    names_en = ", ".join(by[p]["name_en"] for p in evaluation["unsafe_params"]) or ""
    names_hi = ", ".join(by[p]["name_hi"] for p in evaluation["unsafe_params"]) or ""
    if v == "unsafe":
        summary_en = f"{head_en} {names_en} is too high. Boiling will not fix this. {cheapest_en}"
        summary_hi = f"{head_hi} {names_hi} बहुत ज़्यादा है। उबालने से यह ठीक नहीं होगा। {cheapest_hi}"
    elif v == "caution":
        cn_en = ", ".join(by[p]["name_en"] for p in evaluation["caution_params"])
        cn_hi = ", ".join(by[p]["name_hi"] for p in evaluation["caution_params"])
        summary_en = f"{head_en} {cn_en} is above the ideal level. {cheapest_en}"
        summary_hi = f"{head_hi} {cn_hi} आदर्श स्तर से ज़्यादा है। {cheapest_hi}"
    elif v == "retake":
        summary_en = f"{head_en} {steps_en[0] if steps_en else ''}"
        summary_hi = f"{head_hi} {steps_hi[0] if steps_hi else ''}"
    else:
        summary_en = f"{head_en} The strip cannot check germs, so boil or chlorinate if the source is open."
        summary_hi = f"{head_hi} स्ट्रिप कीटाणु नहीं जाँचती, इसलिए खुला स्रोत हो तो उबालें या क्लोरीन डालें।"
    return {
        "summary_en": re.sub(r"\s+", " ", summary_en).strip(),
        "summary_hi": re.sub(r"\s+", " ", summary_hi).strip(),
        "steps_en": steps_en[:8], "steps_hi": steps_hi[:8],
        "health_en": health_en, "health_hi": health_hi,
        "doctor_en": doctor_en, "doctor_hi": doctor_hi,
        "germs_en": GERMS_EN, "germs_hi": GERMS_HI,
        "agent": "rules",
    }


def complaint_draft(evaluation: dict, place: dict, lang: str = "en", date_str: str = "") -> str:
    """A ready-to-copy complaint to the district PHED / Jal Jeevan Mission. Never sent by the app."""
    by = {r["param"]: r for r in evaluation["results"]}
    bad = evaluation["unsafe_params"] + evaluation["caution_params"]
    district = place.get("district") or "[district]"
    state = place.get("state") or "[state]"
    if lang == "hi":
        lines = [f"• {by[p]['name_hi']}: {by[p]['value']:g} {by[p]['unit']} (BIS सीमा {by[p]['limit']} {by[p]['unit']})" for p in bad]
        body = "\n".join(lines) or "• जाँच में पानी की गुणवत्ता पर संदेह है।"
        return (
            f"सेवा में,\nअधिशासी अभियंता, लोक स्वास्थ्य अभियांत्रिकी विभाग (PHED) / जल जीवन मिशन,\nज़िला {district}, {state}\n\n"
            f"विषय: पेयजल की गुणवत्ता खराब होने की शिकायत एवं जाँच का अनुरोध\n\n"
            f"महोदय/महोदया,\n"
            f"मैं गाँव/मोहल्ला [नाम], ब्लॉक [नाम], ज़िला {district} का निवासी/निवासिनी हूँ। "
            f"दिनांक {date_str or '[तारीख]'} को हमारे पेयजल स्रोत [हैंडपंप/नल/कुआँ] की घरेलू टेस्ट-स्ट्रिप से जाँच में ये मान BIS IS 10500:2012 की सीमा से अधिक मिले:\n"
            f"{body}\n\n"
            f"यह घरेलू स्ट्रिप जाँच है, प्रयोगशाला जाँच नहीं। कृपया:\n"
            f"1. ज़िला जल परीक्षण प्रयोगशाला से इस स्रोत के पानी की जाँच कराएँ।\n"
            f"2. जाँच में पुष्टि होने पर सुरक्षित पेयजल (सामुदायिक जल शोधन संयंत्र/वैकल्पिक स्रोत) की व्यवस्था करें।\n"
            f"3. की गई कार्यवाही की सूचना दें।\n\n"
            f"धन्यवाद।\nनाम: [आपका नाम]\nमोबाइल: [नंबर]\nपता: [पता]\n\n"
            f"(यह शिकायत CPGRAMS https://pgportal.gov.in/ पर या अपने राज्य की जल शिकायत हेल्पलाइन पर भी दर्ज की जा सकती है।)"
        )
    lines = [f"- {by[p]['name_en']}: {by[p]['value']:g} {by[p]['unit']} (BIS limit {by[p]['limit']} {by[p]['unit']})" for p in bad]
    body = "\n".join(lines) or "- The test raised doubts about the water quality."
    return (
        f"To,\nThe Executive Engineer, Public Health Engineering Department (PHED) / Jal Jeevan Mission,\n"
        f"District {district}, {state}\n\n"
        f"Subject: Complaint about unsafe drinking water and request for testing\n\n"
        f"Sir/Madam,\n"
        f"I am a resident of village/ward [name], block [name], district {district}. On {date_str or '[date]'}, a home "
        f"test strip on our drinking water source [handpump/tap/well] showed these values above BIS IS 10500:2012 limits:\n"
        f"{body}\n\n"
        f"This was a home strip test, not a laboratory test. I request you to:\n"
        f"1. Test water from this source at the district water testing laboratory.\n"
        f"2. If confirmed, arrange safe drinking water (community water purification plant / alternate source).\n"
        f"3. Inform me of the action taken.\n\n"
        f"Thank you.\nName: [your name]\nMobile: [number]\nAddress: [address]\n\n"
        f"(You can also file this on CPGRAMS https://pgportal.gov.in/ or your state's water grievance helpline.)"
    )


_BOIL = re.compile(r"boil|उबाल", re.I)
_CHEM = re.compile(r"fluorid|arsenic|nitrat|nitrit|lead|फ्लोराइड|आर्सेनिक|नाइट्रेट|नाइट्राइट|लेड", re.I)
_NEG = re.compile(r"\bnot\b|n't|\bno\b|नहीं|न\s|ना\s", re.I)


def unsafe_boiling_claim(text: str) -> bool:
    """True if a sentence mentions boiling together with a chemical but without a negation."""
    for sent in re.split(r"[.!?।\n]", text or ""):
        if _BOIL.search(sent) and _CHEM.search(sent) and not _NEG.search(sent):
            return True
    return False
