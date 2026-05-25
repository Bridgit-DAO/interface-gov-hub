"""Soft-launch scaffold pages: fixtures-driven, minimal Bootstrap (Meta-Layer canvas)."""
from __future__ import annotations

import html
from typing import Optional

from flask import Blueprint, current_app, request

from config import SOFT_LAUNCH_WIRED_ARTIFACT_ID
from fixtures.soft_launch import (
    HOMEPAGE,
    full_fixtures_payload,
)
from services.soft_launch_lifecycle import (
    ORDERED_STATUSES,
    STAGE_EXPLAINER,
    allowed_artifact_actions,
    index_of_status,
)

bp = Blueprint('soft_launch_pages', __name__, url_prefix='')


def _imports():
    from services.rendering import generate_user_menu, render_page

    return generate_user_menu, render_page


def _esc(s):
    return html.escape(str(s or ''), quote=True)


def _status_badge_class(status_key: str) -> str:
    key = (status_key or '').strip().lower()
    return {
        'draft': 'sl-badge sl-badge-draft',
        'under_review': 'sl-badge sl-badge-review',
        'vote_scheduled': 'sl-badge sl-badge-vote-scheduled',
        'vote_open': 'sl-badge sl-badge-voting',
        'approved': 'sl-badge sl-badge-approved',
        'implemented': 'sl-badge sl-badge-implemented',
    }.get(key, 'sl-badge sl-badge-draft')


def _lifecycle_stepper(current_status: str) -> str:
    idx = index_of_status(current_status)
    items = []
    for i, st in enumerate(ORDERED_STATUSES):
        cls = 'text-primary fw-bold' if i == idx else 'text-muted'
        items.append(f'<span class="{cls}" data-gh-i18n="softLaunch.status.{st}"></span>')
    sep = '<span class="text-muted" data-gh-i18n="softLaunch.common.stageSeparator"></span>'
    return f' {sep} '.join(items)


def _artifact_explainer_span(stored_status: str) -> str:
    st = (stored_status or '').strip().lower()
    if st not in STAGE_EXPLAINER:
        st = 'under_review'
    return f'<span data-gh-i18n="softLaunch.explainer.{st}"></span>'


def _build_homepage_html() -> str:
    h = HOMEPAGE
    activity_specs = [
        {
            'href': '/soft-launch/artifact/?scenario=under_review_ready',
            'status_key': 'under_review',
            'type_key': 'softLaunch.activityCards.agentType',
            'title_key': 'softLaunch.activityCards.agentTitle',
            'status_key_i18n': 'softLaunch.activityCards.agentStatus',
            'space_key': 'softLaunch.activityCards.agentSpace',
            'activity_key': 'softLaunch.activityCards.agentActivity',
            'updated_key': 'softLaunch.activityCards.agentUpdated',
            'cta_key': 'softLaunch.activityCards.agentCta',
        },
        {
            'href': '/soft-launch/artifact/?scenario=draft',
            'status_key': 'draft',
            'type_key': 'softLaunch.activityCards.carbonType',
            'title_key': 'softLaunch.activityCards.carbonTitle',
            'status_key_i18n': 'softLaunch.activityCards.carbonStatus',
            'space_key': 'softLaunch.activityCards.carbonSpace',
            'activity_key': 'softLaunch.activityCards.carbonActivity',
            'updated_key': 'softLaunch.activityCards.carbonUpdated',
            'cta_key': 'softLaunch.activityCards.carbonCta',
        },
    ]
    activity_cols = []
    for c in activity_specs:
        sk = c['status_key']
        badge_cls = _status_badge_class(sk)
        href = _esc(c['href'])
        activity_cols.append(
            f'''<div class="col-md-6 mb-4">
            <a href="{href}" class="sl-interactive-card">
              <div class="sl-card-body">
                <div class="sl-card-type"><span data-gh-i18n="{c['type_key']}"></span></div>
                <div class="sl-card-title"><span data-gh-i18n="{c['title_key']}"></span></div>
                <div class="d-flex flex-wrap align-items-center gap-2 mb-2">
                  <span class="{badge_cls}"><span data-gh-i18n="{c['status_key_i18n']}"></span></span>
                  <span class="sl-card-meta"><span data-gh-i18n="{c['space_key']}"></span></span>
                </div>
                <div class="sl-card-meta-row"><span data-gh-i18n="{c['activity_key']}"></span></div>
                <div class="sl-card-fresh"><span data-gh-i18n="{c['updated_key']}"></span></div>
                <div class="sl-card-cta"><span data-gh-i18n="{c['cta_key']}"></span></div>
              </div>
            </a>
          </div>'''
        )

    steps_cols = [
        f'''<div class="col-md-4 mb-3 mb-md-0">
            <div class="sl-how-step">
              <div class="sl-how-step-num"><span data-gh-i18n="softLaunch.how.step1Label"></span></div>
              <strong><span data-gh-i18n="softLaunch.how.contributeTitle"></span></strong>
              <p><span data-gh-i18n="softLaunch.how.contributeBody"></span></p>
            </div>
          </div>''',
        f'''<div class="col-md-4 mb-3 mb-md-0">
            <div class="sl-how-step">
              <div class="sl-how-step-num"><span data-gh-i18n="softLaunch.how.step2Label"></span></div>
              <strong><span data-gh-i18n="softLaunch.how.reviewTitle"></span></strong>
              <p><span data-gh-i18n="softLaunch.how.reviewBody"></span></p>
            </div>
          </div>''',
        f'''<div class="col-md-4 mb-3 mb-md-0">
            <div class="sl-how-step">
              <div class="sl-how-step-num"><span data-gh-i18n="softLaunch.how.step3Label"></span></div>
              <strong><span data-gh-i18n="softLaunch.how.decideTitle"></span></strong>
              <p><span data-gh-i18n="softLaunch.how.decideBody"></span></p>
            </div>
          </div>''',
    ]

    participation_specs = [
        ('/soft-launch/onboarding/', 'shareTitle', 'shareBody', 'shareCta'),
        ('/soft-launch/artifact/?scenario=under_review_ready', 'reviewTitle', 'reviewBody', 'reviewCta'),
        ('/soft-launch/artifact/?scenario=approved', 'buildTitle', 'buildBody', 'buildCta'),
    ]
    participation_cols = []
    for href, tk, bk, ck in participation_specs:
        participation_cols.append(
            f'''<div class="col-md-4 mb-4 mb-md-0">
            <a href="{_esc(href)}" class="sl-interactive-card sl-participation-card">
              <div class="sl-card-body">
                <div class="sl-card-title"><span data-gh-i18n="softLaunch.participation.{tk}"></span></div>
                <p class="sl-card-desc mb-0"><span data-gh-i18n="softLaunch.participation.{bk}"></span></p>
                <span class="btn btn-outline-primary btn-sm mt-3"><span data-gh-i18n="softLaunch.participation.{ck}"></span></span>
              </div>
            </a>
          </div>'''
        )

    sec_cta_href = _esc(h['secondary_cta']['href'])
    pri_href = _esc(h['primary_cta']['href'])

    monument = h.get('monument') or {}
    monument_html = ''
    if monument.get('title'):
        mp = monument.get('cta_primary') or {}
        ms = monument.get('cta_secondary') or {}
        monument_html = f'''
    <section class="sl-section sl-monument-band" aria-labelledby="sl-monument-heading">
      <div class="container">
        <div class="sl-monument-card">
          <h2 class="sl-section-title sl-monument-title" id="sl-monument-heading"><span data-gh-i18n="softLaunch.home.monumentTitle"></span></h2>
          <p class="sl-monument-lead mb-1"><span data-gh-i18n="softLaunch.home.monumentLine1"></span></p>
          <p class="sl-monument-lead text-muted mb-4"><span data-gh-i18n="softLaunch.home.monumentLine2"></span></p>
          <div class="d-flex flex-wrap gap-2 align-items-center">
            <a href="{_esc(mp.get('href', ''))}" class="btn btn-primary sl-cta-primary"><span data-gh-i18n="softLaunch.home.monumentCtaPrimary"></span></a>
            <a href="{_esc(ms.get('href', ''))}" class="btn btn-outline-secondary sl-cta-secondary"><span data-gh-i18n="softLaunch.home.monumentCtaSecondary"></span></a>
          </div>
        </div>
      </div>
    </section>
    '''

    return f'''
    <link rel="stylesheet" href="/static/css/soft-launch.css">
    <div class="container sl-hero">
      <div class="row">
        <div class="col-xl-9 col-lg-10 mx-auto text-center">
          <h1 class="display-5 fw-bold mb-3"><span data-gh-i18n="softLaunch.home.headline"></span></h1>
          <p class="lead text-muted sl-hero-sub"><span data-gh-i18n="softLaunch.home.subtext"></span></p>
          <div class="d-flex flex-wrap gap-3 justify-content-center align-items-center mt-4 pt-2">
            <a href="{pri_href}" class="btn btn-primary btn-lg sl-cta-primary">
              <span data-gh-i18n="softLaunch.home.primaryCta"></span>
            </a>
            <a href="{sec_cta_href}" class="btn btn-outline-secondary btn-lg sl-cta-secondary">
              <span data-gh-i18n="softLaunch.home.secondaryCta"></span>
            </a>
          </div>
          <p class="small text-muted mt-4 mb-0"><span data-gh-i18n="softLaunch.home.primaryMicrocopy"></span></p>
        </div>
      </div>
    </div>
{monument_html}
    <section class="sl-section">
      <div class="container">
        <h2 class="sl-section-title"><span data-gh-i18n="softLaunch.home.howTitle"></span></h2>
        <div class="row g-3">{''.join(steps_cols)}</div>
      </div>
    </section>

    <section class="sl-section sl-section-alt" id="sl-live-activity">
      <div class="container">
        <h2 class="sl-section-title"><span data-gh-i18n="softLaunch.home.liveActivityTitle"></span></h2>
        <div class="row">{''.join(activity_cols)}</div>
      </div>
    </section>

    <section class="sl-section pb-5">
      <div class="container">
        <h2 class="sl-section-title"><span data-gh-i18n="softLaunch.home.participationTitle"></span></h2>
        <div class="row g-3 pt-1">{''.join(participation_cols)}</div>
      </div>
    </section>
    '''


