import { agentScopeClient } from './request';

export type ChunkStrategy = 'general' | 'parent_child' | 'qa';
export type IndexMethod = 'hybrid' | 'keyword' | 'knowledge_graph' | 'vector';

export interface PipelineStage {
  type:
    | 'build_graph'
    | 'clean'
    | 'datasource'
    | 'embed'
    | 'extract'
    | 'index'
    | 'qa'
    | 'split'
    | 'split_parent_child';
  name: string;
  config: Record<string, any>;
}

export interface KnowledgeBase {
  id: string;
  owner_user_id: string;
  name: string;
  description: string;
  icon: string;
  chunk_strategy: ChunkStrategy;
  index_method: IndexMethod;
  kg_type: string;
  kg_credential_id: string;
  kg_model: string;
  qa_type: string;
  qa_credential_id: string;
  qa_model: string;
  pipeline: PipelineStage[];
  top_k: number;
  score_threshold: number;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeTriple {
  id: string;
  subject: string;
  predicate: string;
  object: string;
  document_id: string;
  chunk_id: string;
}

export interface KnowledgeBaseListItem {
  kb: KnowledgeBase;
  doc_count: number;
  chunk_count: number;
}

export interface KnowledgeDocument {
  id: string;
  kb_id: string;
  name: string;
  content: string;
  status: 'failed' | 'indexed' | 'pending';
  chunk_count: number;
  triple_count: number;
  error: string;
  created_at: string;
  updated_at: string;
}

export interface RetrievedTriple {
  subject: string;
  predicate: string;
  object: string;
}

export interface RetrievedChunk {
  id: string;
  document_id: string;
  seq: number;
  content: string;
  answer?: string;
  score: number;
  context?: string;
  triples?: RetrievedTriple[];
}

export function listKnowledgeBases() {
  return agentScopeClient.get<{
    items: KnowledgeBaseListItem[];
    total: number;
  }>('/admin/knowledge-bases/');
}

export function getKnowledgeBase(kbId: string) {
  return agentScopeClient.get<KnowledgeBase>(`/admin/knowledge-bases/${kbId}`);
}

export function createKnowledgeBase(payload: Partial<KnowledgeBase>) {
  return agentScopeClient.post<KnowledgeBase>(
    '/admin/knowledge-bases/',
    payload,
  );
}

export function updateKnowledgeBase(
  kbId: string,
  payload: Partial<KnowledgeBase>,
) {
  return agentScopeClient.request<KnowledgeBase>(
    `/admin/knowledge-bases/${kbId}`,
    { method: 'PATCH', data: payload },
  );
}

export function deleteKnowledgeBase(kbId: string) {
  return agentScopeClient.delete(`/admin/knowledge-bases/${kbId}`);
}

export function listDocuments(kbId: string) {
  return agentScopeClient.get<{ items: KnowledgeDocument[]; total: number }>(
    `/admin/knowledge-bases/${kbId}/documents`,
  );
}

export function addDocument(
  kbId: string,
  payload: { content: string; name: string },
) {
  return agentScopeClient.post<KnowledgeDocument>(
    `/admin/knowledge-bases/${kbId}/documents`,
    payload,
  );
}

export function reindexDocument(kbId: string, docId: string) {
  return agentScopeClient.post<KnowledgeDocument>(
    `/admin/knowledge-bases/${kbId}/documents/${docId}/reindex`,
  );
}

export function deleteDocument(kbId: string, docId: string) {
  return agentScopeClient.delete(
    `/admin/knowledge-bases/${kbId}/documents/${docId}`,
  );
}

export function retrieve(
  kbId: string,
  query: string,
  topK?: number,
  method?: string,
) {
  return agentScopeClient.post<{ items: RetrievedChunk[]; total: number }>(
    `/admin/knowledge-bases/${kbId}/retrieve`,
    { query, top_k: topK, method },
  );
}

export function reindexKnowledgeBase(kbId: string) {
  return agentScopeClient.post<{ ok: boolean; reindexed: number }>(
    `/admin/knowledge-bases/${kbId}/reindex`,
  );
}

export function listTriples(kbId: string, documentId?: string) {
  return agentScopeClient.get<{ items: KnowledgeTriple[]; total: number }>(
    `/admin/knowledge-bases/${kbId}/triples`,
    documentId ? { params: { document_id: documentId } } : undefined,
  );
}
