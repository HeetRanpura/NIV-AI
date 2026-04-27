const API = 'https://niv-ai-216564346797.asia-south1.run.app';

// === STATE MANAGEMENT ===
const STATE = {
    currentStep: 1, selectedLanguage: 'english',
    lastReport: null, lastInput: null, lastComputed: null,
    whatIfOriginal: null, lastInputCached: null,
    comparisonReport: null, currentShareUrl: '',
    bankEmailContent: null, frictionAnswers: {},
    marketRatesCache: null, marketRatesFetchTime: 0,
    propertyPhotoFiles: [],
    visualInspectionResult: null,
};

// === UTILITY FUNCTIONS ===
/**
 * Animates element textContent from 0 to target value with easing.
 * @param {HTMLElement} el @param {number} target @param {number} duration
 * @param {Function} formatter
 */
function animateCount(el, target, duration = 800, formatter = v => Math.round(v)) {
    const start = performance.now();
    function tick(now) {
        const p = Math.min((now - start) / duration, 1);
        const ease = 1 - Math.pow(1 - p, 3);
        el.textContent = formatter(ease * target);
        if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
}

/**
 * Staggered entrance animation on array of elements.
 * @param {NodeList|Array} elements @param {string} className @param {number} staggerMs
 */
function staggerEntrance(elements, className, staggerMs = 60) {
    [...elements].forEach((el, i) =>
        setTimeout(() => el.classList.add(className), i * staggerMs));
}

/**
 * IntersectionObserver that fires callback once when element enters viewport.
 * @param {HTMLElement} el @param {Function} callback @param {number} threshold
 */
function onVisible(el, callback, threshold = 0.2) {
    if (!el) return;
    new IntersectionObserver((entries, obs) => {
        if (entries[0].isIntersecting) { callback(); obs.unobserve(el); }
    }, { threshold }).observe(el);
}

function formatIndianDigits(raw) {
    if (!raw) return '';
    if (raw.length <= 3) return raw;
    const lastThree = raw.slice(-3);
    const rest = raw.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ',');
    return `${rest},${lastThree}`;
}

function countDigitsBeforeCaret(value, caretPos) {
    return value.slice(0, caretPos).replace(/\D/g, '').length;
}

function caretFromDigitIndex(formatted, digitIndex) {
    if (digitIndex <= 0) return 0;
    let digitsSeen = 0;
    for (let i = 0; i < formatted.length; i++) {
        if (/\d/.test(formatted[i])) digitsSeen += 1;
        if (digitsSeen >= digitIndex) return i + 1;
    }
    return formatted.length;
}

/**
 * Formats rupee-style numeric inputs with Indian commas while preserving caret position.
 * @param {HTMLInputElement} input
 */
function setupIndianNumberFormat(input) {
    if (!input) return;
    input.addEventListener('input', function () {
        const selectionStart = this.selectionStart ?? this.value.length;
        let raw = this.value.replace(/\D/g, '');
        if (raw.length > 12) raw = raw.slice(0, 12);

        const digitsBeforeCaret = countDigitsBeforeCaret(this.value, selectionStart);
        const formatted = formatIndianDigits(raw);

        this.dataset.raw = raw;
        this.value = formatted;

        const nextCaret = caretFromDigitIndex(formatted, Math.min(digitsBeforeCaret, raw.length));
        this.setSelectionRange(nextCaret, nextCaret);
    });
}

// --- STATE VARIABLES ---
let currentStep = 1;
let selectedLanguage = 'english';
let frictionGateAnswers = {};
let frictionQuestionOrder = [];
let frictionGateStage = 0;
let frictionCurrentRequiredIds = [];
let lastInput = null;
let lastReport = null;
let whatIfOriginal = null;
let whatIfDebounceTimer = null;
let lastInput_cached = null;
let comparisonReport = null;
let currentShareUrl = '';
let reportPageIndex = 0;
let loadingQuoteTimer = null;
let bankEmailReturnPage = 0;

const reportPageDescriptions = [
    'Start with the decision summary, core affordability, and top warning signals.',
    'Pressure-test the purchase with scenarios and real-world shock simulations.',
    'Analyze the physical asset quality, local pricing benchmarks, and rent-vs-buy math.',
    'Review the true acquisition cost including hidden friction and interior projections.',
    'Understand the reasoning, challenged assumptions, and buyer blind spots behind the verdict.',
    'Compare alternatives, verify documents, and export your full audit report.'
];


const loadingQuotes = [
    {
        quote: 'A good property decision is usually won at entry price, not at brochure quality.',
        note: 'We are checking whether the numbers still make sense after EMI, maintenance, and real-world buffers.'
    },
    {
        quote: 'In real estate, liquidity matters. A home is easy to enter and expensive to exit.',
        note: 'This is why tenure, runway, and downside resilience matter as much as monthly affordability.'
    },
    {
        quote: 'An affordable EMI can still be a weak decision if it wipes out your safety cushion.',
        note: 'We are comparing affordability with survival capacity, not just bank eligibility.'
    },
    {
        quote: 'Builder reputation reduces uncertainty, but it never replaces document and delay risk checks.',
        note: 'We are weighing project signals, execution risk, and cost drag together.'
    },
    {
        quote: 'The best property is not always the one you can buy. It is the one you can hold safely.',
        note: 'Our agents are testing whether this purchase still works when life is slightly uncooperative.'
    }
];

// --- HELPERS ---
function esc(s) { const d = document.createElement('div'); d.textContent = String(s || ''); return d.innerHTML; }
function inr(n) { if (n == null) return '—'; return '₹' + Math.round(n).toLocaleString('en-IN'); }
function pct(n) { return (n * 100).toFixed(1) + '%'; }
function getNum(id) {
    const val = document.getElementById(id)?.value || '';
    return parseFloat(val.replace(/,/g, '')) || 0;
}
function getVal(id) { return document.getElementById(id)?.value || ''; }
function preview(el, previewId) {
    const raw = (el.value || '').replace(/,/g, '');
    const v = parseFloat(raw);
    const p = document.getElementById(previewId);
    if (!p) return;
    p.textContent = (v > 0) ? '≈ ' + inr(v) : '';
}

// === FORM / WIZARD ===
function setLang(lang, btn) {
    selectedLanguage = lang;
    document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
}

function goStep(n) {
    // Validation
    if (n === 2 && currentStep === 1) {
        const inc = getNum('monthly_income');
        if (inc <= 0) {
            document.getElementById('monthly_income').setAttribute('aria-invalid', 'true');
            document.getElementById('monthly_income').focus();
            showErr('Monthly income is required to proceed.');
            return;
        }
        document.getElementById('monthly_income').removeAttribute('aria-invalid');
        document.getElementById('err').style.display = 'none';
    }
    if (n === 3 && currentStep === 2) {
        const price = getNum('property_price');
        const loc = getVal('location_area');
        const dp = getNum('down_payment_available');
        if (price <= 100000) { showErr('Property price must be > ₹1,00,000'); return; }
        if (!loc) { showErr('Location is required'); return; }
        if (dp >= price) { showErr('Down payment must be less than property price'); return; }
        document.getElementById('err').style.display = 'none';
    }

    // Animate outgoing step slides left
    const outgoing = document.querySelector('[data-step].active');
    const incoming = document.querySelector(`[data-step="${n}"]`);
    if (outgoing && incoming && outgoing !== incoming) {
        outgoing.style.transition = 'transform 0.3s ease, opacity 0.3s ease';
        outgoing.style.transform = 'translateX(-30px)';
        outgoing.style.opacity = '0';
        setTimeout(() => {
            outgoing.style.transition = '';
            outgoing.style.transform = '';
            outgoing.style.opacity = '';
        }, 300);
    }

    document.querySelectorAll('[data-step]').forEach(el => el.classList.remove('active'));

    // Animate incoming step from right
    if (incoming) {
        incoming.style.transform = 'translateX(30px)';
        incoming.style.opacity = '0';
        incoming.classList.add('active');
        requestAnimationFrame(() => requestAnimationFrame(() => {
            incoming.style.transition = 'transform 0.3s ease, opacity 0.3s ease';
            incoming.style.transform = 'translateX(0)';
            incoming.style.opacity = '1';
            setTimeout(() => {
                incoming.style.transition = '';
                incoming.style.transform = '';
                incoming.style.opacity = '';
            }, 300);
        }));
    } else {
        document.querySelector(`[data-step="${n}"]`).classList.add('active');
    }

    document.querySelectorAll('.w-label-glass').forEach((el, idx) => {
        el.classList.remove('active', 'completed');
        if (idx + 1 < n) el.classList.add('completed');
        if (idx + 1 === n) el.classList.add('active');
    });

    document.querySelectorAll('.wizard-checkpoint').forEach((el, idx) => {
        el.classList.remove('active', 'completed');
        if (idx + 1 < n) el.classList.add('completed');
        if (idx + 1 === n) el.classList.add('active');
    });

    const fillBar = document.getElementById('wizard-fill-bar');
    if (fillBar) {
        const progress = n === 1 ? 5 : (n === 2 ? 50 : 100);
        fillBar.style.width = progress + '%';
    }





    currentStep = n;

    window.scrollTo(0, 0);
    if (n === 2) { updateEMIPreview(); loadMarketRates(); }
}

function showAllSteps(e) {
    e.preventDefault();
    const nav = document.querySelector('.glass-wizard-nav');
    if (nav) nav.style.display = 'none';

    document.querySelectorAll('[data-step]').forEach(el => el.classList.add('active'));
    e.target.style.display = 'none';
    const btn = document.createElement('button');
    btn.className = 'btn-primary';
    btn.textContent = 'Run Full AI Analysis — 6 Agents';
    btn.onclick = onSubmitClick;
    document.querySelector('[data-step="3"]').appendChild(btn);
}


// --- LIVE METRICS (STEP 1 & 2) ---
function updateFinancialHealth() {
    const inc = getNum('monthly_income'); const sp = getNum('spouse_income');
    const emis = getNum('existing_emis'); const exp = getNum('monthly_expenses');
    const capacity = inc + sp - emis - exp;
    const el = document.getElementById('financial-health');
    if (el) {
        el.textContent = inr(capacity);
        el.style.color = capacity > 20000 ? 'var(--green)' : capacity >= 5000 ? 'var(--yellow)' : 'var(--red)';
    }
    const fill = document.getElementById('health-fill-bar');
    if (fill) {
        const pct = Math.min(Math.max((capacity / (inc + sp > 0 ? inc + sp : 1)) * 100, 0), 100);
        fill.style.width = pct + '%';
        fill.style.background = capacity > 20000 ? 'var(--green)' : capacity >= 5000 ? 'var(--yellow)' : 'var(--red)';
    }
}

function calculateClientEMI(principal, annualRatePct, tenureYears) {
    if (principal <= 0 || annualRatePct <= 0 || tenureYears <= 0) return 0;
    const r = annualRatePct / 12 / 100;
    const n = tenureYears * 12;
    return principal * r * Math.pow(1 + r, n) / (Math.pow(1 + r, n) - 1);
}

let marketRatesData = null;

// === MARKET DATA ===
/**
 * Fetches live market rates from /api/v1/market/rates.
 * Caches result for 5 minutes. Updates #market-rates-banner.
 */
async function fetchMarketRates() {
    const banner = document.getElementById('market-rates-banner');
    if (!banner) return;
    const now = Date.now();
    if (STATE.marketRatesCache && now - STATE.marketRatesFetchTime < 300000) {
        displayMarketRates(STATE.marketRatesCache); return;
    }
    try {
        const res = await fetch(`${API}/api/v1/market/rates`);
        if (!res.ok) return;
        const data = await res.json();
        STATE.marketRatesCache = data;
        STATE.marketRatesFetchTime = now;
        displayMarketRates(data);
    } catch (e) { /* silent fail */ }
}

function displayMarketRates(data) {
    const banner = document.getElementById('market-rates-banner');
    const text = document.getElementById('market-rates-text');
    if (!banner || !text) return;
    const floor = data.sbi_rate || data.min_rate || 8.5;
    const ceil = data.max_rate || 9.9;
    const repo = data.rbi_repo_rate || 6.5;
    text.textContent = `Market rates: ${floor}–${ceil}% · RBI repo: ${repo}%`;
    banner.style.display = 'flex';
    const userRate = +document.getElementById('expected_interest_rate')?.value;
    if (userRate && userRate < floor) {
        text.style.color = 'var(--yellow)';
        text.textContent += ' ⚠ Your rate may be below current market floor';
    }
}

// === EMI PREVIEW ===
let emiDebounce;
function updateEMIPreview() {
    clearTimeout(emiDebounce);
    emiDebounce = setTimeout(() => {
        const price = getNum('property_price'); const dp = getNum('down_payment_available');
        const tenure = getNum('loan_tenure_years') || 20; const rate = getNum('expected_interest_rate') || 8.5;
        const inc = getNum('monthly_income'); const sp = getNum('spouse_income');
        const emis = getNum('existing_emis'); const exp = getNum('monthly_expenses');

        const principal = Math.max(price - dp, 0);
        const emi = Math.round(calculateClientEMI(principal, rate, tenure));
        const household = inc + sp;
        const surplus = household - emi - emis - exp;
        const ratio = household > 0 ? emi / household : 0;

        document.getElementById('ep-loan').textContent = principal > 0 ? inr(principal) : '—';
        document.getElementById('ep-emi').textContent = emi > 0 ? inr(emi) : '—';

        const surpEl = document.getElementById('ep-surplus');
        surpEl.textContent = surplus !== 0 ? (surplus >= 0 ? inr(surplus) : '−' + inr(Math.abs(surplus))) : '—';
        surpEl.style.color = surplus > 20000 ? 'var(--green)' : surplus > 5000 ? 'var(--yellow)' : 'var(--red)';

        const ratioEl = document.getElementById('ep-ratio');
        ratioEl.textContent = ratio > 0 ? (ratio * 100).toFixed(1) + '%' : '—';
        ratioEl.style.color = ratio < 0.30 ? 'var(--green)' : ratio < 0.45 ? 'var(--yellow)' : 'var(--red)';

        const zoneEl = document.getElementById('ep-zone');
        if (ratio < 0.30) {
            zoneEl.style.color = 'var(--green-light)';
            zoneEl.textContent = 'COMFORTABLE — EMI is safely within limits';
        } else if (ratio < 0.45) {
            zoneEl.style.color = 'var(--yellow-light)';
            zoneEl.textContent = 'STRETCHED — manageable but thin margin';
        } else if (ratio > 0) {
            zoneEl.style.color = 'var(--red-light)';
            zoneEl.textContent = 'DANGER — this EMI is dangerously high';
        } else {
            zoneEl.textContent = '';
        }

        function updateEMIArc(ratio) {
            const path = document.getElementById('arc-fill-path');
            const label = document.getElementById('arc-label');
            if (!path || !label) return;
            const maxDash = 251;
            const fill = Math.min(ratio, 0.6) / 0.6;
            path.style.strokeDashoffset = maxDash - (maxDash * fill);
            path.style.stroke = ratio < 0.3 ? 'var(--green)' :
                ratio < 0.45 ? 'var(--yellow)' : 'var(--red)';
            label.textContent = (ratio * 100).toFixed(1) + '%';
            path.style.transition = 'stroke-dashoffset 0.4s ease, stroke 0.3s ease';
        }
        updateEMIArc(ratio);

        // Show rate warning if market data is loaded
        if (marketRatesData && rate > 0) updateRateWarning(rate, marketRatesData);
    }, 300);
}

// --- FRICTION GATE ---
function shouldShowFrictionGate() {
    const isUC = getVal('is_ready_to_move') === 'false';
    const dp = getNum('down_payment_available'); const sav = getNum('liquid_savings');
    const dpRatio = sav > 0 ? dp / sav : 0;
    const hh = getNum('monthly_income') + getNum('spouse_income');
    const emi = calculateClientEMI(Math.max(getNum('property_price') - dp, 0), getNum('expected_interest_rate') || 8.5, getNum('loan_tenure_years') || 20);
    const emiRatio = hh > 0 ? emi / hh : 0;
    return isUC || dpRatio > 0.60 || emiRatio > 0.40;
}

function getVisibleFrictionQuestions() {
    return Array.from(document.querySelectorAll('.friction-question')).filter(
        el => el.dataset.enabled !== 'false'
    );
}

function setVisibleFrictionQuestions(questionIds) {
    const required = new Set(questionIds);
    document.querySelectorAll('.friction-question').forEach(el => {
        const show = required.has(el.id);
        el.classList.toggle('active', show);
        el.style.display = show ? 'block' : 'none';
    });
}

function refreshFrictionDots() {
    const visibleIds = frictionQuestionOrder;
    visibleIds.forEach((id, idx) => {
        const dot = document.getElementById(`fd-${idx + 1}`);
        if (!dot) return;
        dot.classList.toggle('done', Boolean(frictionGateAnswers[id]));
        dot.classList.toggle('current', frictionCurrentRequiredIds.includes(id));
        dot.style.display = 'block';
    });
    for (let idx = visibleIds.length; idx < 5; idx += 1) {
        const dot = document.getElementById(`fd-${idx + 1}`);
        if (dot) {
            dot.classList.remove('done');
            dot.classList.remove('current');
            dot.style.display = 'none';
        }
    }
}

function setFrictionStage(stage) {
    frictionGateStage = stage;
    const questions = frictionQuestionOrder;
    if (!questions.length) {
        frictionCurrentRequiredIds = [];
        setVisibleFrictionQuestions([]);
        return;
    }

    const currentQuestionId = questions[Math.min(stage, questions.length - 1)];
    frictionCurrentRequiredIds = currentQuestionId ? [currentQuestionId] : [];
    if (!frictionCurrentRequiredIds.length) frictionCurrentRequiredIds = [questions[0]];

    setVisibleFrictionQuestions(frictionCurrentRequiredIds);
    const labelEl = document.getElementById('friction-stage-label');
    const copyEl = document.getElementById('friction-progress-copy');
    const btn = document.getElementById('friction-proceed');
    const totalSteps = questions.length;
    const currentStep = Math.min(stage + 1, totalSteps);
    if (labelEl) labelEl.textContent = `Question ${currentStep} of ${totalSteps}`;
    if (copyEl) {
        copyEl.textContent = currentStep < totalSteps
            ? 'Answer this reality check to move to the next one.'
            : 'Answer the final reality check, then explicitly start the full analysis.';
    }
    if (btn) {
        btn.textContent = currentStep < totalSteps
            ? 'Next Question →'
            : 'Proceed to Analysis →';
    }
    refreshFrictionDots();
}