def _build_onboarding_html() -> str:
    intent_keys = [
        ('share', 'softLaunch.onboarding.intentShare'),
        ('review', 'softLaunch.onboarding.intentReview'),
        ('explore', 'softLaunch.onboarding.intentExplore'),
    ]
    opts1 = ''.join(
        f'''<div class="form-check mb-2">
          <input class="form-check-input" type="radio" name="intent" id="intent-{iid}" value="{_esc(iid)}">
          <label class="form-check-label" for="intent-{iid}"><span data-gh-i18n="{ik}"></span></label>
        </div>'''
        for iid, ik in intent_keys
    )
    space_opts_spec = [
        ('space-ai', 'softLaunch.spaces.ai'),
        ('space-climate', 'softLaunch.spaces.climate'),
        ('space-civic', 'softLaunch.spaces.civic'),
    ]
    # <option> cannot hold nested spans; labels filled after GovHubI18n.init
    spaces_opts = ''.join(
        f'<option value="{_esc(sid)}" data-sl-space-i18n="{sk}"></option>'
        for sid, sk in space_opts_spec
    )

    fields_html = f'''
            <div class="mb-3">
              <label class="form-label" for="title"><span data-gh-i18n="softLaunch.onboarding.fieldTitleLabel"></span></label>
              <input type="text" class="form-control" id="title" data-gh-i18n-placeholder="softLaunch.onboarding.fieldTitlePlaceholder">
            </div>
            <div class="mb-3">
              <label class="form-label" for="description"><span data-gh-i18n="softLaunch.onboarding.fieldDescLabel"></span></label>
              <input type="text" class="form-control" id="description" data-gh-i18n-placeholder="softLaunch.onboarding.fieldDescPlaceholder">
            </div>
            <div class="mb-3">
              <label class="form-label" for="link"><span data-gh-i18n="softLaunch.onboarding.fieldLinkLabel"></span>
                <span class="text-muted"><span data-gh-i18n="softLaunch.common.optional"></span></span>
              </label>
              <input type="text" class="form-control" id="link" data-gh-i18n-placeholder="softLaunch.onboarding.fieldLinkPlaceholder">
            </div>'''

    step5_items = (
        'softLaunch.onboarding.step5opt1',
        'softLaunch.onboarding.step5opt2',
        'softLaunch.onboarding.step5opt3',
    )
    step5 = ''.join(f'<li><span data-gh-i18n="{k}"></span></li>' for k in step5_items)

    return f'''
    <div class="container py-4" style="max-width: 640px;">
      <nav aria-label="breadcrumb" class="mb-3">
        <ol class="breadcrumb">
          <li class="breadcrumb-item"><a href="/soft-launch/"><span data-gh-i18n="softLaunch.nav.softLaunch"></span></a></li>
          <li class="breadcrumb-item active"><span data-gh-i18n="softLaunch.nav.onboarding"></span></li>
        </ol>
      </nav>

      <div id="ob-step-1" class="ob-step">
        <h1 class="h3 mb-3"><span data-gh-i18n="softLaunch.onboarding.step1Title"></span></h1>
        {opts1}
        <button type="button" class="btn btn-primary mt-3 ob-next"><span data-gh-i18n="softLaunch.common.continue"></span></button>
      </div>

      <div id="ob-step-2" class="ob-step d-none">
        <h1 class="h3 mb-3"><span data-gh-i18n="softLaunch.onboarding.step2Title"></span></h1>
        <p class="text-muted"><span data-gh-i18n="softLaunch.onboarding.step2Helper"></span></p>
        <select class="form-select mb-3" id="space-select">
          <option value="" data-sl-space-i18n="softLaunch.spaces.select"></option>
          {spaces_opts}
        </select>
        <button type="button" class="btn btn-outline-secondary ob-back"><span data-gh-i18n="softLaunch.common.back"></span></button>
        <button type="button" class="btn btn-primary ob-next"><span data-gh-i18n="softLaunch.common.continue"></span></button>
      </div>

      <div id="ob-step-3" class="ob-step d-none">
        <h1 class="h3 mb-3"><span data-gh-i18n="softLaunch.onboarding.step3Title"></span></h1>
        <p class="text-muted small"><span data-gh-i18n="softLaunch.onboarding.step3Hint"></span></p>
        {fields_html}
        <button type="button" class="btn btn-outline-secondary ob-back"><span data-gh-i18n="softLaunch.common.back"></span></button>
        <button type="button" class="btn btn-primary" id="ob-publish"><span data-gh-i18n="softLaunch.onboarding.publishCta"></span></button>
      </div>

      <div id="ob-step-4" class="ob-step d-none">
        <div class="sl-brick-placed mb-4" role="status">
          <p class="sl-brick-headline mb-2">
            <span class="me-1" aria-hidden="true">🧱</span>
            <strong><span data-gh-i18n="softLaunch.onboarding.step4BrickHeadline"></span></strong>
          </p>
          <p class="mb-0 text-muted"><span data-gh-i18n="softLaunch.onboarding.step4BrickBody"></span></p>
        </div>
        <p class="alert alert-info small mb-3">
          <span data-gh-i18n="softLaunch.onboarding.step4Banner"></span>
          <strong><span id="ob-layer-name"></span> <span data-gh-i18n="softLaunch.onboarding.layerSuffix"></span></strong>.
        </p>
        <button type="button" class="btn btn-primary ob-next"><span data-gh-i18n="softLaunch.common.continue"></span></button>
      </div>

      <div id="ob-step-5" class="ob-step d-none">
        <h1 class="h3 mb-3"><span data-gh-i18n="softLaunch.onboarding.step5Title"></span></h1>
        <ul>{step5}</ul>
        <a href="/soft-launch/artifact/" class="btn btn-primary"><span data-gh-i18n="softLaunch.onboarding.viewDemo"></span></a>
        <a href="/soft-launch/" class="btn btn-outline-secondary ms-2"><span data-gh-i18n="softLaunch.common.home"></span></a>
      </div>
    </div>
    <script>
    (function() {{
      function fillSpaceOptions() {{
        if (!window.GovHubI18n || !GovHubI18n.t) return;
        document.querySelectorAll('[data-sl-space-i18n]').forEach(function (opt) {{
          var k = opt.getAttribute('data-sl-space-i18n');
          if (k) opt.textContent = GovHubI18n.t(k);
        }});
      }}
      window.__GH_I18N_READY__.then(function () {{ fillSpaceOptions(); }});
      let step = 1;
      const total = 5;
      function show(s) {{
        for (let i = 1; i <= total; i++) {{
          const el = document.getElementById('ob-step-' + i);
          if (el) el.classList.toggle('d-none', i !== s);
        }}
        step = s;
      }}
      document.querySelectorAll('.ob-next').forEach(function(btn) {{
        btn.addEventListener('click', function() {{
          if (step === 2) {{
            const sel = document.getElementById('space-select');
            const name = sel.options[sel.selectedIndex]?.text || '';
            const fb = (window.GovHubI18n && GovHubI18n.t)
              ? GovHubI18n.t('softLaunch.onboarding.step4LayerFallback')
              : 'AI Governance';
            document.getElementById('ob-layer-name').textContent = name || fb;
          }}
          if (step < total) show(step + 1);
        }});
      }});
      document.querySelectorAll('.ob-back').forEach(function(btn) {{
        btn.addEventListener('click', function() {{ if (step > 1) show(step - 1); }});
      }});
      document.getElementById('ob-publish').addEventListener('click', function() {{ show(4); }});
    }})();
    </script>
    '''


