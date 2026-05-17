import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Upload, Trash2, FileText, Loader2, Search, Network } from 'lucide-react';
import { ragApi } from '../../services/api';
import ConceptGraphSection from '../Analysis/ConceptGraph';
import { ConceptGraph } from '../../types';

interface RagDocument {
  id: number;
  original_filename: string;
  file_size_bytes: number;
  total_chunks: number;
  uploaded_at: string;
  concept_graph?: ConceptGraph | null;
}

const RAGUpload: React.FC = () => {
  const [documents, setDocuments] = useState<RagDocument[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState('');
  const [uploadPct, setUploadPct] = useState(0);
  const [totalChunks, setTotalChunks] = useState<number | null>(null);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [expandedGraphId, setExpandedGraphId] = useState<number | null>(null);
  const [conceptLoading, setConceptLoading] = useState(false);

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

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith('.pdf') && !file.name.endsWith('.docx')) {
      alert('Please upload PDF or DOCX files only');
      return;
    }

    setUploading(true);
    setUploadProgress('Uploading file...');
    setUploadPct(0);
    setTotalChunks(null);

    try {
      const { task_id } = await ragApi.uploadDocumentAsync(file);
      setUploadProgress('Processing document...');

      const poll = async () => {
        try {
          const status = await ragApi.uploadProgress(task_id);
          setUploadPct(Math.round((status.progress || 0) * 100));
          setUploadProgress(status.message || 'Processing...');
          if (status.total_chunks) setTotalChunks(status.total_chunks);

          if (status.status === 'complete') {
            setUploadProgress(`Done — ${status.result?.chunks_created ?? 0} chunks created`);
            setUploadPct(100);
            setTotalChunks(status.result?.chunks_created ?? null);
            fetchDocuments();
            setTimeout(() => {
              setUploadProgress('');
              setUploading(false);
              setUploadPct(0);
              setTotalChunks(null);
            }, 3000);
            return;
          }
          if (status.status === 'error') {
            setUploadProgress('Upload failed: ' + (status.error || 'Unknown error'));
            setUploading(false);
            return;
          }
          setTimeout(poll, 800);
        } catch {
          setUploadProgress('Lost connection to server');
          setUploading(false);
        }
      };
      setTimeout(poll, 1000);
    } catch (error: any) {
      console.error('Upload error:', error);
      setUploadProgress('Upload failed: ' + (error.response?.data?.error || 'Unknown error'));
      setUploading(false);
    }

    e.target.value = '';
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this textbook? This cannot be undone.')) return;

    try {
      await ragApi.deleteDocument(id);
      fetchDocuments();
    } catch (error) {
      console.error('Delete error:', error);
      alert('Failed to delete document');
    }
  };

  const handleConceptGraph = async (docId: number) => {
    if (expandedGraphId === docId) {
      setExpandedGraphId(null);
      return;
    }

    setExpandedGraphId(docId);
    const doc = documents.find((d) => d.id === docId);
    if (doc?.concept_graph) return;

    setConceptLoading(true);
    try {
      const result = await ragApi.generateConceptGraph(docId);
      setDocuments((prev) =>
        prev.map((d) => (d.id === docId ? { ...d, concept_graph: result.conceptGraph } : d))
      );
    } catch (err) {
      console.error('Failed to generate concept graph:', err);
    } finally {
      setConceptLoading(false);
    }
  };

  const handleRegenerateConceptGraph = async (docId: number) => {
    setConceptLoading(true);
    try {
      const result = await ragApi.generateConceptGraph(docId);
      setDocuments((prev) =>
        prev.map((d) => (d.id === docId ? { ...d, concept_graph: result.conceptGraph } : d))
      );
    } catch (err) {
      console.error('Failed to regenerate concept graph:', err);
    } finally {
      setConceptLoading(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
  };

  return (
    <div>
      {/* Progress is shown inline in the upload area — no fullscreen overlay */}

      <div className="flex items-start justify-between mb-8 gap-4 flex-wrap">
        <div>
          <div className="cw-eyebrow mb-2">Library</div>
          <h1 className="cw-hero" style={{ fontSize: 28 }}>Upload Textbooks</h1>
          <p className="mt-2" style={{ color: 'var(--text-3)', fontSize: 12.5 }}>
            Add PDFs or DOCX files to your RAG library for semantic search.
          </p>
        </div>
        <Link to="/rag/query" className="cw-btn cw-btn-secondary">
          <Search className="w-4 h-4" />
          Query Textbooks
        </Link>
      </div>

      {/* Upload Area */}
      <div className="cw-card cw-card-pad-lg mb-5">
        <div className="cw-eyebrow mb-3">Upload Source</div>

        <div
          className="rounded-lg p-10 text-center transition-colors"
          style={{
            border: '2px dashed var(--border-strong)',
            background: 'var(--surface-sunk)',
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--p-500)';
            (e.currentTarget as HTMLDivElement).style.background = 'color-mix(in srgb, var(--p-50) 50%, var(--surface-sunk))';
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--border-strong)';
            (e.currentTarget as HTMLDivElement).style.background = 'var(--surface-sunk)';
          }}
        >
          <input
            type="file"
            accept=".pdf,.docx"
            onChange={handleFileUpload}
            disabled={uploading}
            className="hidden"
            id="rag-file-upload"
          />
          <Upload className="w-8 h-8 mx-auto mb-4" style={{ color: 'var(--text-4)' }} />
          <label htmlFor="rag-file-upload" className="cw-btn cw-btn-primary cw-btn-lg cursor-pointer">
            {uploading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Processing…
              </>
            ) : (
              'Choose PDF or DOCX File'
            )}
          </label>

          {uploadProgress && (
            <div className="mt-4" style={{ maxWidth: 360, margin: '16px auto 0' }}>
              <div className="flex items-center justify-between mb-1.5">
                <span style={{ fontSize: 12, color: 'var(--text-2)', fontWeight: 500 }}>
                  {uploadProgress}
                </span>
                {uploading && uploadPct > 0 && (
                  <span style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>
                    {uploadPct}%
                  </span>
                )}
              </div>
              {uploading && (
                <div
                  className="rounded-full overflow-hidden"
                  style={{ height: 6, background: 'var(--surface-sunk)' }}
                >
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${uploadPct}%`,
                      background: 'var(--p-500)',
                      transition: 'width 0.4s ease',
                    }}
                  />
                </div>
              )}
              {totalChunks !== null && uploading && (
                <p style={{ fontSize: 11, color: 'var(--text-4)', marginTop: 6 }}>
                  {totalChunks} chunks
                </p>
              )}
            </div>
          )}
        </div>

        <p className="mt-4" style={{ fontSize: 12, color: 'var(--text-3)', lineHeight: 1.55 }}>
          Supports large textbooks (hundreds of pages). Processing may take a few minutes.
        </p>
      </div>

      {/* Document List */}
      <div className="cw-card cw-card-pad-lg">
        <div className="flex items-center gap-2 mb-4">
          <h2 className="cw-section-title">Uploaded Textbooks</h2>
          <span className="cw-badge cw-badge-neutral">{documents.length}</span>
        </div>

        {loadingDocs ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-5 h-5 animate-spin" style={{ color: 'var(--text-4)' }} />
          </div>
        ) : documents.length === 0 ? (
          <p
            className="text-center py-10"
            style={{ color: 'var(--text-4)', fontStyle: 'italic', fontSize: 12.5 }}
          >
            No textbooks uploaded yet. Upload a PDF or DOCX to get started.
          </p>
        ) : (
          <div className="cw-scroll-x">
            <table className="cw-table">
              <thead>
                <tr>
                  <th>Filename</th>
                  <th>Size</th>
                  <th>Chunks</th>
                  <th>Uploaded</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <React.Fragment key={doc.id}>
                  <tr>
                    <td>
                      <div className="flex items-center gap-2">
                        <FileText className="w-3.5 h-3.5" style={{ color: 'var(--text-4)' }} />
                        <span>{doc.original_filename}</span>
                      </div>
                    </td>
                    <td style={{ color: 'var(--text-3)', fontFamily: 'var(--font-mono)', fontSize: 11.5 }}>
                      {formatFileSize(doc.file_size_bytes)}
                    </td>
                    <td style={{ color: 'var(--text-3)', fontFamily: 'var(--font-mono)', fontSize: 11.5 }}>
                      {doc.total_chunks}
                    </td>
                    <td style={{ color: 'var(--text-3)' }}>
                      {new Date(doc.uploaded_at).toLocaleDateString()}
                    </td>
                    <td>
                      <div className="flex items-center gap-3">
                        <button
                          onClick={() => handleConceptGraph(doc.id)}
                          className="inline-flex items-center gap-1 transition-colors"
                          style={{
                            color: expandedGraphId === doc.id ? 'var(--p-600)' : 'var(--text-3)',
                            fontSize: 12,
                            fontWeight: 500,
                          }}
                        >
                          <Network className="w-3.5 h-3.5" />
                          Concept Map
                        </button>
                        <button
                          onClick={() => handleDelete(doc.id)}
                          className="inline-flex items-center gap-1"
                          style={{ color: 'var(--err-500)', fontSize: 12, fontWeight: 500 }}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                  {expandedGraphId === doc.id && (
                    <tr>
                      <td colSpan={5} style={{ padding: 0 }}>
                        <div className="px-4 py-4">
                          <ConceptGraphSection
                            conceptGraph={doc.concept_graph}
                            onGenerate={() => handleRegenerateConceptGraph(doc.id)}
                            loading={conceptLoading}
                          />
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default RAGUpload;
