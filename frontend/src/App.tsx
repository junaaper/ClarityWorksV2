import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './utils/auth';
import Layout from './components/Layout/Layout';
import Login from './components/Auth/Login';
import Register from './components/Auth/Register';
import Dashboard from './components/Dashboard/Dashboard';
import TextInput from './components/TextInput/TextInput';
import AnalysisResults from './components/Analysis/AnalysisResults';
import History from './components/History/History';
import Profile from './components/Profile/Profile';
import AdminDashboard from './components/Admin/AdminDashboard';
import UserManagement from './components/Admin/UserManagement';
import AnalysisManagement from './components/Admin/AnalysisManagement';
import AdminRoute from './components/Admin/AdminRoute';
import SimplifyPage from './components/Simplification/SimplifyPage';
import RAGUpload from './components/RAG/RAGUpload';
import RAGQuery from './components/RAG/RAGQuery';
import ComparePage from './components/Compare/ComparePage';
import BatchPage from './components/Batch/BatchPage';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/" element={<Layout />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="analyze" element={<TextInput />} />
            <Route path="analysis/:id" element={<AnalysisResults />} />
            <Route path="simplify/:analysisId" element={<SimplifyPage />} />
            <Route path="rag/upload" element={<RAGUpload />} />
            <Route path="rag/query" element={<RAGQuery />} />
            <Route path="compare" element={<ComparePage />} />
            <Route path="batch" element={<BatchPage />} />
            <Route path="history" element={<History />} />
            <Route path="profile" element={<Profile />} />

            {/* Admin Routes */}
            <Route path="admin" element={<AdminRoute><AdminDashboard /></AdminRoute>} />
            <Route path="admin/users" element={<AdminRoute><UserManagement /></AdminRoute>} />
            <Route path="admin/analyses" element={<AdminRoute><AnalysisManagement /></AdminRoute>} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