def _demo_btn(i18n_key: str, btn_class: str, wire: Optional[str] = None) -> str:
    wire_attr = f' data-sl-wire="{_esc(wire)}"' if wire else ''
    return (
        f'<button type="button" class="btn {btn_class} btn-sm sl-demo-action-btn" '
        f'data-sl-demo-action-i18n="{_esc(i18n_key)}"{wire_attr}>'
        f'<span data-gh-i18n="{_esc(i18n_key)}"></span></button>'
    )


def _build_artifact_demo_html(
    artifact: dict,
    show_dev_hints: bool = False,
    wired_artifact_id: Optional[str] = None,
) -> str:
    st = artifact.get('status') or 'under_review'
    flags = allowed_artifact_actions(st)
    explainer_html = _artifact_explainer_span(st)
    stepper = _lifecycle_stepper(st)

    wire_sup = 'support' if wired_artifact_id else None
    wire_opp = 'opposition' if wired_artifact_id else None
    actions = []
    if flags['show_support']:
        actions.append(_demo_btn('softLaunch.artifact.actions.support', 'btn-outline-success', wire_sup))
    if flags['show_oppose']:
        actions.append(_demo_btn('softLaunch.artifact.actions.oppose', 'btn-outline-danger', wire_opp))
    if flags['show_comment']:
        actions.append(_demo_btn('softLaunch.artifact.actions.comment', 'btn-outline-secondary'))
    if flags['show_add_evidence']:
        actions.append(_demo_btn('softLaunch.artifact.actions.addEvidence', 'btn-outline-secondary'))
    if flags['show_abstain']:
        actions.append(_demo_btn('softLaunch.artifact.actions.abstain', 'btn-outline-warning'))
    actions_html = (
        ' '.join(actions)
        if actions
        else '<span class="text-muted small" data-gh-i18n="softLaunch.artifact.noActionsFixture"></span>'
    )

    readiness_rows = artifact.get('readiness_rows')
    readiness_items = ''
    if readiness_rows:
        for row in readiness_rows:
            href = row.get('href')
            lk = row.get('link_label_key')
            link_html = ''
            if href and lk:
                link_html = (
                    f'<div class="mt-1"><a href="{_esc(href)}" class="small">'
                    f'<span data-gh-i18n="{_esc(lk)}"></span></a></div>'
                )
            lbl_k = row.get('label_key')
            lbl = (
                f'<span data-gh-i18n="{_esc(lbl_k)}"></span>'
                if lbl_k
                else _esc(row.get('label', ''))
            )
            dk = row.get('detail_key')
            if dk:
                dc = row.get('detail_count')
                count_attr = (
                    f' data-i18n-count="{_esc(dc)}"'
                    if dc is not None
                    else ''
                )
                detail_html = (
                    f'<p class="small text-muted mb-0 mt-1" '
                    f'data-gh-i18n-interp="{_esc(dk)}"{count_attr}></p>'
                )
            else:
                detail_html = (
                    f'<p class="small text-muted mb-0 mt-1">'
                    f'{_esc(row.get("detail", ""))}</p>'
                )
            readiness_items += f'''
            <li class="list-group-item sl-readiness-row px-3 py-3">
              <div class="d-flex align-items-start gap-2">
                <span class="sl-check-icon text-muted" aria-hidden="true">○</span>
                <div class="flex-grow-1 min-w-0">
                  <div class="fw-semibold">{lbl}</div>
                  {detail_html}
                  {link_html}
                </div>
              </div>
            </li>'''
    else:
        readiness_items = ''.join(
            f'<li class="list-group-item sl-readiness-row px-3 py-3"><span class="me-2">○</span>'
            f'<span data-gh-i18n="{_esc(x)}"></span></li>'
            for x in artifact.get('readiness_checklist', [])
        )

    readiness_panel = ''
    if flags['show_readiness_panel']:
        intro = (
            '<p class="sl-readiness-intro px-3 mb-0 pt-1">'
            '<span data-gh-i18n="softLaunch.artifact.readinessIntro"></span></p>'
        )
        if readiness_rows:
            body_intro = intro
        else:
            body_intro = ''
        readiness_panel = f'''
        <div class="card border-info sl-readiness-panel mb-4">
          <div class="card-header py-3"><strong><span data-gh-i18n="softLaunch.artifact.readinessHeading"></span></strong></div>
          <div class="card-body px-0 pt-2 pb-0">
            {body_intro}
            <ul class="list-group list-group-flush mt-2">{readiness_items}</ul>
          </div>
        </div>'''
    
    # Schedule vote modal (only if wired and ready)
    schedule_vote_modal = ''
    if wired_artifact_id and artifact.get('readiness_met'):
        schedule_vote_modal = f'''
        <div class="modal fade" id="sl-schedule-vote-modal" tabindex="-1">
          <div class="modal-dialog">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title"><span data-gh-i18n="softLaunch.artifact.scheduleModalTitle"></span></h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
              </div>
              <div class="modal-body">
                <form id="sl-schedule-vote-form">
                  <div class="mb-3">
                    <label class="form-label"><span data-gh-i18n="softLaunch.artifact.scheduleQuestionLabel"></span></label>
                    <textarea class="form-control" id="vote-title" rows="2" required data-gh-i18n-value="softLaunch.artifact.scheduleQuestionDefault"></textarea>
                  </div>
                  
                  <div class="mb-3">
                    <label class="form-label"><span data-gh-i18n="softLaunch.artifact.scheduleStart"></span></label>
                    <input type="datetime-local" class="form-control" id="vote-start" required>
                  </div>
                  
                  <div class="mb-3">
                    <label class="form-label"><span data-gh-i18n="softLaunch.artifact.scheduleEnd"></span></label>
                    <input type="datetime-local" class="form-control" id="vote-end" required>
                  </div>
                  
                  <div class="mb-3">
                    <label class="form-label"><span data-gh-i18n="softLaunch.artifact.scheduleQuorum"></span></label>
                    <input type="number" class="form-control" id="vote-quorum" value="3" min="1" required>
                  </div>
                  
                  <button type="submit" class="btn btn-primary"><span data-gh-i18n="softLaunch.artifact.scheduleSubmit"></span></button>
                </form>
              </div>
            </div>
          </div>
        </div>'''

    callout = ''
    if flags['show_transition_callout'] and artifact.get('readiness_met'):
        schedule_btn_attr = ''
        if wired_artifact_id:
            schedule_btn_attr = ' data-bs-toggle="modal" data-bs-target="#sl-schedule-vote-modal"'
        callout = f'''
        <div class="alert alert-info border-info">
          <h6 class="alert-heading"><span data-gh-i18n="softLaunch.artifact.transitionHeading"></span></h6>
          <p class="small mb-2"><span data-gh-i18n="softLaunch.artifact.transitionBody"></span></p>
          <button type="button" class="btn btn-sm btn-primary me-1 sl-demo-action-btn" data-sl-demo-action-i18n="softLaunch.artifact.reviewReadiness"><span data-gh-i18n="softLaunch.artifact.reviewReadiness"></span></button>
          <button type="button" class="btn btn-sm btn-outline-primary"{schedule_btn_attr}><span data-gh-i18n="softLaunch.artifact.scheduleVote"></span></button>
        </div>'''

    activity_rows = ''.join(
        f'<li class="list-group-item">{_esc(a["actor"])} <span data-gh-i18n="{_esc(a.get("verb_key", ""))}"></span> · {_esc(a["when"])}</li>'
        for a in artifact.get('activity', [])
    )

    rel = artifact.get('relationships') or {}

    def rel_section(title_i18n: str, key: str, section_id: str):
        rows = rel.get(key) or []
        if not rows:
            return (
                f'<div id="{_esc(section_id)}" class="sl-rel-section mb-3">'
                f'<h6 class="mt-3 mb-2"><span data-gh-i18n="{_esc(title_i18n)}"></span></h6>'
                f'<p class="small text-muted mb-0"><span data-gh-i18n="softLaunch.artifact.relEmpty"></span></p></div>'
            )
        inner = []
        for r in rows:
            tit = r.get('title_key')
            tit_html = f'<span data-gh-i18n="{_esc(tit)}"></span>' if tit else _esc(r.get('title', ''))
            inner.append(
                f'<li class="list-group-item"><a href="#">{tit_html}</a> '
                f'<code class="small">{_esc(r["ref"])}</code></li>'
            )
        inner_s = ''.join(inner)
        return (
            f'<div id="{_esc(section_id)}" class="sl-rel-section mb-3">'
            f'<h6 class="mt-3 mb-2"><span data-gh-i18n="{_esc(title_i18n)}"></span></h6>'
            f'<ul class="list-group list-group-flush border rounded">{inner_s}</ul></div>'
        )

    voting_block = ''
    if st == 'vote_open':
        v = artifact.get('voting') or {}
        vote_id_attr = ''
        if wired_artifact_id:
            # Approval votes use Ballot.choice: yes | no | abstain (Support/Oppose/Abstain in UI)
            from models import Vote
            real_vote = Vote.query.filter_by(artifact_id=wired_artifact_id, status='active').first()
            if real_vote:
                vote_id_attr = f' data-vote-id="{real_vote.id}"'
        
        voting_block = f'''
        <div class="card mb-4" id="sl-voting-panel"{vote_id_attr}>
          <div class="card-header"><strong><span data-gh-i18n="softLaunch.artifact.castVoteHeading"></span></strong></div>
          <div class="card-body">
            <p class="small text-muted"><span data-gh-i18n="softLaunch.artifact.castVoteHint"></span></p>
            <div class="d-flex flex-wrap gap-2 mb-3">
              <button type="button" class="btn btn-success btn-sm sl-vote-btn" data-choice="yes"><span data-gh-i18n="softLaunch.artifact.voteSupport"></span></button>
              <button type="button" class="btn btn-danger btn-sm sl-vote-btn" data-choice="no"><span data-gh-i18n="softLaunch.artifact.voteOppose"></span></button>
              <button type="button" class="btn btn-warning btn-sm sl-vote-btn" data-choice="abstain"><span data-gh-i18n="softLaunch.artifact.voteAbstain"></span></button>
            </div>
            <div id="sl-vote-details">
              <p class="small mb-1"><strong><span data-gh-i18n="softLaunch.artifact.voteClosesIn"></span></strong> {_esc(v.get('closes_in_label', '—'))}</p>
              <p class="small mb-3"><strong><span data-gh-i18n="softLaunch.artifact.voteOpenedOn"></span></strong> {_esc(v.get('opened_on_label', '—'))}</p>
              <p class="small mb-0"><span data-gh-i18n-interp="softLaunch.artifact.voteTallyLine" data-i18n-supports="{_esc(v.get('supports', 0))}" data-i18n-opposes="{_esc(v.get('opposes', 0))}" data-i18n-abstains="{_esc(v.get('abstains', 0))}"></span></p>
            </div>
          </div>
        </div>'''

    ctx_panel = ''
    if flags['show_voting_context_panel']:
        c = artifact.get('vote_context') or {}
        ctx_panel = f'''
        <div class="card mb-4">
          <div class="card-header"><strong><span data-gh-i18n="softLaunch.artifact.informedHeading"></span></strong></div>
          <div class="card-body small">
            <ul class="mb-0 ps-3">
              <li><span data-gh-i18n="softLaunch.artifact.informedEvidence"></span> {_esc(c.get('evidence_count', 0))}</li>
              <li><span data-gh-i18n="softLaunch.artifact.informedOpposition"></span> {_esc(c.get('opposition_count', 0))}</li>
              <li><span data-gh-i18n="softLaunch.artifact.informedComments"></span> {_esc(c.get('comment_count', 0))}</li>
              <li><span data-gh-i18n="softLaunch.artifact.informedRelated"></span> {_esc(c.get('related_contributions_count', 0))}</li>
            </ul>
          </div>
        </div>'''

    approved_block = ''
    if st == 'approved':
        approved_block = '''
        <div class="card border-success mb-4">
          <div class="card-header bg-success text-white"><strong><span data-gh-i18n="softLaunch.artifact.approvedHeading"></span></strong></div>
          <div class="card-body">
            <p class="mb-2"><strong><span data-gh-i18n="softLaunch.artifact.approvedOutcome"></span></strong> <span data-gh-i18n="softLaunch.artifact.approvedYes"></span></p>
            <button type="button" class="btn btn-sm btn-primary sl-demo-action-btn" data-sl-demo-action-i18n="softLaunch.artifact.beginImplementation"><span data-gh-i18n="softLaunch.artifact.beginImplementation"></span></button>
          </div>
        </div>'''
    
    # Comments section
    comments_section = ''
    if wired_artifact_id:
        comments_section = f'''
        <div class="card mt-4" id="comments-section">
          <div class="card-header"><strong><span data-gh-i18n="softLaunch.artifact.commentsHeading"></span></strong></div>
          <div class="card-body">
            <form id="sl-comment-form" class="mb-4">
              <textarea class="form-control mb-2" id="comment-text" name="text" rows="3" 
                        data-gh-i18n-placeholder="softLaunch.artifact.commentPlaceholder" required></textarea>
              <button type="submit" class="btn btn-primary btn-sm"><span data-gh-i18n="softLaunch.artifact.postComment"></span></button>
            </form>
            <div id="sl-comments-list">
              <p class="text-muted small" data-gh-i18n="softLaunch.artifact.commentsLoading"></p>
            </div>
          </div>
        </div>'''
    
    # Evidence section
    evidence_section = ''
    if wired_artifact_id:
        evidence_section = f'''
        <div class="card mt-4" id="evidence-section">
          <div class="card-header d-flex justify-content-between align-items-center">
            <strong><span data-gh-i18n="softLaunch.artifact.evidenceHeading"></span></strong>
            <button type="button" class="btn btn-outline-secondary btn-sm" data-bs-toggle="modal" data-bs-target="#sl-evidence-modal">
              <span data-gh-i18n="softLaunch.artifact.addEvidence"></span>
            </button>
          </div>
          <div class="card-body">
            <div id="sl-evidence-list">
              <p class="text-muted small" data-gh-i18n="softLaunch.artifact.evidenceLoading"></p>
            </div>
          </div>
        </div>
        
        <!-- Evidence Modal -->
        <div class="modal fade" id="sl-evidence-modal" tabindex="-1">
          <div class="modal-dialog">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title"><span data-gh-i18n="softLaunch.artifact.evidenceModalTitle"></span></h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
              </div>
              <div class="modal-body">
                <form id="sl-evidence-form">
                  <div class="mb-3">
                    <label class="form-label"><span data-gh-i18n="softLaunch.artifact.evidenceUrlLabel"></span></label>
                    <input type="url" class="form-control" id="evidence-url" required 
                           data-gh-i18n-placeholder="softLaunch.artifact.evidenceUrlPlaceholder">
                    <div class="form-text"><span data-gh-i18n="softLaunch.artifact.evidenceUrlHelp"></span></div>
                  </div>
                  
                  <div class="mb-3">
                    <label class="form-label"><span data-gh-i18n="softLaunch.artifact.evidenceRelLabel"></span></label>
                    <select class="form-select" id="evidence-relationship">
                      <option value="supported_by" data-gh-i18n="softLaunch.artifact.evidenceRelSupportedBy"></option>
                      <option value="contradicted_by" data-gh-i18n="softLaunch.artifact.evidenceRelContradictedBy"></option>
                      <option value="cites" data-gh-i18n="softLaunch.artifact.evidenceRelCites"></option>
                      <option value="related_to" data-gh-i18n="softLaunch.artifact.evidenceRelRelated"></option>
                    </select>
                  </div>
                  
                  <div class="mb-3">
                    <label class="form-label"><span data-gh-i18n="softLaunch.artifact.evidenceExplainLabel"></span></label>
                    <textarea class="form-control" id="evidence-explanation" rows="2" 
                              data-gh-i18n-placeholder="softLaunch.artifact.evidenceExplainPlaceholder"></textarea>
                  </div>
                  
                  <button type="submit" class="btn btn-primary"><span data-gh-i18n="softLaunch.artifact.evidenceSubmit"></span></button>
                </form>
              </div>
            </div>
          </div>
        </div>'''

    dev_hints = ''
    if show_dev_hints:
        dev_hints = '''
      <p class="small text-muted border-top pt-3 mt-4 mb-0"><span data-gh-i18n="softLaunch.artifact.devHints"></span></p>'''

    title_key = artifact.get('title_key')
    title_html = (
        f'<span data-gh-i18n="{_esc(title_key)}"></span>'
        if title_key
        else _esc(artifact.get('title', ''))
    )
    type_key = artifact.get('artifact_type_key')
    type_html = (
        f'<span data-gh-i18n="{_esc(type_key)}"></span>'
        if type_key
        else _esc(artifact.get('artifact_type', ''))
    )
    space_key = artifact.get('space_name_key')
    space_inner = (
        f'<span data-gh-i18n="{_esc(space_key)}"></span>'
        if space_key
        else _esc(artifact.get('space_name', ''))
    )
    body_key = artifact.get('body_key')
    body_html = (
        f'<span data-gh-i18n="{_esc(body_key)}"></span>'
        if body_key
        else _esc(artifact.get('body', ''))
    )

    wired_dom = ''
    if wired_artifact_id:
        wired_dom = f' data-wired-artifact-id="{_esc(wired_artifact_id)}"'

    return f'''
    <link rel="stylesheet" href="/static/css/soft-launch.css">
    <div class="container py-4 sl-artifact-demo"{wired_dom}>
      <nav aria-label="breadcrumb" class="mb-3">
        <ol class="breadcrumb">
          <li class="breadcrumb-item"><a href="/soft-launch/" data-gh-i18n="softLaunch.nav.softLaunch"></a></li>
          <li class="breadcrumb-item active"><span data-gh-i18n="softLaunch.nav.demoContribution"></span></li>
        </ol>
      </nav>

      <p class="small text-muted mb-2"><span data-gh-i18n="softLaunch.common.lifecycle"></span> {stepper}</p>
      <div class="d-flex flex-wrap align-items-center gap-2 mb-2">
        <span class="badge bg-secondary">{type_html}</span>
        <span class="badge bg-primary"><span data-gh-i18n="softLaunch.status.{st}"></span></span>
        <span class="text-muted small"><span data-gh-i18n="softLaunch.common.space"></span> {space_inner}</span>
      </div>
      <h1 class="h3 mb-2">{title_html}</h1>
      <p class="text-muted small mb-4">{explainer_html}</p>

      {callout}

      <div class="d-flex flex-wrap gap-2 mb-4">{actions_html}</div>

      <div class="card mb-4">
        <div class="card-body">
          <p class="mb-0">{body_html}</p>
        </div>
      </div>

      {readiness_panel}
      {voting_block}
      {ctx_panel}
      {approved_block}

      <h6 class="mt-4 mb-2"><span data-gh-i18n="softLaunch.artifact.relationshipsHeading"></span></h6>
      <p class="small text-muted mb-3"><span data-gh-i18n="softLaunch.artifact.relationshipsIntro"></span></p>
      {rel_section('softLaunch.artifact.relSupports', 'supports', 'sl-rel-supports')}
      {rel_section('softLaunch.artifact.relOpposition', 'opposes', 'sl-rel-opposition')}
      {rel_section('softLaunch.artifact.relBuildsOn', 'builds_on', 'sl-rel-builds-on')}

      <h6 class="mt-4 mb-2" id="sl-artifact-activity"><span data-gh-i18n="softLaunch.artifact.activityHeading"></span></h6>
      <ul class="list-group mb-4">{activity_rows or '<li class="list-group-item text-muted"><span data-gh-i18n="softLaunch.artifact.noActivity"></span></li>'}</ul>

      {evidence_section}
      {comments_section}
      
      {dev_hints}
    </div>
    {schedule_vote_modal}
    <div id="sl-demo-toast" class="alert alert-info shadow-sm position-fixed bottom-0 end-0 m-3 d-none py-2 px-3 small" style="z-index:1080; max-width:20rem;" role="status" aria-live="polite"></div>
    <script>
    (function () {{
      var R = window.__GH_I18N_READY__ || Promise.resolve();
      R.then(function () {{
        var G = window.GovHubI18n;
        function t(k, v) {{
          return G && typeof G.t === 'function' ? G.t(k, v || {{}}) : k;
        }}
        function slParseFetchResult(r) {{
          return r.text().then(function (txt) {{
            var j = {{}};
            try {{
              j = txt ? JSON.parse(txt) : {{}};
            }} catch (e1) {{
              j = {{ error: txt ? txt.slice(0, 240) : '' }};
            }}
            return {{ ok: r.ok, status: r.status, j: j }};
          }});
        }}
        function slApiUserMessage(status, j) {{
          j = j || {{}};
          var out = Object.assign({{}}, j);
          if (!out.error_code) {{
            if (status === 403) out.error_code = 'FORBIDDEN';
            else if (status === 404) out.error_code = 'NOT_FOUND';
            else if (status === 400) out.error_code = 'BAD_REQUEST';
          }}
          return G.apiErrorMessage(out);
        }}

        var toast = document.getElementById('sl-demo-toast');
        function flash(msg, isErr) {{
          if (!toast) return;
          toast.textContent = msg;
          toast.classList.toggle('alert-danger', !!isErr);
          toast.classList.toggle('alert-info', !isErr);
          toast.classList.remove('d-none');
          clearTimeout(toast._t);
          toast._t = setTimeout(function () {{ toast.classList.add('d-none'); }}, 3200);
        }}
        var root = document.querySelector('.sl-artifact-demo');
        var aid = root && root.getAttribute('data-wired-artifact-id');
        function demoActionLabel(el) {{
          var ik = el.getAttribute('data-sl-demo-action-i18n');
          if (ik) return t(ik);
          return el.getAttribute('data-sl-demo-action') || el.textContent.trim();
        }}
        function wirePost(kind, el) {{
          if (!aid) return false;
          var path = kind === 'support' ? '/support/' : '/opposition/';
          el.disabled = true;
          fetch('/api/artifacts/' + encodeURIComponent(aid) + path, {{
            method: 'POST',
            credentials: 'same-origin',
            headers: {{ 'Content-Type': 'application/json', 'Accept': 'application/json' }},
            body: '{{}}'
          }}).then(slParseFetchResult).then(function (x) {{
            el.disabled = false;
            if (x.ok) {{
              flash(t('softLaunch.js.savedReloading', {{ action: demoActionLabel(el) }}), false);
              setTimeout(function () {{ window.location.reload(); }}, 800);
              return;
            }}
            if (x.status === 401) {{
              flash(t('softLaunch.js.signInSupport'), true);
              return;
            }}
            flash(slApiUserMessage(x.status, x.j), true);
          }}).catch(function () {{
            el.disabled = false;
            flash(t('softLaunch.js.networkError'), true);
          }});
          return true;
        }}
        document.querySelectorAll('.sl-demo-action-btn').forEach(function (el) {{
          el.addEventListener('click', function () {{
            var w = el.getAttribute('data-sl-wire');
            if (w === 'support' && wirePost('support', el)) return;
            if (w === 'opposition' && wirePost('opposition', el)) return;
            flash(t('softLaunch.js.previewOnly', {{ action: demoActionLabel(el) }}), false);
          }});
        }});

        // Comments functionality
        (function() {{
          var aidC = document.querySelector('.sl-artifact-demo')?.getAttribute('data-wired-artifact-id');
          if (!aidC) return;

          var commentForm = document.getElementById('sl-comment-form');
          var commentsList = document.getElementById('sl-comments-list');

          function loadComments() {{
            if (!commentsList) return;
            fetch('/api/artifacts/' + encodeURIComponent(aidC) + '/comments/', {{
              credentials: 'same-origin'
            }}).then(r => r.json())
              .then(data => {{
                if (data.comments && data.comments.length > 0) {{
                  var html = '';
                  data.comments.forEach(c => {{
                    html += '<div class="border-bottom pb-2 mb-2">';
                    html += '<div class="small fw-semibold">' + (c.author || t('softLaunch.common.anonymous')) + '</div>';
                    html += '<div class="small text-muted">' + new Date(c.timestamp).toLocaleString() + '</div>';
                    html += '<p class="mb-0 mt-1">' + (c.text || '').replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</p>';
                    html += '</div>';
                  }});
                  commentsList.innerHTML = html;
                }} else {{
                  commentsList.innerHTML = '<p class="text-muted small">' + t('softLaunch.artifact.commentsEmpty') + '</p>';
                }}
              }})
              .catch(() => {{
                commentsList.innerHTML = '<p class="text-muted small">' + t('softLaunch.artifact.commentsError') + '</p>';
              }});
          }}

          if (commentForm) {{
            commentForm.addEventListener('submit', e => {{
              e.preventDefault();
              var textField = document.getElementById('comment-text');
              var text = textField.value.trim();
              if (!text) return;

              fetch('/api/artifacts/' + encodeURIComponent(aidC) + '/comments/', {{
                method: 'POST',
                credentials: 'same-origin',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ text: text }})
              }}).then(slParseFetchResult).then(x => {{
                if (x.status === 401) {{
                  alert(t('softLaunch.js.signInComments'));
                  return Promise.reject('auth');
                }}
                if (!x.ok) {{
                  alert(slApiUserMessage(x.status, x.j));
                  return Promise.reject('fail');
                }}
                textField.value = '';
                loadComments();
              }}).catch(err => {{
                if (err !== 'auth' && err !== 'fail') alert(t('softLaunch.js.networkError'));
              }});
            }});
          }}

          loadComments();
        }})();

        // Evidence functionality
        (function() {{
          var aidE = document.querySelector('.sl-artifact-demo')?.getAttribute('data-wired-artifact-id');
          if (!aidE) return;

          var evidenceForm = document.getElementById('sl-evidence-form');
          var evidenceList = document.getElementById('sl-evidence-list');
          var evidenceModal = document.getElementById('sl-evidence-modal');

          function loadEvidence() {{
            if (!evidenceList) return;
            var artifactUrl = window.location.origin + '/artifacts/' + aidE;

            fetch('/api/bridges/?source_url=' + encodeURIComponent(artifactUrl), {{
              credentials: 'same-origin'
            }}).then(r => r.json())
              .then(data => {{
                if (data.bridges && data.bridges.length > 0) {{
                  var grouped = {{}};
                  data.bridges.forEach(b => {{
                    var rel = b.relationship || 'related_to';
                    if (!grouped[rel]) grouped[rel] = [];
                    grouped[rel].push(b);
                  }});

                  var html = '';
                  var relLabels = {{
                    'supported_by': t('softLaunch.artifact.evidenceGroupSupportedBy'),
                    'contradicted_by': t('softLaunch.artifact.evidenceGroupContradictedBy'),
                    'cites': t('softLaunch.artifact.evidenceGroupCites'),
                    'related_to': t('softLaunch.artifact.evidenceGroupRelated')
                  }};

                  Object.keys(relLabels).forEach(rel => {{
                    if (grouped[rel]) {{
                      html += '<h6 class="mt-3 mb-2">' + relLabels[rel] + '</h6>';
                      html += '<ul class="list-group list-group-flush">';
                      grouped[rel].forEach(b => {{
                        html += '<li class="list-group-item">';
                        html += '<a href="' + (b.target?.url || '#') + '" target="_blank" rel="noopener">' +
                                (b.name || t('softLaunch.common.evidenceFallbackName')) + '</a>';
                        if (b.explanation) {{
                          html += '<div class="small text-muted mt-1">' + (b.explanation || '').replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</div>';
                        }}
                        html += '</li>';
                      }});
                      html += '</ul>';
                    }}
                  }});

                  evidenceList.innerHTML = html || ('<p class="text-muted small">' + t('softLaunch.artifact.evidenceEmpty') + '</p>');
                }} else {{
                  evidenceList.innerHTML = '<p class="text-muted small">' + t('softLaunch.artifact.evidenceEmpty') + '</p>';
                }}
              }})
              .catch(() => {{
                evidenceList.innerHTML = '<p class="text-muted small">' + t('softLaunch.artifact.evidenceError') + '</p>';
              }});
          }}

          if (evidenceForm) {{
            evidenceForm.addEventListener('submit', e => {{
              e.preventDefault();
              var url = document.getElementById('evidence-url').value.trim();
              var relationship = document.getElementById('evidence-relationship').value;
              var explanation = document.getElementById('evidence-explanation').value.trim();

              if (!url) return;

              var artifactUrl = window.location.origin + '/artifacts/' + aidE;

              fetch('/api/bridges/', {{
                method: 'POST',
                credentials: 'same-origin',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{
                  name: t('softLaunch.js.evidenceBridgeName'),
                  source: {{
                    url: artifactUrl,
                    content_type: 'text'
                  }},
                  target: {{
                    url: url,
                    content_type: 'text'
                  }},
                  relationship: relationship,
                  explanation: explanation || null
                }})
              }}).then(slParseFetchResult).then(x => {{
                if (x.status === 401) {{
                  alert(t('softLaunch.js.signInEvidence'));
                  return Promise.reject('auth');
                }}
                if (!x.ok) {{
                  alert(slApiUserMessage(x.status, x.j));
                  return Promise.reject('fail');
                }}
                evidenceForm.reset();
                if (evidenceModal) {{
                  var modalEl = bootstrap.Modal.getInstance(evidenceModal);
                  if (modalEl) modalEl.hide();
                }}
                if (G && typeof G.applyDom === 'function') G.applyDom(document.getElementById('sl-evidence-modal'));
                loadEvidence();
              }}).catch(err => {{
                if (err !== 'auth' && err !== 'fail') alert(t('softLaunch.js.networkError'));
              }});
            }});
          }}

          loadEvidence();
        }})();

        // Voting functionality
        (function() {{
          var votingPanel = document.getElementById('sl-voting-panel');
          if (!votingPanel) return;

          var voteId = votingPanel.getAttribute('data-vote-id');
          if (!voteId) {{
            console.log('No real vote wired for this artifact');
            return;
          }}

          var voteButtons = document.querySelectorAll('.sl-vote-btn');
          var voteDetails = document.getElementById('sl-vote-details');

          function loadVoteDetails() {{
            fetch('/api/votes/' + encodeURIComponent(voteId) + '/', {{
              credentials: 'same-origin'
            }}).then(r => r.json())
              .then(data => {{
                if (voteDetails && data) {{
                  var html = '';
                  var endDate = new Date(data.end_at);
                  var now = new Date();
                  var hoursLeft = Math.max(0, (endDate - now) / (1000 * 60 * 60));

                  html += '<p class="small mb-1"><strong>' + t('softLaunch.artifact.voteClosesIn') + '</strong> ' +
                          hoursLeft.toFixed(1) + ' ' + t('softLaunch.js.hoursSuffix') + '</p>';
                  html += '<p class="small mb-3"><strong>' + t('softLaunch.artifact.voteOpenedOn') + '</strong> ' +
                          new Date(data.start_at).toLocaleString() + '</p>';
                  html += '<p class="small mb-1"><strong>' + t('softLaunch.votePanel.statusLine') + '</strong> ' + (data.status || '—') + '</p>';
                  html += '<p class="small mb-0">' + t('softLaunch.votePanel.ballotsCast') + ' ' + (data.ballot_count != null ? data.ballot_count : '—') +
                          ' · ' + t('softLaunch.votePanel.eligible') + ' ' + (data.eligible_count != null ? data.eligible_count : '—') + '</p>';
                  html += '<p class="small text-muted mt-2 mb-0">' + t('softLaunch.votePanel.tallyNote') + '</p>';
                  voteDetails.innerHTML = html;
                }}
              }})
              .catch(err => {{
                console.error('Failed to load vote details:', err);
              }});
          }}

          voteButtons.forEach(btn => {{
            btn.addEventListener('click', e => {{
              e.preventDefault();
              var choice = btn.getAttribute('data-choice');
              if (!choice) return;

              btn.disabled = true;

              fetch('/api/votes/' + encodeURIComponent(voteId) + '/ballot/', {{
                method: 'POST',
                credentials: 'same-origin',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ choice: choice }})
              }}).then(slParseFetchResult).then(x => {{
                if (x.status === 401) {{
                  alert(t('softLaunch.js.signInVote'));
                  btn.disabled = false;
                  return;
                }}
                if (!x.ok) {{
                  btn.disabled = false;
                  alert(slApiUserMessage(x.status, x.j));
                  return;
                }}
                alert(t('softLaunch.js.voteRecorded'));
                loadVoteDetails();
                voteButtons.forEach(b => b.disabled = true);
              }}).catch(() => {{
                btn.disabled = false;
                alert(t('softLaunch.js.networkError'));
              }});
            }});
          }});

          loadVoteDetails();
        }})();

        // Schedule vote functionality
        (function() {{
          var scheduleForm = document.getElementById('sl-schedule-vote-form');
          if (!scheduleForm) return;

          var aidS = document.querySelector('.sl-artifact-demo')?.getAttribute('data-wired-artifact-id');
          if (!aidS) return;

          function toDatetimeLocalValue(d) {{
            var pad = function (n) {{ return String(n).padStart(2, '0'); }};
            return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) +
              'T' + pad(d.getHours()) + ':' + pad(d.getMinutes());
          }}
          var startSoon = new Date(Date.now() + 3 * 60 * 1000);
          var endWeek = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);
          document.getElementById('vote-start').value = toDatetimeLocalValue(startSoon);
          document.getElementById('vote-end').value = toDatetimeLocalValue(endWeek);

          scheduleForm.addEventListener('submit', e => {{
            e.preventDefault();

            var title = document.getElementById('vote-title').value.trim();
            var startAt = document.getElementById('vote-start').value;
            var endAt = document.getElementById('vote-end').value;
            var quorum = parseInt(document.getElementById('vote-quorum').value);

            if (!title || !startAt || !endAt || !quorum) {{
              alert(t('softLaunch.js.scheduleFillFields'));
              return;
            }}

            var startIso = startAt.length === 16 ? startAt + ':00' : startAt;
            var endIso = endAt.length === 16 ? endAt + ':00' : endAt;

            fetch('/api/artifacts/' + encodeURIComponent(aidS) + '/', {{
              credentials: 'same-origin'
            }}).then(r => r.json())
              .then(artifact => {{
                var layerId = artifact.layer_id;
                if (!layerId) {{
                  alert(t('softLaunch.js.scheduleNoLayer'));
                  return Promise.reject('no_layer');
                }}

                var subId = artifact.submission_id;
                if (!subId) {{
                  alert(t('softLaunch.js.scheduleNoSubmission'));
                  return Promise.reject('no_submission');
                }}
                return fetch('/api/layers/' + encodeURIComponent(layerId) + '/votes/', {{
                  method: 'POST',
                  credentials: 'same-origin',
                  headers: {{ 'Content-Type': 'application/json' }},
                  body: JSON.stringify({{
                    title: title,
                    start_at: startIso,
                    end_at: endIso,
                    quorum_count: quorum,
                    submission_id: subId,
                    vote_type: 'approval'
                  }})
                }});
              }})
              .then(slParseFetchResult)
              .then(x => {{
                if (x.status === 401) {{
                  alert(t('softLaunch.js.scheduleSignIn'));
                  return Promise.reject('auth');
                }}
                if (!x.ok) {{
                  alert(slApiUserMessage(x.status, x.j));
                  return Promise.reject('fail');
                }}
                return x.j;
              }})
              .then(() => {{
                alert(t('softLaunch.js.scheduleSuccess'));
                var modalEl = bootstrap.Modal.getInstance(document.getElementById('sl-schedule-vote-modal'));
                if (modalEl) modalEl.hide();
              }})
              .catch(err => {{
                if (err !== 'auth' && err !== 'no_layer' && err !== 'no_submission' && err !== 'fail') {{
                  alert(t('softLaunch.js.networkError'));
                }}
              }});
          }});
        }})();
      }});
    }})();
    </script>
    '''


