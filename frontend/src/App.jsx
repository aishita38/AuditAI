import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom';
import { AuthProvider, isReviewer, useAuth } from './auth/AuthContext';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import Upload from './pages/Upload';
import ClaimsTable from './pages/ClaimsTable';
import ClaimDetail from './pages/ClaimDetail';
import AuditScreens from './pages/AuditScreens';
import Login from './pages/Login';
import ReviewQueue from './pages/ReviewQueue';
import CaseDetail from './pages/CaseDetail';
import RecordDetail from './pages/RecordDetail';

function ProtectedLayout() {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="auth-loading">Checking your session…</div>;
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  return <div className="app-container"><Navbar /><Outlet /></div>;
}

function ReviewerOnly({ children }) {
  const { user } = useAuth();
  return isReviewer(user) ? children : <Navigate to="/claims" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<ProtectedLayout />}>
          <Route path="/" element={<ReviewerOnly><Dashboard /></ReviewerOnly>} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/claims" element={<ClaimsTable />} />
          <Route path="/claims/:id" element={<ClaimDetail />} />
          <Route path="/audit-screens" element={<ReviewerOnly><AuditScreens /></ReviewerOnly>} />
          <Route path="/review/cases/:caseId" element={<ReviewerOnly><CaseDetail /></ReviewerOnly>} />
          <Route path="/records/:kind/:recordId" element={<ReviewerOnly><RecordDetail /></ReviewerOnly>} />
          <Route path="/review-queue" element={<ReviewerOnly><ReviewQueue /></ReviewerOnly>} />
          <Route path="/circular-payments" element={<Navigate to="/audit-screens?tab=circular" replace />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
