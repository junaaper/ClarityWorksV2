import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Upload, Trash2, FileText, Loader2, Search } from 'lucide-react';
import { ragApi } from '../../services/api';
import LoadingSpinner from '../common/LoadingSpinner';

interface RagDocument {
  id: number;
  original_filename: string;
  file_size_bytes: number;
  total_chunks: number;
  uploaded_at: string;
}

const RAGUpload: React.FC = () => {
  const [documents, setDocuments] = useState<RagDocument[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState('');
  const [loadingDocs, setLoadingDocs] = useState(true);

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

    try {
      setUploadProgress('Processing and chunking document... This may take a few minutes for large files.');
      const result = await ragApi.uploadDocument(file);

      setUploadProgress(`Success! Created ${result.total_chunks} chunks`);
      fetchDocuments();

      setTimeout(() => {
        setUploadProgress('');
        setUploading(false);
      }, 3000);
    } catch (error: any) {
      console.error('Upload error:', error);
      setUploadProgress('Upload failed: ' + (error.response?.data?.error || 'Unknown error'));
      setUploading(false);
    }

    // Reset file input
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

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
  };

  return (
    <div className="max-w-5xl mx-auto">
      {uploading && <LoadingSpinner message="Uploading and processing textbook..." fullScreen />}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold text-gray-800">RAG Textbook Upload</h1>
        <Link
          to="/rag/query"
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
        >
          <Search className="w-4 h-4" />
          Query Textbooks
        </Link>
      </div>

      {/* Upload Area */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Upload Textbook</h2>

        <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-primary-400 transition-colors">
          <input
            type="file"
            accept=".pdf,.docx"
            onChange={handleFileUpload}
            disabled={uploading}
            className="hidden"
            id="rag-file-upload"
          />
          <Upload className="w-10 h-10 text-gray-400 mx-auto mb-4" />
          <label
            htmlFor="rag-file-upload"
            className={`cursor-pointer inline-block px-6 py-3 rounded-lg text-white font-medium transition-colors ${
              uploading
                ? 'bg-gray-400 cursor-not-allowed'
                : 'bg-primary-600 hover:bg-primary-700'
            }`}
          >
            {uploading ? (
              <span className="flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                Processing...
              </span>
            ) : (
              'Choose PDF or DOCX File'
            )}
          </label>

          {uploadProgress && (
            <p className="mt-4 text-sm text-gray-700">{uploadProgress}</p>
          )}
        </div>

        <p className="text-sm text-gray-500 mt-4">
          Supports large textbooks (100s-1000s of pages). Processing may take a few minutes for large files.
        </p>
      </div>

      {/* Document List */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">
          Uploaded Textbooks ({documents.length})
        </h2>

        {loadingDocs ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
          </div>
        ) : documents.length === 0 ? (
          <p className="text-gray-400 italic text-center py-8">
            No textbooks uploaded yet. Upload a PDF or DOCX to get started.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b">
                  <th className="py-3 px-4 font-medium text-gray-600">Filename</th>
                  <th className="py-3 px-4 font-medium text-gray-600">Size</th>
                  <th className="py-3 px-4 font-medium text-gray-600">Chunks</th>
                  <th className="py-3 px-4 font-medium text-gray-600">Uploaded</th>
                  <th className="py-3 px-4 font-medium text-gray-600">Actions</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr key={doc.id} className="border-b hover:bg-gray-50">
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-gray-400" />
                        {doc.original_filename}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-sm text-gray-600">
                      {formatFileSize(doc.file_size_bytes)}
                    </td>
                    <td className="py-3 px-4 text-sm text-gray-600">{doc.total_chunks}</td>
                    <td className="py-3 px-4 text-sm text-gray-600">
                      {new Date(doc.uploaded_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-4">
                      <button
                        onClick={() => handleDelete(doc.id)}
                        className="flex items-center gap-1 text-red-600 hover:text-red-800 text-sm"
                      >
                        <Trash2 className="w-4 h-4" />
                        Delete
                      </button>
                    </td>
                  </tr>
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
