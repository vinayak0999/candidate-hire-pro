import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { authApi } from './services/api';
import type { User } from './types';

// Candidate Components
import Layout from './components/Layout/Layout';
import Login from './pages/Login';
import Signup from './pages/Signup';
import VerifyEmail from './pages/VerifyEmail';
import ForgotPassword from './pages/ForgotPassword';
import ResetPassword from './pages/ResetPassword';
import ProfileWizard from './pages/ProfileWizard';
import Dashboard from './pages/Dashboard';
import Jobs from './pages/Jobs';
import Courses from './pages/Courses';
import Assessments from './pages/Assessments';
import Profile from './pages/Profile';
import Notifications from './pages/Notifications';

// Test Components
import TestTaking from './pages/test/TestTaking';
import TestResult from './pages/test/TestResult';
import InPageBrowserDemo from './pages/InPageBrowserDemo';

// Admin Components
import AdminLayout from './components/AdminLayout/AdminLayout';
import AdminLogin from './pages/admin/AdminLogin';
import AdminDashboard from './pages/admin/AdminDashboard';
import TestManagement from './pages/admin/TestManagement';
import JobManagement from './pages/admin/JobManagement';
import CandidatesPage from './pages/admin/CandidatesPage';
import ReportsPage from './pages/admin/ReportsPage';
import AdminAnnouncements from './pages/admin/AdminAnnouncements';
import DivisionManagement from './pages/admin/DivisionManagement';
import AdminResults from './pages/admin/AdminResults';


import './index.css';

