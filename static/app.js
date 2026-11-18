'use strict';
const $=id=>document.getElementById(id);
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let config,caseId=null,record=null,analysis=null,sourceList=[],demo=false,busy=false,unlocked=0;
function notice(text){$('notice').textContent=text;}
let guestToken = null;
let accountUsername = null;
let idleTimer;
let lockedButtons = [];

async function api(path, data = {}) {
    const guest = guestToken;
    if (!guest) throw new Error('Continue as a guest first.');
    refreshGuestTimer();
    const response = await fetch('/api/' + path, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({id: caseId, guest, live_consent: $('consent').checked, ...data}),
    });
    if (guest !== guestToken) throw new Error('Guest session ended.');
    if (response.status === 401) {
        finishGuest('Your session ended. Sign in or continue as a guest.');
        throw new Error('Guest session ended.');
    }
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Request failed');
    }
    return response;
}
async function request(path, data) {
    const guest = guestToken;
    const result = await (await api(path, data)).json();
    if (guest !== guestToken) throw new Error('Guest session ended.');
    return result;
}
function unlockButtons() {
    lockedButtons.forEach(([button, disabled]) => button.disabled = disabled);
    lockedButtons = [];
    document.querySelectorAll('.step').forEach((button, i) => button.disabled = i > unlocked);
}
async function task(action) {
    if (busy || !guestToken) return;
    const guest = guestToken;
    busy = true;
    lockedButtons = [...document.querySelectorAll('button:not(#endGuest)')].map(button => [button, button.disabled]);
    lockedButtons.forEach(([button]) => button.disabled = true);
    notice('Working on your case…');
    try {
        await action();
        if (guest === guestToken) notice('');
    } catch (error) {
        if (guest === guestToken) notice(error.message);
    } finally {
        if (guest === guestToken) {
            busy = false;
            unlockButtons();
        }
    }
}
function show(stage) {
    document.querySelectorAll('.stage').forEach((section, index) => section.hidden = index !== stage);
    document.querySelectorAll('.step').forEach((button, index) => {
        button.classList.toggle('active', index === stage);
        if (index === stage) button.setAttribute('aria-current', 'step');
        else button.removeAttribute('aria-current');
    });
    if (stage === 3) updateDraftRecommendation();
    window.scrollTo({top: 0, behavior: 'smooth'});
}
function list(items){return '<ul>'+items.map(x=>'<li>'+passageLinks(x)+'</li>').join('')+'</ul>';}

const calendarLabel = new Intl.DateTimeFormat('en-IN', {
    day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC',
});
function renderTimeline(events) {
    let previousDay = null;
    return events.map((event, index) => {
        const day = event.date ? calendarLabel.format(new Date(event.date + 'T00:00:00Z')) : event.day || '';
        const heading = day && day !== previousDay ? '<h4 class="timeline-day">' + esc(day) + '</h4>' : '';
        previousDay = day;
        const timing = esc(event.time || ('Event ' + (index + 1)));
        return heading + '<div class="event"><time>' + timing + '</time><div><p>' +
            esc(event.description) + '</p><small>' + passageLinks(event.basis) + '</small></div></div>';
    }).join('');
}
let insights = null;
let timelineChanges = null;
let reviewSnapshot = null;

function renderInsights() {
    const focus = insights?.follow_up;
    $('focusedFollowUp').hidden = !focus;
    $('focusedQuestion').textContent = focus?.question || '';
    $('focusedWhy').textContent = focus?.why || '';
    $('focusedAnswer').value = '';
    const map = insights?.fact_map;
    $('factMap').hidden = !map;
    $('factMapContent').innerHTML = map ? `
        <p class="fine">Evidence links are suggestions for review. Check what each passage actually says.</p>
        ${map.rows.map(row => `<article class="fact-row">
            <h4>Event ${row.event} · ${esc(row.fact)}</h4>
            <p><strong>Reported source</strong> ${passageLinks(row.basis)}</p>
            ${row.materials.map(link => `<p><strong>${esc(link.label)}</strong> ${passageLinks(link.ref)}<br>
                <span class="fine">${esc(link.excerpt)}</span></p>`).join('')}
            ${row.related_notes.length ? '<p><strong>Related notes from your account</strong></p>' + list(row.related_notes) : ''}
            ${row.conflicts.length ? '<p><strong>Possible conflicting detail</strong></p>' + list(row.conflicts) : ''}
            <p class="fine">${esc(row.gap)}</p>
        </article>`).join('')}` : '';
}

function eventLine(event) {
    return [event.date || event.day, event.time, event.description, event.basis].filter(Boolean).join(' · ');
}

function timelineChangeLines(changes) {
    if (!changes) return [];
    const fields = {goal: 'Desired outcome', location: 'Location', evidence: 'Evidence notes', contradictions: 'Conflicting details'};
    return [
        ...(changes.order_changed ? ['The order of previously reported events changed.'] : []),
        ...changes.added.map(event => 'Added event: ' + eventLine(event)),
        ...changes.updated.map(pair => 'Updated event: ' + eventLine(pair.before) + ' → ' + eventLine(pair.after)),
        ...changes.removed.map(event => 'Removed from the revised timeline: ' + eventLine(event)),
        ...changes.changed_fields.map(field => fields[field] + ' updated.'),
        ...changes.added_pages.map(ref => 'Added evidence passage ' + ref),
        ...changes.removed_pages.map(ref => 'Removed evidence passage ' + ref),
        ...changes.changed_pages.map(ref => 'Replaced evidence passage ' + ref),
    ];
}

function reviewChangeLines(changes) {
    if (!changes) return [];
    return [
        ...(changes.stage_changed ? ['The reported case stage changed.'] : []),
        ...changes.law_changes.map(law => law.title + ': ' + law.before + ' → ' + law.after),
        ...changes.new_next_steps.map(step => 'New next step: ' + step),
        ...changes.removed_next_steps.map(step => 'Earlier next step removed: ' + step),
    ];
}

