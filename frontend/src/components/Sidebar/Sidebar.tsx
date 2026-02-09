import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import smallLogo from '../../assets/small-logo.jpeg';
import './Sidebar.css';

// SVG Icons
const DashboardIcon = () => (
    <svg viewBox="0 0 24 24" fill="currentColor">
        <path d="M4 4h4v4H4V4zm6 0h4v4h-4V4zm6 0h4v4h-4V4zM4 10h4v4H4v-4zm6 0h4v4h-4v-4zm6 0h4v4h-4v-4zM4 16h4v4H4v-4zm6 0h4v4h-4v-4zm6 0h4v4h-4v-4z" />
    </svg>
);

const CoursesIcon = () => (
    <svg viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 3L1 9l11 6l9-4.91V17h2V9L12 3z" />
        <path d="M5 13.18v4L12 21l7-3.82v-4L12 17l-7-3.82z" />
    </svg>
);

const JobsIcon = () => (
    <svg viewBox="0 0 24 24" fill="currentColor">
        <path d="M20 6h-4V4c0-1.11-.89-2-2-2h-4c-1.11 0-2 .89-2 2v2H4c-1.11 0-2 .89-2 2v11c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V8c0-1.11-.89-2-2-2zm-6 0h-4V4h4v2z" />
    </svg>
);

const AssessmentsIcon = () => (
    <svg viewBox="0 0 24 24" fill="currentColor">
        <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z" />
    </svg>
);

const LeaderboardIcon = () => (
    <svg viewBox="0 0 24 24" fill="currentColor">
        <path d="M7.5 21H2V9h5.5v12zm7.25-18h-5.5v18h5.5V3zM22 11h-5.5v10H22V11z" />
    </svg>
);

interface SidebarProps {
    mobileOpen?: boolean;
    onMobileClose?: () => void;
}

export default function Sidebar({ mobileOpen = false, onMobileClose }: SidebarProps) {
    const [isCollapsed, setIsCollapsed] = useState(true);

    const handleNavClick = () => {
        if (window.innerWidth < 768 && onMobileClose) {
            onMobileClose();
        }
    };

    return (
        <nav
            className={`sidebar ${isCollapsed ? 'collapsed' : ''} ${mobileOpen ? 'open' : ''}`}
            onMouseEnter={() => setIsCollapsed(false)}
            onMouseLeave={() => setIsCollapsed(true)}
        >
            <div className="sidebar-header">
                <div className="sidebar-logo">
                    <img
                        src={smallLogo}
                        alt="Logo"
                        style={{ opacity: isCollapsed ? 0.8 : 1 }}
                    />
                </div>
            </div>

            <div className="sidebar-nav">
                <NavLink
                    to="/dashboard"
                    className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                    onClick={handleNavClick}
                >
                    <DashboardIcon />
                    <span className="nav-text">Dashboard</span>
                </NavLink>

                <NavLink
                    to="/opportunities"
                    className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                    onClick={handleNavClick}
                >
                    <JobsIcon />
                    <span className="nav-text">Opportunities</span>
                </NavLink>

                <NavLink
                    to="/courses"
                    className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                    onClick={handleNavClick}
                >
                    <CoursesIcon />
                    <span className="nav-text">Courses</span>
                </NavLink>

                <NavLink
                    to="/assessments"
                    className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                    onClick={handleNavClick}
                >
                    <AssessmentsIcon />
                    <span className="nav-text">Assessments</span>
                </NavLink>

                <NavLink
                    to="/leaderboard"
                    className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                    onClick={handleNavClick}
                >
                    <LeaderboardIcon />
                    <span className="nav-text">Leaderboard</span>
                </NavLink>
            </div>
        </nav>
    );
}
