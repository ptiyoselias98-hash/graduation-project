export const meta = {
  name: 'pulmo-debate-all260',
  description: 'Claude multi-agent guideline-grounded COPD vs COPD-PH debate over all 260 cohort cases',
  phases: [{ title: 'Debate', detail: '52 batches × 5 cases' }],
}
phase('Debate')
const NB = (args && args.nbatches) ? args.nbatches : 52
const DIR = 'C:\\Users\\cheng\\graphrag_pulmo'

const ENTRY = {
  type: 'object',
  properties: {
    id: { type: 'string' },
    kg_retrieval: { type: 'array', items: { type: 'object', additionalProperties: false, properties: {
      id: { type: 'string' }, node_id: { type: 'string' }, source: { type: 'string' },
      chunk: { type: 'string' }, score: { type: 'number' }, supports: { type: 'string' } },
      required: ['id', 'node_id', 'source', 'chunk', 'score', 'supports'] } },
    rounds: { type: 'array', items: { type: 'object', additionalProperties: false, properties: {
      round: { type: 'integer' },
      responses: { type: 'array', items: { type: 'object', additionalProperties: false, properties: {
        agent: { type: 'string' }, claim: { type: 'string' }, confidence: { type: 'number' },
        evidence: { type: 'array', items: { type: 'string' } }, cot: { type: 'string' }, control: { type: 'string' } },
        required: ['agent', 'claim', 'confidence', 'evidence', 'cot', 'control'] } },
      vote: { type: 'object', additionalProperties: { type: 'integer' } }, synthesis: { type: 'string' } },
      required: ['round', 'responses', 'vote', 'synthesis'] } },
    final: { type: 'object', additionalProperties: false, properties: {
      diagnosis: { type: 'string' }, confidence: { type: 'number' },
      evidence_chain: { type: 'array', items: { type: 'string' } },
      fallback_triggered: { type: 'boolean' }, trace_id: { type: 'string' } },
      required: ['diagnosis', 'confidence', 'evidence_chain', 'fallback_triggered', 'trace_id'] } },
  required: ['id', 'kg_retrieval', 'rounds', 'final'], additionalProperties: false,
}
const BATCH_SCHEMA = { type: 'object', additionalProperties: false,
  properties: { results: { type: 'array', items: ENTRY } }, required: ['results'] }

function prompt(i) {
  const bf = `${DIR}\\batches\\batch_${String(i).padStart(3, '0')}.json`
  return `你是一套「基于 2022 ESC/ERS 指南的 GraphRAG 多智能体诊断系统」。任务：对一批患者做 **COPD vs COPD-PH（肺病相关肺动脉高压）** 的盲诊（不提供金标准），每例产出可溯源的检索证据 + 三专家辩论 + 终判。

【读取这三个文件（Read 工具）】
1. 病例批次：${bf}  （含若干 case，每个有 patient / structural_metrics / density_metrics / vessel_tree_metrics / qualitative_findings / rf_proba_ph）
2. 指南证据库：${DIR}\\chunks.jsonl  （76 条 ESC/ERS 指南页码级 chunk：chunk_id/text/source(含p.页码)/entities/metadata.page）
3. 知识图谱节点表：${DIR}\\out_kg_nodes.json  （node id/label/type，node_id 必须取自此表，缺省用 "PH"）

【重要校准（务必遵守，否则会过度判 PH）】本队列均为晚期 COPD 患者，PA/AO 与主肺动脉径普遍偏高，PA/AO>0.9 或 MPA≥30mm 单独**不能**区分是否合并 PH。判别力优先级：① rf_proba_ph（RF 结构模型在本队列校准的 P(PH)：<0.3 强烈倾向 COPD，>0.7 倾向 COPD-PH，0.4–0.6 为真不确定）；② 右心受累 RV/LV≥1.0、RA 扩张；③ 血管表型 BV5↓、低 DLCO。PA/AO 与 MPA 仅作辅助。若 rf_proba_ph 在 0.4–0.6 且 RV/LV<1.0，应判 **COPD** 且 confidence<0.6 并触发 fallback。

【每个 case 的产出】
- kg_retrieval：从 76 条 chunk 中选与该病例最相关的 **5 条**。每条：id=chunk_id；node_id=最相关的 KG 节点 id（取自节点表）；source=chunk 的 source（含页码）；chunk=chunk 文本（≤200 字）；score=相关性 0–1（两位小数，递减）；supports=贡献串（如 "COPD-PH +0.5" / "COPD +0.6" / "context +0.0"）。
- rounds：三位专家 PulmonologistAgent（肺实质/气道/DLCO/血管表型）、CardiologistAgent（右心/血流动力学/RV-LV/RA）、RadiologistAgent（CT 征象 PA/AO、RV/LV、血管修剪、钙化）。每位：claim∈{"COPD","COPD-PH"}；confidence 0–1；evidence=2–3 条短证据（含数值与页码，如 "RV/LV=1.49>1.0 (ESC/ERS p.3644)"）；cot=1–2 句中文推理；control∈{"Continue","Complete","Terminate"}。vote=票数对象（如 {"COPD-PH":2,"COPD":1}）。synthesis=CoordinatorAgent 2–3 句中文总结（票数/是否共识≥2/分歧/决定）。通常 1 轮即可；仅当首轮无人达 2 票共识时才加第 2 轮（交叉检验）。
- final：diagnosis∈{"COPD","COPD-PH"}（共识/多数）；confidence（同意方均值，两位小数）；evidence_chain=3–5 条审计串（"structural_metrics.RV_LV_ratio=1.49 → RV/LV≥1 支持 PH (p.3644)" 这种，含数值→指南→页码）；fallback_triggered（按校准规则）；trace_id="MDT-"+case id。

只输出结构化对象 {results:[每个 case 一个条目...]}，顺序与批次文件一致。务必简洁（evidence/cot 精炼）以保证完整输出。`
}

const out = await parallel(
  Array.from({ length: NB }, (_, i) => () =>
    agent(prompt(i), { label: `batch_${String(i).padStart(3, '0')}`, phase: 'Debate', schema: BATCH_SCHEMA })
      .then((r) => (r && r.results ? r.results : []))
      .catch(() => []))
)
const entries = out.filter(Boolean).flat()
return { total: entries.length, entries }