function renderRecord() {
    const facts = [
        '<p>' + esc(record.summary) + '</p>',
        '<p><strong>Desired outcome:</strong> ' + esc(record.goal) + '</p>',
        '<p><strong>Location:</strong> ' + esc(record.location) + '</p>',
        '<h3>Timeline</h3>' + renderTimeline(record.events),
        '<h3>Evidence reported or provided</h3>' + (record.evidence.length ? list(record.evidence) :
            '<p>You can explore possible legal issues from your description and add supporting material later.</p>'),
    ];
    if (!insights?.follow_up && record.questions.length && !insights?.seen_questions?.length) {
        facts.push('<details><summary>Open questions from intake</summary>' + list(record.questions) + '</details>');
    }
    if (record.contradictions.length) facts.push('<h3>Conflicting details</h3>' + list(record.contradictions));
    $('caseContent').innerHTML = facts.join('');
    $('timelineChanges').innerHTML = timelineChanges ?
        '<details class="scope" open><summary>What changed in your timeline</summary>' +
        list(timelineChangeLines(timelineChanges).length ? timelineChangeLines(timelineChanges) :
            ['No changes were detected in the events or evidence list.']) + '</details>' : '';
    renderInsights();
    $('recordEditor').value = JSON.stringify(record, null, 2);
    $('confirmed').checked = false;
    $('caseReview').hidden = false;
}
function courtGuidanceText({suggestions, route}) {
    const decisions = suggestions.map(item => [
        `${item.purpose} · ${item.title}`, `${item.court} · ${item.date} · ${item.reference}`,
        item.takeaway, item.connection, item.difference, item.preparation, item.url,
    ].join('\n'));
    if (route) decisions.push([route.title, route.details, route.url].join('\n'));
    return decisions.join('\n\n');
}

function renderCourtGuidance(guidance) {
    const section = $('courtGuidance');
    section.hidden = !guidance;
    section.replaceChildren();
    if (!guidance) return;
    const {suggestions, route} = guidance;
    const cards = suggestions.map((item, index) => `
        <details class="card court-decision" ${index === 0 ? 'open' : ''}>
          <summary><strong>${esc(item.title)}</strong>
            <span class="fine">${esc(item.purpose)} · ${esc(item.court)} · ${esc(item.date)}</span>
          </summary>
          <p class="fine">${esc(item.reference)}</p>
          <dl>
            <dt>What the court decided</dt><dd>${esc(item.takeaway)}</dd>
            <dt>Why it came up for your case</dt><dd>${esc(item.connection)}</dd>
            <dt>What to check before relying on it</dt><dd>${esc(item.difference)}</dd>
            <dt>What you can prepare</dt><dd>${esc(item.preparation)}</dd>
          </dl>
          ${officialLink(item.url, 'Read the official judgment or order ↗')}
        </details>`).join('');
    section.innerHTML = `
      <h3 id="courtGuidanceHeading">Court decisions to compare</h3>
      <p class="fine">Suggestions from a selected library of Indian court decisions. Check the facts, current law and later rulings before citing a decision.</p>
      ${cards || '<p>No reviewed decision in this library matched the details supplied so far.</p>'}
      ${route ? `<div class="court-route">
        <h4>Reporting or filing under current law</h4>
        <p><strong>${esc(route.title)}</strong></p><p>${esc(route.details)}</p>
        ${officialLink(route.url, 'Read the official provision ↗')}
      </div>` : ''}`;
}

function evidencePlanText(plan) {
    return [plan.heading, plan.safety, ...(plan.scene_points || []), ...plan.prompts, ...plan.suggestions.map(row =>
        [row.title, row.look_for, row.why, row.action].join('\n'))].filter(Boolean).join('\n\n');
}

function renderEvidencePlan(plan) {
    const section = $('evidencePlan');
    if (!plan) {
        section.hidden = true;
        section.replaceChildren();
        return;
    }
    section.innerHTML = `
        <h2>${esc(plan.heading)}</h2>
        <p>Use the checks that fit your account. Record what you observed and what is still uncertain.</p>
        ${plan.safety ? `<p class="scene-safety">${esc(plan.safety)}</p>` : ''}
        <details>
            <summary>${plan.scene ? 'Questions about the scene' : 'Questions to clarify'}</summary>
            ${plan.scene_points?.length ? '<h3>From your timeline</h3>' + list(plan.scene_points) : ''}
            ${list(plan.prompts)}
        </details>
        <div class="evidence-checks">
          ${plan.suggestions.map(row => `
            <details>
                <summary>${esc(row.title)}</summary>
                <dl>
                    <dt>What to look for</dt><dd>${esc(row.look_for)}</dd>
                    <dt>Why it matters</dt><dd>${esc(row.why)}</dd>
                    <dt>What you can do safely</dt><dd>${esc(row.action)}</dd>
                </dl>
            </details>`).join('')}
        </div>`;
    section.hidden = false;
}