function setupFrictionGate() {
    frictionGateAnswers = {};
    frictionGateStage = 0;
    frictionCurrentRequiredIds = [];
    document.querySelectorAll('.friction-option.selected').forEach(el => el.classList.remove('selected'));
    ['fq1', 'fq2', 'fq3', 'fq4', 'fq5'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.dataset.enabled = 'true';
            el.style.display = 'none';
            const warn = el.querySelector('.friction-warning');
            if (warn) warn.style.display = 'none';
        }
    });

    frictionQuestionOrder = getVisibleFrictionQuestions().map(el => el.id);
    setFrictionStage(0);
    refreshFrictionDots();
}

function onSubmitClick() {
    if (shouldShowFrictionGate()) {
        document.getElementById('friction-gate').style.display = 'flex';
        setupFrictionGate();
        checkFrictionComplete();
    } else {
        submitAnalysis();
    }
}

function selectFriction(qId, val, btn) {
    frictionGateAnswers[qId] = val;
    const qDiv = document.getElementById(qId);
    qDiv.querySelectorAll('.friction-option').forEach(el => el.classList.remove('selected'));
    btn.classList.add('selected');

    const warn = qDiv.querySelector('.friction-warning');
    if (warn) {
        if (val === 'C' || (val === 'B' && qId !== 'fq3')) {
            warn.style.display = 'block';
        } else {
            warn.style.display = 'none';
        }
    }
    checkFrictionComplete();
}

function checkFrictionComplete() {
    const visibleQs = getVisibleFrictionQuestions();
    const requiredCount = frictionCurrentRequiredIds.length;
    const answeredCount = frictionCurrentRequiredIds.filter(id => frictionGateAnswers[id]).length;
    const btn = document.getElementById('friction-proceed');
    const sumEl = document.getElementById('friction-summary');
    const meterSegments = Array.from(document.querySelectorAll('#concern-meter .cm-seg'));
    const countEl = document.getElementById('friction-progress-count');
    const visibleIds = new Set(frictionQuestionOrder);
    const allQuestions = getVisibleFrictionQuestions();
    const concerns = allQuestions.filter(el => {
        const answer = frictionGateAnswers[el.id];
        return answer === 'C' || (answer === 'B' && el.id !== 'fq3');
    }).length;

    meterSegments.forEach((seg, idx) => {
        seg.style.background = idx < concerns ? 'var(--red)' : 'var(--border)';
    });
    refreshFrictionDots();
    if (countEl) countEl.textContent = `${answeredCount} / ${requiredCount} answered`;

    if (answeredCount === requiredCount && requiredCount > 0) {
        btn.disabled = false;
        if (sumEl) {
            sumEl.style.display = 'block';
            if (frictionGateStage < frictionQuestionOrder.length - 1) {
                sumEl.style.background = 'var(--surface-2)';
                sumEl.style.borderColor = 'var(--border)';
                sumEl.style.color = 'var(--text)';
                sumEl.textContent = 'Response captured. Continue when you are ready for the next reality check.';
            } else if (concerns === 0) {
                sumEl.style.background = 'var(--green-bg)';
                sumEl.style.borderColor = 'var(--green-border)';
                sumEl.style.color = 'var(--green)';
                sumEl.textContent = 'You have answered every visible check. Proceeding with a clean pre-analysis profile.';
            } else if (concerns <= 2) {
                sumEl.style.background = 'var(--yellow-bg)';
                sumEl.style.borderColor = 'var(--yellow-border)';
                sumEl.style.color = 'var(--yellow)';
                sumEl.textContent = 'A few caution signals showed up. The analysis will weigh them directly.';
            } else {
                sumEl.style.background = 'var(--red-bg)';
                sumEl.style.borderColor = 'var(--red-border)';
                sumEl.style.color = 'var(--red)';
                sumEl.textContent = 'Multiple concern signals are active. Read the analysis carefully before deciding.';
            }
        }
    } else {
        btn.disabled = true;
        if (sumEl) {
            sumEl.style.display = 'none';
            sumEl.textContent = '';
        }
    }

    Object.keys(frictionGateAnswers).forEach(key => {
        if (!visibleIds.has(key)) delete frictionGateAnswers[key];
    });
}

function closeFrictionGate() {
    document.getElementById('friction-gate').style.display = 'none';
    document.querySelectorAll('.friction-question').forEach(el => {
        el.classList.remove('active');
        el.style.display = 'none';
    });
}
function proceedFromFriction() {
    if (frictionCurrentRequiredIds.some(id => !frictionGateAnswers[id])) return;
    if (frictionGateStage < frictionQuestionOrder.length - 1) {
        setFrictionStage(frictionGateStage + 1);
        checkFrictionComplete();
        return;
    }
    closeFrictionGate();
    submitAnalysis();
}

// --- SUBMISSION & API ---
function collectFormData() {
    const r = getVal('is_rera_registered');

    let combinedNotes = getVal('property_notes') || '';
    const gstin = getVal('builder_gstin');
    const rera = getVal('rera_number');
    if (gstin) combinedNotes += (combinedNotes ? ' | ' : '') + 'Builder GSTIN: ' + gstin;
    if (rera) combinedNotes += (combinedNotes ? ' | ' : '') + 'RERA Number: ' + rera;

    return {
        financial: {
            monthly_income: getNum('monthly_income'), spouse_income: getNum('spouse_income'),
            employment_type: getVal('employment_type'), years_in_current_job: getNum('years_in_current_job') || 2,
            expected_annual_growth_pct: getNum('expected_annual_growth_pct') || 8,
            existing_emis: getNum('existing_emis'), monthly_expenses: getNum('monthly_expenses'),
            current_rent: getNum('current_rent'), liquid_savings: getNum('liquid_savings'),
            dependents: getNum('dependents'), financial_notes: getVal('financial_notes')
        },
        property: {
            property_price: getNum('property_price'), location_area: getVal('location_area') || 'Mumbai',
            location_city: 'Mumbai', configuration: getVal('configuration'),
            carpet_area_sqft: getNum('carpet_area_sqft') || 650,
            is_ready_to_move: getVal('is_ready_to_move') === 'true',
            is_rera_registered: r === 'null' ? null : r === 'true',
            builder_name: getVal('builder_name'), possession_date: getVal('possession_date'),
            down_payment_available: getNum('down_payment_available'),
            loan_tenure_years: getNum('loan_tenure_years') || 20,
            expected_interest_rate: getNum('expected_interest_rate') || 8.5,
            buyer_gender: getVal('buyer_gender'), commute_distance_km: getNum('commute_distance_km') || 0,
            is_first_property: getVal('is_first_property') === 'true', property_notes: combinedNotes
        },
        output_language: selectedLanguage,
        behavioral_checklist_responses: Object.keys(frictionGateAnswers).length ? frictionGateAnswers : null
    };
}

let _t = null;
function setA(id, st) {
    const dot = document.getElementById(id + '-dot');
    const txt = document.getElementById(id);
    if (dot) dot.className = 'agent-dot ' + (st === 'done' ? 'done' : st === 'running' ? 'running' : '');
    if (txt) {
        txt.textContent = st === 'running' ? 'running…' : st === 'done' ? '✓ done' : 'waiting';
        txt.classList.remove('done', 'running');
        if (st === 'done' || st === 'running') txt.classList.add(st);
    }
}
function updateLoadingQuote(index) {
    const item = loadingQuotes[index % loadingQuotes.length];
    const quoteEl = document.getElementById('loading-quote');
    const noteEl = document.getElementById('loading-quote-note');
    if (quoteEl) quoteEl.textContent = item.quote;
    if (noteEl) noteEl.textContent = item.note;
}
function startLoadingQuotes() {
    clearInterval(loadingQuoteTimer);
    let idx = 0;
    updateLoadingQuote(idx);
    loadingQuoteTimer = setInterval(() => {
        idx = (idx + 1) % loadingQuotes.length;
        updateLoadingQuote(idx);
    }, 3500);
}
function stopLoadingQuotes() {
    clearInterval(loadingQuoteTimer);
    loadingQuoteTimer = null;
}
function startA() {
    const ids = ['a1', 'a2', 'a3', 'a4', 'a5', 'a6']; let i = 0;
    startLoadingQuotes();
    function t() { if (i > 0) setA(ids[i - 1], 'done'); if (i < ids.length) { setA(ids[i], 'running'); i++; _t = setTimeout(t, 4000); } }
    t();
}
function stopA() { clearTimeout(_t); stopLoadingQuotes();['a1', 'a2', 'a3', 'a4', 'a5', 'a6'].forEach(id => setA(id, 'done')); }

function showErr(m) { const el = document.getElementById('err'); el.style.display = 'block'; el.textContent = '⚠ ' + m; window.scrollTo(0, 0); }

