# DP Challenge Readiness

This complements the existing desirableproperties.org work by routing the
domain into Gov Hub's current DP Challenge hub instead of replacing any site
content in progress.

## Domain Routing

- `desirableproperties.org` and `www.desirableproperties.org` are recognized by
  `middleware/dp_challenge_host_wsgi.py`.
- The host root rewrites to `/dp-challenge/`; existing `/static/`, `/api/`,
  `/auth/`, `/login/`, and deployment paths are left untouched.
- Deployment still needs DNS and reverse proxy host headers pointed at the Gov
  Hub app.

## Recruitment Permissions

- Leads and co-leads can edit workgroups and invite members.
- Layer admins and site admins retain operational control.
- Members can participate after joining but are not automatically recruiters.
- Co-leads use the existing workgroup nomination system with
  `position_key='co_lead'`; no schema migration is required.

## Member Approval

Direct joins and invite acceptance both use the same membership helper. If a
static workgroup configuration requires member approval, both paths create or
reuse a pending `WorkgroupMemberRequest`; otherwise both paths create a
`WorkingGroupMember`.

## Contributor Badges

DP contributor badges are scaffolded as off-chain workgroup-authority awards.
The admin readiness page reports whether each DP workgroup has existing
workgroup badge settings enabled.

On-chain issuance and Inscription Day preservation remain a future operations
step. No automated ordinal issuance is performed by this readiness work.