function renderAnalysis() {
    const cards = [`<article class="card"><h2>Case overview</h2><p>${passageLinks(analysis.overview)}</p></article>`];
    const indexedLaws = analysis.laws.map((law, index) => ({law, number: index + 1}));
    const groups = [
        ['supported', 'Possible starting points'],
        ['conditional', 'Provisions to revisit as facts develop'],
        ['unsupported', 'Less likely on current facts'],
    ];
    for (const [support, heading] of groups) {
        const laws = indexedLaws.filter(item => item.law.support === support);
        if (!laws.length) continue;
        cards.push(`<h2 class="group-title">${esc(heading)}</h2>`);
        for (const {law, number} of laws) {
            const source = sourceList.find(entry => entry.id === law.source_id);
            const distinctUse = law.when_to_use && law.when_to_use !== law.connection;
            const specificIssue = law.issue && law.issue !== 'Which legal requirements match the reported events?';
            cards.push(`<article class="card">
                ${law.case_stage === 'follow_up' ? '<div class="status">Possible follow-up</div>' : ''}
                <div class="law-title">
                    <h2>${esc(source.title)} · ${esc(source.section)}</h2>
                    <button class="citation" data-source="${esc(source.id)}" data-number="${number}" aria-label="Open citation ${number}">(${number})</button>
                </div>
                ${specificIssue ? `<p><strong>${esc(law.issue)}</strong></p>` : ''}
                <p>${esc(law.explanation)}</p>
                <dl>
                    ${distinctUse ? `<dt>When it may apply</dt><dd>${esc(law.when_to_use)}</dd>` : ''}
                    <dt>How it connects to your account</dt><dd>${passageLinks(law.connection)}</dd>
                    <dt>What to clarify</dt><dd>${esc(law.missing)}</dd>
                    <dt>When it may not fit</dt><dd>${esc(law.objection)}</dd>
                </dl>
            </article>`);
        }
    }
    cards.push(`<article class="card">
        <h2>Next steps</h2>${list(analysis.next_steps)}
        <p class="fine">Your account and supporting material have not been independently verified.</p>
        <details><summary>Limits of this review</summary>${list(analysis.limits)}</details>
    </article>`);
    $('legalContent').innerHTML = cards.join('');
    const changes = reviewChangeLines(analysis.changes);
    $('reviewChanges').innerHTML = analysis.changes ? `
        <details class="scope" open>
          <summary>What changed since the last review</summary>
          ${changes.length ? list(changes) : '<p>The suggested provisions and next steps stayed the same.</p>'}
          <p class="fine">${analysis.changes.revised_inputs.length ?
              'This review used ' + esc(analysis.changes.revised_inputs.join(', ')) + '.' :
              'This comparison shows differences between the two reviews.'}</p>
        </details>` : '';
    if (analysis.evidence_plan) renderEvidencePlan(analysis.evidence_plan);
    renderCourtGuidance(analysis.court_guidance);
    $('scenarioContent').innerHTML = analysis.scenarios.length ? analysis.scenarios.map(scenario => `
        <article class="card">
            <h2>${esc(scenario.question)}</h2>
            <p>${esc(scenario.effect)}</p>
            <p><strong>How to prepare</strong><br>${esc(scenario.preparation)}</p>
        </article>`).join('') : '<div class="card"><p>No case-specific practice questions are available for this review.</p></div>';
    $('demand').value = record.goal;
}
function citation(id, number) {
    const source = sourceList.find(item => item.id === id);
    const law = analysis.laws.find(item => item.source_id === id);
    if (!source || !law) return;
    const distinctUse = law.when_to_use && law.when_to_use !== law.connection;
    $('citationContent').innerHTML = `
        <div class="eyebrow">Source (${esc(number)})</div>
        <h2>${esc(source.title)} · ${esc(source.section)}</h2>
        <p>${esc(law.explanation)}</p>
        ${distinctUse ? `<p><strong>When it may apply</strong><br>${esc(law.when_to_use)}</p>` : ''}
        <p><strong>How it connects to your account</strong><br>${passageLinks(law.connection)}</p>
        ${source.elements?.length ? '<h3>Conditions to check</h3>' + list(source.elements) : ''}
        ${law.source_check ? `<details>
            <summary>How this source was checked</summary>
            <p>${esc(law.source_check.status)}.</p>
            ${law.source_check.scope?.length ? list(law.source_check.scope) : ''}
            ${law.source_check.passages.map(pair =>
                `${pair.partial ? '' : '<p>' + esc(pair.claim) + '</p>'}<blockquote>${esc(pair.quote)}${pair.partial ? ' …' : ''}</blockquote>`).join('')}
        </details>` : ''}
        <h3>Original statutory excerpt</h3>
        <pre class="source-text">${esc(source.text)}</pre>
        ${officialLink(source.url, 'Open official legislation ↗')}
        ${judgmentExamples(source.examples)}
        <details>
            <summary>Source details</summary>
            <p>${esc(source.status)}</p>
            <p>${esc(source.version)}</p>
            <p>Excerpt checked ${esc(source.verified_on)}</p>
        </details>`;
    $('citationDialog').showModal();
}
document.querySelectorAll('.step').forEach((b,i)=>b.onclick=()=>show(i));
$('sample').onclick=()=>{demo=true;$('story').value=config.sample;$('language').value='English';$('evidence').value='';$('mode').textContent='Scripted sample · no AI call';notice('This is a fictional, scripted demonstration. Edit the story to leave sample mode.');};
function dirty(){demo=false;unlocked=0;document.querySelectorAll('.step').forEach((b,i)=>b.disabled=i>0);$('caseReview').hidden=true;$('documentOutput').hidden=true;$('mode').textContent=config?.live?'Live AI configured':'Offline extraction';}
function noteEvidenceChange() {
    if (record) {
        notice('Evidence selection changed. Add a short case update to apply it to the timeline.');
    } else {
        dirty();
    }
}