@bp.route('/soft-launch/', strict_slashes=False)
def soft_launch_home():
    generate_user_menu, render_page = _imports()
    from flask import session
    from services.identity import get_current_user

    user_menu = generate_user_menu()
    theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')
    return render_page(
        'Soft Launch — Gov-Hub',
        _build_homepage_html(),
        theme=theme,
        user_menu=user_menu,
        body_attrs='class="soft-launch-page"',
    )


@bp.route('/soft-launch/onboarding/', strict_slashes=False)
def soft_launch_onboarding():
    generate_user_menu, render_page = _imports()
    from flask import session
    from services.identity import get_current_user

    user_menu = generate_user_menu()
    theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')
    return render_page(
        'Onboarding — Soft Launch',
        _build_onboarding_html(),
        theme=theme,
        user_menu=user_menu,
    )


@bp.route('/soft-launch/artifact/', strict_slashes=False)
def soft_launch_artifact_demo():
    generate_user_menu, render_page = _imports()
    from flask import session
    from services.identity import get_current_user

    scenario = (request.args.get('scenario') or 'under_review').strip().lower()
    payload = full_fixtures_payload()
    artifacts = payload.get('artifacts') or {}
    artifact = artifacts.get(scenario) or artifacts.get('under_review')
    if artifact is None:
        from fixtures.soft_launch import demo_artifact

        artifact = demo_artifact('under_review', readiness_met=False)

    user_menu = generate_user_menu()
    theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')
    wired = SOFT_LAUNCH_WIRED_ARTIFACT_ID or None
    return render_page(
        f"Demo — {_esc(artifact.get('title') or 'Soft launch')}",
        _build_artifact_demo_html(
            artifact,
            show_dev_hints=current_app.debug,
            wired_artifact_id=wired,
        ),
        theme=theme,
        user_menu=user_menu,
    )