function App() {
    const [user, setUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [isAdminAuthenticated, setIsAdminAuthenticated] = useState(false);
    const [profileComplete, setProfileComplete] = useState(false);

    useEffect(() => {
        checkAuth();
    }, []);

    const checkAuth = async () => {
        const token = localStorage.getItem('access_token');
        if (token) {
            try {
                const userData = await authApi.getMe();
                setUser(userData);
                setIsAuthenticated(true);

                // Check if profile is complete (resume uploaded)
                // Admin users bypass this check
                if (userData.role?.toUpperCase() === 'ADMIN') {
                    setProfileComplete(true);
                } else {
                    setProfileComplete(userData.profile_complete === true);
                }

                // Also check if this user should have admin access
                const adminToken = localStorage.getItem('admin_token');
                if (adminToken) {
                    // Verify user is actually an admin
                    if (userData.role?.toUpperCase() === 'ADMIN') {
                        setIsAdminAuthenticated(true);
                    } else {
                        // Not an admin - revoke admin token
                        localStorage.removeItem('admin_token');
                        setIsAdminAuthenticated(false);
                    }
                }
            } catch {
                localStorage.removeItem('access_token');
                localStorage.removeItem('admin_token');
                setIsAuthenticated(false);
                setIsAdminAuthenticated(false);
                setProfileComplete(false);
            }
        } else {
            // No access token, clear admin token too
            localStorage.removeItem('admin_token');
            setIsAdminAuthenticated(false);
            setProfileComplete(false);
        }

        setLoading(false);
    };

    const handleLogin = () => {
        checkAuth();
    };

    const handleLogout = () => {
        localStorage.removeItem('access_token');
        setUser(null);
        setIsAuthenticated(false);
    };

    const handleAdminLogin = () => {
        setIsAdminAuthenticated(true);
    };

    const handleAdminLogout = () => {
        localStorage.removeItem('admin_token');
        setIsAdminAuthenticated(false);
    };

    if (loading) {
        return (
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100vh',
                background: 'var(--color-bg-primary)'
            }}>
                <div className="spinner" style={{
                    width: 32,
                    height: 32,
                    border: '3px solid #e5e5e5',
                    borderTopColor: 'var(--color-primary)',
                    borderRadius: '50%',
                    animation: 'spin 0.8s linear infinite'
                }} />
            </div>
        );
    }

    return (
        <BrowserRouter>
            <Routes>
                {/* Public Routes */}
                <Route
                    path="/"
                    element={
                        isAuthenticated
                            ? (profileComplete ? <Navigate to="/dashboard" /> : <Navigate to="/complete-profile" />)
                            : <Login onLogin={handleLogin} />
                    }
                />
                <Route
                    path="/signup"
                    element={isAuthenticated ? <Navigate to="/dashboard" /> : <Signup />}
                />
                <Route
                    path="/verify-email"
                    element={isAuthenticated ? <Navigate to="/dashboard" /> : <VerifyEmail />}
                />
                <Route
                    path="/forgot-password"
                    element={isAuthenticated ? <Navigate to="/dashboard" /> : <ForgotPassword />}
                />
                <Route
                    path="/reset-password"
                    element={isAuthenticated ? <Navigate to="/dashboard" /> : <ResetPassword />}
                />
                <Route
                    path="/complete-profile"
                    element={
                        isAuthenticated
                            ? (profileComplete ? <Navigate to="/dashboard" /> : <ProfileWizard onComplete={() => { setProfileComplete(true); }} />)
                            : <Navigate to="/" />
                    }
                />

                {/* Protected Candidate Routes - Requires profile completion (resume upload) */}
                {isAuthenticated && profileComplete ? (
                    <Route element={<Layout user={user} onLogout={handleLogout} />}>
                        <Route path="/dashboard" element={<Dashboard user={user} />} />
                        <Route path="/opportunities" element={<Jobs />} />
                        <Route path="/courses" element={<Courses />} />
                        <Route path="/assessments" element={<Assessments />} />
                        <Route path="/company-tests" element={<Assessments />} />
                        <Route path="/profile" element={<Profile user={user} />} />
                        <Route path="/ide" element={<div className="dashboard"><h1>Open IDE</h1><p>IDE integration coming soon...</p></div>} />
                        <Route path="/notifications" element={<Notifications />} />
                    </Route>
                ) : isAuthenticated && !profileComplete ? (
                    // Redirect to complete-profile if authenticated but profile incomplete
                    <Route element={<Navigate to="/complete-profile" replace />}>
                        <Route path="/dashboard" element={null} />
                        <Route path="/opportunities" element={null} />
                        <Route path="/courses" element={null} />
                        <Route path="/assessments" element={null} />
                        <Route path="/company-tests" element={null} />
                        <Route path="/profile" element={null} />
                        <Route path="/ide" element={null} />
                        <Route path="/notifications" element={null} />
                    </Route>
                ) : null}

                {/* Test Taking Routes - Also requires profile completion */}
                {isAuthenticated && profileComplete && (
                    <>
                        <Route path="/test/:testId" element={<TestTaking />} />
                        <Route path="/test-result/:attemptId" element={<TestResult />} />
                    </>
                )}
                {isAuthenticated && !profileComplete && (
                    <>
                        <Route path="/test/:testId" element={<Navigate to="/complete-profile" replace />} />
                        <Route path="/test-result/:attemptId" element={<Navigate to="/complete-profile" replace />} />
                    </>
                )}

                {/* Demo Route - In-Page Browser */}
                <Route path="/demo/browser" element={<InPageBrowserDemo />} />

                {/* Admin Routes */}
                <Route
                    path="/admin/login"
                    element={isAdminAuthenticated ? <Navigate to="/admin" /> : <AdminLogin onLogin={handleAdminLogin} />}
                />

                {isAdminAuthenticated ? (
                    <Route path="/admin" element={<AdminLayout onLogout={handleAdminLogout} />}>
                        <Route index element={<AdminDashboard />} />
                        <Route path="tests" element={<TestManagement />} />
                        <Route path="jobs" element={<JobManagement />} />
                        <Route path="candidates" element={<CandidatesPage />} />
                        <Route path="reports" element={<ReportsPage />} />
                        <Route path="announcements" element={<AdminAnnouncements />} />
                        <Route path="divisions" element={<DivisionManagement />} />
                        <Route path="results" element={<AdminResults />} />
                    </Route>
                ) : (
                    <Route path="/admin/*" element={<Navigate to="/admin/login" />} />
                )}

                <Route path="*" element={<Navigate to="/" />} />
            </Routes>
        </BrowserRouter>
    );
}

export default App;