async function submitAnalysis() {
    document.getElementById('err').style.display = 'none';
    const body = collectFormData();
    lastInput = body;

    if (STATE.visualInspectionResult) {
        body.visual_inspection = STATE.visualInspectionResult;
    }

    document.getElementById('form-section').style.display = 'none';
    document.getElementById('loading-view').style.display = 'block';
    document.getElementById('report-view').style.display = 'none';
    document.body.classList.remove('report-visible');
    startA();
    updateAnalysisProgress();

    try {
        const res = await fetch(`${API}/api/v1/analyze`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        if (!res.ok) { const e = await res.json().catch(() => { }); throw new Error(e?.detail || `HTTP ${res.status}`); }
        const data = await res.json();
        lastReport = data;
        stopA();
        document.getElementById('loading-view').style.display = 'none';
        renderReport(data);
        document.getElementById('report-view').style.display = 'block';
        document.body.classList.add('report-visible');
        window.scrollTo(0, 0);
        autoSaveReport(data);
    } catch (e) {
        stopA();
        document.getElementById('loading-view').style.display = 'none';
        document.getElementById('form-section').style.display = 'block';
        if (e.message.includes('429') || e.message.toLowerCase().includes('rate limit')) {
            showErr('You have reached the analysis limit (5 per 10 minutes). Please wait a moment and try again.');
        } else if (e.message.includes('503')) {
            showErr('The AI service is temporarily unavailable. Please try again in 30 seconds.');
        } else {
            showErr('Analysis failed: ' + e.message + '. If this persists, try refreshing the page.');
        }
    }
}

function renderEmptyState(message) {
    return `<div class="empty-state-note">${esc(message)}</div>`;
}

function renderBulletList(items, emptyMessage) {
    return items && items.length
        ? items.map(item => `<li>${esc(item)}</li>`).join('')
        : renderEmptyState(emptyMessage);
}

function getAffordabilitySummary(surplus, emiRatio, runway) {
    if (surplus > 20000 && emiRatio < 0.35 && runway >= 6) {
        return 'The current structure looks manageable on paper and still leaves some room for mistakes.';
    }
    if (surplus > 5000 && emiRatio < 0.45 && runway >= 3) {
        return 'The purchase is possible, but the margin for error is thin and needs disciplined cash management.';
    }
    return 'The purchase currently looks fragile because one bad surprise could pressure both EMI comfort and savings.';
}

function getPropertySummary(propertyAssessment) {
    const verdict = propertyAssessment?.price_assessment?.verdict || '';
    if (verdict === 'good_value') return 'The asset looks reasonably priced versus the local benchmark, so the main question shifts to holding power and risk.';
    if (verdict === 'overpriced') return 'The property appears expensive relative to local benchmarks, which raises the cost of a wrong decision.';
    return 'Use this page to separate property quality from emotional appeal before you commit.';
}

function getStressSummary(stressScenarios = []) {
    const passed = stressScenarios.filter(s => s.can_survive).length;
    if (passed >= 3) return 'Most core downside scenarios still hold, which is a strong sign of resilience.';
    if (passed >= 2) return 'Some shocks are survivable, but the decision is sensitive to disruption.';
    return 'This purchase is vulnerable under realistic stress, so caution is warranted.';
}

function formatEmailDraftPreview(text) {
    if (!text) return '';
    const normalized = text.replace(/\r\n/g, '\n').trim();
    const blocks = normalized.split(/\n\s*\n/).map(block => block.trim()).filter(Boolean);
    const html = blocks.map((block, index) => {
        const lines = block.split('\n').map(line => line.trim()).filter(Boolean);
        const heading = lines[0];
        const isSectionHeading = /^[A-Z][A-Z\s/&-]{3,}$/.test(heading);
        if (isSectionHeading) {
            const paragraphs = lines.slice(1).map(line => `<p class="bank-email-paragraph">${esc(line)}</p>`).join('');
            return `
                <section class="bank-email-block">
                    <div class="bank-email-block-label">${esc(heading)}</div>
                    <div class="bank-email-block-body">${paragraphs || `<p class="bank-email-paragraph">${esc(heading)}</p>`}</div>
                </section>`;
        }
        return `
            <section class="bank-email-block">
                ${index === 0 ? '<div class="bank-email-block-label">Opening Note</div>' : ''}
                <div class="bank-email-block-body">
                    ${lines.map(line => `<p class="bank-email-paragraph">${esc(line)}</p>`).join('')}
                </div>
            </section>`;
    }).join('');
    return html;
}

function setReportPage(index) {
    const pages = Array.from(document.querySelectorAll('#report-view .report-page'));
    if (!pages.length) return;
    reportPageIndex = Math.max(0, Math.min(index, pages.length - 1));
    pages.forEach((page, idx) => page.classList.toggle('active', idx === reportPageIndex));

    const title = pages[reportPageIndex].dataset.pageTitle || `Page ${reportPageIndex + 1}`;
    const titleEl = document.getElementById('report-page-title');
    const progressEl = document.getElementById('report-page-progress');
    const subtitleEl = document.getElementById('report-page-subtitle');
    if (titleEl) titleEl.textContent = `Page ${reportPageIndex + 1} of ${pages.length} · ${title}`;
    if (progressEl) progressEl.textContent = `Page ${reportPageIndex + 1} of ${pages.length}`;
    if (subtitleEl) subtitleEl.textContent = reportPageDescriptions[reportPageIndex] || 'A guided view of your audit.';

    pages.forEach((_, idx) => {
        const dot = document.getElementById(`report-page-dot-${idx}`);
        if (dot) dot.classList.toggle('active', idx === reportPageIndex);
    });

    const prevBtn = document.getElementById('report-prev-btn');
    const nextBtn = document.getElementById('report-next-btn');
    if (prevBtn) prevBtn.disabled = reportPageIndex === 0;
    if (nextBtn) {
        nextBtn.disabled = reportPageIndex === pages.length - 1;
        nextBtn.textContent = reportPageIndex === pages.length - 1 ? 'Done' : 'Next';
    }

    const top = document.getElementById('report-view');
    if (top) top.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function nextReportPage() {
    const pages = document.querySelectorAll('#report-view .report-page');
    if (reportPageIndex < pages.length - 1) setReportPage(reportPageIndex + 1);
}

function prevReportPage() {
    if (reportPageIndex > 0) setReportPage(reportPageIndex - 1);
}

function normalizeLabel(value) {
    return String(value || '').replace(/_/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2').replace(/\s+/g, ' ').trim();
}

function startCase(value) {
    return normalizeLabel(value).replace(/\w\S*/g, part => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase());
}

function getZoneClass(type, value) {
    if (type === 'ratio') return value < 0.30 ? 'safe' : value < 0.45 ? 'warn' : 'danger';
    if (type === 'runway') return value >= 6 ? 'safe' : value >= 3 ? 'warn' : 'danger';
    if (type === 'count') return value >= 3 ? 'safe' : value >= 2 ? 'warn' : 'danger';
    if (type === 'price') return value === 'overpriced' ? 'danger' : value ? 'safe' : 'warn';
    return 'info';
}

function makeStatusChip(text, zone) {
    return `<span class="status-chip ${zone}">${esc(text)}</span>`;
}

function toggleAccordion(button) {
    const card = button.closest('.accordion-card');
    if (!card) return;
    const isOpen = card.classList.toggle('open');
    button.setAttribute('aria-expanded', String(isOpen));
}

function getCashflowSegments(computed = {}, financial = {}) {
    const income = (financial.monthly_income || 0) + (financial.spouse_income || 0);
    const emi = computed.monthly_emi || 0;
    const ownership = computed.monthly_ownership_cost || emi;
    const maintenance = Math.max(ownership - emi, 0);
    const existingEmis = financial.existing_emis || 0;
    const expenses = financial.monthly_expenses || 0;
    const surplus = Math.max(income - emi - maintenance - existingEmis - expenses, 0);
    return [
        { label: 'New Home EMI', value: emi, color: '#ef4444', hint: 'Primary home loan payment.' },
        { label: 'Maint. + Insurance', value: maintenance, color: '#f59e0b', hint: 'Recurring ownership overhead.' },
        { label: 'Existing EMIs', value: existingEmis, color: '#f97316', hint: 'Other debt already in the system.' },
        { label: 'Living Expenses', value: expenses, color: '#64748b', hint: 'Monthly life costs not tied to the home.' },
        { label: 'Monthly Surplus', value: surplus, color: '#22c55e', hint: 'Cash left after all ongoing obligations.' }
    ].filter(item => item.value > 0 || item.label === 'Monthly Surplus');
}

function renderCashflowSection(computed = {}, financial = {}) {
    const household = (financial.monthly_income || 0) + (financial.spouse_income || 0);
    if (household <= 0) return renderEmptyState('Income details are needed to show the monthly cash-flow snapshot.');
    const ratio = computed.emi_to_income_ratio || 0;
    const runway = computed.emergency_runway_months || 0;
    const ownership = computed.monthly_ownership_cost || computed.monthly_emi || 0;
    const surplus = household - ownership - (financial.existing_emis || 0) - (financial.monthly_expenses || 0);
    const segments = getCashflowSegments(computed, financial);
    return `
        <div class="bank-email-insight" style="display:block; margin-bottom:18px;">${esc(getAffordabilitySummary(surplus, ratio, runway))}</div>
        <div class="rcard cashflow-card">
            <div class="cashflow-kpis">
                <div class="cashflow-kpi">
                    <div class="metric-label">Monthly Surplus</div>
                    <div class="cashflow-kpi-value" style="color:${surplus >= 0 ? 'var(--text)' : 'var(--red)'}">${surplus >= 0 ? inr(surplus) : '−' + inr(Math.abs(surplus))}</div>
                </div>
                <div class="cashflow-kpi">
                    <div class="metric-label">EMI / Income</div>
                    <div class="cashflow-kpi-value">${pct(ratio)}</div>
                </div>
                <div class="cashflow-kpi">
                    <div class="metric-label">Runway</div>
                    <div class="cashflow-kpi-value">${runway.toFixed(1)} mo</div>
                </div>
            </div>
            <div class="metric-label" style="margin-top:20px;">Money Flow Snapshot</div>
            <div class="cashflow-stack">
                ${segments.map(segment => {
        const share = household > 0 ? (segment.value / household) * 100 : 0;
        return `<button type="button" class="cashflow-segment" data-cash-segment data-label="${esc(segment.label)}" data-value="${segment.value}" data-share="${share.toFixed(1)}" style="width:${Math.max(share, 8)}%;background:${segment.color};">
                        <span class="cashflow-segment-inner"><span>${esc(segment.label)}</span><span class="cashflow-segment-value">${share.toFixed(0)}%</span></span>
                    </button>`;
    }).join('')}
            </div>
            <div class="cashflow-details">
                ${segments.map(segment => {
        const share = household > 0 ? (segment.value / household) * 100 : 0;
        return `<div class="cashflow-row">
                        <div><div class="cashflow-row-label">${esc(segment.label)}</div><div class="cashflow-row-hint">${esc(segment.hint)}</div></div>
                        <div class="cashflow-row-amount">${inr(segment.value)}</div>
                        <div class="cashflow-row-share">${share.toFixed(1)}% of income</div>
                    </div>`;
    }).join('')}
            </div>
        </div>`;
}

function renderScorecardSection(report, computed, ratio, runway, dpRatio) {
    const priceVerdict = report.property_assessment?.price_assessment?.verdict || '';
    const stressPassed = (report.stress_scenarios || []).filter(s => s.can_survive).length;
    const ratioZone = getZoneClass('ratio', ratio);
    const runwayZone = getZoneClass('runway', runway);
    const priceZone = getZoneClass('price', priceVerdict);
    const stressZone = getZoneClass('count', stressPassed);
    const gaugePercent = Math.min(ratio / 0.60, 1);
    const radius = 58;
    const circumference = Math.PI * radius;
    const dashOffset = circumference - (circumference * gaugePercent);
    const gaugeColor = ratioZone === 'safe' ? '#22c55e' : ratioZone === 'warn' ? '#f59e0b' : '#ef4444';
    const runwaySegments = Array.from({ length: 8 }, (_, index) => {
        const threshold = ((index + 1) / 8) * 12;
        return `<span class="runway-segment ${runway >= threshold ? `filled ${runwayZone}` : ''}"></span>`;
    }).join('');
    return `
        <div class="bank-email-insight" style="display:block; margin-bottom:18px;">
            ${stressPassed >= 3 ? 'The structure looks broadly resilient, but document and execution risks still matter.' : stressPassed >= 2 ? 'The structure is workable but clearly stretched, so one weak area can drag the whole decision down.' : 'Multiple weak points are active, so the deal needs better terms or better buffers.'}
        </div>
        <div class="scorecard-shell">
            <div class="scorecard-card">
                <div class="scorecard-topline">
                    <div><div class="metric-label">EMI Load</div><div class="scorecard-value">${pct(ratio)}</div></div>
                    <span class="scorecard-zone ${ratioZone}">${ratioZone === 'safe' ? 'Healthy' : ratioZone === 'warn' ? 'Stretched' : 'Danger'}</span>
                </div>
                <div class="gauge-shell">
                    <svg viewBox="0 0 160 96" width="100%" height="120" aria-hidden="true">
                        <path class="gauge-track" d="M20 80 A60 60 0 0 1 140 80"></path>
                        <path class="gauge-fill" d="M20 80 A60 60 0 0 1 140 80" style="stroke:${gaugeColor};stroke-dasharray:${circumference};stroke-dashoffset:${dashOffset};"></path>
                    </svg>
                    <div class="gauge-scale"><span>Easy</span><span>Borderline</span><span>Too High</span></div>
                </div>
                <div class="scorecard-note">This shows clearly how much household income the home loan consumes every month.</div>
            </div>
            <div class="scorecard-card">
                <div class="scorecard-topline">
                    <div><div class="metric-label">Safety Buffer</div><div class="scorecard-value">${runway.toFixed(1)} mo</div></div>
                    <span class="scorecard-zone ${runwayZone}">${runwayZone === 'safe' ? 'Comfortable' : runwayZone === 'warn' ? 'Thin' : 'Fragile'}</span>
                </div>
                <div class="runway-meter">${runwaySegments}</div>
                <div class="scorecard-note">${runway >= 6 ? 'Savings cover a meaningful disruption window.' : runway >= 3 ? 'There is some room for mistakes, but not much.' : 'One shock can pressure both EMI comfort and savings.'}</div>
            </div>
            <div class="scorecard-card full">
                <div class="scorecard-mini-grid">
                    <div class="scorecard-mini">
                        <div class="metric-label">Stress Tests</div>
                        <div class="scorecard-mini-value">${stressPassed}/4</div>
                        ${makeStatusChip(stressZone === 'safe' ? 'Resilient' : stressZone === 'warn' ? 'Mixed' : 'Vulnerable', stressZone)}
                    </div>
                    <div class="scorecard-mini">
                        <div class="metric-label">Savings Used</div>
                        <div class="scorecard-mini-value">${pct(dpRatio)}</div>
                        ${makeStatusChip(dpRatio < 0.60 ? 'Safe' : dpRatio < 0.80 ? 'High' : 'Risky', dpRatio < 0.60 ? 'safe' : dpRatio < 0.80 ? 'warn' : 'danger')}
                    </div>
                    <div class="scorecard-mini">
                        <div class="metric-label">Price Signal</div>
                        <div class="scorecard-mini-value">${priceVerdict ? startCase(priceVerdict) : 'Pending'}</div>
                        ${makeStatusChip(priceVerdict ? startCase(priceVerdict) : 'Awaiting', priceZone)}
                    </div>
                </div>
            </div>
        </div>`;
}

function renderPropertyAssessment(pa = {}) {
    const flags = pa.property_flags || [];
    return `
        <div class="p-card" style="grid-column: 1 / -1; margin-bottom: 0;">
            <div class="p-card-meta" style="font-size: 14px; color: var(--text);">${esc(getPropertySummary(pa))}</div>
        </div>
        <div class="p-card">
            <div class="p-card-label">Price / Sqft</div>
            <div class="p-card-val">${inr(pa.price_assessment?.price_per_sqft)}</div>
            <div class="p-card-meta">Your input price divided by carpet area.</div>
        </div>
        <div class="p-card">
            <div class="p-card-label">Area Median</div>
            <div class="p-card-val">${inr(pa.price_assessment?.area_median_per_sqft)}</div>
            <div class="p-card-meta">Locality benchmark for this property tier.</div>
        </div>
        ${flags.map(flag => `
            <div class="p-card" style="border-left: 3px solid ${flag.severity === 'critical' ? 'var(--red)' : flag.severity === 'high' ? 'var(--yellow)' : 'var(--accent)'}">
                <div class="p-card-label">${esc(startCase(flag.flag))}</div>
                <div class="p-card-val" style="font-size: 14px;">${flag.severity.toUpperCase()}</div>
                <div class="p-card-meta">${esc(flag.detail)}</div>
            </div>`).join('')}
        <div class="p-card" style="grid-column: 1 / -1;">
            ${renderOcCcStatus(pa.oc_cc_status)}
        </div>`;
}


function renderAccordionSection(summary, items, emptyMessage) {
    if (!items.length) return renderEmptyState(emptyMessage);
    return `<div class="accordion-stack">
        <div class="bank-email-insight" style="display:block; margin-bottom:0;">${esc(summary)}</div>
        ${items.map((item, index) => `<div class="accordion-card ${index === 0 ? 'open' : ''}">
            <button type="button" class="accordion-toggle" onclick="toggleAccordion(this)" aria-expanded="${index === 0 ? 'true' : 'false'}">
                <span class="accordion-toggle-main"><span class="accordion-title">${esc(item.title)}</span><span class="accordion-summary">${esc(item.summary)}</span></span>
                <span class="accordion-chevron">⌄</span>
            </button>
            <div class="accordion-body"><div class="detail-list">${item.details.map(detail => `<div class="detail-row"><span class="detail-icon">${esc(detail.icon || '•')}</span><div>${detail.status ? makeStatusChip(detail.status, detail.zone || 'info') : ''}<div style="margin-top:${detail.status ? '8px' : '0'}; line-height:1.65;">${esc(detail.text)}</div></div></div>`).join('')}</div></div>
        </div>`).join('')}
    </div>`;
}

function setupCashflowInteractions() {
    const tooltip = document.getElementById('cashflow-tooltip');
    const segments = Array.from(document.querySelectorAll('[data-cash-segment]'));
    if (!tooltip || !segments.length) return;
    const clearDim = () => segments.forEach(seg => seg.classList.remove('is-dimmed'));
    const hideTooltip = () => { tooltip.style.display = 'none'; clearDim(); };
    const showTooltip = (segment, event) => {
        segments.forEach(seg => seg.classList.toggle('is-dimmed', seg !== segment));
        tooltip.innerHTML = `<div class="cashflow-tooltip-title">${esc(segment.dataset.label || '')}</div><div class="cashflow-tooltip-value">${inr(Number(segment.dataset.value || 0))}</div><div class="cashflow-tooltip-meta">${esc(segment.dataset.share || '0')}% of total monthly income</div>`;
        tooltip.style.display = 'block';
        tooltip.style.left = `${Math.min((event?.clientX || segment.getBoundingClientRect().left) + 16, window.innerWidth - 220)}px`;
        tooltip.style.top = `${Math.max((event?.clientY || segment.getBoundingClientRect().top) - 18, 16)}px`;
    };
    segments.forEach(segment => {
        segment.addEventListener('mouseenter', event => showTooltip(segment, event));
        segment.addEventListener('mousemove', event => showTooltip(segment, event));
        segment.addEventListener('mouseleave', hideTooltip);
        segment.addEventListener('focus', event => showTooltip(segment, event));
        segment.addEventListener('blur', hideTooltip);
    });
}

function setSliderVisual(input) {
    if (!input) return;
    const min = Number(input.min || 0);
    const max = Number(input.max || 100);
    const value = Number(input.value || 0);
    const pctValue = ((value - min) / (max - min || 1)) * 100;
    input.style.background = `linear-gradient(90deg, #4f46e5 0%, #4f46e5 ${pctValue}%, #d7dbe7 ${pctValue}%, #d7dbe7 100%)`;
}

// ─── Signal Card metadata — Crimson / Amber / Slate palette ───────────────
const _SIG_META = [
    { bg: 'rgba(153,27,27,0.06)',  border: 'rgba(153,27,27,0.20)',  dot: '#991b1b', label: 'CRITICAL',  labelBg: 'rgba(153,27,27,0.10)', labelColor: '#991b1b' },
    { bg: 'rgba(180,83,9,0.06)',   border: 'rgba(180,83,9,0.20)',   dot: '#b45309', label: 'HIGH RISK', labelBg: 'rgba(180,83,9,0.10)',  labelColor: '#b45309' },
    { bg: 'rgba(71,85,105,0.05)',  border: 'rgba(71,85,105,0.16)',  dot: '#475569', label: 'CAUTION',   labelBg: 'rgba(71,85,105,0.09)', labelColor: '#475569' },
    { bg: 'rgba(71,85,105,0.03)',  border: 'rgba(71,85,105,0.10)',  dot: '#64748b', label: 'NOTE',      labelBg: 'rgba(100,116,139,0.08)', labelColor: '#64748b' },
];

function _sigCard(reason, i) {
    const meta  = _SIG_META[Math.min(i, _SIG_META.length - 1)];
    const parts = reason.split(/(?<=\.)\s+/);
    const title = (parts[0] || reason).replace(/\.$/, '');
    const body  = parts.slice(1).join(' ').trim() || '';
    const pctMatch = reason.match(/(\d+(?:\.\d+)?)\s*%/);
    const pctVal   = pctMatch ? parseFloat(pctMatch[1]) : 0;
    const hasBar   = pctVal > 25;
    const barW     = Math.min(pctVal, 100);
    const safeBar  = hasBar
        ? `<div class="sig-bar-wrap">
               <div class="sig-bar-header">
                   <span class="sig-bar-label mono">${esc(pctMatch[1])}% actual</span>
                   <span class="sig-bar-label mono sig-bar-threshold-label">30% safe threshold</span>
               </div>
               <div class="sig-bar-track">
                   <div class="sig-bar-fill" data-w="${barW}%" style="width:0%;background:${meta.dot};"></div>
                   <div class="sig-bar-threshold" style="left:30%"></div>
               </div>
           </div>`
        : '';
    return `<div class="sig-card" style="--sig-bg:${meta.bg};--sig-border:${meta.border};">
        <div class="sig-card-accent" style="background:${meta.dot};"></div>
        <div class="sig-card-body">
            <div class="sig-card-header">
                <div class="sig-card-title">${esc(title)}</div>
                <span class="sig-badge" style="color:${meta.labelColor};background:${meta.labelBg};border-color:${meta.dot}33;">${meta.label}</span>
            </div>
            ${body ? `<div class="sig-card-desc">${esc(body)}</div>` : ''}
            ${safeBar}
        </div>
    </div>`;
}

function renderSignalCards(elId, reasons, r) {
    const container = document.getElementById(elId);
    if (!container) return;
    const runway      = r?.computed_numbers?.emergency_runway_months || 0;
    const runwayColor = runway >= 6 ? '#065f46' : runway >= 3 ? '#b45309' : '#991b1b';
    const runwayLabel = runway >= 6 ? 'Comfortable' : runway >= 3 ? 'Thin' : 'Fragile';
    const runwaySegs  = Array.from({ length: 8 }, (_, k) => {
        const threshold = (k + 1) * 1.5;
        const filled    = runway >= threshold;
        return `<span class="rb-seg ${filled ? 'rb-seg-on' : ''}" style="${filled ? `background:${runwayColor};` : ''}"></span>`;
    }).join('');

    const runwayBadge = `<div class="runway-badge" style="--rb-color:${runwayColor};">
        <div class="rb-left">
            <span class="rb-num mono">${runway.toFixed(1)}</span>
            <span class="rb-unit">months emergency runway</span>
        </div>
        <div class="rb-meter">${runwaySegs}</div>
        <span class="rb-tag" style="color:${runwayColor};background:color-mix(in srgb,${runwayColor} 10%,transparent);border-color:${runwayColor}44;">${runwayLabel}</span>
    </div>`;

    const first4    = reasons.slice(0, 4);
    const rest      = reasons.slice(4);
    const cardsHTML = first4.map((reason, i) => _sigCard(reason, i)).join('');

    let moreHTML = '';
    if (rest.length) {
        const moreId   = elId + '-more';
        const toggleId = elId + '-toggle';
        moreHTML = `<div id="${moreId}" class="sig-more" style="display:none;">${rest.map((r2, i) => _sigCard(r2, i + 4)).join('')}</div>
        <button type="button" class="view-all-btn" id="${toggleId}" data-target="${elId}">
            <span>View All ${reasons.length} Factors</span>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
        </button>`;
    }

    container.innerHTML = `${runwayBadge}<div class="sig-stack" id="${elId}-stack">${cardsHTML}</div>${moreHTML}`;

    // Wire up toggle via event listener — no inline onclick
    const toggleBtn = container.querySelector('.view-all-btn');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => toggleSigMore(elId));
    }

    requestAnimationFrame(() => {
        container.querySelectorAll('.sig-bar-fill').forEach(bar => {
            bar.style.transition = 'width 0.8s cubic-bezier(0.16,1,0.3,1)';
            bar.style.width = bar.dataset.w;
        });
    });
}

function toggleSigMore(elId) {
    const more = document.getElementById(elId + '-more');
    const btn  = document.getElementById(elId + '-toggle');
    if (!more || !btn) return;
    const open = more.style.display !== 'none';
    more.style.display = open ? 'none' : 'block';
    btn.querySelector('span').textContent = open ? `View All Factors` : 'Show Less';
    btn.querySelector('svg').style.transform = open ? '' : 'rotate(180deg)';
}

function renderReport(r) {
    const c = r.computed_numbers || {};
    const v = (r.verdict || 'risky').toLowerCase();
    document.getElementById('compare-bar').style.display = 'block';

    const integrityScore = r.bias_detection?.integrity_score || 0;
    const integrityColor = integrityScore >= 80 ? 'var(--green)' : integrityScore >= 60 ? 'var(--yellow)' : 'var(--red)';
    document.getElementById('r-verdict').innerHTML = `
        <div class="verdict-display" aria-label="Analysis verdict: ${v}">
            <div class="verdict-word v-word ${v.toUpperCase()}">${esc(v).toUpperCase()}</div>
            <div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap;margin-bottom:16px;">
                <span style="font-family:var(--font-mono);font-size:14px;">${esc(r.verdict_reason || '')}</span>
                <span style="font-family:var(--font-mono);font-size:11px;padding:4px 12px;border-radius:20px;background:rgba(0,0,0,0.04);border:1px solid var(--border);">
                    AI Integrity: <strong style="color:${integrityColor}">${integrityScore}/100</strong>${r.bias_detection?.verdict_was_corrected ? ' · <span style="color:var(--red)">Corrected</span>' : ''}
                </span>
            </div>
            <div class="confidence-bar"><div class="confidence-fill" id="conf-fill" data-target="${Math.min((r.confidence_score || 0) * 10, 100)}%" style="width:0%"></div></div>
        </div>`;
    animateVerdictEntrance(document.querySelector('.v-word'));
    renderVerdictPulse(document.getElementById('r-verdict'), v);

    const rw = r.research_warnings || [];
    const rwDiv = document.getElementById('r-research-warnings');
    if (rw.length > 0) {
        rwDiv.style.display = 'block';
        rwDiv.innerHTML = rw.map((w, i) => `<div class="research-warning ${w.severity} warning-enter" style="animation-delay:${i * 80}ms"><div style="font-family:var(--font-mono); font-size:10px; text-transform:uppercase; color:var(--text-muted); margin-bottom:8px;">${w.severity} severity</div><div style="font-size:14px; color:var(--text); margin-bottom:8px;">${esc(w.stat)}</div><div style="font-family:var(--font-mono); font-size:10px; color:var(--text-muted)">Source: ${esc(w.source)}</div></div>`).join('');
    } else {
        rwDiv.style.display = 'none';
    }

    const household = (lastInput?.financial?.monthly_income || 0) + (lastInput?.financial?.spouse_income || 0);
    const existEMIs = lastInput?.financial?.existing_emis || 0;
    const expenses = lastInput?.financial?.monthly_expenses || 0;
    const ownership = c.monthly_ownership_cost || 0;
    const surplus = household - ownership - existEMIs - expenses;
    const emiR = c.emi_to_income_ratio || 0;
    const runway = c.emergency_runway_months || 0;
    const dpR = c.down_payment_to_savings_ratio || 0;

    try { document.getElementById('r-cashflow').innerHTML = renderCashflowSection(c, lastInput?.financial || {}); } catch (e) { document.getElementById('r-cashflow').innerHTML = '<div class="empty-state-note">Section unavailable</div>'; console.error('renderCashflowSection failed:', e); }
    try { document.getElementById('r-scorecard').innerHTML = renderScorecardSection(r, c, emiR, runway, dpR); } catch (e) { document.getElementById('r-scorecard').innerHTML = '<div class="empty-state-note">Section unavailable</div>'; console.error('renderScorecardSection failed:', e); }

    try {
        if (c.true_total_acquisition_cost) {
            document.getElementById('r-tco').innerHTML = `
            <div class="dtable-shell">
                <table class="dtable">
                    <tr><td>Base Property Price</td><td>${inr(lastInput?.property?.property_price)}</td></tr>
                    <tr><td>Taxes & Registration</td><td>${inr((c.total_acquisition_cost || 0) - (lastInput?.property?.property_price || 0))}</td></tr>
                    <tr><td>Estimated Interiors (12%)</td><td>${inr(c.interiors_estimated_cost)}</td></tr>
                    <tr class="total-row"><td>True Upfront Cost</td><td>${inr(c.true_total_acquisition_cost)}</td></tr>
                    <tr class="opp-cost-row"><td>10-Yr Down Payment Opp. Cost</td><td>${inr(c.down_payment_opportunity_cost_10yr)}</td></tr>
                </table>
            </div>`;

        } else {
            document.getElementById('r-tco').parentElement.style.display = 'none';
        }
    } catch (e) { document.getElementById('r-tco').innerHTML = '<div class="empty-state-note">Section unavailable</div>'; console.error('r-tco failed:', e); }

    try {
        document.getElementById('r-stress').innerHTML = (r.stress_scenarios || []).map(s => `
            <div class="p-card stress-card ${s.can_survive ? 'pass' : 'fail'}">
                <div class="p-card-label">${esc(startCase(s.name))}</div>
                <div class="p-card-val" style="color: ${s.can_survive ? 'var(--green)' : 'var(--red)'}">${esc(s.key_number)}</div>
                <div class="p-card-meta">${s.can_survive ? 'Survives: Buffer holds.' : 'At Risk: Scenario breaks budget.'}</div>
                ${(s.name || '').includes('job_loss') ? '<div class="ponr-timeline" id="ponr-container" style="margin-top:12px;"></div>' : ''}
            </div>`).join('');
        document.getElementById('r-stress').insertAdjacentHTML('afterbegin', `<div class="p-card" style="grid-column: 1 / -1; margin-bottom: 0;"><div class="p-card-meta" style="font-size:14px; color:var(--text);">${esc(getStressSummary(r.stress_scenarios || []))}</div></div>`);
        animateStressCards();
    } catch (e) { document.getElementById('r-stress').innerHTML = '<div class="empty-state-note">Section unavailable</div>'; console.error('r-stress failed:', e); }


    try {
        if (r.path_to_safe) {
            const ps = document.getElementById('r-path-to-safe');
            ps.style.display = 'block';
            ps.innerHTML = `<div class="rcard" style="border-color:var(--green);"><div style="font-family:var(--font-mono); font-size:12px; color:var(--green); letter-spacing:1px; margin-bottom:16px;">Path to Safe</div><div style="font-size:14px;color:var(--text); line-height:1.7;">To achieve a SAFE verdict, you must either increase your down payment by <strong style="color:var(--green)">${inr(r.path_to_safe.additional_down_payment_needed)}</strong> or reduce the property price to <strong style="color:var(--green)">${inr(r.path_to_safe.max_viable_property_price)}</strong>. At your current savings rate, gathering this extra down payment will take approximately <strong style="color:var(--text)">${r.path_to_safe.months_to_save_at_current_rate.toFixed(1)} months</strong>.</div></div>`;
        } else {
            document.getElementById('r-path-to-safe').style.display = 'none';
        }
    } catch (e) { console.error('r-path-to-safe failed:', e); }

    try { const pa = r.property_assessment || {}; document.getElementById('r-property').innerHTML = renderPropertyAssessment(pa); } catch (e) { document.getElementById('r-property').innerHTML = '<div class="empty-state-note">Section unavailable</div>'; console.error('r-property failed:', e); }

    try {
        const rvb = r.rent_vs_buy || {};
        const breakEven = (c.rent_vs_buy_break_even_years || 0).toFixed(1);
        const isLongBreakEven = parseFloat(breakEven) > 7;
        const insightLine = isLongBreakEven
            ? 'Break-even is long — buying only makes financial sense if you plan to stay 7+ years.'
            : 'The buy case catches up relatively quickly — ownership improves if you hold through the cycle.';
        const pct = Math.min(100, Math.round((parseFloat(breakEven) / 15) * 100));
        document.getElementById('r-rvb').innerHTML = `
        <div class="rvb-v2">
            <div class="rvb-cols">
                <div class="rvb-col rvb-col-rent">
                    <div class="rvb-col-label">If You Rent</div>
                    <div class="rvb-col-num">${inr(rvb.equivalent_monthly_rent)}</div>
                    <div class="rvb-col-sub">per month</div>
                </div>
                <div class="rvb-divider-v">
                    <span class="rvb-vs-badge">VS</span>
                </div>
                <div class="rvb-col rvb-col-buy">
                    <div class="rvb-col-label">If You Buy</div>
                    <div class="rvb-col-num">${inr(rvb.buying_monthly_cost)}</div>
                    <div class="rvb-col-sub">monthly ownership cost</div>
                </div>
            </div>
            <div class="rvb-breakeven-row">
                <div class="rvb-breakeven-label">Break-even point</div>
                <div class="rvb-breakeven-track">
                    <div class="rvb-breakeven-fill" style="width:${pct}%"></div>
                    <span class="rvb-breakeven-pin" style="left:${pct}%">${breakEven} yrs</span>
                </div>
                <div class="rvb-breakeven-range"><span>0 yrs</span><span>15 yrs</span></div>
            </div>
            <div class="rvb-insight-line ${isLongBreakEven ? 'rvb-insight-warn' : 'rvb-insight-ok'}">${insightLine}</div>
        </div>`;
    } catch (e) { document.getElementById('r-rvb').innerHTML = '<div class="empty-state-note">Section unavailable</div>'; console.error('r-rvb failed:', e); }

    function safeSetHTML(id, html) {
        const el = document.getElementById(id);
        if (el) el.innerHTML = html;
        else console.warn(`Element #${id} not found in DOM`);
    }

    try {
        safeSetHTML('r-challenges', renderAccordionSection(
            'These are the weak links in the story that buyers usually ignore when they are already emotionally committed.',
            (r.challenged_assumptions || []).map(item => ({
                title: startCase(item.severity),
                summary: item.challenge,
                details: [
                    { icon: '!', status: startCase(item.severity), zone: item.severity === 'critical' ? 'danger' : item.severity === 'high' ? 'warn' : 'info', text: item.impact || item.challenge },
                    { icon: '?', text: item.challenge }
                ]
            })),
            'No explicit challenged assumptions were returned, which usually means the run found fewer high-confidence contradictions.'
        ));
    } catch (e) { console.error('r-challenges failed:', e); }

    try {
        const allReasons = r.top_reasons || [];
        if (!allReasons.length) {
            safeSetHTML('r-reasons', renderEmptyState('Top reasons are still being synthesized.'));
        } else {
            renderSignalCards('r-reasons', allReasons, r);
        }
    } catch (e) { console.error('r-reasons failed:', e); }

    try {
        const actions = r.recommended_actions || [];
        if (!actions.length) {
            safeSetHTML('r-actions', renderEmptyState('No action list was returned for this scenario.'));
        } else {
            const taskMeta = [
                { badge: 'DO FIRST', color: '#991b1b', bg: 'rgba(153,27,27,0.08)', border: 'rgba(153,27,27,0.25)', leftBar: '#991b1b' },
                { badge: 'URGENT',   color: '#b45309', bg: 'rgba(180,83,9,0.08)',  border: 'rgba(180,83,9,0.25)',  leftBar: '#b45309' },
                { badge: 'PLAN',     color: '#475569', bg: 'rgba(71,85,105,0.07)', border: 'rgba(71,85,105,0.20)', leftBar: '#475569' },
                { badge: 'OPTIONAL', color: '#64748b', bg: 'rgba(100,116,139,0.05)', border: 'rgba(100,116,139,0.15)', leftBar: '#94a3b8' },
            ];
            const rows = actions.map((action, i) => {
                const m        = taskMeta[Math.min(i, taskMeta.length - 1)];
                const dotIdx   = action.indexOf('.');
                const titleRaw = dotIdx > 0 ? action.slice(0, dotIdx) : action;
                const detail   = dotIdx > 0 ? action.slice(dotIdx + 1).trim() : '';
                return `<div class="task-row" style="border-left:3px solid ${m.leftBar};">
                    <svg class="task-check" viewBox="0 0 20 20" fill="none" stroke="${m.color}" stroke-width="2">
                        <rect x="3" y="3" width="14" height="14" rx="3"/>
                        <polyline points="6.5 10 9 12.5 13.5 7.5" stroke="${m.color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" opacity="0.35"/>
                    </svg>
                    <div class="task-body">
                        <div class="task-title">${esc(titleRaw)}</div>
                        ${detail ? `<div class="task-detail">${esc(detail)}</div>` : ''}
                    </div>
                    <span class="task-badge" style="color:${m.color};background:${m.bg};border:1px solid ${m.border};">${m.badge}</span>
                </div>`;
            }).join('');
            safeSetHTML('r-actions', `<div class="task-list">${rows}</div>`);
        }
    } catch (e) { console.error('r-actions failed:', e); }

    try { safeSetHTML('r-reasoning-insight', `<strong>Read the narrative only after the summary cards.</strong>${esc(getAffordabilitySummary(surplus, emiR, runway))}<div style="margin-top:10px;">This section preserves the full audit, but the summary cards above should do most of the decision work.</div>`); } catch (e) { console.error('r-reasoning-insight failed:', e); }

    try { safeSetHTML('r-reasoning', r.full_reasoning ? `<div class="rcard" style="padding:20px; line-height:1.8;">${esc(r.full_reasoning).replace(/\n/g, '<br>')}</div>` : renderEmptyState('Full reasoning was not included in this response.')); } catch (e) { console.error('r-reasoning failed:', e); }

    try {
        const blindSpots = r.blind_spots || [];
        if (!blindSpots.length) {
            safeSetHTML('r-blind', renderEmptyState('No blind spots were flagged in this run.'));
        } else {
            const flashlightSVG = `<svg class="intel-icon" viewBox="0 0 24 24" fill="none" stroke="#b45309" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M8 13V4.5a1.5 1.5 0 0 1 3 0V13"/>
                <path d="M11 13v-2.5a1.5 1.5 0 0 1 3 0V13"/>
                <path d="M14 13v-1a1.5 1.5 0 0 1 3 0v3a6 6 0 0 1-6 6H9a7 7 0 0 1-7-7 1 1 0 0 1 1-1h3"/>
                <path d="M5 3 3 5"/>
                <path d="m3 3 2 2"/>
            </svg>`;
            const alerts = blindSpots.map(item => {
                const dotIdx   = item.indexOf('.');
                const titleRaw = dotIdx > 0 ? item.slice(0, dotIdx) : item;
                const body     = dotIdx > 0 ? item.slice(dotIdx + 1).trim() : '';
                const hasBody  = body.length > 0;
                return `<div class="intel-alert">
                    ${flashlightSVG}
                    <div class="intel-body">
                        <div class="intel-title">${esc(titleRaw)}</div>
                        ${hasBody ? `<div class="intel-desc">${esc(body)}</div>` : ''}
                    </div>
                    <span class="intel-tag">BLINDSPOT</span>
                </div>`;
            }).join('');
            safeSetHTML('r-blind', `<div class="intel-list">${alerts}</div>`);
        }
    } catch (e) { console.error('r-blind failed:', e); }

    try {
        safeSetHTML('r-emo', renderAccordionSection(
            'Signals that the choice may be driven by urgency, sunk cost, optimism, or confirmation-seeking.',
            (r.emotional_flags || []).map(item => ({ title: startCase(item), summary: item, details: [{ icon: '⚑', status: 'Bias Risk', zone: 'warn', text: item }] })),
            'No cognitive or emotional flags were returned.'
        ));
    } catch (e) { console.error('r-emo failed:', e); }

    let covMsg = "";
    if (r.benchmark_coverage?.coverage_level === "default") covMsg = `<span style="color:var(--red)">⚠ ${esc(r.benchmark_coverage.warning)}</span> · `;
    else if (r.benchmark_coverage?.coverage_level === "partial") covMsg = `<span style="color:var(--yellow)">⚠ Partial benchmark data</span> · `;
    safeSetHTML('r-meta', `<div class="bank-email-insight" style="display:block; margin-bottom:18px;">Use this metadata to judge how much confidence to place in the output and where you may still need manual verification.</div>${covMsg}Analysis in ${r._meta?.pipeline_time_seconds || '?'}s · ${(r.data_sources || []).join(' · ')}`);


    initWhatIf(r);

    setupCashflowInteractions();
    const jobLossScenario = (r.stress_scenarios || []).find(s => (s.name || '').includes('job_loss'));
    renderPointOfNoReturn(document.getElementById('ponr-container'), jobLossScenario || { can_survive: runway >= 6, months_before_default: Math.max(Math.round(runway), 0) });
    requestAnimationFrame(() => drawNetWorthMountain(document.getElementById('mountain-canvas'), c, lastInput));
    initTimelineScenarios(r, lastInput);
    setReportPage(0);
}

// --- WHAT-IF SLIDERS ---
function initWhatIf(report) {
    const c = report.computed_numbers || {};
    whatIfOriginal = { ...c }; lastInput_cached = { ...lastInput };
    const p = lastInput.property;

    const dp = document.getElementById('wi-dp');
    dp.min = Math.max(0, p.down_payment_available - 1000000); dp.max = p.property_price * 0.9; dp.value = p.down_payment_available;

    const pr = document.getElementById('wi-price');
    pr.min = Math.round(p.property_price * 0.8 / 50000) * 50000; pr.max = Math.round(p.property_price * 1.1 / 50000) * 50000; pr.value = p.property_price;

    const tn = document.getElementById('wi-tenure');
    tn.value = p.loan_tenure_years || 20;

    document.getElementById('sensitivity-section').style.display = 'block';
    ['wi-dp', 'wi-price', 'wi-tenure'].forEach(id => {
        const input = document.getElementById(id);
        input.oninput = onWhatIfSlide;
        document.getElementById(id + '-val').textContent = id === 'wi-tenure' ? input.value + ' yrs' : inr(+input.value);
        setSliderVisual(input);
    });
    updateWhatIfDisplay(c, c);
}

function onWhatIfSlide() {
    document.getElementById('wi-dp-val').textContent = inr(+document.getElementById('wi-dp').value);
    document.getElementById('wi-price-val').textContent = inr(+document.getElementById('wi-price').value);
    document.getElementById('wi-tenure-val').textContent = document.getElementById('wi-tenure').value + ' yrs';
    ['wi-dp', 'wi-price', 'wi-tenure'].forEach(id => setSliderVisual(document.getElementById(id)));
    clearTimeout(whatIfDebounceTimer);
    whatIfDebounceTimer = setTimeout(fetchWhatIf, 400);
}

async function fetchWhatIf() {
    if (!lastInput_cached) return;
    const fin = lastInput_cached.financial; const prop = lastInput_cached.property;
    const params = new URLSearchParams({
        monthly_income: fin.monthly_income, spouse_income: fin.spouse_income || 0,
        existing_emis: fin.existing_emis || 0, monthly_expenses: fin.monthly_expenses || 0,
        liquid_savings: fin.liquid_savings || 0, property_price: +document.getElementById('wi-price').value,
        down_payment: +document.getElementById('wi-dp').value, loan_tenure_years: +document.getElementById('wi-tenure').value,
        interest_rate: prop.expected_interest_rate || 8.5, carpet_area_sqft: prop.carpet_area_sqft || 650,
        is_ready_to_move: prop.is_ready_to_move !== false, location_area: prop.location_area || ''
    });
    try {
        const res = await fetch(`${API}/api/v1/calculate?${params}`);
        if (res.ok) updateWhatIfDisplay(await res.json(), whatIfOriginal);
    } catch (e) { }
}

function updateWhatIfDisplay(curr, orig) {
    const hh = (lastInput_cached?.financial?.monthly_income || 0) + (lastInput_cached?.financial?.spouse_income || 0);
    const fixed = (lastInput_cached?.financial?.existing_emis || 0) + (lastInput_cached?.financial?.monthly_expenses || 0);
    const animateValueChange = (id, value) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.innerHTML = `<span class="value-ticker">${esc(value)}</span>`;
        const card = document.querySelector(`[data-output-card="${id}"]`);
        if (card) {
            card.classList.remove('updated');
            requestAnimationFrame(() => {
                card.classList.add('updated');
                setTimeout(() => card.classList.remove('updated'), 650);
            });
        }
    };

    const setM = (id, cur, ori, fmt, hBetter) => {
        animateValueChange(id, fmt(cur));
        const dEl = document.getElementById(id + '-d');
        if (!dEl) return;
        const diff = cur - ori;
        if (Math.abs(diff) < 0.01) { dEl.textContent = ''; return; }
        const sign = diff > 0 ? '+' : '';
        dEl.textContent = `${sign}${fmt(diff)} vs orig`;
        dEl.className = 'wm-delta ' + ((hBetter ? diff > 0 : diff < 0) ? 'better' : 'worse');
    };

    setM('wm-emi', curr.monthly_emi, orig.monthly_emi, inr, false);
    setM('wm-surplus', hh - curr.monthly_emi - fixed, hh - orig.monthly_emi - fixed, inr, true);
    setM('wm-runway', curr.emergency_runway_months, orig.emergency_runway_months, v => v.toFixed(1) + 'mo', true);

    const ratioEl = document.getElementById('wm-ratio');
    if (ratioEl) {
        animateValueChange('wm-ratio', (curr.emi_to_income_ratio * 100).toFixed(1) + '%');
        ratioEl.style.color = curr.emi_to_income_ratio < 0.3 ? 'var(--green)' : curr.emi_to_income_ratio < 0.45 ? 'var(--yellow)' : 'var(--red)';
    }
    const rDiff = curr.emi_to_income_ratio - orig.emi_to_income_ratio;
    const rDel = document.getElementById('wm-ratio-d');
    if (rDel && Math.abs(rDiff) > 0.001) {
        rDel.textContent = `${rDiff > 0 ? '+' : ''}${(rDiff * 100).toFixed(1)}% vs orig`;
        rDel.className = 'wm-delta ' + (rDiff < 0 ? 'better' : 'worse');
    } else if (rDel) { rDel.textContent = ''; }
}

