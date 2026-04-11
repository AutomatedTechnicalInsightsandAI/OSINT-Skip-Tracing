# GoHighLevel CRM Integration

This module delivers qualified OSINT leads directly into GoHighLevel (GHL) pipelines
for three verticals: **Home Services**, **Real Estate/Mortgage**, and **B2B**.

---

## Environment Variables

Set these in your `.env` file or shell before running the app.

### Required

| Variable | Description |
|---|---|
| `GHL_API_KEY` | GoHighLevel Bearer token (find in GHL → Settings → API Keys) |

### Optional — Override Pipeline IDs

| Variable | Default | Description |
|---|---|---|
| `GHL_HS_PIPELINE_ID` | `hs_pipeline_001` | Home Services pipeline ID |
| `GHL_RE_PIPELINE_ID` | `re_pipeline_001` | Real Estate pipeline ID |
| `GHL_B2B_PIPELINE_ID` | `b2b_pipeline_001` | B2B pipeline ID |

### Optional — Override Stage IDs (Home Services)

| Variable | Default | Stage |
|---|---|---|
| `GHL_HS_STAGE_NEW` | `stage_hs_01` | New Lead |
| `GHL_HS_STAGE_QUAL` | `stage_hs_02` | Qualified |
| `GHL_HS_STAGE_APPT` | `stage_hs_03` | Appointment Set |
| `GHL_HS_STAGE_KEPT` | `stage_hs_04` | Appointment Kept |
| `GHL_HS_STAGE_EST` | `stage_hs_05` | Estimate Sent |
| `GHL_HS_STAGE_WON` | `stage_hs_06` | Closed Won |
| `GHL_HS_STAGE_LOST` | `stage_hs_07` | Closed Lost |

### Optional — Override Stage IDs (Real Estate / Mortgage)

| Variable | Default | Stage |
|---|---|---|
| `GHL_RE_STAGE_NEW` | `stage_re_01` | New Lead |
| `GHL_RE_STAGE_PREQ` | `stage_re_02` | Pre-Qualified |
| `GHL_RE_STAGE_QUAL` | `stage_re_03` | Qualified |
| `GHL_RE_STAGE_DOCS` | `stage_re_04` | Docs Requested |
| `GHL_RE_STAGE_TERM` | `stage_re_05` | Term Sheet Sent |
| `GHL_RE_STAGE_CONT` | `stage_re_06` | Under Contract |
| `GHL_RE_STAGE_FUND` | `stage_re_07` | Closed / Funded |
| `GHL_RE_STAGE_LOST` | `stage_re_08` | Closed Lost |

### Optional — Override Stage IDs (B2B)

| Variable | Default | Stage |
|---|---|---|
| `GHL_B2B_STAGE_NEW` | `stage_b2b_01` | New Lead |
| `GHL_B2B_STAGE_CONT` | `stage_b2b_02` | Contacted |
| `GHL_B2B_STAGE_QUAL` | `stage_b2b_03` | Qualified |
| `GHL_B2B_STAGE_DEMO` | `stage_b2b_04` | Demo Scheduled |
| `GHL_B2B_STAGE_PROP` | `stage_b2b_05` | Proposal Sent |
| `GHL_B2B_STAGE_NEG` | `stage_b2b_06` | Negotiation |
| `GHL_B2B_STAGE_WON` | `stage_b2b_07` | Closed Won |
| `GHL_B2B_STAGE_LOST` | `stage_b2b_08` | Closed Lost |

### Webhook Security

| Variable | Description |
|---|---|
| `GHL_WEBHOOK_SECRET` | Shared secret for HMAC-SHA256 webhook signature verification |

---

## Pipeline Stage Mapping

### Home Services

```
New Lead → Qualified → Appointment Set → Appointment Kept → Estimate Sent → Closed Won / Lost
```

Default lead values per sub-vertical:

| Sub-Vertical | Default Value |
|---|---|
| HVAC | $185 |
| Roofing | $225 |
| Plumbing | $125 |
| Solar | $275 |
| Electrical | $150 |
| Water Damage | $300 |
| Windows | $175 |
| Pest Control | $85 |

### Real Estate / Mortgage

```
New Lead → Pre-Qualified → Qualified → Docs Requested → Term Sheet Sent → Under Contract → Closed/Funded / Lost
```

Default lead values per sub-vertical:

| Sub-Vertical | Default Value |
|---|---|
| DSCR Loan | $350 |
| Hard Money | $450 |
| Fix & Flip | $300 |
| Bridge Loan | $400 |
| Commercial RE | $700 |
| Wholesale Buyer | $200 |
| Apartment Syndication | $900 |

### B2B

```
New Lead → Contacted → Qualified → Demo Scheduled → Proposal Sent → Negotiation → Closed Won / Lost
```

Default lead values per segment:

| Segment | Default Value |
|---|---|
| SMB (< $250k assessed) | $500 |
| Mid-Market ($250k–$1M assessed) | $2,500 |
| Enterprise (> $1M assessed) | $10,000 |

---

## How to Find Pipeline & Stage IDs in GHL

1. Log in to GoHighLevel.
2. Navigate to **CRM → Pipelines**.
3. Click the pipeline you want to use.
4. The URL will contain the pipeline ID, e.g.:
   `https://app.gohighlevel.com/v2/location/XYZ/pipeline/YOUR_PIPELINE_ID`
5. For stage IDs, open browser DevTools → Network tab → reload the page and
   inspect the `/pipelines` API response, or use the GHL API:
   ```
   GET https://rest.gohighlevel.com/v1/pipelines/
   Authorization: Bearer YOUR_API_KEY
   ```

---

## Example `.env` File

```dotenv
# GoHighLevel API
GHL_API_KEY=your_bearer_token_here
GHL_WEBHOOK_SECRET=your_webhook_secret_here

# Home Services Pipeline
GHL_HS_PIPELINE_ID=abc123
GHL_HS_STAGE_NEW=stage_001
GHL_HS_STAGE_QUAL=stage_002
GHL_HS_STAGE_APPT=stage_003
GHL_HS_STAGE_KEPT=stage_004
GHL_HS_STAGE_EST=stage_005
GHL_HS_STAGE_WON=stage_006
GHL_HS_STAGE_LOST=stage_007

# Real Estate Pipeline
GHL_RE_PIPELINE_ID=def456
GHL_RE_STAGE_NEW=stage_101
GHL_RE_STAGE_PREQ=stage_102
GHL_RE_STAGE_QUAL=stage_103
GHL_RE_STAGE_DOCS=stage_104
GHL_RE_STAGE_TERM=stage_105
GHL_RE_STAGE_CONT=stage_106
GHL_RE_STAGE_FUND=stage_107
GHL_RE_STAGE_LOST=stage_108

# B2B Pipeline
GHL_B2B_PIPELINE_ID=ghi789
GHL_B2B_STAGE_NEW=stage_201
GHL_B2B_STAGE_CONT=stage_202
GHL_B2B_STAGE_QUAL=stage_203
GHL_B2B_STAGE_DEMO=stage_204
GHL_B2B_STAGE_PROP=stage_205
GHL_B2B_STAGE_NEG=stage_206
GHL_B2B_STAGE_WON=stage_207
GHL_B2B_STAGE_LOST=stage_208
```
