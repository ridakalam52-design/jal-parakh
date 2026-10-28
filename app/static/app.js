/* Jal Parakh front-end — vanilla JS, no build step, Hindi-first. */
(function () {
  'use strict';
  const $ = (s, el) => (el || document).querySelector(s);
  const $$ = (s, el) => Array.from((el || document).querySelectorAll(s));
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const pct = (x) => Math.round((Number(x) || 0) * 100) + '%';

  const I18N = {
    hi: {
      nav_impact: 'असर', nav_about: 'जानकारी', mock_bar: 'डेमो मोड: AI कुंजी नहीं है, इसलिए स्ट्रिप की रीडिंग नकली (mock) है।',
      disclaimer_short: 'यह प्रयोगशाला जाँच नहीं है। गंभीर नतीजे की पुष्टि ज़िला जल प्रयोगशाला से कराएँ।',
      hero_title: 'क्या आपका पानी पीने लायक है?',
      hero_lead: 'टेस्ट-स्ट्रिप की फोटो लें। जल परख उसे पढ़कर BIS मानक से मिलाता है, आपके ज़िले का खतरा बताता है, और सबसे सस्ता असरदार उपाय हिंदी और अंग्रेज़ी में बताता है।',
      place_title: 'पानी कहाँ का है?', state: 'राज्य', district: 'ज़िला', choose_state: 'राज्य चुनें', or_pincode: 'या पिनकोड',
      place_privacy: 'सिर्फ़ ज़िला सहेजा जाता है — नाम, फ़ोन या सही पता कभी नहीं।',
      tab_strip: 'स्ट्रिप फोटो', tab_manual: 'मान भरें', tab_risk: 'ज़िले का खतरा',
      strip_title: 'टेस्ट-स्ट्रिप की फोटो', tip1: 'स्ट्रिप को पानी में डुबोएँ और पैक पर लिखा समय रुकें।',
      tip2: 'स्ट्रिप को बोतल के रंग-चार्ट के ठीक बगल में रखें।', tip3: 'दिन की रोशनी में, बिना फ्लैश, सीधी फोटो लें।',
      take_photo: 'फोटो लें / चुनें', check_water: 'पानी जाँचें', demo_try: 'स्ट्रिप नहीं है? एक नकली (synthetic) डेमो फोटो आज़माएँ:',
      demo_safe: 'साफ़ पानी', demo_fluoride: 'ज़्यादा फ्लोराइड', demo_nitrate: 'नाइट्रेट + आयरन', demo_blurry: 'धुंधली फोटो',
      manual_title: 'स्ट्रिप/किट के मान खुद भरें', manual_help: 'जो पैड आपने पढ़े, सिर्फ़ वही भरें। बाकी खाली छोड़ दें।',
      risk_title: 'मेरे ज़िले में किस चीज़ की जाँच करूँ?', risk_help: 'ऊपर राज्य और ज़िला (या पिनकोड) चुनें। हम CGWB के सरकारी आँकड़ों से बताएँगे।',
      show_risk: 'खतरा देखें', how1_t: 'पढ़ना', how1: 'Gemini विज़न हर पैड का रंग चार्ट से मिलाता है और भरोसा बताता है।',
      how2_t: 'नियम', how2: 'तय नियम (AI नहीं) BIS IS 10500 से तुलना करते हैं। कम भरोसा = दोबारा फोटो।',
      how3_t: 'ज़िला', how3: 'CGWB आँकड़ों से आपके ज़िले के फ्लोराइड/आर्सेनिक खतरे।',
      how4_t: 'उपाय', how4: 'सबसे सस्ता असरदार उपाय, डॉक्टर कब, और शिकायत का मसौदा।',
      reading: 'स्ट्रिप पढ़ी जा रही है…', reading_help: 'फ़्री सर्वर पर स्ट्रिप पढ़ने में एक मिनट तक लग सकता है। यह पेज अपने-आप अपडेट होगा।', new_test: 'नई जाँच',
      advising: 'उपाय तैयार हो रहे हैं…',
      v_safe: 'जाँचे गए मानकों पर सुरक्षित', v_caution: 'सावधानी से इस्तेमाल करें', v_unsafe: 'पीने लायक नहीं', v_retake: 'फिर से फोटो लें',
      v_safe_sub: 'स्ट्रिप कीटाणु नहीं जाँचती।', v_caution_sub: 'कुछ मान आदर्श से ज़्यादा हैं।', v_unsafe_sub: 'एक या ज़्यादा स्वास्थ्य मानक सीमा से ऊपर है।',
      v_retake_sub: 'हम पक्का नहीं हैं, इसलिए पानी को सुरक्षित नहीं कहेंगे।', v_error: 'फोटो नहीं पढ़ी जा सकी',
      v_error_sub: 'कृपया फिर से कोशिश करें, या मान खुद भरें। तब तक पानी को असुरक्षित मानें।',
      listen: '🔊 सुनें', stop: '⏹ रोकें', share: 'व्हाट्सऐप पर भेजें', demo_flag: 'डेमो जाँच — सार्वजनिक आँकड़ों में नहीं गिनी जाती',
      readings: 'हर मानक का नतीजा', confidence: 'भरोसा', what_to_do: 'क्या करें', health: 'सेहत पर असर', doctor: 'डॉक्टर को कब दिखाएँ',
      germs: 'कीटाणु', your_area: 'आपके इलाके का सरकारी डेटा', test_for: 'इनकी जाँच ज़रूर करें:',
      complaint_btn: '📝 शिकायत का मसौदा बनाएँ', complaint_title: 'शिकायत का मसौदा (आप खुद भेजें)',
      complaint_note: 'जल परख कुछ नहीं भेजता। इसे कॉपी करके PHED / जल जीवन मिशन को दें, या CPGRAMS पर दर्ज करें।',
      copy: 'कॉपी करें', copied: 'कॉपी हो गया', where_send: 'कहाँ भेजें', retake_btn: '📸 फिर से फोटो लें',
      status_ok: 'ठीक', status_caution: 'सावधानी', status_unsafe: 'असुरक्षित', status_uncertain: 'पक्का नहीं', status_low: 'कम',
      no_place: 'पहले राज्य और ज़िला चुनें, या पिनकोड डालें।', no_risk_data: 'इस ज़िले के लिए फ्लोराइड/आर्सेनिक की कोई सरकारी रिपोर्ट हमारे डेटा में नहीं है।',
      risk_district: 'ज़िला-स्तर', risk_state: 'राज्य-स्तर', source: 'स्रोत',
      impact_title: 'जनता का पानी-नक्शा', impact_lead: 'हर जाँच ज़िला-स्तर पर, बिना किसी निजी जानकारी के, यहाँ दर्ज होती है।',
      c_tests: 'जाँचें', c_unsafe: 'असुरक्षित मिले', c_rate: 'असुरक्षित दर', c_complaints: 'शिकायत मसौदे', c_districts: 'ज़िले',
      map_title: 'नक्शा', layer_official: 'सरकारी फ्लोराइड/आर्सेनिक ज़िले', include_demo: 'डेमो जाँचें भी दिखाएँ',
      lg_low: 'ज़्यादातर सुरक्षित', lg_mid: 'कुछ असुरक्षित', lg_high: 'ज़्यादातर असुरक्षित', lg_f: 'फ्लोराइड (CGWB)', lg_a: 'आर्सेनिक (CGWB)',
      by_district: 'ज़िलेवार', unsafe: 'असुरक्षित', top_params: 'मुख्य समस्या', no_reports: 'अभी कोई जाँच दर्ज नहीं हुई। पहली जाँच आप करें!',
      unknown_place: '(जगह नहीं बताई)',
      e_photo_missing: 'पहले फोटो लें।', e_photo_too_big: 'फोटो बहुत बड़ी है (8 MB तक)।', e_photo_type: 'यह फोटो फ़ाइल नहीं लगती (JPG/PNG)।',
      e_rate_limited: 'बहुत सारी जाँचें हो गईं, थोड़ी देर बाद कोशिश करें।', e_no_values: 'कम से कम एक मान भरें।',
      e_place_not_found: 'जगह नहीं मिली। राज्य चुनें या सही पिनकोड डालें।', e_generic: 'कुछ गड़बड़ हुई, फिर से कोशिश करें।',
      practice: 'यह अभ्यास जाँच है (सार्वजनिक नक्शे में न गिनें)',
    },
    en: {
      nav_impact: 'Impact', nav_about: 'About', mock_bar: 'Demo mode: no AI key, so strip readings are simulated (mock).',
      disclaimer_short: 'This is not a laboratory test. Confirm serious results at your district water lab.',
      hero_title: 'Is your water safe to drink?',
      hero_lead: 'Photograph a test strip. Jal Parakh reads it, checks it against the BIS standard, tells you your district\'s risks, and gives the cheapest fix that works — in Hindi and English.',
      place_title: 'Where is the water from?', state: 'State', district: 'District', choose_state: 'Choose state', or_pincode: 'or pincode',
      place_privacy: 'Only the district is saved — never your name, phone or exact address.',
      tab_strip: 'Strip photo', tab_manual: 'Enter values', tab_risk: 'District risk',
      strip_title: 'Test-strip photo', tip1: 'Dip the strip and wait the time printed on the pack.',
      tip2: 'Hold the strip right next to the colour chart on the bottle.', tip3: 'Daylight, no flash, photo taken straight on.',
      take_photo: 'Take / choose photo', check_water: 'Check water', demo_try: 'No strip? Try a synthetic demo photo:',
      demo_safe: 'Clean water', demo_fluoride: 'High fluoride', demo_nitrate: 'Nitrate + iron', demo_blurry: 'Blurry photo',
      manual_title: 'Type in your strip / kit values', manual_help: 'Fill only the pads you read. Leave the rest empty.',
      risk_title: 'What should I test for in my district?', risk_help: 'Pick state and district (or pincode) above. We answer from official CGWB data.',
      show_risk: 'Show risks', how1_t: 'Read', how1: 'Gemini vision matches every pad to the chart and says how sure it is.',
      how2_t: 'Rules', how2: 'Fixed rules (not AI) compare with BIS IS 10500. Low confidence = retake.',
      how3_t: 'District', how3: 'Fluoride/arsenic risks for your district from CGWB data.',
      how4_t: 'Act', how4: 'Cheapest effective fix, when to see a doctor, and a complaint draft.',
      reading: 'Reading your strip…', reading_help: 'Reading can take up to a minute on the free server. The page updates itself.', new_test: 'New test',
      advising: 'Preparing advice…',
      v_safe: 'Safe on the tested parameters', v_caution: 'Use with caution', v_unsafe: 'Unsafe to drink', v_retake: 'Please retake the photo',
      v_safe_sub: 'A strip cannot check for germs.', v_caution_sub: 'Some values are above the ideal level.', v_unsafe_sub: 'One or more health parameters are over the limit.',
      v_retake_sub: 'We are not sure, so we will not call this water safe.', v_error: 'Could not read the photo',
      v_error_sub: 'Please try again or enter the values yourself. Treat the water as unsafe until then.',
      listen: '🔊 Listen', stop: '⏹ Stop', share: 'Share on WhatsApp', demo_flag: 'Demo test — not counted in public data',
      readings: 'Result for each parameter', confidence: 'confidence', what_to_do: 'What to do', health: 'Health effects', doctor: 'When to see a doctor',
      germs: 'Germs', your_area: 'Official data for your area', test_for: 'Be sure to test for:',
      complaint_btn: '📝 Draft a complaint', complaint_title: 'Complaint draft (you send it)',
      complaint_note: 'Jal Parakh never sends anything. Copy this and give it to PHED / Jal Jeevan Mission, or file it on CPGRAMS.',
      copy: 'Copy', copied: 'Copied', where_send: 'Where to send', retake_btn: '📸 Retake photo',
      status_ok: 'OK', status_caution: 'Caution', status_unsafe: 'Unsafe', status_uncertain: 'Not sure', status_low: 'Low',
      no_place: 'Pick a state and district first, or enter a pincode.', no_risk_data: 'Our data has no official fluoride/arsenic report for this district.',
      risk_district: 'district level', risk_state: 'state level', source: 'Source',
      impact_title: 'People\'s water map', impact_lead: 'Every test is logged here at district level, with no personal data.',
      c_tests: 'Tests', c_unsafe: 'Unsafe found', c_rate: 'Unsafe rate', c_complaints: 'Complaints drafted', c_districts: 'Districts',
      map_title: 'Map', layer_official: 'Official fluoride/arsenic districts', include_demo: 'Include demo tests',
      lg_low: 'Mostly safe', lg_mid: 'Some unsafe', lg_high: 'Mostly unsafe', lg_f: 'Fluoride (CGWB)', lg_a: 'Arsenic (CGWB)',
      by_district: 'By district', unsafe: 'Unsafe', top_params: 'Main problem', no_reports: 'No tests logged yet. Be the first!',
      unknown_place: '(place not given)',
      e_photo_missing: 'Take a photo first.', e_photo_too_big: 'Photo is too large (max 8 MB).', e_photo_type: 'That does not look like a photo (JPG/PNG).',
      e_rate_limited: 'Too many tests, please try again in a few minutes.', e_no_values: 'Enter at least one value.',
      e_place_not_found: 'Place not found. Choose a state or enter a valid pincode.', e_generic: 'Something went wrong, please try again.',
      practice: 'This is a practice test (do not count it on the public map)',
    },
  };

  let JP_initHome, JP_initTest, JP_initImpact;
  let LANG = localStorage.getItem('jp-lang') || 'hi';
  const t = (k) => (I18N[LANG] && I18N[LANG][k]) || I18N.en[k] || k;
  const L = (obj, base) => (obj ? (obj[base + '_' + LANG] ?? obj[base + '_en']) : '');
  const rerenders = [];

  function applyLang() {
    document.documentElement.lang = LANG;
    document.documentElement.dataset.lang = LANG;
    $$('[data-i18n]').forEach((el) => { el.textContent = t(el.dataset.i18n); });
    rerenders.forEach((fn) => fn());
  }
  function onLang(fn) { rerenders.push(fn); }

  window.toast = function (msg, isErr) {
    const el = $('#toast');
    el.textContent = msg; el.className = 'toast show' + (isErr ? ' err' : '');
    clearTimeout(el._h); el._h = setTimeout(() => (el.className = 'toast'), 4200);
  };
  function busy(btn, on) {
    if (!btn) return;
    if (on) { btn._label = btn.innerHTML; btn.disabled = true; btn.innerHTML = '<span class="spin"></span>'; }
    else { btn.disabled = false; if (btn._label) btn.innerHTML = btn._label; }
  }
  async function api(url, opts = {}) {
    const init = { method: opts.method || 'GET', headers: {} };
    if (opts.form) init.body = opts.form;
    else if (opts.body !== undefined) { init.body = JSON.stringify(opts.body); init.headers['Content-Type'] = 'application/json'; }
    const r = await fetch(url, init);
    let data = null; try { data = await r.json(); } catch (_) { /* empty */ }
    if (!r.ok) {
      const code = (data && (data.error || data.detail)) || 'generic';
      const err = new Error(I18N[LANG]['e_' + code] ? t('e_' + code) : t('e_generic'));
      err.code = code; throw err;
    }
    return data;
  }

  // ---------------------------------------------------------------- speech (free, on-device)
  let speaking = false;
  function speak(text, btn) {
    if (!('speechSynthesis' in window)) { toast('Speech not supported on this phone', true); return; }
    if (speaking) { speechSynthesis.cancel(); speaking = false; if (btn) btn.textContent = t('listen'); return; }
    const u = new SpeechSynthesisUtterance(text);
    u.lang = LANG === 'hi' ? 'hi-IN' : 'en-IN';
    const v = speechSynthesis.getVoices().find((x) => x.lang && x.lang.toLowerCase().startsWith(LANG === 'hi' ? 'hi' : 'en-in'));
    if (v) u.voice = v;
    u.rate = 0.95;
    u.onend = () => { speaking = false; if (btn) btn.textContent = t('listen'); };
    speaking = true; if (btn) btn.textContent = t('stop');
    speechSynthesis.speak(u);
  }

  // ---------------------------------------------------------------- place picker
  const placeKey = 'jp-place';
  function getPlace() {
    return { state: ($('#state') || {}).value || '', district: (($('#district') || {}).value || '').trim(), pincode: (($('#pincode') || {}).value || '').trim() };
  }
  async function initPlace() {
    const sel = $('#state'); if (!sel) return;
    const saved = JSON.parse(localStorage.getItem(placeKey) || '{}');
    try {
      const data = await api('/api/places');
      const fill = () => {
        const cur = sel.value || saved.state || '';
        sel.innerHTML = `<option value="">${esc(t('choose_state'))}</option>` +
          data.states.map((s) => `<option value="${esc(s.en)}">${esc(LANG === 'hi' ? s.hi + ' · ' + s.en : s.en)}</option>`).join('');
        sel.value = cur;
      };
      fill(); onLang(fill);
    } catch (_) { /* offline */ }
    $('#district').value = saved.district || '';
    $('#pincode').value = saved.pincode || '';
    const loadDistricts = async () => {
      const dl = $('#district-list'); dl.innerHTML = '';
      if (!sel.value) return;
      try { const d = await api('/api/places?state=' + encodeURIComponent(sel.value)); dl.innerHTML = d.districts.map((x) => `<option value="${esc(x)}">`).join(''); } catch (_) { /* ignore */ }
    };
    const save = () => localStorage.setItem(placeKey, JSON.stringify(getPlace()));
    sel.addEventListener('change', () => { loadDistricts(); save(); });
    $('#district').addEventListener('change', save);
    $('#pincode').addEventListener('change', save);
    loadDistricts();
  }

  // ---------------------------------------------------------------- home
  function renderRisk(r) {
    const district = r.district || r.state || '';
    const items = (r.risks || []).map((x) => `<li class="${x.level === 'district' ? 'district' : ''}">
        <b>${esc(LANG === 'hi' ? x.hi : x.en)}</b>
        <div class="small muted">${esc(x.level === 'district' ? t('risk_district') : t('risk_state'))} · <a href="${esc(x.source)}" target="_blank" rel="noopener">${esc(t('source'))}: PIB / CGWB</a></div></li>`).join('');
    const tf = (r.test_for || []).map((p) => `<span>${esc(paramName(p))}</span>`).join('');
    return `<div class="card" style="margin:14px 0 0;box-shadow:none">
      <h3>📍 ${esc(district)}${r.state && r.district ? ', ' + esc(r.state) : ''}</h3>
      ${r.known_district ? '' : `<p class="muted small">${esc(t('no_risk_data'))}</p>`}
      <ul class="risk-list">${items}</ul>
      <p><b>${esc(t('test_for'))}</b></p><div class="testfor">${tf}</div>
      <p class="note small">${esc(LANG === 'hi' ? r.note_hi : r.note_en)}</p></div>`;
  }
  let LIMITS = {};
  const paramName = (p) => (LIMITS[p] ? (LANG === 'hi' ? LIMITS[p].name_hi : LIMITS[p].name_en) : p);

  JP_initHome = async function (params) {
    applyLang();
    $('#lang-toggle').addEventListener('click', toggleLang);
    initPlace();
    try { (await api('/api/limits')).limits.forEach((l) => { LIMITS[l.param] = l; }); } catch (_) { /* ignore */ }

    $$('.tab').forEach((b) => b.addEventListener('click', () => {
      $$('.tab').forEach((x) => x.classList.toggle('active', x === b));
      ['strip', 'manual', 'risk'].forEach((n) => { $('#panel-' + n).hidden = n !== b.dataset.tab; });
    }));

    // strip
    let file = null;
    const preview = $('#preview');
    const setFile = (f) => {
      file = f; $('#strip-btn').disabled = !f;
      if (f) { preview.src = URL.createObjectURL(f); preview.hidden = false; $('#shot-cta').hidden = true; }
    };
    $('#photo').addEventListener('change', (e) => setFile(e.target.files[0] || null));
    $$('[data-demo]').forEach((c) => c.addEventListener('click', async () => {
      const r = await fetch(c.dataset.demo); const b = await r.blob();
      setFile(new File([b], c.dataset.demo.split('/').pop(), { type: 'image/png' }));
      $('#strip-btn').scrollIntoView({ behavior: 'smooth', block: 'center' });
    }));
    $('#strip-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!file) { toast(t('e_photo_missing'), true); return; }
      const btn = $('#strip-btn'); busy(btn, true);
      const p = getPlace(); const fd = new FormData();
      fd.append('photo', file); fd.append('state', p.state); fd.append('district', p.district); fd.append('pincode', p.pincode); fd.append('lang', LANG);
      try { const res = await api('/api/tests', { method: 'POST', form: fd }); location.href = res.url; }
      catch (err) { toast(err.message, true); busy(btn, false); }
    });

    // manual
    const form = $('#manual-form');
    const drawManual = () => {
      const keep = {}; $$('input', form).forEach((i) => { keep[i.name] = i.value; });
      form.innerHTML = params.slice(0, 11).map((p) => {
        const l = LIMITS[p] || { name_en: p, name_hi: p, unit: '' };
        return `<label>${esc(LANG === 'hi' ? l.name_hi : l.name_en)} <small>${esc(l.unit || (p === 'ph' ? 'pH' : ''))}</small>
          <input name="${esc(p)}" inputmode="decimal" placeholder="—" value="${esc(keep[p] || '')}"></label>`;
      }).join('');
    };
    drawManual(); onLang(drawManual);
    $('#manual-btn').addEventListener('click', async () => {
      const values = {}; $$('input', form).forEach((i) => { if (i.value.trim() !== '') values[i.name] = i.value.trim(); });
      if (!Object.keys(values).length) { toast(t('e_no_values'), true); return; }
      const btn = $('#manual-btn'); busy(btn, true);
      try { const res = await api('/api/manual', { method: 'POST', body: { values, ...getPlace(), lang: LANG } }); location.href = res.url; }
      catch (err) { toast(err.message, true); busy(btn, false); }
    });

    // district risk
    let lastRisk = null;
    $('#risk-btn').addEventListener('click', async () => {
      const p = getPlace();
      if (!p.state && !p.district && !p.pincode) { toast(t('no_place'), true); $('#place-card').scrollIntoView({ behavior: 'smooth' }); return; }
      const btn = $('#risk-btn'); busy(btn, true);
      try {
        lastRisk = await api(`/api/risk?state=${encodeURIComponent(p.state)}&district=${encodeURIComponent(p.district)}&pincode=${encodeURIComponent(p.pincode)}`);
        if (lastRisk.state && !p.state) { $('#state').value = lastRisk.state; }
        if (lastRisk.district && !p.district) { $('#district').value = lastRisk.district; }
        $('#risk-out').innerHTML = renderRisk(lastRisk);
      } catch (err) { toast(err.message, true); }
      busy(btn, false);
    });
    onLang(() => { if (lastRisk) $('#risk-out').innerHTML = renderRisk(lastRisk); });
  };

  function toggleLang() {
    LANG = LANG === 'hi' ? 'en' : 'hi';
    localStorage.setItem('jp-lang', LANG);
    if (speaking && 'speechSynthesis' in window) { speechSynthesis.cancel(); speaking = false; }
    applyLang();
  }

  // ---------------------------------------------------------------- test result
  const V_ICON = { safe: '✅', caution: '⚠️', unsafe: '⛔', retake: '📸' };
  let complaintData = null;

  function renderTest(d) {
    const box = $('#result');
    if (d.status === 'error') {
      box.innerHTML = `<section class="card verdict v-error"><div class="v-row"><span class="v-icon">📸</span><div>
        <h2>${esc(t('v_error'))}</h2><p>${esc(t('v_error_sub'))}</p></div></div>
        <div class="v-actions"><a class="btn" href="/">${esc(t('retake_btn'))}</a></div></section>`;
      return;
    }
    if (!d.verdict) { box.innerHTML = `<section class="card verdict v-loading"><div class="v-row"><span class="spin big"></span><div><h2>${esc(t('reading'))}</h2><p class="small">${esc(t('reading_help'))}</p></div></div></section>`; return; }
    const ev = d.evaluation; const a = d.advice;
    const summary = a ? L(a, 'summary') : '';
    const place = [d.district, d.state].filter(Boolean).join(', ');
    let html = `<section class="card verdict v-${esc(d.verdict)}"><div class="v-row"><span class="v-icon">${V_ICON[d.verdict]}</span><div>
        <h2>${esc(t('v_' + d.verdict))}</h2><p>${esc(t('v_' + d.verdict + '_sub'))}</p>
        ${place ? `<p class="small">📍 ${esc(place)}</p>` : ''}</div></div>
        ${summary ? `<p style="position:relative;z-index:1;margin-top:12px">${esc(summary)}</p>` : `<p class="small" style="position:relative;z-index:1"><span class="spin"></span> ${esc(t('advising'))}</p>`}
        <div class="v-actions">
          ${summary ? `<button class="btn btn-sm" id="speak">${esc(t('listen'))}</button>` : ''}
          ${d.verdict === 'retake' ? `<a class="btn btn-sm" href="/">${esc(t('retake_btn'))}</a>` : ''}
          ${summary ? `<a class="btn btn-sm" target="_blank" rel="noopener" href="https://wa.me/?text=${encodeURIComponent('जल परख / Jal Parakh: ' + summary + ' ' + location.href)}">${esc(t('share'))}</a>` : ''}
        </div>
        ${d.is_demo ? `<span class="demo-flag">${esc(t('demo_flag'))}</span>` : ''}</section>`;

    if (a) {
      const steps = L(a, 'steps') || [];
      html += `<section class="card"><h2>🛠️ ${esc(t('what_to_do'))}</h2><ol class="steps">${steps.map((s) => `<li>${esc(s)}</li>`).join('')}</ol>
        <div class="note"><b>🦠 ${esc(t('germs'))}:</b> ${esc(L(a, 'germs'))}</div></section>`;
      const health = L(a, 'health') || []; const doctor = L(a, 'doctor') || [];
      if (health.length || doctor.length) {
        html += `<section class="card">${health.length ? `<h2>❤️ ${esc(t('health'))}</h2><ul class="plain">${health.map((s) => `<li>${esc(s)}</li>`).join('')}</ul>` : ''}
          ${doctor.length ? `<h3>🩺 ${esc(t('doctor'))}</h3><div class="note ${d.verdict === 'unsafe' ? 'bad' : 'warn'}"><ul class="plain" style="margin:0">${doctor.map((s) => `<li>${esc(s)}</li>`).join('')}</ul></div>` : ''}</section>`;
      }
    }

    if (ev.results.length) {
      html += `<section class="card"><h2>🧪 ${esc(t('readings'))}</h2><ul class="params">${ev.results.map((r) => `
        <li><span class="p-name">${esc(LANG === 'hi' ? r.name_hi : r.name_en)} <span class="pill p-${esc(r.status)}">${esc(t('status_' + r.status))}</span></span>
          <span class="p-val">${r.value === null ? '?' : esc(r.value)} <small class="muted">${esc(r.unit)}</small></span>
          <span class="p-reason">${esc(LANG === 'hi' ? r.reason_hi : r.reason_en)} <span class="muted">· ${esc(r.source === 'WHO' ? 'WHO' : 'BIS')} ${esc(r.limit)}</span></span>
          ${d.source === 'strip' ? `<span class="conf" title="${esc(t('confidence'))} ${pct(r.confidence)}"><i style="width:${pct(r.confidence)}"></i></span>` : ''}
        </li>`).join('')}</ul>
        ${d.source === 'strip' ? `<p class="small muted">${esc(t('confidence'))}: ${esc(LANG === 'hi' ? 'पट्टी जितनी लंबी, भरोसा उतना ज़्यादा' : 'longer bar = more confident')} · ${esc(LANG === 'hi' ? 'सीमा' : 'threshold')} ${pct(ev.threshold)}</p>` : ''}</section>`;
    }

    if (d.risk && (d.risk.risks || []).length) {
      html += `<section class="card"><h2>🗺️ ${esc(t('your_area'))}</h2><ul class="risk-list">${d.risk.risks.map((x) => `<li class="${x.level === 'district' ? 'district' : ''}">${esc(LANG === 'hi' ? x.hi : x.en)} <a class="small" href="${esc(x.source)}" target="_blank" rel="noopener">PIB/CGWB</a></li>`).join('')}</ul></section>`;
    }

    if (d.verdict === 'unsafe' || d.verdict === 'caution') {
      html += `<section class="card" id="complaint-card"><h2>📝 ${esc(t('complaint_title'))}</h2>
        <p class="small muted">${esc(t('complaint_note'))}</p>
        ${complaintData ? `<textarea class="complaint" id="complaint-text" readonly>${esc(LANG === 'hi' ? complaintData.text_hi : complaintData.text_en)}</textarea>
          <button class="btn btn-primary btn-xl" id="copy-complaint">${esc(t('copy'))}</button>
          <p class="small"><b>${esc(t('where_send'))}:</b> <a href="${esc(complaintData.channels.cpgrams)}" target="_blank" rel="noopener">CPGRAMS (pgportal.gov.in)</a> ·
          <a href="${esc(complaintData.channels.ddws)}" target="_blank" rel="noopener">DDWS grievance</a> · ${LANG === 'hi' ? 'अपने ज़िले का PHED कार्यालय / ग्राम पंचायत' : 'your district PHED office / Gram Panchayat'}${d.state === 'Uttar Pradesh' ? ' · UP Jal Samadhan: 1800 121 2164' : ''}</p>`
        : `<button class="btn btn-primary btn-xl" id="make-complaint">${esc(t('complaint_btn'))}</button>`}</section>`;
    }
    if (a && a.agent) html += `<p class="agent center">advice: ${esc(a.agent)} · reader: ${esc(d.agent || '')} · BIS IS 10500:2012</p>`;
    box.innerHTML = html;

    const sp = $('#speak'); if (sp) sp.addEventListener('click', () => speak(summary + ' ' + (L(a, 'steps') || []).slice(0, 3).join(' '), sp));
    const mk = $('#make-complaint'); if (mk) mk.addEventListener('click', async () => {
      busy(mk, true);
      try { complaintData = await api(`/api/tests/${d.id}/complaint?lang=${LANG}`, { method: 'POST' }); renderTest(d); $('#complaint-card').scrollIntoView({ behavior: 'smooth' }); }
      catch (err) { toast(err.message, true); busy(mk, false); }
    });
    const cp = $('#copy-complaint'); if (cp) cp.addEventListener('click', async () => {
      const ta = $('#complaint-text');
      try { await navigator.clipboard.writeText(ta.value); } catch (_) { ta.removeAttribute('readonly'); ta.select(); document.execCommand('copy'); ta.setAttribute('readonly', ''); }
      toast(t('copied'));
    });
  }

  JP_initTest = function (id) {
    applyLang();
    $('#lang-toggle').addEventListener('click', toggleLang);
    let last = null; let tries = 0;
    onLang(() => { if (last) renderTest(last); });
    const poll = async () => {
      tries += 1;
      try { last = await api('/api/tests/' + id); renderTest(last); } catch (_) { /* retry */ }
      if (!last || (last.status !== 'done' && last.status !== 'error')) setTimeout(poll, tries < 60 ? 2000 : 6000);
    };
    poll();
  };

  // ---------------------------------------------------------------- impact
  JP_initImpact = function () {
    applyLang();
    $('#lang-toggle').addEventListener('click', toggleLang);
    let map = null; let reportLayer = null; let officialLayer = null; let data = null;
    if (window.L) {
      map = window.L.map('map', { scrollWheelZoom: false }).setView([22.8, 79.5], 4.4);
      window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 12, attribution: '&copy; OpenStreetMap contributors' }).addTo(map);
      reportLayer = window.L.layerGroup().addTo(map);
      officialLayer = window.L.layerGroup().addTo(map);
      api('/api/risk-layer').then((r) => {
        r.districts.forEach((d) => {
          const color = d.arsenic && !d.fluoride ? '#3a3a3a' : '#8e5bd1';
          window.L.circleMarker([d.lat, d.lng], { radius: 4, weight: d.arsenic && d.fluoride ? 2 : 0, color: '#3a3a3a', fillColor: color, fillOpacity: 0.45 })
            .bindTooltip(`${d.district}, ${d.state}: ${[d.fluoride ? 'fluoride' : '', d.arsenic ? 'arsenic' : ''].filter(Boolean).join(' + ')} (CGWB)`)
            .addTo(officialLayer);
        });
      }).catch(() => {});
      $('#layer-official').addEventListener('change', (e) => { if (e.target.checked) officialLayer.addTo(map); else map.removeLayer(officialLayer); });
    }
    const colorFor = (rate) => (rate === null ? '#50606c' : rate >= 0.5 ? '#c0262d' : rate > 0 ? '#e09a12' : '#12804c');
    const render = () => {
      if (!data) return;
      const c = data.counters;
      $('#c-tests').textContent = c.tests_run; $('#c-unsafe').textContent = c.unsafe_found;
      $('#c-rate').textContent = c.unsafe_rate === null ? '–' : pct(c.unsafe_rate);
      $('#c-complaints').textContent = c.complaints_drafted; $('#c-districts').textContent = c.districts;
      const tb = $('#district-table tbody');
      tb.innerHTML = data.districts.length ? data.districts.map((d) => `<tr><td>${esc(d.district || d.state || t('unknown_place'))}${d.district && d.state ? `<br><span class="muted small">${esc(d.state)}</span>` : ''}</td>
        <td>${d.tests}</td><td>${d.unsafe}</td><td>${d.unsafe_rate === null ? '–' : pct(d.unsafe_rate)}</td><td>${esc(d.top_params.map(paramName).join(', '))}</td></tr>`).join('')
        : `<tr><td colspan="5" class="muted">${esc(t('no_reports'))}</td></tr>`;
      $('#privacy').textContent = data.privacy;
      if (reportLayer) {
        reportLayer.clearLayers();
        data.districts.filter((d) => d.lat !== null).forEach((d) => {
          window.L.circleMarker([d.lat, d.lng], { radius: Math.min(26, 8 + Math.sqrt(d.tests) * 4), color: '#fff', weight: 2, fillColor: colorFor(d.unsafe_rate), fillOpacity: 0.85 })
            .bindPopup(`<b>${esc(d.district || d.state)}</b><br>${esc(t('c_tests'))}: ${d.tests}<br>${esc(t('unsafe'))}: ${d.unsafe} (${d.unsafe_rate === null ? '–' : pct(d.unsafe_rate)})${d.top_params.length ? '<br>' + esc(d.top_params.map(paramName).join(', ')) : ''}`)
            .addTo(reportLayer);
        });
      }
    };
    const load = async () => {
      const demo = $('#include-demo').checked;
      $('#csv-link').href = '/api/impact.csv' + (demo ? '?include_demo=true' : '');
      try {
        if (!Object.keys(LIMITS).length) (await api('/api/limits')).limits.forEach((l) => { LIMITS[l.param] = l; });
        data = await api('/api/impact' + (demo ? '?include_demo=true' : '')); render();
      } catch (err) { toast(err.message, true); }
    };
    $('#include-demo').addEventListener('change', load);
    onLang(render);
    load();
  };

  window.JP = {
    initHome: (p) => JP_initHome(p), initTest: (id) => JP_initTest(id), initImpact: () => JP_initImpact(),
    initStatic: () => { applyLang(); const b = $('#lang-toggle'); if (b) b.addEventListener('click', toggleLang); },
  };
  // pages without a dedicated init (about) still get the language toggle
  window.addEventListener('load', () => { if (!window.__jpInit) window.JP.initStatic(); });
  ['initHome', 'initTest', 'initImpact'].forEach((k) => { const f = window.JP[k]; window.JP[k] = (...a) => { window.__jpInit = true; return f(...a); }; });
})();