function resetWhatIf() { if (whatIfOriginal) initWhatIf({ computed_numbers: whatIfOriginal }); }

// --- COMPARISON ---
function startComparison() { document.getElementById('compare-form').style.display = 'block'; document.getElementById('compare-bar').style.display = 'none'; }
function cancelComparison() { document.getElementById('compare-form').style.display = 'none'; document.getElementById('compare-bar').style.display = 'block'; }
function clearComparison() { document.getElementById('compare-results').style.display = 'none'; document.getElementById('compare-bar').style.display = 'block'; }

async function runComparison() {
    const p2 = +document.getElementById('c_price').value; const l2 = getVal('c_loc');
    if (!p2 || !l2) return alert('Price and Location required');
    const body = { financial: { ...lastInput.financial }, property: { ...lastInput.property, property_price: p2, location_area: l2, down_payment_available: getNum('c_dp') || Math.round(p2 * .2), carpet_area_sqft: getNum('c_sqft') || 650, is_ready_to_move: getVal('c_rdy') === 'true', builder_name: getVal('c_bld') } };
    const btn = document.querySelector('#compare-form .btn-primary'); btn.disabled = true; btn.textContent = 'Analyzing...';
    try {
        const res = await fetch(`${API}/api/v1/analyze`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        if (res.ok) renderComparisonTable(lastReport, await res.json());
    } finally { btn.disabled = false; btn.textContent = 'Analyze Property 2'; }
}

function renderComparisonTable(r1, r2) {
    comparisonReport = r2;
    const c1 = r1.computed_numbers || {};
    const c2 = r2.computed_numbers || {};
    const loc1 = lastInput?.property?.location_area || 'Property 1';
    const loc2 = document.getElementById('c_loc').value || 'Property 2';

    const better = (v1, v2, higherIsBetter) => {
        if (v1 == null || v2 == null) return 'tie';
        return higherIsBetter ? (v1 > v2 ? '1' : v1 < v2 ? '2' : 'tie')
            : (v1 < v2 ? '1' : v1 > v2 ? '2' : 'tie');
    };

    const verdictOrder = { safe: 0, risky: 1, reconsider: 2 };
    const v1 = r1.verdict || 'risky';
    const v2 = r2.verdict || 'risky';
    const verdictBetter = verdictOrder[v1] <= verdictOrder[v2] ? '1' : '2';
    const ss1 = (r1.stress_scenarios || []).filter(s => s.can_survive).length;
    const ss2 = (r2.stress_scenarios || []).filter(s => s.can_survive).length;
    const pv1 = r1.property_assessment?.price_assessment?.premium_over_market_pct || 0;
    const pv2 = r2.property_assessment?.price_assessment?.premium_over_market_pct || 0;

    const surplus1 = Math.max((lastInput?.financial?.monthly_income || 0) + (lastInput?.financial?.spouse_income || 0) - (c1.monthly_ownership_cost || 0) - (lastInput?.financial?.existing_emis || 0) - (lastInput?.financial?.monthly_expenses || 0), 0);
    const surplus2 = Math.max((lastInput?.financial?.monthly_income || 0) + (lastInput?.financial?.spouse_income || 0) - (c2.monthly_ownership_cost || 0) - (lastInput?.financial?.existing_emis || 0) - (lastInput?.financial?.monthly_expenses || 0), 0);

    const rows = [
        { metric: 'Overall Verdict', v1: v1.toUpperCase(), v2: v2.toUpperCase(), better: verdictBetter, isVerdict: true },
        { metric: 'EMI / Income', v1: pct(c1.emi_to_income_ratio), v2: pct(c2.emi_to_income_ratio), better: better(c1.emi_to_income_ratio, c2.emi_to_income_ratio, false) },
        { metric: 'Emergency Runway', v1: (c1.emergency_runway_months || 0).toFixed(1) + ' mo', v2: (c2.emergency_runway_months || 0).toFixed(1) + ' mo', better: better(c1.emergency_runway_months, c2.emergency_runway_months, true) },
        { metric: 'Stress Tests Passed', v1: ss1 + ' / 4', v2: ss2 + ' / 4', better: better(ss1, ss2, true) },
        { metric: 'Monthly Surplus', v1: inr(surplus1), v2: inr(surplus2), better: better(surplus1, surplus2, true) },
        { metric: 'Monthly EMI', v1: inr(c1.monthly_emi || 0), v2: inr(c2.monthly_emi || 0), better: better(c1.monthly_emi, c2.monthly_emi, false) },
        { metric: 'Price vs Market', v1: (pv1 >= 0 ? '+' : '') + pv1.toFixed(1) + '%', v2: (pv2 >= 0 ? '+' : '') + pv2.toFixed(1) + '%', better: better(pv1, pv2, false) },
        { metric: 'Rent-vs-Buy Break-Even', v1: (c1.rent_vs_buy_break_even_years || 0).toFixed(1) + ' yrs', v2: (c2.rent_vs_buy_break_even_years || 0).toFixed(1) + ' yrs', better: better(c1.rent_vs_buy_break_even_years, c2.rent_vs_buy_break_even_years, false) },
        { metric: 'True Acquisition Cost', v1: inr(c1.true_total_acquisition_cost || c1.total_acquisition_cost || 0), v2: inr(c2.true_total_acquisition_cost || c2.total_acquisition_cost || 0), better: better(c1.true_total_acquisition_cost, c2.true_total_acquisition_cost, false) }
    ];

    const wins1 = rows.filter(r => r.better === '1').length;
    const wins2 = rows.filter(r => r.better === '2').length;
    const overall = wins1 >= wins2 ? '1' : '2';
    const vColors = { safe: 'var(--green)', risky: 'var(--yellow)', reconsider: 'var(--red)' };

    let html = `<table style="width:100%;border-collapse:collapse;font-size:13px">
        <thead><tr>
            <th style="text-align:left;padding:10px 0;color:var(--text-muted);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;border-bottom:1px solid var(--border)">Metric</th>
            <th style="text-align:center;padding:10px;color:var(--text-muted);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;border-bottom:1px solid var(--border)">${esc(loc1)}</th>
            <th style="text-align:center;padding:10px;color:var(--text-muted);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;border-bottom:1px solid var(--border)">${esc(loc2)}</th>
        </tr></thead><tbody>`;

    rows.forEach(row => {
        const c1w = row.better === '1';
        const c2w = row.better === '2';
        html += `<tr>
            <td style="padding:10px 0;color:var(--text-dim);border-bottom:1px solid var(--border)">${esc(row.metric)}</td>
            <td style="text-align:center;padding:10px;border-bottom:1px solid var(--border);font-family:var(--font-mono);color:${row.isVerdict ? (vColors[r1.verdict] || 'var(--text)') : c1w ? 'var(--green)' : 'var(--text)'};font-weight:${c1w ? '700' : '400'}">
                ${esc(row.v1)}${c1w ? ' ✓' : ''}
            </td>
            <td style="text-align:center;padding:10px;border-bottom:1px solid var(--border);font-family:var(--font-mono);color:${row.isVerdict ? (vColors[r2.verdict] || 'var(--text)') : c2w ? 'var(--green)' : 'var(--text)'};font-weight:${c2w ? '700' : '400'}">
                ${esc(row.v2)}${c2w ? ' ✓' : ''}
            </td>
        </tr>`;
    });

    const winnerName = overall === '1' ? esc(loc1) : esc(loc2);
    html += `<tr style="background:rgba(34,197,94,0.07)">
        <td style="padding:12px 0;font-weight:700;color:var(--text)">Overall Recommendation</td>
        <td colspan="2" style="text-align:center;padding:12px;font-weight:700;color:var(--green)">
            ${winnerName} wins on ${overall === '1' ? wins1 : wins2} of ${rows.length} metrics
        </td>
    </tr></tbody></table>`;

    document.getElementById('compare-results').innerHTML = html;
    document.getElementById('compare-form').style.display = 'none';
    document.getElementById('compare-results').style.display = 'block';
    document.getElementById('compare-results').scrollIntoView({ behavior: 'smooth' });
}

// --- SHARE & EXPORT ---
function getUserId() {
    let uid = localStorage.getItem('niv_uid');
    if (!uid) { uid = 'anon_' + Date.now(); localStorage.setItem('niv_uid', uid); }
    return uid;
}

async function autoSaveReport(report) {
    try {
        const res = await fetch(`${API}/api/v1/reports`, {
            method: 'POST', headers: { 'Content-Type': 'application/json', 'X-User-Id': getUserId() },
            body: JSON.stringify({ report: report, input: lastInput })
        });
        if (res.ok) {
            const data = await res.json();
            if (data.id) {
                currentShareUrl = `${window.location.origin}/report/${data.id}`;
                document.getElementById('share-url-input').value = currentShareUrl;
                document.getElementById('share-bar').style.display = 'block';
            }
        }
    } catch (e) { }
}

function copyShareUrl() {
    navigator.clipboard.writeText(currentShareUrl).then(() => {
        const b = document.getElementById('copy-btn'); b.textContent = '✓ Copied';
        setTimeout(() => b.textContent = 'Copy Link', 2000);
    });
}

function loadDemoScenario() {
    const fields = {
        monthly_income: '150000', spouse_income: '80000',
        liquid_savings: '3500000', existing_emis: '12000',
        monthly_expenses: '55000', property_price: '12000000',
        location_area: 'Andheri West', down_payment_available: '2400000',
        loan_tenure_years: '20', expected_interest_rate: '8.75',
        employment_type: 'salaried', years_in_current_job: '4',
        dependents: '1', configuration: '2BHK', carpet_area_sqft: '680',
        is_ready_to_move: 'false', builder_name: 'Lodha Group',
        possession_date: '06/2027', buyer_gender: 'male',
        is_rera_registered: 'true', expected_annual_growth_pct: '8',
    };
    Object.entries(fields).forEach(([id, val]) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.value = val;
        if (el.tagName === 'INPUT') el.dispatchEvent(new Event('input'));
    });
    goStep(1);
    updateFinancialHealth();
    updateEMIPreview();
}

