"""Knowledge base + ingestion pipeline (Dify-style).

A :class:`KnowledgeBase` owns :class:`Document` rows; each document is split
into :class:`Chunk` rows by a configurable ingestion *pipeline*. Retrieval is
a dependency-free TF-IDF cosine ranking so the feature works without any
external embedding service. Retrieval is reused as a workflow node and as an
agent tool.
"""
