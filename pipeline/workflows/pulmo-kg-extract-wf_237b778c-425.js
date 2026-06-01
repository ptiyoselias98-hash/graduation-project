export const meta = {
  name: 'pulmo-kg-extract',
  description: 'Auto-extract entities + relations from the 76 guideline chunks (GraphRAG indexing via Claude)',
  phases: [{ title: 'Extract', detail: '8 batches over chunks.jsonl' }],
}
phase('Extract')
const CHUNKS = 'C:\\Users\\cheng\\graphrag_pulmo\\chunks.jsonl'
const TOTAL = 76, NB = 8
const per = Math.ceil(TOTAL / NB)

const SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    entities: { type: 'array', items: { type: 'object', additionalProperties: false,
      properties: { name: { type: 'string' }, type: { type: 'string' }, description: { type: 'string' } },
      required: ['name', 'type', 'description'] } },
    relations: { type: 'array', items: { type: 'object', additionalProperties: false,
      properties: { source: { type: 'string' }, target: { type: 'string' }, relation: { type: 'string' },
        page: { type: 'integer' }, description: { type: 'string' } },
      required: ['source', 'target', 'relation', 'page', 'description'] } },
  }, required: ['entities', 'relations'],
}

const ranges = Array.from({ length: NB }, (_, i) => [i * per, Math.min(TOTAL, (i + 1) * per)])
const out = await parallel(ranges.map(([s, e]) => () =>
  agent(
`你在为「肺动脉高压(PH) vs COPD-PH 诊断」构建知识图谱，做 GraphRAG 的实体/关系抽取步骤。

用 Read 工具读取 ${CHUNKS}（每行一个 JSON：chunk_id/text/source/entities/metadata.page）。只处理**第 ${s} 到 ${e-1} 行（0 基，含端点）**这 ${e - s} 条 chunk。

对这些 chunk 抽取构建诊断知识图谱所需的：
- entities：实体。name=规范术语（英文缩写优先，如 "mPAP","PVR","PA/AO","RV/LV","TRV","DLCO","COPD","COPD-PH","Group 3 PH","PAH","CTEPH","pre-capillary PH","emphysema","vascular pruning"…）；type∈{"disease","indicator","threshold","finding","concept","source"}；description=1 句中文释义（含阈值，如 "PVR>5 WU 定义严重 Group3 PH"）。
- relations：关系三元组。source/target=实体 name；relation∈{"defines","supports","subtype_of","differentiates","splits_severity","measured_by","associated_with","cites"}；page=该关系来源 chunk 的 metadata.page（整数）；description=1 短句中文依据。

要求：术语规范统一（同义归一，如 "mean pulmonary arterial pressure"→"mPAP"）；只抽诊断相关、有出处的；每条 chunk 约 3-6 实体、2-5 关系。只输出结构化对象。`,
    { label: `extract_${s}-${e - 1}`, phase: 'Extract', schema: SCHEMA }
  ).then((r) => r || { entities: [], relations: [] }).catch(() => ({ entities: [], relations: [] }))
))
const entities = out.flatMap((o) => o.entities || [])
const relations = out.flatMap((o) => o.relations || [])
return { n_entities: entities.length, n_relations: relations.length, entities, relations }