async function sendReportToWhatsApp() {
    const phoneInput = document.getElementById('wa-phone-input');
    const btn = document.getElementById('wa-send-btn');
    const status = document.getElementById('wa-send-status');
    const raw = (phoneInput?.value || '').replace(/\D/g, '');
    if (raw.length !== 10) {
        status.style.display = 'block';
        status.className = 'wa-send-status wa-status-error';
        status.textContent = 'Please enter a valid 10-digit Indian mobile number.';
        return;
    }
    const phone = '91' + raw;
    btn.disabled = true;
    btn.textContent = 'Sending…';
    status.style.display = 'none';
    try {
        const res = await fetch(`${API}/api/v1/whatsapp/send`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone_number: phone, report: lastReport, share_url: currentShareUrl || '' }),
        });
        const data = await res.json();
        if (res.ok && data.status === 'sent') {
            status.style.display = 'block';
            status.className = 'wa-send-status wa-status-ok';
            status.textContent = '✓ Report sent to +91 ' + raw.slice(0, 5) + 'XXXXX';
            btn.textContent = 'Sent ✓';
        } else if (res.status === 503) {
            status.style.display = 'block';
            status.className = 'wa-send-status wa-status-dev';
            status.innerHTML = '🚧 <strong>WhatsApp — Coming Soon</strong><br><span style="font-weight:400;">This feature is almost ready. We\'re finishing our Meta Business verification. Check back in a few days — it\'ll be worth the wait!</span>';
            btn.disabled = false;
            btn.textContent = 'Send Report';
        } else {
            throw new Error(data.detail || 'Send failed');
        }
    } catch (err) {
        status.style.display = 'block';
        if (err.message && (err.message.includes('503') || err.message.includes('not enabled'))) {
            status.className = 'wa-send-status wa-status-dev';
            status.innerHTML = '🚧 <strong>WhatsApp — Coming Soon</strong><br><span style="font-weight:400;">We\'re almost there. Meta Business API credentials are being set up. Your report will land on WhatsApp very soon!</span>';
        } else {
            status.className = 'wa-send-status wa-status-error';
            status.textContent = 'Could not send right now. Please try the Copy Link option above.';
        }
        btn.disabled = false;
        btn.textContent = 'Send Report';
    }
}

function shareWhatsApp() {
    if (!currentShareUrl || !lastReport) return;
    const verdict = (lastReport.verdict || 'risky').toUpperCase();
    const location = lastInput?.property?.location_area || 'a property';
    const price = lastInput?.property?.property_price;
    const priceStr = price ? inr(price) : 'a property';
    const emi = lastReport.computed_numbers?.monthly_emi;
    const emiStr = emi ? inr(Math.round(emi)) + '/month EMI' : '';
    const reason = lastReport.verdict_reason || '';
    const msg = [
        `*NIV AI Property Analysis*`,
        ``,
        `Property: ${priceStr} in ${location}`,
        `Verdict: *${verdict}* (${lastReport.confidence_score}/10 confidence)`,
        emiStr ? `Monthly EMI: ${emiStr}` : '',
        reason ? `Reason: ${reason.substring(0, 100)}` : '',
        ``,
        `AI Integrity Score: ${lastReport.bias_detection?.integrity_score || '?'}/100`,
        ``,
        `Full analysis → ${currentShareUrl}`,
        `_(Analyzed by NIV AI — unbiased home buying intelligence)_`
    ].filter(Boolean).join('\n');
    window.open(`https://wa.me/?text=${encodeURIComponent(msg)}`, '_blank', 'noopener,noreferrer');
}

function downloadPDF() {
    document.getElementById('print-date').textContent = new Date().toLocaleDateString('en-IN');
    document.getElementById('print-meta').textContent = `${lastInput?.property?.location_area} · ${inr(lastInput?.property?.property_price)}`;
    window.print();
}

function downloadLinkedInCard() {
    if (!lastReport) return;
    const cvs = document.createElement('canvas');
    cvs.width = 1200; cvs.height = 628;
    const ctx = cvs.getContext('2d');

    const BG = '#080810', SURFACE = '#0e0e1a', BORDER = '#1c1c2e';
    const ACCENT = '#7c6af7', GREEN = '#22c55e', YELLOW = '#f59e0b', RED = '#ef4444';
    const TEXT = '#f0eeff', MUTED = '#9896b8';

    const rr = (x, y, w, h, r) => {
        if (ctx.roundRect) { ctx.roundRect(x, y, w, h, r); }
        else { ctx.rect(x, y, w, h); }
    };

    // Background
    ctx.fillStyle = BG; ctx.fillRect(0, 0, 1200, 628);

    // Left accent bar
    ctx.fillStyle = ACCENT; ctx.fillRect(0, 0, 6, 628);

    // Header band
    ctx.fillStyle = SURFACE; ctx.fillRect(0, 0, 1200, 120);
    ctx.fillStyle = BORDER; ctx.fillRect(0, 120, 1200, 1);

    ctx.fillStyle = ACCENT; ctx.font = 'bold 18px Arial'; ctx.fillText('NIV AI', 40, 45);
    ctx.fillStyle = MUTED; ctx.font = '14px Arial';
    ctx.fillText('Home Buying Decision Intelligence', 40, 68);
    ctx.fillText('My Financial Stress Test Results', 40, 92);

    // Verdict
    const v = (lastReport.verdict || 'risky').toLowerCase();
    const vColor = v === 'safe' ? GREEN : v === 'reconsider' ? RED : YELLOW;
    ctx.fillStyle = vColor; ctx.font = 'bold 64px Arial';
    ctx.fillText(v.toUpperCase(), 40, 200);

    // Confidence badge
    ctx.fillStyle = BORDER; ctx.beginPath(); rr(40, 215, 200, 32, 6); ctx.fill();
    ctx.fillStyle = MUTED; ctx.font = '14px Arial';
    ctx.fillText('Confidence: ' + (lastReport.confidence_score || '?') + '/10', 55, 236);

    const scenarios = lastReport.stress_scenarios || [];
    const passed = scenarios.filter(s => s.can_survive).length;

    ctx.fillStyle = TEXT; ctx.font = 'bold 22px Arial';
    ctx.fillText('Stress Tests: ' + passed + ' of ' + scenarios.length + ' Survived', 40, 295);

    const scenarioLabels = {
        'job_loss_6_months': 'Job Loss (6 months)',
        'interest_rate_hike_2pct': 'Rate Hike (+2%)',
        'unexpected_expense_5L': 'Emergency ₹5L Expense',
        'income_stagnation_3_years': 'Income Stagnation (3yr)'
    };

    scenarios.forEach((s, i) => {
        const y = 330 + i * 65;
        const color = s.can_survive ? GREEN : RED;
        const label = scenarioLabels[s.name] || (s.name || '').replace(/_/g, ' ');

        ctx.fillStyle = BORDER; ctx.beginPath(); rr(40, y, 500, 48, 6); ctx.fill();
        ctx.fillStyle = color; ctx.beginPath(); rr(40, y, s.can_survive ? 500 : 200, 48, 6); ctx.fill();
        ctx.fillStyle = '#fff'; ctx.font = 'bold 16px Arial';
        ctx.fillText((s.can_survive ? '✓ ' : '✗ ') + label, 56, y + 30);
        ctx.fillStyle = MUTED; ctx.font = '13px Arial';
        ctx.fillText((s.key_number || '').substring(0, 55), 560, y + 30);
    });

    // Right metrics panel
    const emiRatio = lastReport.computed_numbers?.emi_to_income_ratio || 0;
    const runway = lastReport.computed_numbers?.emergency_runway_months || 0;

    ctx.fillStyle = SURFACE; ctx.beginPath(); rr(760, 145, 400, 380, 10); ctx.fill();
    ctx.strokeStyle = BORDER; ctx.lineWidth = 1; ctx.stroke();
    ctx.fillStyle = MUTED; ctx.font = 'bold 11px Arial'; ctx.fillText('KEY METRICS', 800, 180);

    const metrics = [
        { label: 'EMI / Income', value: (emiRatio * 100).toFixed(1) + '%', color: emiRatio < 0.30 ? GREEN : emiRatio < 0.45 ? YELLOW : RED },
        { label: 'Emergency Runway', value: runway.toFixed(1) + ' months', color: runway >= 6 ? GREEN : runway >= 3 ? YELLOW : RED },
        { label: 'Stress Tests', value: passed + '/' + scenarios.length, color: passed >= 3 ? GREEN : passed >= 2 ? YELLOW : RED }
    ];

    metrics.forEach((m, i) => {
        const y = 210 + i * 85;
        ctx.fillStyle = BORDER; ctx.beginPath(); rr(790, y, 340, 68, 8); ctx.fill();
        ctx.fillStyle = MUTED; ctx.font = '12px Arial'; ctx.fillText(m.label, 810, y + 24);
        ctx.fillStyle = m.color; ctx.font = 'bold 28px Arial'; ctx.fillText(m.value, 810, y + 56);
    });

    // Footer
    ctx.fillStyle = BORDER; ctx.fillRect(0, 590, 1200, 1);
    ctx.fillStyle = MUTED; ctx.font = '13px Arial';
    ctx.fillText('Niv AI — Home Buying Decision Intelligence', 40, 616);
    ctx.fillText('Analysis for informational purposes only. Not financial advice.', 700, 616);

    const a = document.createElement('a');
    a.download = `niv-ai-stress-test-${Date.now()}.png`;
    a.href = cvs.toDataURL('image/png');
    a.click();
}