$('story').addEventListener('input',dirty);$('evidence').addEventListener('input',dirty);$('language').addEventListener('change',dirty);
async function submitCaseUpdate(update, focus) {
    if (!update) throw new Error('Add a correction or update first.');
    const evidence = $('evidence').value;
    const result = await request('follow-up', {story: update, evidence, documents: selectedPages(),
        question_key: focus?.key});
    rememberDraft();
    if (focus) remember('Case Companion', 'Follow-up question', focus.question);
    remember('You', 'Case update', update);
    record = result.record;
    insights = result.insights;
    timelineChanges = result.changes;
    const summary = timelineChangeLines(timelineChanges);
    if (summary.length) remember('Case Companion', 'Timeline changes', summary.join('\n'));
    remember('Case Companion', 'Revised timeline', recordText(record));
    demo = false;
    unlocked = 0;
    resetAnalysis();
    if (!focus) $('clarification').value = '';
    $('mode').textContent = result.mode;
    renderRecord();
}
$('clarify').onclick = () => task(() => submitCaseUpdate($('clarification').value.trim()));
$('answerFocus').onclick = () => task(() => submitCaseUpdate($('focusedAnswer').value.trim(), insights?.follow_up));
$('skipFocus').onclick = () => task(async () => {
    const focus = insights?.follow_up;
    if (!focus) return;
    const result = await request('skip-question', {key: focus.key});
    insights = result.insights;
    renderInsights();
});
$('evidenceFile').onchange = async () => {
    const guest = guestToken;
    const file = $('evidenceFile').files[0];
    if (!guest || !file) return;
    if (!file.name.toLowerCase().endsWith('.txt') || file.size > 100000) {
        notice('Choose a .txt file smaller than 100 KB.');
        return;
    }
    const content = await file.text();
    if (guest !== guestToken) return;
    $('evidence').value += '\n\nEvidence file: ' + file.name + '\n' + content;
    noteEvidenceChange();
};
$('intake').onclick=()=>task(async()=>{const result=await request('intake',{story:$('story').value,evidence:$('evidence').value,language:$('language').value,demo,documents:demo?[]:selectedPages()});if (!caseId) { $('procedureStage').value='unknown'; $('procedureDetails').value=''; updateProcedureQuestion(); } caseId=result.id;record=result.record;insights=result.insights;timelineChanges=null;reviewSnapshot=null;rememberDraft();remember('You', 'Story and evidence', [$('story').value, $('evidence').value].filter(Boolean).join('\n\n'));remember('Case Companion', 'Case summary and timeline', recordText(record));resetAnalysis();unlocked=0;$('mode').textContent=result.mode;$('documentOutput').hidden=true;renderRecord();$('caseReview').scrollIntoView({behavior:'smooth'});});
const stageQuestions = {
    unknown: 'Has anyone filed a complaint or received an official document?',
    starting: 'What decision or outcome do you need help with first?',
    reported: 'Where and when did you file or report it? What status were you given?',
    notice: 'When did you receive it, what does it ask for, and what date is shown?',
    hearing: 'When is the hearing and what issue is listed?',
    decision: 'When did you receive the decision, what did it direct, and what part concerns you?',
};
function updateProcedureQuestion() {
    $('procedureLabel').textContent = stageQuestions[$('procedureStage').value];
}
$('procedureStage').onchange = updateProcedureQuestion;
updateProcedureQuestion();

function resetAnalysis() {
    analysis = null;
    sourceList = [];
    renderEvidencePlan(null);
    renderCourtGuidance(null);
    for (const id of ['legalContent', 'scenarioContent', 'practiceFeedback', 'reviewChanges']) {
        $(id).replaceChildren();
    }
    for (const id of ['toScenarios', 'practiceForm', 'documentOutput']) {
        $(id).hidden = true;
    }
    $('practiceAnswer').value = '';
    $('draftText').value = '';
}

$('confirm').onclick = () => task(async () => {
    if (!$('confirmed').checked) throw new Error('Check the confirmation box after reviewing your account.');
    let edited;
    try {
        edited = JSON.parse($('recordEditor').value);
    } catch {
        throw new Error('Correct the structured case JSON before confirming.');
    }
    const confirmed = await request('confirm', {record: edited});
    rememberDraft();
    record = confirmed.record;
    insights = confirmed.insights;
    renderRecord();
    $('confirmed').checked = true;
    remember('You', 'Confirmed account', recordText(record));
    demo = confirmed.demo;
    resetAnalysis();
    renderCourtGuidance(confirmed.court_guidance);
    if (confirmed.court_guidance) {
        const decisions = courtGuidanceText(confirmed.court_guidance);
        if (decisions) remember('Case Companion', 'Court decisions and filing guidance', decisions);
    }
    if (confirmed.evidence_plan) {
        renderEvidencePlan(confirmed.evidence_plan);
        remember('Case Companion', confirmed.evidence_plan.heading, evidencePlanText(confirmed.evidence_plan));
    }
    unlocked = 1;
    show(1);
});

$('legalForm').onsubmit = event => {
    event.preventDefault();
    task(async () => {
        const result = await request('analyse', {
            stage: $('procedureStage').value,
            details: $('procedureDetails').value,
        });
        reviewSnapshot = result.review_snapshot;
        rememberDraft();
        remember('You', 'Latest procedural step', [stageQuestions[$('procedureStage').value], $('procedureDetails').value].filter(Boolean).join('\n'));
        remember('Case Companion', 'Legal analysis and scenarios', analysisText(result));
        const draftInputs = Object.fromEntries(['demand', 'reference'].map(id => [id, $(id).value]));
        const hadAnalysis = Boolean(analysis);
        resetAnalysis();
        analysis = result.analysis;
        sourceList = result.sources;
        renderAnalysis();
        if (hadAnalysis) {
            for (const [id, value] of Object.entries(draftInputs)) $(id).value = value;
        }
        const guidance = document.createElement('div');
        guidance.className = 'card';
        guidance.innerHTML = `<h2>Next step for your stage</h2><p><strong>${esc(analysis.procedure.label)}</strong></p><p>${esc(analysis.procedure.guidance)}</p>`;
        $('legalContent').prepend(guidance);
        $('practiceScenario').innerHTML = analysis.scenarios.map((scenario, index) =>
            `<option value="${index}">${esc(scenario.question)}</option>`).join('');
        $('practiceForm').hidden = !analysis.scenarios.length;
        $('toScenarios').hidden = false;
        unlocked = 3;
        guidance.scrollIntoView({behavior: 'smooth'});
    });
};

$('practiceScenario').onchange = () => {
    $('practiceAnswer').value = '';
    $('practiceFeedback').replaceChildren();
};
$('practiceAnswer').oninput = () => $('practiceFeedback').replaceChildren();
$('practiceForm').onsubmit = event => {
    event.preventDefault();
    task(async () => {
        const scenario = $('practiceScenario').value;
        const answer = $('practiceAnswer').value;
        const question = $('practiceScenario').selectedOptions[0]?.textContent || '';
        const result = await request('rehearse', {scenario: Number(scenario), answer});
        remember('You', 'Practice answer', [question, answer].filter(Boolean).join('\n\n'));
        remember('Case Companion', 'Practice feedback', result.feedback + '\n\n' + result.suggestion);
        if (scenario !== $('practiceScenario').value || answer !== $('practiceAnswer').value) return;
        $('practiceFeedback').innerHTML = `<h3>${esc(result.mode)}</h3><p>${esc(result.feedback)}</p><p><strong>Suggested wording or structure</strong><br>${esc(result.suggestion)}</p>`;
    });
};
$('legalContent').onclick=e=>{const b=e.target.closest('[data-source]');if(b)citation(b.dataset.source,b.dataset.number);};
$('closeCitation').onclick=()=>$('citationDialog').close();
$('citationDialog').onclick=e=>{if(e.target===$('citationDialog'))$('citationDialog').close();};
$('toScenarios').onclick=()=>show(2);$('toDocuments').onclick=()=>show(3);
const draftFields = ['kind', 'sender', 'recipient', 'subject', 'reference', 'facts', 'demand', 'enclosures'];

