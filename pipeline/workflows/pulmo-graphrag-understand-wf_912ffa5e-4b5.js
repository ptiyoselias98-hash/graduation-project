export const meta = {
  name: 'pulmo-graphrag-understand',
  description: 'Deep-read existing GraphRAG framework, LLM wiring, ESC/ERS guideline, and demo contract to design a real GraphRAG diagnosis build',
  phases: [{ title: 'Understand', detail: '4 parallel deep readers' }],
}

phase('Understand')

const graphragDir = 'C:\\Users\\cheng\\graphrag_pulmo\\LungNoduleAgent\\lung_agents\\graphrag'
const agentbaseRoot = 'C:\\Users\\cheng\\graphrag_pulmo\\LungNoduleAgent'
const pdf = 'D:\\Wechat\\xwechat_files\\wxid_tqhcohrsdr5622_9227\\msg\\file\\2026-05\\Humbert 等 - 2022 - 2022 ESCERS Guidelines for the diagnosis and treatment of pulmonary hypertension.pdf'
const demo = 'E:\\桌面文件\\5月14日下午毕业设计\\！！！前端演示'

const results = await parallel([
  () => agent(
`You are reverse-engineering an EXISTING GraphRAG module so we can REUSE it (not rebuild). Read these local files fully with the Read tool:
- ${graphragDir}\\__init__.py
- ${graphragDir}\\config.py
- ${graphragDir}\\index_builder.py
- ${graphragDir}\\preprocess.py
- ${graphragDir}\\retriever.py
- ${graphragDir}\\tool.py
- ${graphragDir}\\backends\\msgraphrag.py
- ${graphragDir}\\backends\\__init__.py

Produce a precise markdown report:
1. END-TO-END FLOW: how raw documents become an index, and how a query becomes retrieved evidence. Name the actual classes/functions and the order they run.
2. BACKEND: Is this Microsoft GraphRAG (graphrag pip pkg) under the hood? What exact pipeline/config does msgraphrag.py drive (entity extraction, community detection, embeddings, local/global search)? What does it require to run (graphrag version, settings.yaml, env vars, API base/keys)?
3. EMBEDDINGS + LLM: what embedding model and chat model does indexing/retrieval call, and HOW is it configured (hardcoded? from config? OpenAI-compatible base_url?). Can it be pointed at a local model?
4. INPUT FORMAT: exact format/dir layout of documents the indexer ingests (txt? chunked? metadata?).
5. OUTPUT/RETRIEVAL SCHEMA: the exact shape of what retriever returns (fields), and what graph artifacts get written (nodes/edges files, formats).
6. REUSE RECIPE: concrete steps to index a clinical guideline corpus (ESC/ERS PH PDF + GOLD + ATS/ERS) and serve dual retrieval (graph + vector) returning evidence chunks with source + page. Note exactly which files we'd touch and any gaps.
Quote key code lines. Be concrete and exhaustive.`,
    { label: 'graphrag-reuse', phase: 'Understand' }
  ),

  () => agent(
`You are mapping the LLM/agent wiring of an existing multi-agent diagnosis framework so we can reuse it and point models at LOCAL weights. Read fully with the Read tool:
- ${agentbaseRoot}\\agentbase\\model\\litellm_model.py
- ${agentbaseRoot}\\agentbase\\model\\schema.py
- ${agentbaseRoot}\\agentbase\\model\\base.py
- ${agentbaseRoot}\\agentbase\\config\\base.py
- ${agentbaseRoot}\\agentbase\\config\\config_example.yaml
- ${agentbaseRoot}\\agentbase\\agent\\base.py
- ${agentbaseRoot}\\agentbase\\agent\\tool_agent.py
- ${agentbaseRoot}\\agentbase\\tool\\manager.py
- ${agentbaseRoot}\\config.example.yaml
- ${agentbaseRoot}\\config.py
- ${agentbaseRoot}\\config.single_model.yaml
- ${agentbaseRoot}\\lung_agents\\settings.py
- ${agentbaseRoot}\\lung_agents\\orchestrator.py
- ${agentbaseRoot}\\lung_agents\\judge_agent.py
- ${agentbaseRoot}\\lung_agents\\judges.py
- ${agentbaseRoot}\\lung_agents\\conversation.py
- ${agentbaseRoot}\\lung_agents\\main.py

Produce a precise markdown report:
1. MODEL LAYER: how litellm_model.py calls LLMs. What provider/base_url/model names appear in the example configs? Is it OpenAI-compatible (so a local vLLM/Qwen server works)? What env vars/keys are needed?
2. HOW TO POINT AT LOCAL QWEN: concretely, what config changes make it call a local Qwen2.5-7B-Instruct (e.g. via an OpenAI-compatible endpoint) instead of a hosted API. Note if litellm supports this.
3. MULTI-AGENT ORCHESTRATION: how orchestrator.py + judge_agent.py + conversation.py run the agent loop / debate / voting. What's the role/prompt structure? Is this directly reusable to build Pulmonologist/Cardiologist/Radiologist debate rounds with vote+synthesis (matching the demo's debates.json)?
4. TOOLS: how tools (incl. the graphrag tool) are registered and invoked by agents.
5. REUSE ASSESSMENT: what we keep vs. change to drive a guideline-grounded GraphRAG PH/COPD-PH diagnosis with traceable evidence. List concrete touch points and gaps.
Quote key code lines. Be concrete.`,
    { label: 'agentbase-llm', phase: 'Understand' }
  ),

  () => agent(
`Extract the DIAGNOSIS-relevant knowledge from the 2022 ESC/ERS Pulmonary Hypertension Guidelines PDF so we can seed and validate a clinical knowledge graph. The PDF is large (~100+ pages); be efficient.
PDF path: ${pdf}

Approach: First Read pages 1-3 (and any table-of-contents pages) to locate section page numbers. Then Read ONLY the diagnosis-relevant sections using the pages parameter (max 20 pages/call): hemodynamic definitions, clinical classification (the 5 groups), the diagnostic algorithm/flowchart, and ESPECIALLY Group 3 PH (PH associated with lung disease / COPD) and severity assessment (PVR, mPAP cutoffs). Skip the treatment-only chapters.

Produce a precise markdown report (with page citations for everything):
1. HEMODYNAMIC DEFINITIONS: the 2022 definitions/cutoffs (mPAP > 20 mmHg, PAWP, PVR > 2 WU, pre/post-capillary, exercise PH) — exact numbers + page.
2. CLINICAL CLASSIFICATION: the 5 groups (esp. Group 1 PAH, Group 3 lung-disease PH incl. COPD, Group 4 CTEPH) — page.
3. GROUP 3 / COPD-PH: definitions of "PH associated with COPD" and "severe PH in lung disease" (e.g. PVR threshold), the ATS/ERS-style severity split, imaging/clinical signs the guideline names — page.
4. DIAGNOSTIC ALGORITHM: the stepwise pathway (echo probability -> RHC etc.), risk stratification — as an ordered list with page refs.
5. ENTITIES + RELATIONS + THRESHOLDS: a structured list (entity, type, threshold, relation-to-disease, source-page) suitable for building KG nodes/edges. Cover: diseases (COPD, PAH, CTEPH, COPD-PH), indicators (mPAP, PAWP, PVR, PA/AO, RV/LV, RA, echo PASP, BV5/pruning), and how each supports/refutes which diagnosis.
Be exhaustive on diagnosis; ignore drug dosing.`,
    { label: 'guideline-knowledge', phase: 'Understand' }
  ),

  () => agent(
`Reverse-engineer the EXACT data contract of a frontend demo so a real backend can produce drop-in-compatible output. Read fully with the Read tool:
- ${demo}\\data\\kg.json
- ${demo}\\data\\debates.json
- ${demo}\\data\\cases.json
- ${demo}\\index.html
- ${demo}\\app.js   (large ~38KB, read it all)

Produce a precise markdown report:
1. kg.json SCHEMA: every field of nodes and edges (id, label, type enum values, x/y/size, rel enum values, w). How x/y layout + node types + edge rels are rendered.
2. debates.json SCHEMA: full nested schema per case — kg_retrieval[] (id, source, chunk, score, supports), rounds[] (round, responses[] with agent/claim/confidence/evidence/cot/control), vote{}, synthesis. List EVERY field and its type/meaning, including the agent role names and the 'control' enum and how a final diagnosis is reached.
3. cases.json SCHEMA: every field (patient features, ground-truth label, the SCR feature names used).
4. RENDER MAP: which JSON fields drive which UI scene/panel in app.js (the KG graph view, the retrieval evidence list, the debate rounds, the verdict). Name the app.js functions.
5. BACKEND OUTPUT CONTRACT: a concise spec of exactly what a real GraphRAG+debate backend must emit (file by file, field by field) so this existing frontend renders real results unchanged. Note any field currently hand-faked that must become real (esp. kg_retrieval.chunk/source/score and node/edge provenance).
Quote concrete keys/values. Be exhaustive.`,
    { label: 'demo-contract', phase: 'Understand' }
  ),
])

return {
  graphragReuse: results[0],
  agentbaseLlm: results[1],
  guidelineKnowledge: results[2],
  demoContract: results[3],
}
