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
  };
  similarity_score: number;
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

  const getSimilarityColor = (score: number) => {
    if (score >= 0.7) return 'text-green-600 bg-green-100';
    if (score >= 0.5) return 'text-yellow-600 bg-yellow-100';
    return 'text-gray-600 bg-gray-100';
  };

  return (
    <div className="max-w-7xl mx-auto">
      {loading && <LoadingSpinner message="Searching documents..." fullScreen />}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold text-gray-800">Query Textbooks</h1>
        <Link
          to="/rag/upload"
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
        >
          <Upload className="w-4 h-4" />
          Upload Textbooks
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Document Selection Sidebar */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 h-fit">
          <h3 className="font-semibold text-gray-800 mb-4">Select Textbooks</h3>

          {loadingDocs ? (
            <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
          ) : documents.length === 0 ? (
            <div>
              <p className="text-gray-400 italic text-sm mb-3">No textbooks uploaded</p>
              <Link to="/rag/upload" className="text-sm text-primary-600 hover:underline">
                Upload one
              </Link>
            </div>
          ) : (
            <div className="space-y-2">
              {documents.map((doc) => (
                <label key={doc.id} className="flex items-start gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedDocs.includes(doc.chromadb_collection_id)}
                    onChange={() => toggleDocument(doc.chromadb_collection_id)}
                    className="mt-1"
                  />
                  <span className="text-sm text-gray-700">{doc.original_filename}</span>
                </label>
              ))}

              {selectedDocs.length > 0 && (
                <button
                  onClick={() => setSelectedDocs([])}
                  className="text-sm text-primary-600 hover:underline mt-3"
                >
                  Clear selection (search all)
                </button>
              )}

              <p className="text-xs text-gray-400 mt-3">
                {selectedDocs.length === 0
                  ? 'Searching all documents'
                  : `Searching ${selectedDocs.length} document(s)`}
              </p>
            </div>
          )}
        </div>

        {/* Query & Results */}
        <div className="lg:col-span-3">
          {/* Query Input */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
            <h3 className="font-semibold text-gray-800 mb-4">Search Query</h3>

            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder="e.g., Retrieve all content about the heart and cardiovascular system"
              className="w-full h-24 border border-gray-300 rounded-lg p-3 resize-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            />

            <div className="flex items-center justify-between mt-4">
              <p className="text-xs text-gray-400">Press Enter to search</p>
              <button
                onClick={handleQuery}
                disabled={loading || !query.trim()}
                className="flex items-center gap-2 px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Search className="w-4 h-4" />
                )}
                {loading ? 'Searching...' : 'Search'}
              </button>
            </div>
          </div>

          {/* Results */}
          {!loading && (answer || results.length > 0) && (
            <div className="space-y-6">
              {/* AI-Generated Answer */}
              {hasAnswer && answer && (
                <div className="bg-gradient-to-r from-green-50 to-emerald-50 border-2 border-green-300 rounded-xl p-6">
                  <div className="flex items-start justify-between mb-3">
                    <h3 className="text-lg font-bold text-green-800 flex items-center gap-2">
                      <Bot className="w-5 h-5" />
                      AI-Generated Answer
                    </h3>
                    <span className="text-xs bg-green-200 text-green-800 px-2 py-1 rounded-full font-medium">
                      Generated from {results.length} sources
                    </span>
                  </div>

                  <div className="text-gray-800 whitespace-pre-wrap leading-relaxed text-sm">
                    {answer}
                  </div>

                  <div className="mt-4 pt-3 border-t border-green-200">
                    <p className="text-xs text-gray-500 italic">
                      This answer was synthesized from your uploaded textbooks.
                      Click on sources below to verify information.
                    </p>
                  </div>
                </div>
              )}

              {/* No Answer Warning */}
              {!hasAnswer && results.length > 0 && (
                <div className="bg-yellow-50 border border-yellow-300 rounded-lg p-4">
                  <p className="text-sm text-yellow-800">
                    Answer generation is disabled. Add GROQ_API_KEY to your .env file to enable AI-generated answers.
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
                  className="flex items-center gap-1 px-3 py-1.5 bg-red-500 text-white rounded-lg text-sm hover:bg-red-600 transition-colors"
                >
                  <Download className="w-3.5 h-3.5" />
                  Export PDF
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
                  className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors"
                >
                  <FileText className="w-3.5 h-3.5" />
                  Export DOCX
                </button>
                <button
                  onClick={exportResults}
                  className="flex items-center gap-1 px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-sm hover:bg-gray-200 transition-colors"
                >
                  <Download className="w-3.5 h-3.5" />
                  Export TXT
                </button>
                <button
                  onClick={copyAll}
                  className="flex items-center gap-1 px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-sm hover:bg-gray-200 transition-colors"
                >
                  <Copy className="w-3.5 h-3.5" />
                  {copied ? 'Copied!' : 'Copy All'}
                </button>
              </div>

              {/* Source Documents (Expandable) */}
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
                  <BookOpen className="w-5 h-5 text-primary-600" />
                  Source Documents ({results.length})
                </h3>
                <p className="text-xs text-gray-500 mb-4">
                  Click on a source to expand the full text chunk
                </p>

                <div className="space-y-3">
                  {results.map((result, i) => (
                    <div
                      key={i}
                      className="border border-gray-200 rounded-lg overflow-hidden hover:border-primary-300 transition-colors"
                    >
                      <button
                        onClick={() => toggleSource(i)}
                        className="w-full px-4 py-3 bg-gray-50 hover:bg-gray-100 flex items-center justify-between transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <span className="font-semibold text-primary-600 text-sm">
                            Source {i + 1}
                          </span>
                          <span
                            className={`px-2 py-0.5 rounded text-xs font-medium ${getSimilarityColor(
                              result.similarity_score
                            )}`}
                          >
                            {(result.similarity_score * 100).toFixed(1)}% match
                          </span>
                          <span className="text-xs text-gray-400">
                            {result.metadata.word_count} words
                          </span>
                        </div>
                        {expandedSources.includes(i) ? (
                          <ChevronDown className="w-4 h-4 text-gray-500" />
                        ) : (
                          <ChevronRight className="w-4 h-4 text-gray-500" />
                        )}
                      </button>

                      {expandedSources.includes(i) && (
                        <div className="p-4 bg-white border-t border-gray-100">
                          <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                            {result.text}
                          </p>
                          <div className="mt-3 pt-2 border-t border-gray-100 text-xs text-gray-400">
                            Chunk ID: {result.metadata.chunk_id} | Words: {result.metadata.word_count}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {results.length === 0 && !loading && query && (
            <div className="text-center py-12 text-gray-400">
              No results yet. Enter a query and click Search.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default RAGQuery;
