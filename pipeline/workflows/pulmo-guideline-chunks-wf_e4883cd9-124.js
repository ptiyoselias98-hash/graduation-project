export const meta = {
  name: 'pulmo-guideline-chunks',
  description: 'Extract page-cited diagnosis chunks from the 2022 ESC/ERS PH guideline into a canonical retrieval corpus',
  phases: [{ title: 'Chunk', detail: '6 parallel page-range readers' }],
}

phase('Chunk')
const pdf = 'D:\\Wechat\\xwechat_files\\wxid_tqhcohrsdr5622_9227\\msg\\file\\2026-05\\Humbert 等 - 2022 - 2022 ESCERS Guidelines for the diagnosis and treatment of pulmonary hypertension.pdf'

const CHUNK_SCHEMA = {
  type: 'object',
  properties: {
    chunks: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          chunk_id: { type: 'string' },
          text: { type: 'string' },
          source: { type: 'string' },
          entities: { type: 'array', items: { type: 'string' } },
          page: { type: 'integer' },
          section: { type: 'string' },
        },
        required: ['chunk_id', 'text', 'source', 'entities', 'page', 'section'],
        additionalProperties: false,
      },
    },
  },
  required: ['chunks'],
  additionalProperties: false,
}

const RANGES = [
  { pages: '20-22', section: 'Definitions & Classification', focus: 'Table 5 haemodynamic definitions (mPAP>20; pre/post-capillary PAWP≤15 vs >15; PVR>2 WU; exercise PH mPAP/CO>3); the 5-group clinical classification (Table 6), especially Group 1 PAH, Group 2 LHD, Group 3 lung disease/COPD, Group 4 CTEPH.' },
  { pages: '27-30', section: 'Echo / CT / ECG signs & RHC normals', focus: 'ECG & chest X-ray signs (incl. peripheral vascular pruning); echocardiographic signs & PH probability (Table 10 / Fig 5: peak TRV>2.8 m/s, RV/LV>1.0, septal flattening/LVEI, TAPSE/sPAP, RA area>18, RVOT-AT<105ms, PA diameter); CT signs (PA/AO>0.9, PA diameter≥30mm, RVOT wall≥6mm, RV/LV≥1); RHC normal values & formulae (PVR=(mPAP-PAWP)/CO).' },
  { pages: '32-36', section: 'Diagnostic algorithm', focus: 'The stepwise diagnostic pathway (Fig 6): Step1 suspicion (BNP/NT-proBNP, ECG); Step2 detection (echo central first-line, PFT+DLCO, ABG, chest CT); echo probability low/intermediate/high; Step3 confirmation at PH centre + RHC, V/Q for CTEPH; fast-track warning signs; characteristic features by group (Table 14).' },
  { pages: '40-43', section: 'Risk stratification', focus: 'WHO functional class; three-strata risk at diagnosis (Table 16) and four-strata at follow-up (Table 18) with cutoffs for 6MWD, BNP/NT-proBNP, RAP, CI, SvO2, SVI, RA area, TAPSE/sPAP.' },
  { pages: '74-76', section: 'Group 3 / COPD-PH', focus: 'PH associated with lung disease: non-severe vs severe split by PVR (non-severe PVR≤5 WU, SEVERE PH = PVR>5 WU — the key 2022 change); prevalence (severe PH in 1-5% of COPD); pulmonary vascular phenotype (preserved spirometry, low DLCO, hypoxaemia, low PaCO2, vascular pruning); imaging/echo composite (RV:LV, RA area, LVEI) when TRV unmeasurable; contrast CT signs.' },
  { pages: '77-78', section: 'CTEPH', focus: 'Chronic thromboembolic PH diagnosis: V/Q mismatched perfusion defects (normal scan excludes CTEPH), CTPA/DSA organized clots, webs/bands/ring stenoses, ≥3 months anticoagulation, distinction from PAH.' },
]

const results = await parallel(RANGES.map((r) => () =>
  agent(
`Read pages ${r.pages} of this PDF (use the Read tool with the pages parameter): ${pdf}

This is the 2022 ESC/ERS Pulmonary Hypertension Guidelines. Focus section: "${r.section}". Extract the DIAGNOSIS-relevant statements as a set of self-contained retrieval chunks (each 1-4 sentences, near-verbatim from the text but CLEANED).

CLEANING RULES:
- The PDF text extractor sometimes renders ">" as "." and "<" as "," — fix these to the correct inequality based on clinical meaning (e.g. "mPAP . 20 mmHg" -> "mPAP > 20 mmHg"; "PAWP , 15" -> "PAWP ≤ 15").
- Keep exact numeric thresholds and units. Do not invent content not on the page.

For EACH chunk emit:
- chunk_id: "esc_ers_ph_2022::p<JP>::c<n>" where <JP> is the printed JOURNAL page number visible on the page header/footer (the guideline runs Eur Heart J 2022;43:3618-3731; if not visible, compute JP = 3616 + <pdf_page>), and <n> is a 1-based index within this range.
- text: the cleaned passage.
- source: "ESC/ERS 2022 PH Guidelines, p.<JP>".
- entities: key clinical terms in the chunk (e.g. ["mPAP","PVR","pre-capillary PH","Group 3","COPD"]).
- page: <JP> as an integer.
- section: "${r.section}".

Aim for 6-12 high-value, non-overlapping chunks covering: ${r.focus}
Return ONLY the structured object.`,
    { label: `chunks:${r.section}`.slice(0, 40), phase: 'Chunk', schema: CHUNK_SCHEMA }
  ).then((res) => (res && res.chunks ? res.chunks : []))
))

const all = results.filter(Boolean).flat()
return { total: all.length, chunks: all }
