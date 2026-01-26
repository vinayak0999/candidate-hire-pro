import { NavLink, Outlet } from 'react-router-dom';
import './AdminLayout.css';
import smallLogo from '../../assets/small-logo.jpeg';

interface AdminLayoutProps {
    onLogout: () => void;
}

// Admin Icons
const DashboardIcon = () => (
    <svg viewBox="0 0 24 24" fill="currentColor">
        <path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z" />
    </svg>
);

const TestsIcon = () => (
    <svg viewBox="0 0 24 24" fill="currentColor">
        <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z" />
    </svg>
);

const JobsIcon = () => (
    <svg viewBox="0 0 24 24" fill="currentColor">
        <path d="M20 6h-4V4c0-1.11-.89-2-2-2h-4c-1.11 0-2 .89-2 2v2H4c-1.11 0-2 .89-2 2v11c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V8c0-1.11-.89-2-2-2zm-6 0h-4V4h4v2z" />
    </svg>
);

const CandidatesIcon = () => (
    <svg viewBox="0 0 24 24" fill="currentColor">
        <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z" />
    </svg>
);

const ReportsIcon = () => (
    <svg viewBox="0 0 24 24" fill="currentColor">
        <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z" />
    </svg>
);

const LogoutIcon = () => (
    <svg viewBox="0 0 24 24" fill="currentColor">
        <path d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z" />
    </svg>
);

export default function AdminLayout({ onLogout }: AdminLayoutProps) {
    return (
        <div className="admin-layout">
            <aside className="admin-sidebar">
                <div className="admin-logo">
                    <img src={smallLogo} alt="Autonex" className="logo-image" />
                    <span className="logo-text">Admin Panel</span>
                </div>

                <nav className="admin-nav">
                    <NavLink to="/admin" end className={({ isActive }) => `admin-nav-item ${isActive ? 'active' : ''}`}>
                        <DashboardIcon />
                        <span>Dashboard</span>
                    </NavLink>

                    <NavLink to="/admin/tests" className={({ isActive }) => `admin-nav-item ${isActive ? 'active' : ''}`}>
                        <TestsIcon />
                        <span>Test Management</span>
                    </NavLink>

                    <NavLink to="/admin/jobs" className={({ isActive }) => `admin-nav-item ${isActive ? 'active' : ''}`}>
                        <JobsIcon />
                        <span>Job Management</span>
                    </NavLink>

                    <NavLink to="/admin/candidates" className={({ isActive }) => `admin-nav-item ${isActive ? 'active' : ''}`}>
                        <CandidatesIcon />
                        <span>Candidates</span>
                    </NavLink>

                    <NavLink to="/admin/reports" className={({ isActive }) => `admin-nav-item ${isActive ? 'active' : ''}`}>
                        <ReportsIcon />
                        <span>Reports</span>
                    </NavLink>

                    <NavLink to="/admin/announcements" className={({ isActive }) => `admin-nav-item ${isActive ? 'active' : ''}`}>
                        <svg viewBox="0 0 24 24" fill="currentColor">
                            <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-7 12h-2v-2h2v2zm0-4h-2V6h2v4z" />
                        </svg>
                        <span>Announcements</span>
                    </NavLink>

                    <NavLink to="/admin/divisions" className={({ isActive }) => `admin-nav-item ${isActive ? 'active' : ''}`}>
                        <svg viewBox="0 0 24 24" fill="currentColor">
                            <path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z" />
                        </svg>
                        <span>Divisions</span>
                    </NavLink>
                </nav>

                <div className="admin-sidebar-footer">
                    <button className="admin-logout-btn" onClick={onLogout}>
                        <LogoutIcon />
                        <span>Logout</span>
                    </button>
                </div>
            </aside>

            <main className="admin-main">
                <Outlet />
            </main>
        </div>
    );
}