// --- OUTCOME TRACKING ---
function maybeShowOutcomePrompt() {
    const createdStr = window.__NIV_REPORT_CREATED__;
    if (!createdStr || localStorage.getItem('outcome_' + window.__NIV_REPORT_ID__)) return;
    const ageDays = Math.floor((new Date() - new Date(createdStr)) / 86400000);
    if (ageDays < 7 || ageDays > 180) return;

    const popup = document.createElement('div');
    popup.style.cssText = 'position:fixed;bottom:20px;right:20px;background:#0e0e1a;border:1px solid #2a2a40;padding:20px;border-radius:12px;z-index:9999;';

    const title = document.createElement('p');
    title.style.cssText = 'margin-bottom:10px;font-size:14px;font-weight:bold;color:#f1f5f9;';
    title.textContent = 'What did you decide?';

    const boughtBtn = document.createElement('button');
    boughtBtn.style.cssText = 'margin:5px;padding:5px 10px;background:#052010;color:#22c55e;border:1px solid #0f3020;border-radius:5px;cursor:pointer;';
    boughtBtn.textContent = 'Bought it';
    boughtBtn.addEventListener('click', () => submitOutcome('bought', boughtBtn));

    const walkBtn = document.createElement('button');
    walkBtn.style.cssText = 'margin:5px;padding:5px 10px;background:#180808;color:#ef4444;border:1px solid #2a1010;border-radius:5px;cursor:pointer;';
    walkBtn.textContent = 'Walked away';
    walkBtn.addEventListener('click', () => submitOutcome('walked_away', walkBtn));

    const closeBtn = document.createElement('button');
    closeBtn.style.cssText = 'position:absolute;top:5px;right:10px;background:none;border:none;color:#9896b8;cursor:pointer;font-size:16px;';
    closeBtn.textContent = '×';
    closeBtn.addEventListener('click', () => popup.remove());

    popup.appendChild(title);
    popup.appendChild(boughtBtn);
    popup.appendChild(walkBtn);
    popup.appendChild(closeBtn);
    document.body.appendChild(popup);
}

async function submitOutcome(outcome, btn) {
    const id = window.__NIV_REPORT_ID__;
    if (id) {
        try { await fetch(`${API}/api/v1/reports/${id}/outcome`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ outcome }) }); } catch (e) { }
        localStorage.setItem('outcome_' + id, outcome);
    }
    btn.parentElement.innerHTML = '<p style="color:#22c55e">Thanks for your feedback!</p>';
    setTimeout(() => btn.parentElement?.remove(), 2000);
}

function reset() {
    document.getElementById('report-view').style.display = 'none';
    document.getElementById('form-section').style.display = 'block';
    document.getElementById('bank-email-modal').style.display = 'none';
    document.getElementById('friction-gate').style.display = 'none';
    document.body.classList.remove('report-visible');
    ['a1', 'a2', 'a3', 'a4', 'a5', 'a6'].forEach(id => setA(id, 'waiting'));
    window.scrollTo(0, 0);
}

