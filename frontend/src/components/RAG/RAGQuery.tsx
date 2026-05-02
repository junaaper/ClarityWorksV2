import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Search, Upload, Copy, Download, Loader2, FileText, ChevronDown, ChevronRight, Bot, BookOpen } from 'lucide-react';
import { ragApi } from '../../services/api';
import LoadingSpinner from '../common/LoadingSpinner';
import { exportRAGResultsPDF, exportRAGResultsDOCX } from '../../utils/exportRAG';

interface RagDocument {
  id: number;
  original_filename: string;
  chromadb_collection_id: string;
}

interface QueryResult {
  text: string;
  metadata: {
    chunk_id: string;
    page_number: string;
    word_count: string;
    document_id: string;
    filename?: string;
  };
  similarity_score: number;
  rerank_score?: number;
  collection: string;
}

const RAGQuery: React.FC = () => {
  const [documents, setDocuments] = useState<RagDocument[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<QueryResult[]>([]);
  const [answer, setAnswer] = useState<string | null>(null);
  const [hasAnswer, setHasAnswer] = useState(false);
  const [expandedSources, setExpandedSources] = useState<number[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDocuments = async () => {
    try {
      const docs = await ragApi.getDocuments();
      setDocuments(docs);
    } catch (error) {
      console.error('Failed to fetch documents:', error);
    } finally {
      setLoadingDocs(false);
    }
  };

  const handleQuery = async () => {
    if (!query.trim()) {
      alert('Please enter a query');
      return;
    }

    setLoading(true);

    try {
      const documentIds = selectedDocs.length > 0
        ? selectedDocs.map((coll) => coll.replace('doc_', ''))
        : undefined;

      const response = await ragApi.queryDocuments(query, documentIds);
      setResults(response.results || response.sources || []);
      setAnswer(response.answer || null);
      setHasAnswer(response.has_answer || false);
      setExpandedSources([]);
    } catch (error) {
      console.error('Query error:', error);
      alert('Failed to query documents');
    }

    setLoading(false);
  };

  const toggleSource = (index: number) => {
    setExpandedSources((prev) =>
      prev.includes(index)
        ? prev.filter((i) => i !== index)
        : [...prev, index]
    );
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleQuery();
    }
  };

  const toggleDocument = (collectionId: string) => {
    setSelectedDocs((prev) =>
      prev.includes(collectionId)
        ? prev.filter((id) => id !== collectionId)
        : [...prev, collectionId]
    );
  };

  const exportResults = () => {
    const text = results
      .map(
        (r, i) =>
          `[Result ${i + 1}] (Similarity: ${(r.similarity_score * 100).toFixed(1)}%)\n${r.text}\n`
      )
      .join('\n---\n\n');

    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'rag_query_results.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  const copyAll = async () => {
    const text = results.map((r) => r.text).join('\n\n---\n\n');
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getSimilarityBadge = (score: number) => {
    if (score >= 0.7) return 'cw-badge cw-badge-ok';
    if (score >= 0.5) return 'cw-badge cw-badge-warn';
    return 'cw-badge cw-badge-neutral';
  };

  const getDocumentLabel = (result: QueryResult) => {
    if (result.metadata.filename) {
      return result.metadata.filename;
    }
    return documents.find((doc) => doc.chromadb_collection_id === result.collection)?.original_filename || 'Unknown document';
  };

  return (
    <div>
      {loading && <LoadingSpinner message="Searching documents..." fullScreen />}

      <div className="flex items-start justify-between mb-8 gap-4 flex-wrap">
        <div>
          <div className="cw-eyebrow mb-2">Library</div>
          <h1 className="cw-hero" style={{ fontSize: 28 }}>Query Textbooks</h1>
          <p className="mt-2" style={{ color: 'var(--text-3)', fontSize: 12.5 }}>
            Ask questions across your uploaded sources.
          </p>
        </div>
        <Link to="/rag/upload" className="cw-btn cw-btn-secondary">
          <Upload className="w-4 h-4" />
          Upload Textbooks
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-5">
        {/* Document Selection Sidebar */}
        <div className="cw-card cw-card-pad h-fit">
          <div className="cw-eyebrow mb-3">Select Sources</div>

          {loadingDocs ? (
            <Loader2 className="w-5 h-5 animate-spin" style={{ color: 'var(--text-4)' }} />
          ) : documents.length === 0 ? (
            <div>
              <p style={{ color: 'var(--text-4)', fontStyle: 'italic', fontSize: 12, marginBottom: 10 }}>
                No textbooks uploaded
              </p>
              <Link to="/rag/upload" style={{ color: 'var(--p-700)', fontSize: 12, fontWeight: 500 }} className="hover:underline">
                Upload one
              </Link>
            </div>
          ) : (
            <div className="space-y-2">
              {documents.map((doc) => {
                const selected = selectedDocs.includes(doc.chromadb_collection_id);
                return (
                  <label
                    key={doc.id}
                    className="flex items-start gap-2 cursor-pointer p-1.5 rounded"
                    style={{
                      background: selected ? 'var(--p-50)' : 'transparent',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={() => toggleDocument(doc.chromadb_collection_id)}
                      className="mt-1"
                      style={{ accentColor: 'var(--p-700)' }}
                    />
                    <span style={{ fontSize: 12, color: 'var(--text-1)', lineHeight: 1.4 }}>
                      {doc.original_filename}
                    </span>
                  </label>
                );
              })}

              {selectedDocs.length > 0 && (
                <button
                  onClick={() => setSelectedDocs([])}
                  className="mt-3 hover:underline"
                  style={{ color: 'var(--p-700)', fontSize: 11.5, fontWeight: 500 }}
                >
                  Clear selection (search all)
                </button>
              )}

              <p className="mt-3" style={{ fontSize: 11, color: 'var(--text-4)' }}>
                {selectedDocs.length === 0
                  ? 'Searching all documents'
                  : `Searching ${selectedDocs.length} document(s)`}
              </p>
            </div>
          )}
        </div>

        {/* Query & Results */}
        <div className="lg:col-span-3 space-y-5">
          {/* Query Input */}
          <div className="cw-card cw-card-pad-lg">
            <div className="cw-eyebrow mb-3">Search Query</div>

            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder="e.g., Retrieve all content about the heart and cardiovascular system"
              className="cw-textarea"
              style={{ minHeight: 90, fontSize: 13, fontFamily: 'var(--font-serif)' }}
            />

            <div className="flex items-center justify-between mt-4 flex-wrap gap-2">
              <p style={{ fontSize: 11, color: 'var(--text-4)' }}>Press Enter to search</p>
              <button
                onClick={handleQuery}
                disabled={loading || !query.trim()}
                className="cw-btn cw-btn-primary"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                {loading ? 'Searching…' : 'Search'}
              </button>
            </div>
          </div>

          {/* Results */}
          {!loading && (answer || results.length > 0) && (
            <>
              {/* AI-Generated Answer */}
              {hasAnswer && answer && (
                <div className="cw-insight">
                  <div className="flex items-start justify-between gap-3 mb-3 flex-wrap">
                    <div className="flex items-center gap-2">
                      <Bot className="w-4 h-4" />
                      <span style={{ fontFamily: 'var(--font-display)', fontSize: 14, fontWeight: 700 }}>
                        Answer
                      </span>
                    </div>
                    <span
                      className="cw-badge"
                      style={{ background: 'color-mix(in srgb, var(--s-500) 18%, transparent)', color: 'var(--s-700)' }}
                    >
                      {results.length} sources
                    </span>
                  </div>

                  <div
                    className="whitespace-pre-wrap"
                    style={{
                      color: 'var(--text-1)',
                      fontSize: 13,
                      lineHeight: 1.65,
                      fontFamily: 'var(--font-serif)',
                    }}
                  >
                    {answer}
                  </div>

                  <div
                    className="mt-4 pt-3"
                    style={{ borderTop: '1px solid color-mix(in srgb, var(--s-500) 25%, transparent)' }}
                  >
                    <p style={{ fontSize: 11, color: 'var(--text-3)', fontStyle: 'italic' }}>
                      Based on your uploaded textbooks. Expand source documents below to verify.
                    </p>
                  </div>
                </div>
              )}

              {/* No Answer Warning */}
              {!hasAnswer && results.length > 0 && (
                <div
                  className="rounded-md p-3"
                  style={{
                    background: 'var(--warn-50)',
                    border: '1px solid color-mix(in srgb, var(--warn-500) 30%, transparent)',
                  }}
                >
                  <p style={{ fontSize: 12, color: 'var(--warn-700)' }}>
                    Answer generation is disabled. Add FIREWORKS_API_KEY to your .env file to enable AI-generated answers.
                  </p>
                </div>
              )}

              {/* Export Buttons */}
              <div className="flex gap-2 flex-wrap">
                <button
                  onClick={() => exportRAGResultsPDF({
                    query,
                    answer,
                    results: results.map((r) => ({
                      ...r,
                      metadata: {
                        chunk_id: parseInt(r.metadata.chunk_id) || 0,
                        page_number: parseInt(r.metadata.page_number) || undefined,
                        word_count: parseInt(r.metadata.word_count) || 0,
                      }
                    })),
                    documentNames: selectedDocs.length > 0
                      ? selectedDocs.map((id) => documents.find((d) => d.chromadb_collection_id === id)?.original_filename || 'Unknown')
                      : documents.map((d) => d.original_filename)
                  })}
                  className="cw-btn cw-btn-sm cw-btn-secondary"
                >
                  <Download className="w-3.5 h-3.5" /> PDF
                </button>
                <button
                  onClick={() => exportRAGResultsDOCX({
                    query,
                    answer,
                    results: results.map((r) => ({
                      ...r,
                      metadata: {
                        chunk_id: parseInt(r.metadata.chunk_id) || 0,
                        page_number: parseInt(r.metadata.page_number) || undefined,
                        word_count: parseInt(r.metadata.word_count) || 0,
                      }
                    })),
                    documentNames: selectedDocs.length > 0
                      ? selectedDocs.map((id) => documents.find((d) => d.chromadb_collection_id === id)?.original_filename || 'Unknown')
                      : documents.map((d) => d.original_filename)
                  })}
                  className="cw-btn cw-btn-sm cw-btn-secondary"
                >
                  <FileText className="w-3.5 h-3.5" /> DOCX
                </button>
                <button onClick={exportResults} className="cw-btn cw-btn-sm cw-btn-ghost">
                  <Download className="w-3.5 h-3.5" /> TXT
                </button>
                <button onClick={copyAll} className="cw-btn cw-btn-sm cw-btn-ghost">
                  <Copy className="w-3.5 h-3.5" /> {copied ? 'Copied!' : 'Copy All'}
                </button>
              </div>

              {/* Source Documents (Expandable) */}
              <div className="cw-card cw-card-pad-lg">
                <div className="flex items-center gap-2 mb-4">
                  <BookOpen className="w-4 h-4" style={{ color: 'var(--p-700)' }} />
                  <h3 className="cw-section-title">Source Documents</h3>
                  <span className="cw-badge cw-badge-neutral">{results.length}</span>
                </div>
                <p className="cw-eyebrow mb-4" style={{ color: 'var(--text-4)' }}>
                  Click a source to expand the full text chunk
                </p>

                <div className="space-y-2">
                  {results.map((result, i) => {
                    const expanded = expandedSources.includes(i);
                    return (
                      <div
                        key={i}
                        className="rounded-md overflow-hidden"
                        style={{ border: '1px solid var(--border)' }}
                      >
                        <button
                          onClick={() => toggleSource(i)}
                          className="w-full px-3.5 py-2.5 flex items-center justify-between transition-colors gap-3"
                          style={{ background: expanded ? 'var(--surface-alt)' : 'var(--surface-sunk)' }}
                        >
                          <div className="flex items-center gap-2 flex-wrap min-w-0">
                            <span style={{ fontWeight: 700, color: 'var(--p-900)', fontSize: 12 }}>
                              Source {i + 1}
                            </span>
                            <span className={getSimilarityBadge(result.similarity_score)}>
                              {(result.similarity_score * 100).toFixed(1)}% match
                            </span>
                            <span style={{ fontSize: 11, color: 'var(--text-4)' }}>
                              {result.metadata.word_count} words
                            </span>
                            <span className="truncate" style={{ fontSize: 11, color: 'var(--text-3)' }}>
                              {getDocumentLabel(result)}
                            </span>
                          </div>
                          {expanded
                            ? <ChevronDown className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--text-3)' }} />
                            : <ChevronRight className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--text-3)' }} />
                          }
                        </button>

                        {expanded && (
                          <div
                            className="p-4"
                            style={{
                              background: 'var(--surface-raised)',
                              borderTop: '1px solid var(--divider)',
                            }}
                          >
                            <p
                              className="whitespace-pre-wrap"
                              style={{ fontSize: 13, color: 'var(--text-1)', lineHeight: 1.6, fontFamily: 'var(--font-serif)' }}
                            >
                              {result.text}
                            </p>
                            <div
                              className="mt-3 pt-2"
                              style={{
                                borderTop: '1px solid var(--divider)',
                                fontSize: 10.5,
                                color: 'var(--text-4)',
                                fontFamily: 'var(--font-mono)',
                                letterSpacing: '0.02em',
                              }}
                            >
                              {getDocumentLabel(result)} · Chunk {result.metadata.chunk_id} · {result.metadata.word_count} words
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          )}

          {results.length === 0 && !loading && query && (
            <div
              className="cw-card cw-card-pad-lg text-center"
              style={{ padding: '48px 24px', color: 'var(--text-4)', fontSize: 13 }}
            >
              No results yet. Enter a query and click Search.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default RAGQuery;
