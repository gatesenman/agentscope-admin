import { agentScopeClient } from './request';

export interface PipelineStage {
  type: 'clean' | 'extract' | 'index' | 'split';
  name: string;
  config: Record<string, any>;
}

export interface KnowledgeBase {
  id: string;
  owner_user_id: string;
  name: string;
  description: string;
  icon: string;
  pipeline: PipelineStage[];
  top_k: number;
  score_threshold: number;
  created_at: string;
  updated_at: string;
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
  error: string;
  created_at: string;
  updated_at: string;
}

export interface RetrievedChunk {
  id: string;
  document_id: string;
  seq: number;
  content: string;
  score: number;
}

export function listKnowledgeBases() {
  return agentScopeClient.get<{
    items: KnowledgeBaseListItem[];
    total: number;
  }>('/admin/knowledge-bases/');
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

export function retrieve(kbId: string, query: string, topK?: number) {
  return agentScopeClient.post<{ items: RetrievedChunk[]; total: number }>(
    `/admin/knowledge-bases/${kbId}/retrieve`,
    { query, top_k: topK },
  );
}
