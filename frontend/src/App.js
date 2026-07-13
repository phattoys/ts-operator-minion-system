import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Layout from './components/Layout';
import Login from './pages/Login';
import CommandCenter from './pages/CommandCenter';
import EcoHub from './pages/EcoHub';
import WorkerQueue from './pages/WorkerQueue';
import Dashboard from './pages/Dashboard';
import PageQueue from './pages/PageQueue';
import PageWorkspace from './pages/PageWorkspace';
import Settings from './pages/Settings';
import ExemplarLibrary from './pages/ExemplarLibrary';
import HouseTemplates from './pages/HouseTemplates';
import StyleProfiles from './pages/StyleProfiles';
import PromotionQueue from './pages/PromotionQueue';
import SpecLibrary from './pages/SpecLibrary';
import SpecWorkspace from './pages/SpecWorkspace';
import BulkQueue from './pages/BulkQueue';
import LeadMagnetLibrary from './pages/LeadMagnetLibrary';
import LeadMagnetWorkspace from './pages/LeadMagnetWorkspace';
import IntakeDashboard from './pages/IntakeDashboard';
import IntakeSession from './pages/IntakeSession';
import OperatorDashboard from './pages/OperatorDashboard';
import CommsWorkspace from './pages/CommsWorkspace';
import CatalogDashboard from './pages/CatalogDashboard';
import CatalogItemEditor from './pages/CatalogItemEditor';
import DuplicateReview from './pages/DuplicateReview';
import WpPlacementWorkspace from './pages/WpPlacementWorkspace';
import FieldListingDashboard from './pages/FieldListingDashboard';
import FieldListingBatch from './pages/FieldListingBatch';
import ExecutionSpine from './pages/ExecutionSpine';
import './App.css';

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-[#09090B] flex items-center justify-center">
        <div className="text-zinc-500 text-sm animate-pulse">Loading...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Layout>{children}</Layout>;
}

function PublicRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-[#09090B] flex items-center justify-center">
        <div className="text-zinc-500 text-sm animate-pulse">Loading...</div>
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return children;
}

function AppRoutes() {
  return (
    <Routes>
      <Route 
        path="/login" 
        element={
          <PublicRoute>
            <Login />
          </PublicRoute>
        } 
      />
      <Route 
        path="/" 
        element={
          <ProtectedRoute>
            <CommandCenter />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/eco" 
        element={
          <ProtectedRoute>
            <EcoHub />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/queue" 
        element={
          <ProtectedRoute>
            <WorkerQueue />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/page-queue" 
        element={
          <ProtectedRoute>
            <PageQueue />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/health" 
        element={
          <ProtectedRoute>
            <OperatorDashboard />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/comms" 
        element={
          <ProtectedRoute>
            <CommsWorkspace />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/catalog" 
        element={
          <ProtectedRoute>
            <CatalogDashboard />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/catalog/duplicates" 
        element={
          <ProtectedRoute>
            <DuplicateReview />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/catalog/:itemId" 
        element={
          <ProtectedRoute>
            <CatalogItemEditor />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/wp-placement" 
        element={
          <ProtectedRoute>
            <WpPlacementWorkspace />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/workspace/:pageId" 
        element={
          <ProtectedRoute>
            <PageWorkspace />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/exemplars" 
        element={
          <ProtectedRoute>
            <ExemplarLibrary />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/templates" 
        element={
          <ProtectedRoute>
            <HouseTemplates />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/styles" 
        element={
          <ProtectedRoute>
            <StyleProfiles />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/promotions" 
        element={
          <ProtectedRoute>
            <PromotionQueue />
          </ProtectedRoute>
        } 
      />
      <Route path="/settings" 
        element={
          <ProtectedRoute>
            <Settings />
          </ProtectedRoute>
        } 
      />
      <Route path="/specs" 
        element={
          <ProtectedRoute>
            <SpecLibrary />
          </ProtectedRoute>
        } 
      />
      <Route path="/specs/:specId" 
        element={
          <ProtectedRoute>
            <SpecWorkspace />
          </ProtectedRoute>
        } 
      />
      <Route path="/bulk" 
        element={
          <ProtectedRoute>
            <BulkQueue />
          </ProtectedRoute>
        } 
      />
      <Route path="/lead-magnets" 
        element={
          <ProtectedRoute>
            <LeadMagnetLibrary />
          </ProtectedRoute>
        } 
      />
      <Route path="/lead-magnets/:magnetId" 
        element={
          <ProtectedRoute>
            <LeadMagnetWorkspace />
          </ProtectedRoute>
        } 
      />
      <Route path="/intake" 
        element={
          <ProtectedRoute>
            <IntakeDashboard />
          </ProtectedRoute>
        } 
      />
      <Route path="/intake/:sessionId" 
        element={
          <ProtectedRoute>
            <IntakeSession />
          </ProtectedRoute>
        } 
      />
      <Route path="/field-listing" 
        element={
          <ProtectedRoute>
            <FieldListingDashboard />
          </ProtectedRoute>
        } 
      />
      <Route path="/field-listing/:batchId" 
        element={
          <ProtectedRoute>
            <FieldListingBatch />
          </ProtectedRoute>
        } 
      />
      <Route path="/spine" 
        element={
          <ProtectedRoute>
            <ExecutionSpine />
          </ProtectedRoute>
        } 
      />
      <Route path="/old-dashboard" 
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        } 
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