function updateDraftRecommendation() {
    const suggestion = $('draftRecommendation');
    suggestion.hidden = !analysis || !record;
    if (suggestion.hidden) return;
    const ids = analysis.laws.map(law => law.source_id);
    const facts = [record.summary, analysis.procedure?.details, ...record.events.map(event => event.description)].join(' ');
    let kind = 'Case brief';
    if (analysis.procedure?.stage === 'notice' && /\b(?:legal notice|notice of breach|demand notice|notice to comply)\b/i.test(facts)) {
        kind = 'Reply to notice';
    } else if (ids.some(id => id.startsWith('fssa-'))) {
        kind = 'Food safety grievance';
    } else if (ids.includes('cpa-35') && !ids.some(id => id.startsWith('sra-'))) {
        kind = 'Consumer commission complaint';
    } else if (analysis.procedure?.stage === 'starting' && ids.some(id => /^bns-(30[3459]|63|64)$/.test(id))) {
        kind = 'Written police complaint';
    }
    suggestion.textContent = `Suggested format for review: ${kind}. Choose the document that matches your intended next step.`;
}

function renderDraftFields() {
    const spec = config?.document_formats?.[$('kind').value];
    if (!spec) return;
    $('senderLabel').textContent = spec.parties[0];
    $('recipientLabel').textContent = spec.parties[1];
    $('demandLabel').textContent = spec.action;
    $('formatHelp').innerHTML = esc(spec.help) + (spec.source ? ' ' + officialLink(spec.source, 'Official guidance ↗') : '');
    const current = Object.fromEntries([...$('formatFields').querySelectorAll('textarea')].map(field => [field.name, field.value]));
    $('formatFields').innerHTML = Object.entries(spec.fields).map(([key, label]) => `
        <label for="document-${esc(key)}">${esc(label)}</label>
        <textarea name="${esc(key)}" id="document-${esc(key)}" autocomplete="off" rows="2" maxlength="3000"></textarea>`).join('');
    for (const field of $('formatFields').querySelectorAll('textarea')) field.value = current[field.name] ?? '';
}

$('kind').onchange = renderDraftFields;
$('copyDraftTimeline').onclick = () => {
    if (!record) return;
    const lines = record.events.map(event => {
        const mark = [event.date ? calendarLabel.format(new Date(event.date + 'T00:00:00Z')) : event.day, event.time].filter(Boolean).join(', ');
        return (mark ? mark + ' — ' : '') + event.description.replace(/\s+/g, ' ').trim();
    });
    const current = $('facts').value.trim();
    $('facts').value = [current, lines.join('\n')].filter(Boolean).join('\n').slice(0, 26000);
    $('facts').focus();
};
$('draft').onclick = () => task(async () => {
    rememberDraft();
    const options = Object.fromEntries(draftFields.map(key => [key, $(key).value]));
    for (const field of $('formatFields').querySelectorAll('textarea')) options[field.name] = field.value;
    const result = await request('draft', {options});
    $('draftText').value = result.draft;
    rememberDraft();
    $('documentOutput').hidden = false;
});
function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),5000);}
$('export').onclick=()=>task(async()=>{let template=null;const f=$('template').files[0];if(f){if(f.size>1000000)throw new Error('Template must be smaller than 1 MB.');const bytes=new Uint8Array(await f.arrayBuffer());let binary='';for(const byte of bytes)binary+=String.fromCharCode(byte);template=btoa(binary);}const guest = guestToken;const response=await api('export',{text:$('draftText').value,font:$('font').value,size:Number($('size').value),template});const blob = await response.blob();if (guest === guestToken) download(blob,'case-draft.docx');});
$('print').onclick = () => {
    const area = $('printArea');
    area.replaceChildren(...$('draftText').value.split('\n\n').map((text, index) => {
        const paragraph = document.createElement('p');
        paragraph.textContent = text;
        const caption = text.startsWith('BEFORE ') || text === 'VERSUS';
        paragraph.classList.toggle('print-center', caption || index < 2);
        paragraph.classList.toggle('print-heading', caption || (/\p{Lu}/u.test(text) && !text.includes('\n') && text === text.toUpperCase()));
        return paragraph;
    }));
    area.style.fontFamily = $('font').value;
    area.style.fontSize = $('size').value + 'pt';
    window.print();
};
function clearCaseScreen() {
    caseId = null;
    record = null;
    insights = null;
    timelineChanges = null;
    reviewSnapshot = null;
    renderInsights();
    $('timelineChanges').replaceChildren();
    chatEntries = [];
    renderHistory();
    if ($('caseFileDialog').open) $('caseFileDialog').close();
    clearPDFs();
    resetAnalysis();
    demo = false;
    unlocked = 0;
    $('procedureStage').value = 'unknown';
    $('language').value = 'English';
    $('kind').value = 'Case brief';
    $('formatFields').replaceChildren();
    renderDraftFields();
    updateProcedureQuestion();
    for (const id of ['story', 'evidence', 'draftText', 'sender', 'recipient', 'demand',
        'reference', 'subject', 'facts', 'enclosures', 'procedureDetails', 'recordEditor', 'clarification', 'template', 'evidenceFile']) {
        $(id).value = '';
    }
    for (const id of ['caseContent', 'citationContent', 'printArea', 'practiceScenario']) {
        $(id).replaceChildren();
    }
    if ($('citationDialog').open) $('citationDialog').close();
    $('caseReview').hidden = true;
    $('documentOutput').hidden = true;
    $('confirmed').checked = false;
    $('consent').checked = false;
    $('mode').textContent = accountUsername ? 'Local workspace' : 'Guest';
    show(0);
}
$('clear').onclick = () => task(async () => {
    if (caseId) await request('clear');
    clearCaseScreen();
});