// ─────────────────────────────────────────────────────────────────
// FEATURE 1: COUNTER-OFFER PDF
// ─────────────────────────────────────────────────────────────────
async function downloadCounterOffer() {
    if (!lastReport || !lastInput) return;
    const btn = document.getElementById('counter-offer-btn');
    btn.textContent = '⏳ Generating PDF...';
    btn.disabled = true;
    try {
        const res = await fetch(`${API}/api/v1/tools/counter-offer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ report: lastReport, input: lastInput, buyer_name: 'Home Buyer' })
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'PDF generation failed');
        }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        const loc = lastInput?.property?.location_area || 'property';
        a.download = `NIV_AI_Counter_Offer_${loc.replace(/\s+/g, '_')}.pdf`;
        a.href = url;
        a.click();
        URL.revokeObjectURL(url);
    } catch (e) {
        alert('Could not generate counter-offer: ' + e.message);
    } finally {
        btn.textContent = '📄 Counter-Offer Letter';
        btn.disabled = false;
    }
}

// ─────────────────────────────────────────────────────────────────
// FEATURE 2: BANK EMAIL GENERATOR
// ─────────────────────────────────────────────────────────────────
let bankEmailContent = null;

function openBankEmailModal() {
    bankEmailReturnPage = reportPageIndex;
    document.getElementById('bank-email-modal').style.display = 'flex';
    document.getElementById('bank-email-content').style.display = 'none';
    document.getElementById('bank-email-loading').style.display = 'none';
    document.getElementById('bank-email-error').style.display = 'none';
    document.getElementById('bank-email-actions').style.display = 'flex';
    document.getElementById('bank-email-insight').style.display = 'none';
    document.getElementById('bank-email-insight').textContent = '';
    document.getElementById('bank-email-preview').innerHTML = '';
    document.getElementById('bank-email-preview-note').textContent = 'Structured for clarity and ready to customize before sending.';
    document.getElementById('bank-email-copy-btn').disabled = true;
    document.getElementById('bank-email-mailto-btn').disabled = true;
    bankEmailContent = null;
}

function closeBankEmail() {
    document.getElementById('bank-email-modal').style.display = 'none';
    setReportPage(bankEmailReturnPage);
}

async function generateBankEmail() {
    if (!lastReport || !lastInput) return;
    const bank = document.getElementById('target-bank').value;
    const generateBtn = document.getElementById('bank-email-generate-btn');
    document.getElementById('bank-email-loading').style.display = 'block';
    document.getElementById('bank-email-content').style.display = 'none';
    document.getElementById('bank-email-error').style.display = 'none';
    document.getElementById('bank-email-insight').style.display = 'none';
    document.getElementById('bank-email-insight').textContent = '';
    document.getElementById('bank-email-preview').innerHTML = '';
    generateBtn.disabled = true;
    try {
        const res = await fetch(`${API}/api/v1/tools/bank-email`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                computed_numbers: lastReport.computed_numbers || {},
                raw_input: lastInput,
                target_bank: bank
            })
        });
        if (!res.ok) throw new Error('Email generation failed');
        const data = await res.json();
        bankEmailContent = data.full_email_text || '';
        document.getElementById('bank-email-preview').innerHTML = formatEmailDraftPreview(bankEmailContent);
        document.getElementById('bank-email-loading').style.display = 'none';
        document.getElementById('bank-email-content').style.display = 'block';
        document.getElementById('bank-email-copy-btn').disabled = !bankEmailContent;
        document.getElementById('bank-email-mailto-btn').disabled = !bankEmailContent;
        document.getElementById('bank-email-preview-note').textContent = `${bank} draft based on the current report. Review names, phone number, and numbers before sending.`;
        if (data.foir_pct) {
            const insight = document.getElementById('bank-email-insight');
            insight.style.display = 'block';
            insight.style.color = data.foir_pct < 40 ? 'var(--green)' : data.foir_pct < 50 ? 'var(--yellow)' : 'var(--red)';
            insight.style.borderLeftColor = data.foir_pct < 40 ? 'var(--green)' : data.foir_pct < 50 ? 'var(--yellow)' : 'var(--red)';
            insight.textContent = `FOIR ${data.foir_pct}% — ${data.foir_pct < 40 ? 'comfortably bank-friendly' : data.foir_pct < 50 ? 'borderline for many banks' : 'high for standard bank comfort'}.`;
        }
    } catch (e) {
        document.getElementById('bank-email-loading').style.display = 'none';
        document.getElementById('bank-email-error').style.display = 'block';
        document.getElementById('bank-email-error').textContent = 'Failed to generate email: ' + e.message;
        document.getElementById('bank-email-copy-btn').disabled = true;
        document.getElementById('bank-email-mailto-btn').disabled = true;
    } finally {
        generateBtn.disabled = false;
    }
}

function copyBankEmail() {
    if (!bankEmailContent) return;
    navigator.clipboard.writeText(bankEmailContent).then(() => {
        const btn = document.getElementById('bank-email-copy-btn');
        btn.textContent = '✓ Copied!';
        setTimeout(() => btn.textContent = 'Copy Draft', 2000);
    });
}

function openMailto() {
    if (!bankEmailContent) return;
    const subject = encodeURIComponent(`Home Loan Inquiry — ${lastInput?.property?.location_area || 'Property'}`);
    window.location.href = `mailto:?subject=${subject}&body=${encodeURIComponent(bankEmailContent)}`;
}

// ─────────────────────────────────────────────────────────────────
// FEATURE 4: RERA QR SCANNER
// ─────────────────────────────────────────────────────────────────
async function scanReraQR(input) {
    const file = input.files[0];
    if (!file) return;
    const statusEl = document.getElementById('rera-qr-status');
    statusEl.textContent = '⏳ Scanning QR code...';
    statusEl.style.color = 'var(--accent)';

    const formData = new FormData();
    formData.append('file', file);
    try {
        const res = await fetch(`${API}/api/v1/documents/scan-rera-qr`, {
            method: 'POST', body: formData
        });
        const data = await res.json();
        if (data.success && data.extracted_rera_number) {
            let msg = `✓ RERA: ${data.extracted_rera_number}`;
            if (data.rera_data?.registration_status === 'active') msg += ' — Active ✓';
            else if (data.rera_data?.risk_label) msg += ` — ${data.rera_data.risk_label}`;
            statusEl.textContent = msg;
            statusEl.style.color = 'var(--green)';
        } else {
            statusEl.textContent = data.error || 'No QR code detected';
            statusEl.style.color = 'var(--red)';
        }
    } catch (e) {
        statusEl.textContent = 'Scan failed — continue manually';
        statusEl.style.color = 'var(--text-muted)';
    }
    input.value = '';
}

// ─────────────────────────────────────────────────────────────────
// FEATURE 5: MARKET RATES
// ─────────────────────────────────────────────────────────────────
async function loadMarketRates() {
    const banner = document.getElementById('market-rates-banner');
    const textEl = document.getElementById('market-rates-text');
    if (!banner) return;
    banner.style.display = 'flex';
    textEl.textContent = 'Loading current rates...';
    try {
        const userRate = getNum('expected_interest_rate') || null;
        const url = userRate ? `${API}/api/v1/market/rates?user_rate=${userRate}` : `${API}/api/v1/market/rates`;
        const res = await fetch(url);
        if (!res.ok) throw new Error('rates unavailable');
        const data = await res.json();
        marketRatesData = data;
        textEl.textContent = `Market rates: ${data.market_floor}%–${data.market_ceiling}% · RBI Repo: ${data.rbi_repo_rate}% · Source: ${data.data_source}`;
        if (userRate) updateRateWarning(userRate, data);
    } catch (e) {
        textEl.textContent = 'Live rates unavailable — using Apr 2026 benchmarks (8.50–9.90%)';
    }
}

function updateRateWarning(userRate, ratesData) {
    const banner = document.getElementById('market-rates-banner');
    const textEl = document.getElementById('market-rates-text');
    if (!banner || !ratesData) return;
    if (ratesData.rate_warning || (userRate && ratesData.market_floor && userRate < ratesData.market_floor)) {
        const gap = Math.round((ratesData.market_floor - userRate) * 100);
        textEl.innerHTML = `<span style="color:var(--yellow)">⚠ Your rate (${userRate}%) is ${gap}bps below market floor (${ratesData.market_floor}%). EMI may be higher than estimated.</span>`;
    } else {
        textEl.textContent = `Market rates: ${ratesData.market_floor}%–${ratesData.market_ceiling}% · RBI Repo: ${ratesData.rbi_repo_rate}%`;
    }
}

function refreshMarketRates() { marketRatesData = null; loadMarketRates(); }

// ─────────────────────────────────────────────────────────────────
// FEATURE 7 & 8: DOCUMENT UPLOAD (EC + LOAN LETTER)
// ─────────────────────────────────────────────────────────────────
async function uploadEC(input) {
    const file = input.files[0];
    if (!file) return;
    const zone = input.closest('.doc-upload-zone') || input.parentElement;
    zone.classList.add('uploading');
    const resultDiv = document.getElementById('ec-result');
    resultDiv.innerHTML = '<div style="font-size:11px;color:var(--accent);margin-top:8px">⏳ Analyzing EC...</div>';

    const formData = new FormData();
    formData.append('file', file);
    formData.append('location_area', lastInput?.property?.location_area || 'Unknown');
    formData.append('property_price', String(lastInput?.property?.property_price || 0));

    try {
        const res = await fetch(`${API}/api/v1/documents/parse-ec`, { method: 'POST', body: formData });
        const data = await res.json();
        zone.classList.remove('uploading');
        if (data.success && data.analysis) {
            const a = data.analysis;
            const riskClass = a.risk_level || 'caution';
            const riskColor = { clear: 'var(--green)', caution: 'var(--yellow)', high_risk: 'var(--red)' }[riskClass] || 'var(--text-muted)';
            const mortgages = (a.mortgages || []).filter(m => m.status !== 'discharged');
            resultDiv.innerHTML = `
                <div class="doc-result-card ${riskClass}">
                    <div style="font-weight:700;color:${riskColor};font-size:12px;margin-bottom:6px;text-transform:uppercase">
                        ${riskClass.replace('_', ' ')} — ${a.has_encumbrances ? 'Encumbrances Found' : 'No Active Encumbrances'}
                    </div>
                    <div style="color:var(--text-dim);font-size:12px;margin-bottom:8px">${esc(a.summary || '')}</div>
                    ${mortgages.length > 0 ? `<div style="color:var(--red);font-size:11px">⚠ Active mortgages: ${mortgages.map(m => esc(m.lender)).join(', ')}</div>` : ''}
                    ${(a.legal_disputes || []).length > 0 ? `<div style="color:var(--red);font-size:11px">⚠ Legal dispute on record</div>` : ''}
                    <div style="color:var(--text-muted);font-size:11px;margin-top:6px;font-style:italic">${esc(a.recommendation || '')}</div>
                </div>`;
        } else {
            resultDiv.innerHTML = `<div style="color:var(--red);font-size:11px;margin-top:8px">✗ ${esc(data.error || 'Analysis failed')}</div>`;
        }
    } catch (e) {
        zone.classList.remove('uploading');
        resultDiv.innerHTML = '<div style="color:var(--red);font-size:11px;margin-top:8px">✗ Upload failed. Try again.</div>';
    }
    input.value = '';
}

async function uploadLoanLetter(input) {
    const file = input.files[0];
    if (!file) return;
    const zone = input.closest('.doc-upload-zone') || input.parentElement;
    zone.classList.add('uploading');
    const resultDiv = document.getElementById('loan-result');
    resultDiv.innerHTML = '<div style="font-size:11px;color:var(--accent);margin-top:8px">⏳ Extracting loan terms...</div>';

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch(`${API}/api/v1/documents/parse-loan-letter`, { method: 'POST', body: formData });
        const data = await res.json();
        zone.classList.remove('uploading');
        if (data.success && data.data) {
            const d = data.data;
            const hasAutoFill = d.auto_fill?.loan_tenure_years || d.auto_fill?.interest_rate;
            resultDiv.innerHTML = `
                <div class="doc-result-card">
                    <div style="font-weight:700;color:var(--green);font-size:12px;margin-bottom:8px">
                        ✓ ${esc(d.bank_name || 'Bank')} Loan Letter Parsed
                    </div>
                    <table style="width:100%;font-size:11px;border-collapse:collapse">
                        ${d.sanctioned_amount ? `<tr><td style="color:var(--text-muted);padding:2px 0">Sanctioned Amount</td><td style="color:var(--text);text-align:right">${inr(d.sanctioned_amount)}</td></tr>` : ''}
                        ${d.interest_rate_pct ? `<tr><td style="color:var(--text-muted);padding:2px 0">Interest Rate</td><td style="color:var(--text);text-align:right">${d.interest_rate_pct}% (${d.rate_type || 'unknown'})</td></tr>` : ''}
                        ${d.loan_tenure_years ? `<tr><td style="color:var(--text-muted);padding:2px 0">Tenure</td><td style="color:var(--text);text-align:right">${d.loan_tenure_years} years</td></tr>` : ''}
                        ${d.processing_fee ? `<tr><td style="color:var(--yellow);padding:2px 0">Processing Fee</td><td style="color:var(--yellow);text-align:right">${inr(d.processing_fee)}</td></tr>` : ''}
                        ${(d.hidden_charges || []).length > 0 ? `<tr><td colspan="2" style="color:var(--red);padding:4px 0;font-size:10px">⚠ Hidden charges: ${d.hidden_charges.map(h => esc(h)).join(' · ')}</td></tr>` : ''}
                    </table>
                    ${hasAutoFill ? (() => { const autoFillId = 'af_' + Date.now() + '_' + Math.random().toString(36).slice(2); window[autoFillId] = d.auto_fill || {}; return `<button onclick="applyLoanAutoFill(window['${autoFillId}'])" style="margin-top:10px;width:100%;padding:8px;background:var(--accent-dim);border:1px solid var(--accent);border-radius:6px;color:var(--accent);font-size:11px;cursor:pointer">Apply to Form →</button>`; })() : ''}
                    ${d.sanctioned_amount && lastInput?.property?.property_price ?
                    `<div style="font-size:11px;color:var(--text-muted);margin-top:6px">
                        Down Payment Needed: ${inr(Math.max(0, lastInput.property.property_price - d.sanctioned_amount))}
                        </div>` : ''}
                </div>`;
        } else {
            resultDiv.innerHTML = `<div style="color:var(--red);font-size:11px;margin-top:8px">✗ ${esc(data.error || 'Extraction failed')}</div>`;
        }
    } catch (e) {
        zone.classList.remove('uploading');
        resultDiv.innerHTML = '<div style="color:var(--red);font-size:11px;margin-top:8px">✗ Upload failed. Try again.</div>';
    }
    input.value = '';
}

function applyLoanAutoFill(autoFill) {
    if (autoFill.interest_rate) {
        const el = document.getElementById('expected_interest_rate');
        if (el) { el.value = autoFill.interest_rate; updateEMIPreview(); }
    }
    if (autoFill.loan_tenure_years) {
        const el = document.getElementById('loan_tenure_years');
        if (el) { el.value = autoFill.loan_tenure_years; updateEMIPreview(); }
    }
    alert('Loan terms applied to form! Review and re-run analysis if needed.');
}

// ─────────────────────────────────────────────────────────────────
// FEATURE 9: GST HEALTH CHECK
// ─────────────────────────────────────────────────────────────────
async function checkBuilderGST() {
    const gstin = (document.getElementById('builder_gstin')?.value || '').trim().toUpperCase();
    const resultDiv = document.getElementById('gst-result');
    const btn = document.getElementById('gst-check-btn');
    if (!gstin || gstin.length !== 15) {
        resultDiv.textContent = 'Enter 15-character GSTIN first';
        resultDiv.style.color = 'var(--text-muted)';
        return;
    }
    btn.textContent = '...';
    btn.disabled = true;
    try {
        const res = await fetch(`${API}/api/v1/tools/gst-check?gstin=${encodeURIComponent(gstin)}`);
        if (res.status === 422) {
            resultDiv.textContent = 'Invalid GSTIN format';
            resultDiv.style.color = 'var(--red)';
            return;
        }
        const data = await res.json();
        if (data.risk_flag) {
            resultDiv.innerHTML = `<span style="color:var(--red)">✗ Risk — ${esc(data.risk_explanation)}</span>`;
        } else if (data.registration_status === 'active') {
            const filed = data.last_return_filed ? ` · Filed ${data.last_return_filed}` : '';
            resultDiv.innerHTML = `<span style="color:var(--green)">✓ Active${filed}</span>`;
        } else {
            resultDiv.innerHTML = `<span style="color:var(--text-muted)">${esc(data.risk_explanation)}</span>`;
        }
    } catch (e) {
        resultDiv.textContent = 'Verification unavailable';
        resultDiv.style.color = 'var(--text-muted)';
    } finally {
        btn.textContent = 'Verify GST';
        btn.disabled = false;
    }
}

// ─────────────────────────────────────────────────────────────────
// FEATURE 10: OC/CC STATUS RENDER
// ─────────────────────────────────────────────────────────────────
function renderOcCcStatus(occc) {
    if (!occc) return '';
    const colorMap = {
        low: 'var(--green)', medium: 'var(--yellow)',
        high: 'var(--red)', critical: 'var(--red)'
    };
    const color = colorMap[occc.risk_level] || 'var(--text-muted)';
    const label = (occc.risk_level || 'unknown').toUpperCase();
    return `
        <div style="margin-top:12px;padding:12px;background:var(--bg);
             border-radius:8px;border-left:3px solid ${color}">
            <div style="font-size:11px;font-weight:700;color:${color};
                 text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px">
                OC/CC Status: ${label}
            </div>
            <div style="font-size:12px;color:var(--text-dim);margin-bottom:6px">
                ${esc(occc.overall_note || '')}
            </div>
            ${(occc.risk_flags || []).map(f =>
        `<div style="font-size:11px;color:var(--yellow);margin-top:3px">⚠ ${esc(f)}</div>`
    ).join('')}
        </div>`;
}

// === VISUAL FEATURES ===

/**
 * FEATURE 1: Adds verdict-appropriate pulse animation to verdict element.
 * @param {HTMLElement} el @param {string} verdict safe|risky|reconsider
 */
function renderVerdictPulse(el, verdict) {
    if (!el) return;
    el.classList.remove('safe', 'risky', 'reconsider');
    el.classList.add(verdict);
    const conf = document.getElementById('conf-fill');
    if (conf) setTimeout(() => conf.style.width = conf.dataset.target, 100);
}

/**
 * FEATURE 2: Renders SVG shield that fills based on runway months.
 * Full at 12mo, cracked at 3-6mo, shattered at <3mo.
 * @param {HTMLElement} container @param {number} runwayMonths
 */
function renderSavingsShield(container, runwayMonths) {
    if (!container) return;
    const months = runwayMonths || 0;
    const fillRatio = Math.min(months / 12, 1);
    const fillY = 100 - fillRatio * 100;
    const color = months >= 6 ? 'var(--green)' : months >= 3 ? 'var(--yellow)' : 'var(--red)';
    const bgColor = months >= 6 ? 'var(--green-bg)' : months >= 3 ? 'var(--yellow-bg)' : 'var(--red-bg)';
    // Crack paths for degraded states
    const cracks = months < 6 ? `
    <path d="M40 30 L50 50 L38 65" stroke="${color}" stroke-width="1.5" fill="none" opacity="0.7"/>
    <path d="M60 25 L55 45 L65 58" stroke="${color}" stroke-width="1.5" fill="none" opacity="0.7"/>
    ${months < 3 ? `
    <path d="M30 50 L45 55 L35 70" stroke="${color}" stroke-width="1.2" fill="none" opacity="0.5"/>
    <path d="M65 40 L70 60 L58 72" stroke="${color}" stroke-width="1.2" fill="none" opacity="0.5"/>
    <path d="M48 20 L44 35 L55 40" stroke="${color}" stroke-width="1" fill="none" opacity="0.4"/>
    ` : ''}
  ` : '';
    container.innerHTML = `
    <svg viewBox="0 0 100 110" width="80" height="88" style="display:block;margin:0 auto">
      <defs>
        <clipPath id="shield-clip-${container.id || 'sh'}">
          <path d="M50 5 L90 20 L90 55 Q90 85 50 105 Q10 85 10 55 L10 20 Z"/>
        </clipPath>
      </defs>
      <!-- Shield background -->
      <path d="M50 5 L90 20 L90 55 Q90 85 50 105 Q10 85 10 55 L10 20 Z"
            fill="${bgColor}" stroke="${color}" stroke-width="2"/>
      <!-- Fill rect clipped to shield shape -->
      <rect x="10" y="${fillY}" width="80" height="100"
            fill="${color}" opacity="0.25"
            clip-path="url(#shield-clip-${container.id || 'sh'})"/>
      ${cracks}
      <!-- Label -->
      <text x="50" y="58" text-anchor="middle" font-size="16" font-weight="700"
            fill="${color}" font-family="'DM Mono', monospace">${months.toFixed(1)}</text>
      <text x="50" y="72" text-anchor="middle" font-size="8"
            fill="${color}" font-family="'DM Mono', monospace" opacity="0.8">MO</text>
    </svg>`;
}

/**
 * FEATURE 3: Animated SVG river flow replacing cash flow waterfall.
 * Income splits into obligation streams, surplus flows right.
 * @param {HTMLElement} container @param {Object} computed @param {Object} fin
 */
function renderRiverFlow(container, computed, fin) {
    if (!container) return;
    const income = (fin.monthly_income || 0) + (fin.spouse_income || 0);
    if (income <= 0) return;
    const emi = computed.monthly_emi || 0;
    const maint = (computed.monthly_ownership_cost || emi) - emi;
    const emis = fin.existing_emis || 0;
    const exp = fin.monthly_expenses || 0;
    const surplus = Math.max(income - emi - maint - emis - exp, 0);
    const pct = v => Math.max((v / income) * 100, 2).toFixed(1);
    const streams = [
        { label: 'EMI', value: emi, color: 'var(--red)' },
        { label: 'Maint', value: maint, color: 'var(--yellow)' },
        { label: 'Expenses', value: exp, color: '#f97316' },
        { label: 'Surplus', value: surplus, color: 'var(--green)' },
    ].filter(s => s.value > 0);
    let paths = '';
    let yOff = 10;
    streams.forEach((s, i) => {
        const h = Math.max((s.value / income) * 80, 4);
        const cy1 = yOff + h / 2;
        const cx = i === streams.length - 1 ? 260 : 220;
        paths += `
      <path d="M 60 50 C 120 50 140 ${cy1} ${cx} ${cy1}"
            stroke="${s.color}" stroke-width="${Math.max(h * 0.6, 2)}" fill="none"
            stroke-dasharray="200" stroke-dashoffset="200" opacity="0.85">
        <animate attributeName="stroke-dashoffset" from="200" to="0"
                 dur="${0.6 + i * 0.2}s" begin="${i * 0.15}s" fill="freeze" calcMode="spline"
                 keySplines="0.4 0 0.2 1"/>
      </path>
      <text x="${cx + 8}" y="${cy1 + 4}" font-size="9" fill="${s.color}"
            font-family="'DM Mono', monospace">${s.label} ${pct(s.value)}%</text>`;
        yOff += h + 4;
    });
    container.innerHTML = `
    <svg viewBox="0 0 300 100" width="100%" height="100" style="overflow:visible">
      <rect x="0" y="30" width="60" height="40" rx="4"
            fill="var(--accent-dim)" stroke="var(--accent)" stroke-width="1"/>
      <text x="30" y="52" text-anchor="middle" font-size="9" fill="var(--accent)"
            font-family="'DM Mono', monospace">INCOME</text>
      <text x="30" y="63" text-anchor="middle" font-size="7" fill="var(--text-muted)"
            font-family="'DM Mono', monospace">${(income / 100000).toFixed(1)}L</text>
      ${paths}
    </svg>`;
}

/**
 * FEATURE 4: Balance beam SVG tilting based on EMI/income ratio.
 * @param {HTMLElement} container @param {number} emiRatio
 */
function initDebtGravity(container, emiRatio) {
    if (!container) return;
    const deg = emiRatio < 0.25 ? -5 : emiRatio < 0.40 ? -15 :
        emiRatio < 0.55 ? -28 : -45;
    const svg = `<svg viewBox="0 0 120 60" style="width:120px;height:60px">
    <circle cx="60" cy="30" r="4" fill="var(--border-bright)"/>
    <line id="beam" x1="10" y1="30" x2="110" y2="30"
          stroke="var(--text-dim)" stroke-width="2"
          style="transform-origin:60px 30px;
                 transform:rotate(${deg}deg);
                 transition:transform 1s var(--anim-spring)"/>
    <circle cx="25" cy="18" r="12" fill="var(--red-bg)"
            stroke="var(--red)" stroke-width="1.5"/>
    <circle cx="95" cy="18" r="8" fill="var(--green-bg)"
            stroke="var(--green)" stroke-width="1.5"/>
  </svg>`;
    container.innerHTML = svg;
    setTimeout(() => {
        const beam = container.querySelector('#beam');
        if (beam) beam.style.transform = `rotate(${deg}deg)`;
    }, 300);
}

/**
 * FEATURE 5: Circular countdown ring showing runway months.
 * Animates from empty to filled over 800ms.
 * @param {string} svgId - ID of the burn-clock SVG element
 * @param {number} runwayMonths
 */
function initBurnClock(svgId, runwayMonths) {
    const fill = document.getElementById('burn-fill');
    const num = document.getElementById('burn-num');
    if (!fill || !num) return;
    const maxMonths = 12;
    const circumference = 201;
    const ratio = Math.min(runwayMonths, maxMonths) / maxMonths;
    const color = runwayMonths >= 6 ? 'var(--green)' :
        runwayMonths >= 3 ? 'var(--yellow)' : 'var(--red)';
    fill.style.stroke = color;
    fill.style.transition = 'stroke-dashoffset 0.8s var(--anim-ease)';
    let count = 0;
    const target = Math.round(runwayMonths * 10) / 10;
    const steps = 40;
    const interval = setInterval(() => {
        count++;
        const p = count / steps;
        const ease = 1 - Math.pow(1 - p, 3);
        num.textContent = (ease * target).toFixed(1);
        fill.style.strokeDashoffset = circumference - (circumference * ratio * ease);
        if (count >= steps) { clearInterval(interval); num.textContent = target.toFixed(1); }
    }, 800 / steps);
}

/**
 * FEATURE 6: Point of No Return timeline for job loss scenario.
 * Shows which month default risk begins.
 * @param {HTMLElement} container @param {Object} scenario stress scenario object
 */
function renderPointOfNoReturn(container, scenario) {
    if (!container) return;
    const months = Math.min(Math.max(Math.round(scenario.months_before_default || 6), 0), 6);
    const survived = scenario.can_survive;
    let segs = '';
    for (let i = 1; i <= 6; i++) {
        const color = survived ? 'var(--green)' :
            i <= months ? 'var(--yellow)' : 'var(--red)';
        segs += `<div class="ponr-seg" style="background:${color};
      flex:1;height:8px;border-radius:2px;margin:0 2px;
      animation:card-enter 300ms ${i * 50}ms both"></div>`;
    }
    container.innerHTML = `
    <div style="display:flex;margin:10px 0 4px">${segs}</div>
    <div style="font-size:10px;font-family:var(--font-mono);
         color:var(--text-muted);display:flex;justify-content:space-between">
      <span>Month 1</span>
      <span>${survived ? '✓ Survives 6 months' : `⚠ Risk from month ${months}`}</span>
      <span>Month 6</span>
    </div>`;
}

/**
 * FEATURE 7: ECG-style heartbeat canvas showing cash flow rhythm.
 * Healthy surplus = regular beats. Low/negative = flat or erratic.
 * @param {HTMLCanvasElement} canvas @param {number} surplus @param {number} income
 */
function initHeartbeatGraph(canvas, surplus, income) {
    if (!canvas) return;
    onVisible(canvas, () => drawHeartbeat(canvas, surplus, income));
}

function drawHeartbeat(canvas, surplus, income) {
    canvas.width = canvas.offsetWidth || 300;
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height || 80;
    const ratio = Math.max(Math.min(surplus / Math.max(income, 1), 0.5), -0.3);
    const beats = 12, beatW = W / beats;
    const baseY = H * 0.7, spikeH = ratio * H * 1.2;
    ctx.fillStyle = getComputedStyle(document.documentElement)
        .getPropertyValue('--bg').trim() || '#080810';
    ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = 'rgba(255,255,255,0.05)';
    ctx.lineWidth = 1;
    for (let y = H * 0.25; y < H; y += H * 0.25) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    }
    let progress = 0;
    const totalPoints = beats * 10;
    const interval = setInterval(() => {
        progress = Math.min(progress + 2, totalPoints);
        ctx.clearRect(0, 0, W, H);
        ctx.fillStyle = getComputedStyle(document.documentElement)
            .getPropertyValue('--bg').trim() || '#080810';
        ctx.fillRect(0, 0, W, H);
        ctx.beginPath();
        ctx.strokeStyle = surplus > 0 ? '#22c55e' : '#ef4444';
        ctx.lineWidth = 2;
        for (let b = 0; b < beats; b++) {
            const bx = b * beatW;
            const points = [[0, 0], [0.3, 0], [0.4, -0.3], [0.5, 1], [0.6, -0.2], [0.7, 0], [1, 0]];
            points.forEach(([px, py], i) => {
                const x = bx + px * beatW, y = baseY - py * spikeH;
                const ptIdx = b * 10 + Math.round(px * 10);
                if (ptIdx <= progress) {
                    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
                }
            });
        }
        ctx.stroke();
        if (progress >= totalPoints) clearInterval(interval);
    }, 1000 / totalPoints * 1.5);
}

/**
 * FEATURE 8: Staggered risk burst animation on failed stress test cards.
 * @param {NodeList} cards - All stress test card elements
 */
function initRiskBurst(cards) {
    [...cards].forEach((card, i) => {
        if (card.classList.contains('fail') || card.dataset.survive === 'false') {
            requestAnimationFrame(() =>
                setTimeout(() => card.classList.add('burst-animate'), i * 150));
        }
    });
}

/**
 * FEATURE 9: Buy Now vs Wait timeline using /api/v1/calculate.
 * Runs 3 parallel scenarios with Promise.all.
 * @param {Object} report @param {Object} rawInput
 */
async function initTimelineScenarios(report, rawInput) {
    const container = document.getElementById('r-timeline');
    if (!container || !rawInput) return;
    const fin = rawInput.financial || {};
    const prop = rawInput.property || {};
    const monthlySavings = Math.max(
        (fin.monthly_income || 0) + (fin.spouse_income || 0) -
        (fin.existing_emis || 0) - (fin.monthly_expenses || 0) -
        (report.computed_numbers?.monthly_emi || 0), 0);
    const base = `monthly_income=${fin.monthly_income || 0}&spouse_income=${fin.spouse_income || 0}&existing_emis=${fin.existing_emis || 0}&monthly_expenses=${fin.monthly_expenses || 0}&liquid_savings=${fin.liquid_savings || 0}&dependents=${fin.dependents || 0}&loan_tenure_years=${prop.loan_tenure_years || 20}&interest_rate=${prop.expected_interest_rate || 8.5}&carpet_area_sqft=${prop.carpet_area_sqft || 700}&buyer_gender=${prop.buyer_gender || 'male'}&is_ready_to_move=${prop.is_ready_to_move || true}&location_area=${encodeURIComponent(prop.location_area || '')}&`;
    const scenarios = [
        { id: 'ts-now', label: 'BUY NOW', dp: prop.down_payment_available, price: prop.property_price },
        { id: 'ts-6mo', label: 'WAIT 6 MO', dp: (prop.down_payment_available || 0) + monthlySavings * 6, price: (prop.property_price || 0) * 1.025 },
        { id: 'ts-1yr', label: 'WAIT 1 YR', dp: (prop.down_payment_available || 0) + monthlySavings * 12, price: (prop.property_price || 0) * 1.05 },
    ];
    try {
        const results = await Promise.all(scenarios.map(s =>
            fetch(`${API}/api/v1/calculate?${base}property_price=${s.price}&down_payment=${s.dp}`)
                .then(r => r.ok ? r.json() : null).catch(() => null)
        ));
        let bestIdx = 0, bestRatio = Infinity;
        results.forEach((r, i) => {
            if (r && r.emi_to_income_ratio < bestRatio) { bestRatio = r.emi_to_income_ratio; bestIdx = i; }
        });
        const best = results[bestIdx];
        const summaryEl = document.getElementById('timeline-summary');
        if (summaryEl && best) {
            const runwayLift = Math.max((results[2]?.emergency_runway_months || 0) - (results[0]?.emergency_runway_months || 0), 0);
            const equityCost = Math.max((scenarios[2].price || 0) - (scenarios[0].price || 0), 0);
            summaryEl.textContent = `Waiting 1 year could improve runway by ${runwayLift.toFixed(1)} months, but may cost about ${inr(equityCost)} more if prices rise as assumed.`;
        }
        scenarios.forEach((s, i) => {
            const el = document.getElementById(s.id + '-metrics');
            const track = document.getElementById(s.id);
            if (!el || !results[i]) return;
            const r = results[i];
            const zone = r.emi_to_income_ratio < 0.3 ? 'var(--green)' : r.emi_to_income_ratio < 0.45 ? 'var(--yellow)' : 'var(--red)';
            el.innerHTML = `
        <div class="timeline-main" style="color:${zone}">${(r.emi_to_income_ratio * 100).toFixed(1)}%</div>
        <div class="metric-label">EMI / Income</div>
        <div class="timeline-meta">${r.emergency_runway_months?.toFixed(1)} months runway</div>
        <div class="timeline-meta">${inr(r.monthly_emi)} / month EMI</div>
        <div class="timeline-meta">${inr(s.price)} projected price</div>
        ${i === bestIdx ? '<div class="timeline-reco">Recommended</div>' : ''}`;
            if (track) track.classList.toggle('recommended', i === bestIdx);
        });
        container.style.display = 'block';
    } catch (e) { console.warn('Timeline scenarios failed:', e); }
}

/**
 * FEATURE 10: Net worth mountain canvas — 10yr projection.
 * Draws property value line, net worth curve, key markers.
 * @param {HTMLCanvasElement} canvas @param {Object} computed @param {Object} rawInput
 */
function drawNetWorthMountain(canvas, computed, rawInput) {
    if (!canvas) return;
    canvas.width = canvas.offsetWidth || 600;
    const ctx = canvas.getContext('2d');
    const styles = getComputedStyle(document.documentElement);
    const bgColor = styles.getPropertyValue('--surface').trim() || '#ffffff';
    const gridColor = styles.getPropertyValue('--border').trim() || '#e5e7eb';
    const accentColor = styles.getPropertyValue('--yellow').trim() || '#ca8a04';
    const mutedColor = styles.getPropertyValue('--text-muted').trim() || '#9ca3af';
    const W = canvas.width, H = canvas.height || 200;
    const fin = rawInput?.financial || {};
    const prop = rawInput?.property || {};
    const years = 10;
    const pts = [];
    let nw = (fin.liquid_savings || 0) - (prop.down_payment_available || 0);
    const annualSurplus = Math.max(
        ((fin.monthly_income || 0) + (fin.spouse_income || 0)) * 12 -
        (computed.monthly_emi || 0) * 12 - (fin.monthly_expenses || 0) * 12, 0);
    for (let y = 0; y <= years; y++) {
        pts.push(nw);
        nw += annualSurplus * Math.pow(1.08, y) * 0.7 +
            (prop.property_price || 0) * 0.04;
    }
    const minV = Math.min(...pts), maxV = Math.max(...pts);
    const pad = 30;
    function toX(y) { return pad + (y / years) * (W - pad * 2); }
    function toY(v) { return H - pad - ((v - minV) / (maxV - minV || 1)) * (H - pad * 2); }
    ctx.fillStyle = bgColor;
    ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = gridColor;
    for (let i = 0; i <= 5; i++) {
        ctx.beginPath();
        ctx.moveTo(pad, pad + i * (H - pad * 2) / 5);
        ctx.lineTo(W - pad, pad + i * (H - pad * 2) / 5);
        ctx.stroke();
    }
    const propPts = Array.from({ length: years + 1 }, (_, y) => (prop.property_price || 0) * Math.pow(1.04, y));
    const legend = document.getElementById('mountain-legend');
    if (legend) {
        legend.innerHTML = `
      <span style="display:flex;align-items:center;gap:8px;"><span style="width:10px;height:10px;border-radius:999px;background:${accentColor};display:inline-block"></span>Projected net worth</span>
      <span style="display:flex;align-items:center;gap:8px;"><span style="width:10px;height:2px;background:rgba(124,106,247,0.45);display:inline-block"></span>Property value trend</span>
    `;
    }
    ctx.beginPath(); ctx.strokeStyle = 'rgba(124,106,247,0.3)'; ctx.lineWidth = 1.5; ctx.setLineDash([4, 4]);
    propPts.forEach((v, y) => y === 0 ? ctx.moveTo(toX(y), toY(v)) : ctx.lineTo(toX(y), toY(v)));
    ctx.stroke(); ctx.setLineDash([]);
    const grad = ctx.createLinearGradient(0, 0, 0, H);
    grad.addColorStop(0, 'rgba(124,106,247,0.2)'); grad.addColorStop(1, 'rgba(124,106,247,0)');
    ctx.beginPath(); ctx.moveTo(toX(0), toY(pts[0]));
    pts.forEach((v, y) => ctx.lineTo(toX(y), toY(v)));
    ctx.lineTo(toX(years), H - pad); ctx.lineTo(toX(0), H - pad); ctx.closePath();
    ctx.fillStyle = grad; ctx.fill();
    let prog = 0;
    const animate = setInterval(() => {
        ctx.clearRect(0, 0, W, H);
        ctx.fillStyle = bgColor; ctx.fillRect(0, 0, W, H);
        ctx.beginPath(); ctx.strokeStyle = accentColor; ctx.lineWidth = 2.5; ctx.setLineDash([]);
        pts.slice(0, Math.ceil(prog) + 1).forEach((v, i) => i === 0 ? ctx.moveTo(toX(i), toY(v)) : ctx.lineTo(toX(i), toY(v)));
        ctx.stroke();
        prog = Math.min(prog + 0.15, years);
        if (prog >= years) {
            clearInterval(animate);
            ctx.fillStyle = mutedColor; ctx.font = `10px 'DM Mono'`;
            ctx.fillText('Year 0', toX(0) - 10, H - 8);
            ctx.fillText('Year 10', toX(10) - 20, H - 8);
            ctx.fillStyle = accentColor;
            ctx.fillText(inr(pts[years]), toX(years) - 30, toY(pts[years]) - 8);
        }
    }, 1200 / years / 8);
}

// === NEW FEATURE FUNCTIONS ===

/**
 * Renders the AI integrity / bias detection card.
 * High integrity = trust signal. Low = correction warning.
 * Core differentiator: the AI that audits its own reasoning.
 * @param {Object} biasResult - bias_detection from pipeline output
 */
function renderBiasDetection(biasResult) {
    const el = document.getElementById('r-bias-detection');
    if (!el || !biasResult) return;

    const colorMap = {
        green: 'var(--green)', yellow: 'var(--yellow)',
        orange: 'var(--yellow)', red: 'var(--red)',
    };
    const bgMap = {
        green: 'var(--green-bg)', yellow: 'var(--yellow-bg)',
        orange: 'var(--yellow-bg)', red: 'var(--red-bg)',
    };
    const borderMap = {
        green: 'var(--green-border)', yellow: 'var(--yellow-border)',
        orange: 'var(--yellow-border)', red: 'var(--red-border)',
    };

    const c = biasResult.display_color || 'green';
    const icon = biasResult.integrity_score >= 80 ? '🛡' :
        biasResult.integrity_score >= 60 ? '⚖' : '⚠';

    el.innerHTML = `
    <div style="background:${bgMap[c]};border:1px solid ${borderMap[c]};
         border-radius:12px;padding:14px 18px;margin-bottom:16px;
         display:flex;align-items:flex-start;gap:14px">
      <div style="font-size:24px;flex-shrink:0">${icon}</div>
      <div style="flex:1">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;
             flex-wrap:wrap">
          <span style="font-family:var(--font-display);font-size:12px;
              font-weight:700;color:${colorMap[c]};letter-spacing:1px;
              text-transform:uppercase">
            AI Integrity: ${esc(biasResult.display_label)}
          </span>
          <span style="font-family:var(--font-mono);font-size:11px;
              color:var(--text-muted)">${biasResult.integrity_score}/100</span>
          ${biasResult.verdict_was_corrected ?
            `<span style="font-size:10px;font-weight:700;padding:2px 8px;
             border-radius:3px;background:var(--red-bg);color:var(--red);
             border:1px solid var(--red-border)">VERDICT CORRECTED</span>` : ''}
        </div>
        <div style="font-size:12px;color:var(--text-dim);line-height:1.5">
          ${esc(biasResult.bias_explanation ||
                'AI reasoning aligns with mathematical analysis. No systematic bias detected.')}
        </div>
      </div>
    </div>`;
}

/**
 * Handles property photo file selection.
 * Shows thumbnails and triggers background Gemini inspection.
 * @param {HTMLInputElement} input - File input element
 */
function handlePropertyPhotos(input) {
    const files = Array.from(input.files).slice(0, 5);
    STATE.propertyPhotoFiles = files;

    const strip = document.getElementById('photo-preview-strip');
    strip.innerHTML = '';
    strip.style.display = files.length ? 'flex' : 'none';

    files.forEach(f => {
        const img = document.createElement('img');
        img.src = URL.createObjectURL(f);
        img.className = 'photo-thumb';
        strip.appendChild(img);
    });

    if (files.length) {
        document.getElementById('photo-drop-zone').classList.add('has-photos');
        runPropertyInspection(files);
    }
}

/**
 * Uploads property photos to /documents/inspect-property.
 * Runs in background — does not block form submission.
 * @param {File[]} files - Array of image files (max 5)
 */
async function runPropertyInspection(files) {
    const statusEl = document.getElementById('photo-inspection-status');
    if (!statusEl) return;
    statusEl.style.display = 'block';
    statusEl.innerHTML = `
    <div style="font-size:12px;color:var(--accent);padding:10px;
         background:rgba(250,204,21,0.06);border-radius:8px;margin-top:10px">
      <span style="animation:pulse-warn 1s infinite;display:inline-block">●</span>
      Gemini is inspecting your photos...
    </div>`;

    const fd = new FormData();
    files.forEach(f => fd.append('files', f));
    fd.append('location_area', document.getElementById('location_area')?.value || 'Mumbai');
    fd.append('property_price', document.getElementById('property_price')?.value || '0');

    try {
        const res = await fetch(`${API}/api/v1/documents/inspect-property`, {
            method: 'POST', body: fd,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        STATE.visualInspectionResult = data;

        const scoreColor = data.visual_inspection_score >= 70 ? 'var(--green)' :
            data.visual_inspection_score >= 50 ? 'var(--yellow)' :
                'var(--red)';
        statusEl.innerHTML = `
      <div style="padding:12px;background:var(--bg);border-radius:8px;
           border:1px solid var(--border);margin-top:10px">
        <div style="display:flex;justify-content:space-between;
             align-items:center;margin-bottom:8px">
          <span style="font-size:12px;font-weight:700;color:var(--text)">
            Visual Condition: ${esc(data.condition_grade)}
          </span>
          <span style="font-family:var(--font-mono);font-size:14px;
               font-weight:700;color:${scoreColor}">
            ${data.visual_inspection_score}/100
          </span>
        </div>
        ${data.structural_concerns?.length ?
                `<div style="font-size:11px;color:var(--red);margin-bottom:4px">
             ⚠ ${esc(data.structural_concerns[0])}
           </div>` : ''}
        <div style="font-size:11px;color:var(--text-muted)">
          ${esc(data.recommendation)}
        </div>
      </div>`;
    } catch (e) {
        statusEl.innerHTML = `
      <div style="font-size:11px;color:var(--text-muted);margin-top:8px">
        Visual inspection unavailable — analysis proceeds without images.
      </div>`;
    }
}

/**
 * Animates verdict word entrance with spring scale.
 * The single most important animation in the product.
 * @param {HTMLElement} el - The verdict word element (.v-word)
 */
function animateVerdictEntrance(el) {
    if (!el) return;
    el.style.cssText = 'transform:scale(0.4);opacity:0;transition:none';
    requestAnimationFrame(() => requestAnimationFrame(() => {
        el.style.cssText = (
            'transform:scale(1);opacity:1;' +
            'transition:transform 400ms cubic-bezier(0.34,1.56,0.64,1),' +
            'opacity 250ms ease'
        );
    }));
}

/**
 * Staggered stress card entrance with burst effect on failed cards.
 * Implements peak-end rule: failure moments are designed, not instant.
 */
function animateStressCards() {
    const cards = document.querySelectorAll('.sc2');
    cards.forEach((card, i) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(12px)';
        setTimeout(() => {
            card.style.transition = 'opacity 300ms ease, transform 300ms cubic-bezier(0.34,1.56,0.64,1)';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
            if (card.classList.contains('fail')) {
                setTimeout(() => {
                    card.classList.add('burst-active');
                    setTimeout(() => card.classList.remove('burst-active'), 600);
                }, 200);
            }
        }, i * 120);
    });
}

/**
 * Shows live analysis progress counter during pipeline execution.
 * Replaces static "6 agents working" with "Analysis X% complete".
 */
function updateAnalysisProgress() {
    const agentIds = ['a1', 'a2', 'a3', 'a4', 'a5', 'a6'];
    const interval = setInterval(() => {
        const done = agentIds.filter(id => {
            const el = document.getElementById(id);
            return el && el.classList.contains('done');
        }).length;
        const pct = Math.round(done / agentIds.length * 100);
        const subEl = document.querySelector('.load-sub');
        if (!subEl) return;
        const agentNames = ['Context', 'Financial + Property', 'Risk', 'Assumptions', 'Decision'];
        const stageIdx = Math.min(Math.floor((done / agentIds.length) * agentNames.length), agentNames.length - 1);
        subEl.textContent = pct < 100
            ? `${pct}% complete · Running: ${agentNames[stageIdx]}`
            : 'Composing your verdict...';
        if (done === agentIds.length) clearInterval(interval);
    }, 400);
}

/**
 * Initializes sticky summary bar that appears when scrolling past verdict.
 * @param {Object} report - Full pipeline output
 */


function initDocumentDropzones() {
    document.querySelectorAll('.doc-upload-zone').forEach(zone => {
        const input = zone.querySelector('input[type="file"]');
        if (!input) return;
        ['dragenter', 'dragover'].forEach(evt => zone.addEventListener(evt, e => {
            e.preventDefault();
            zone.classList.add('drag-active');
        }));
        ['dragleave', 'drop'].forEach(evt => zone.addEventListener(evt, e => {
            e.preventDefault();
            zone.classList.remove('drag-active');
        }));
        zone.addEventListener('drop', e => {
            const files = e.dataTransfer?.files;
            if (!files || !files.length) return;
            input.files = files;
            if (input.id === 'ec-file') uploadEC(input);
            if (input.id === 'loan-file') uploadLoanLetter(input);
        });
    });
}

// === INITIALIZATION ===
document.addEventListener('DOMContentLoaded', () => {
    updateFinancialHealth();
    updateEMIPreview();
    initDocumentDropzones();

    // Setup Indian number formatting on financial inputs
    ['monthly_income', 'spouse_income', 'liquid_savings', 'existing_emis',
        'monthly_expenses', 'property_price', 'down_payment_available', 'current_rent'].forEach(id => {
            const el = document.getElementById(id);
            if (el) setupIndianNumberFormat(el);
        });

    // Smart defaults for empty fields (formatted strings)
    const smartDefaults = {
        monthly_income: "1,20,000",
        liquid_savings: "20,00,000",
        existing_emis: "5,000",
        monthly_expenses: "45,000",
        current_rent: "25,000",
        property_price: "85,00,000",
        down_payment_available: "17,00,000"
    };
    Object.entries(smartDefaults).forEach(([id, val]) => {
        const el = document.getElementById(id);
        if (el && !el.value) el.value = val;
    });

    [
        ['monthly_income', 'inc-p'],
        ['spouse_income', 'sp-p'],
        ['liquid_savings', 'sav-p'],
        ['property_price', 'pp-p'],
        ['down_payment_available', 'dp-p'],
    ].forEach(([fieldId, previewId]) => {
        const el = document.getElementById(fieldId);
        if (el) preview(el, previewId);
    });

    if (window.__NIV_PRELOADED_REPORT__) {
        lastReport = window.__NIV_PRELOADED_REPORT__;
        document.getElementById('form-section').style.display = 'none';
        renderReport(lastReport);
        document.getElementById('report-view').style.display = 'block';
        document.body.classList.add('report-visible');
        setReportPage(0);

        if (window.__NIV_SHARED_MODE__) {
            const banner = document.createElement('div');
            banner.style.cssText = [
                'background:rgba(124,106,247,0.1)',
                'border:1px solid var(--accent-dim)',
                'border-radius:10px',
                'padding:12px 16px',
                'margin-bottom:16px',
                'font-size:13px',
                'color:var(--text-dim)',
                'text-align:center'
            ].join(';');
            banner.innerHTML = 'This is a shared analysis. '
                + '<a href="/" style="color:var(--accent);font-weight:600">Run your own →</a>';
            document.getElementById('report-view').prepend(banner);
            setTimeout(maybeShowOutcomePrompt, 3000);
        }
    }
});