function refreshGuestTimer() {
    clearTimeout(idleTimer);
    idleTimer = setTimeout(() => finishGuest('Your session expired.'), (config?.guest_idle_seconds || 1800) * 1000);
}

function finishGuest(message = '') {
    const guest = guestToken;
    guestToken = null;
    accountUsername = null;
    renderAccount();
    $('accountForm').reset();
    clearTimeout(idleTimer);
    busy = false;
    clearCaseScreen();
    unlockButtons();
    notice('');
    $('guestStatus').textContent = message;
    if (!$('guestGate').open) $('guestGate').showModal();
    if (guest) {
        fetch('/api/guest-end', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({guest}), keepalive: true,
        }).then(response => {
            if (!response.ok && response.status !== 401) throw new Error();
        }).catch(() => {
            if (!guestToken) $('guestStatus').textContent =
                'This workspace is cleared. The server will expire the session automatically if it did not receive the close request.';
        });
    }
}
$('guestGate').addEventListener('cancel', event => event.preventDefault());
function renderAccount() {
    $('accountName').hidden = !accountUsername;
    $('accountName').textContent = accountUsername || '';
    $('endGuest').textContent = accountUsername ? 'Sign out' : 'End session';
}

async function openSession(path, payload) {
    const buttons = ['startGuest', 'signIn', 'createAccount'].map(id => $(id));
    buttons.forEach(button => button.disabled = true);
    try {
        $('guestStatus').textContent = '';
        const response = await fetch('/api/' + path, {
            method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Could not open the workspace.');
        guestToken = result.guest;
        accountUsername = result.username || null;
        renderAccount();
        $('mode').textContent = accountUsername ? 'Local workspace' : 'Guest';
        refreshGuestTimer();
        $('accountForm').reset();
        $('guestGate').close();
        $('story').focus();
    } catch (error) {
        $('guestStatus').textContent = error.message;
        $('accountPassword').value = '';
    } finally {
        buttons.forEach(button => button.disabled = false);
    }
}

$('startGuest').onclick = () => openSession('guest', {});
$('accountForm').onsubmit = event => {
    event.preventDefault();
    const creating = event.submitter?.id === 'createAccount';
    const username = $('username').value.trim();
    const password = $('accountPassword').value;
    openSession(creating ? 'register' : 'login', {username, password});
};
$('endGuest').onclick = () => finishGuest(accountUsername ? 'Signed out. Workspace cleared.' : 'Guest workspace cleared.');
window.addEventListener('pagehide', () => {
    if (guestToken) finishGuest();
});
window.addEventListener('pageshow', event => {
    if (event.persisted) finishGuest();
});
fetch('/api/config').then(r=>r.json()).then(c=>{
    config=c;
    $('consent').disabled=!c.live;
    $('modeHelp').textContent=c.live?'Local by default. OpenRouter requests require zero-retention routing.':'Local mode is available in English. Live AI is unavailable.';
    $('kind').replaceChildren(...Object.keys(c.document_formats).map(kind => new Option(kind, kind)));
    $('kind').value = 'Case brief';
    renderDraftFields();
}).catch(()=>notice('Could not reach the local server. Start server.py and reload.'));

const pdfDocuments = new Map();
let nextDocument = 1;

function selectedPages() {
    const pages = [];
    for (const [document, entry] of pdfDocuments) {
        for (const page of entry.pages) {
            if (page.selected) pages.push({document, page: page.page, text: page.text});
        }
    }
    if (pages.length > 8) throw new Error('Select up to eight PDF pages.');
    return pages;
}

function clearPDFs() {
    pdfDocuments.clear();
    nextDocument = 1;
    $('pdfFile').value = '';
    $('pdfPages').replaceChildren();
    if ($('passageDialog').open) $('passageDialog').close();
    $('passageText').textContent = '';
    $('passageTitle').textContent = '';
}

function renderPDFs() {
    $('pdfPages').innerHTML = [...pdfDocuments].map(([id, entry]) => `
        <div class="card">
          <h3>${esc(id)} · ${esc(entry.name)}</h3>
          <p class="fine">${entry.pages.length} of ${entry.pageCount} pages have readable text.</p>
          ${entry.pages.map(page => `
            <label class="check">
                <input type="checkbox" data-pdf="${id}" value="${page.page}" ${page.selected ? 'checked' : ''}>
                Use page ${page.page}${page.truncated ? ' (first 4,000 characters)' : ''}
            </label>
            <button type="button" class="quiet" data-passage="${id}:${page.page}">Preview page ${page.page}</button>
          `).join('')}
          <p><button type="button" class="quiet" data-remove-pdf="${id}">Remove PDF</button></p>
        </div>`).join('');
}

$('pdfFile').onchange = () => task(async () => {
    const input = $('pdfFile');
    const file = input.files[0];
    input.value = '';
    if (!file) return;
    if (file.size > 2_000_000) throw new Error('Choose a PDF under 2 MB.');
    if (pdfDocuments.size >= 4 || nextDocument > 999) {
        throw new Error('You can keep up to four PDFs in the workspace. Remove a PDF to add another.');
    }
    const bytes = new Uint8Array(await file.arrayBuffer());
    let binary = '';
    for (let start = 0; start < bytes.length; start += 8192) {
        binary += String.fromCharCode(...bytes.subarray(start, start + 8192));
    }
    const result = await request('pdf-preview', {pdf: btoa(binary)});
    pdfDocuments.set('D' + nextDocument++, {
        name: file.name, pageCount: result.page_count, pages: result.pages,
    });
    noteEvidenceChange();
    renderPDFs();
});

$('pdfPages').onchange = event => {
    if (!event.target.matches('[data-pdf]')) return;
    const page = pdfDocuments.get(event.target.dataset.pdf).pages.find(p => p.page === Number(event.target.value));
    if (busy) { event.target.checked = Boolean(page.selected); return; }
    page.selected = event.target.checked;
    try {
        selectedPages();
    } catch (error) {
        page.selected = event.target.checked = false;
        notice(error.message);
        return;
    }
    noteEvidenceChange();
};

function passageLinks(value) {
    return esc(value).replace(/\[(D[1-9]\d{0,2}) p\.(\d{1,2})\]/g, (ref, id, page) => {
        const known = pdfDocuments.get(id)?.pages.some(row => row.selected && row.page === Number(page));
        return known ? `<button type="button" class="citation" data-passage="${id}:${page}">${ref}</button>` : ref;
    });
}

document.addEventListener('click', event => {
    const button = event.target.closest('[data-passage], [data-remove-pdf]');
    if (!button || busy) return;
    if (button.dataset.removePdf) {
        const id = button.dataset.removePdf;
        pdfDocuments.delete(id);
        renderPDFs();
        noteEvidenceChange();
        return;
    }
    const [id, number] = button.dataset.passage.split(':');
    const entry = pdfDocuments.get(id);
    const passage = entry?.pages.find(row => row.page === Number(number));
    if (!passage) return;
    $('passageTitle').textContent = `${entry.name} · PDF page ${number}`;
    $('passageText').textContent = passage.text;
    $('passageDialog').showModal();
});

const officialSourceHosts = new Set([
    'api.sci.gov.in', 'consumeraffairs.gov.in', 'www.fssai.gov.in',
    'www.indiacode.nic.in', 'indiacode.gov.in', 'www.mha.gov.in', 'www.ncrb.mha.gov.in',
    'e-jagriti.gov.in', 'foscos.fssai.gov.in',
]);
function officialLink(value, label) {
    try {
        const url = new URL(value);
        if (url.protocol === 'https:' && !url.username && !url.password && !url.port &&
            officialSourceHosts.has(url.hostname)) {
            return `<a href="${esc(url.href)}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>`;
        }
    } catch {
        // A missing or invalid source URL must not become a clickable link.
    }
    return '';
}

function judgmentExamples(examples = []) {
    if (!examples.length) return '<h3>Court examples</h3><p>This section has no reviewed example yet.</p>';
    return '<h3>Court examples</h3>' + examples.map(item => `
        <article class="card">
          <h4>${esc(item.title)}</h4>
          <p class="fine">${esc(item.court)} · ${esc(item.date)} · ${esc(item.reference)}</p>
          <p>${esc(item.takeaway)}</p>
          <p><strong>What to compare</strong> ${esc(item.difference)}</p>
          ${officialLink(item.url, 'Open official decision ↗')}
        </article>`).join('') + '<p class="fine">These examples were checked against the linked decisions. Later case history has not been comprehensively checked.</p>';
}

let chatEntries = [];
let fileAction = '';
const caseFileMagic = new TextEncoder().encode('CASECOMPANION1\n');
const caseFileLimit = 10_000_000;

function remember(speaker, title, text) {
    chatEntries.push({speaker, title, text});
    renderHistory();
}

function renderHistory() {
    $('historyPanel').hidden = !chatEntries.length;
    // Imported text is treated as user content and rendered without HTML.
    const fragment = document.createDocumentFragment();
    for (const entry of chatEntries) {
        const item = document.createElement('details');
        const summary = document.createElement('summary');
        summary.textContent = entry.speaker + ' · ' + entry.title;
        const body = document.createElement('pre');
        body.className = 'source-text';
        body.textContent = entry.text;
        item.append(summary, body);
        fragment.append(item);
    }
    $('chatHistory').replaceChildren(fragment);
}

function recordText(caseRecord) {
    const events = caseRecord.events.map(event => {
        const time = [event.date || event.day, event.time].filter(Boolean).join(', ');
        return [time, event.description, event.basis].filter(Boolean).join(' · ');
    });
    return [caseRecord.summary, 'Desired outcome: ' + caseRecord.goal, 'Location: ' + caseRecord.location,
        'Timeline\n' + events.join('\n'),
        ...['evidence', 'questions', 'contradictions'].filter(key => caseRecord[key].length)
            .map(key => key[0].toUpperCase() + key.slice(1) + '\n' + caseRecord[key].join('\n'))].join('\n\n');
}

function analysisText({analysis: answer, sources}) {
    const laws = answer.laws.map(law => {
        const source = sources.find(item => item.id === law.source_id);
        return [source.title + ' · ' + source.section, law.relevance, law.issue, law.explanation,
            law.when_to_use, law.connection, law.missing, law.objection, law.evidence_status, source.url,
            ...(source.examples || []).map(example => [
                example.title, example.reference, example.takeaway, example.difference, example.url,
            ].filter(Boolean).join('\n'))]
            .filter(Boolean).join('\n');
    });
    return [answer.overview, answer.procedure?.guidance, answer.court_guidance && courtGuidanceText(answer.court_guidance),
        answer.evidence_plan && evidencePlanText(answer.evidence_plan),
        ...laws, ...answer.next_steps, ...answer.limits, ...reviewChangeLines(answer.changes),
        ...answer.scenarios.map(item => [item.question, item.effect, item.preparation].join('\n'))]
        .filter(Boolean).join('\n\n');
}

function rememberDraft() {
    const draft = $('draftText').value;
    if (draft && !chatEntries.some(entry => entry.title === 'Document draft' && entry.text === draft)) {
        remember('Case Companion', 'Document draft', draft);
    }
}

function caseFileKey(password, salt) {
    const subtle = globalThis.crypto?.subtle;
    if (!subtle) throw new Error('Open the app on localhost or HTTPS to use encrypted case files.');
    return subtle.importKey('raw', new TextEncoder().encode(password), 'PBKDF2', false, ['deriveKey'])
        .then(key => subtle.deriveKey({name: 'PBKDF2', hash: 'SHA-256', salt, iterations: 600000},
            key, {name: 'AES-GCM', length: 256}, false, ['encrypt', 'decrypt']));
}

function openCaseFile(action) {
    if (action === 'export' && !record) {
        notice('Organise your story first to download the case conversation.');
        return;
    }
    fileAction = action;
    const exporting = action === 'export';
    $('caseFileTitle').textContent = exporting ? 'Download entire chat' : 'Import previous chat';
    $('caseFileHelp').textContent = exporting
        ? 'This file contains your conversation, timeline and selected PDF text. Choose a password you can remember. You’ll need it to reopen the file.'
        : 'Choose a saved case file and enter its password. Import replaces the current workspace. Download the current chat first if you want to keep it.';
    $('caseFileInput').hidden = $('caseFileLabel').hidden = exporting;
    $('caseFileInput').required = !exporting;
    $('caseFilePassword').minLength = exporting ? 12 : 0;
    $('caseFileSubmit').textContent = exporting ? 'Download encrypted file' : 'Import case';
    $('caseFileDialog').showModal();
}

$('openBackup').onclick = () => openCaseFile('export');
$('openImport').onclick = () => openCaseFile('import');
$('closeCaseFile').onclick = () => $('caseFileDialog').close();
$('caseFileDialog').addEventListener('close', () => {
    $('caseFileForm').reset();
    $('caseFileStatus').textContent = '';
});
$('caseFileDialog').addEventListener('cancel', event => {
    if (busy) event.preventDefault();
});

$('caseFileForm').onsubmit = event => {
    event.preventDefault();
    task(async () => {
        const guest = guestToken;
        const password = $('caseFilePassword').value;
        const requireGuest = () => {
            if (guest !== guestToken || !$('caseFileDialog').open) throw new Error('Case file action cancelled.');
        };
        try {
            if (fileAction === 'export') {
                rememberDraft();
                const payload = {
                    version: 1, record, language: $('language').value, documents: selectedPages(),
                    story: $('story').value, evidence: $('evidence').value, history: chatEntries,
                    seen_questions: insights?.seen_questions || [], review_snapshot: reviewSnapshot,
                    stage: $('procedureStage').value, details: $('procedureDetails').value,
                    pendingUpdate: $('clarification').value,
                };
                const plain = new TextEncoder().encode(JSON.stringify(payload));
                if (chatEntries.length > 2000 || plain.byteLength > caseFileLimit - 60) throw new Error('This case exceeds the 10 MB file limit.');
                const salt = crypto.getRandomValues(new Uint8Array(16));
                const iv = crypto.getRandomValues(new Uint8Array(12));
                const key = await caseFileKey(password, salt);
                const sealed = await crypto.subtle.encrypt({name: 'AES-GCM', iv, additionalData: caseFileMagic}, key, plain);
                requireGuest();
                download(new Blob([caseFileMagic, salt, iv, sealed], {type: 'application/octet-stream'}), 'case-conversation.casecompanion');
            } else {
                const file = $('caseFileInput').files[0];
                if (!file || file.size > caseFileLimit) throw new Error('Choose a case file under 10 MB.');
                const bytes = new Uint8Array(await file.arrayBuffer());
                const offset = caseFileMagic.length;
                if (bytes.length < offset + 44 || caseFileMagic.some((byte, i) => byte !== bytes[i])) {
                    throw new Error('This file is not a Case Companion backup.');
                }
                const salt = bytes.slice(offset, offset + 16);
                const iv = bytes.slice(offset + 16, offset + 28);
                const key = await caseFileKey(password, salt);
                let saved;
                try {
                    const plain = await crypto.subtle.decrypt(
                        {name: 'AES-GCM', iv, additionalData: caseFileMagic}, key, bytes.subarray(offset + 28));
                    saved = JSON.parse(new TextDecoder().decode(plain));
                } catch {
                    throw new Error('Could not open the backup. Check the password and file.');
                }
                if (saved?.version !== 1 || !Array.isArray(saved.history) || saved.history.length > 2000 ||
                    !saved.history.every(entry => entry && ['speaker', 'title', 'text'].every(field => typeof entry[field] === 'string'))) {
                    throw new Error('This case file has an unsupported format.');
                }
                requireGuest();
                const restored = await request('import', {record: saved.record, language: saved.language, documents: saved.documents,
                    seen_questions: saved.seen_questions, review_snapshot: saved.review_snapshot});
                requireGuest();
                clearCaseScreen();
                caseId = restored.id;
                record = restored.record;
                insights = restored.insights;
                reviewSnapshot = restored.review_snapshot;
                chatEntries = saved.history;
                $('story').value = typeof saved.story === 'string' ? saved.story : '';
                $('evidence').value = typeof saved.evidence === 'string' ? saved.evidence : '';
                $('clarification').value = typeof saved.pendingUpdate === 'string' ? saved.pendingUpdate : '';
                $('language').value = saved.language || 'English';
                $('procedureStage').value = Object.hasOwn(stageQuestions, saved.stage) ? saved.stage : 'unknown';
                $('procedureDetails').value = typeof saved.details === 'string' ? saved.details : '';
                updateProcedureQuestion();
                restorePassages(restored.documents);
                renderHistory();
                $('historyPanel').open = true;
                renderRecord();
                $('mode').textContent = 'Imported case';
                $('caseReview').scrollIntoView({behavior: 'smooth'});
                $('clarification').focus({preventScroll: true});
            }
            if ($('caseFileDialog').open) $('caseFileDialog').close();
        } catch (error) {
            if (guest === guestToken && $('caseFileDialog').open) $('caseFileStatus').textContent = error.message;
        }
    });
};

function restorePassages(documents) {
    for (const page of documents) {
        const id = page.document;
        if (!pdfDocuments.has(id)) {
            pdfDocuments.set(id, {name: 'Imported PDF excerpts', pageCount: 0, pages: []});
        }
        const entry = pdfDocuments.get(id);
        entry.pages.push({...page, selected: true});
        entry.pageCount += 1;
        nextDocument = Math.max(nextDocument, Number(id.slice(1)) + 1);
    }
    renderPDFs();
}

$('guestGate').showModal();
