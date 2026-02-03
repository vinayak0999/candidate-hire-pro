import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { jobsApi } from '../services/api';
import type { Job, JobStats } from '../types';
import './Jobs.css';



export default function Jobs() {
    const navigate = useNavigate();
    // const [activeTab, setActiveTab] = useState<TabType>('all'); // Removed unused
    const [jobs, setJobs] = useState<Job[]>([]);
    const [stats, setStats] = useState<JobStats | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadJobs();
        loadStats();
    }, []);

    const loadJobs = async () => {
        setLoading(true);
        try {
            // Always fetch 'all' if we removed the tabs, or keep logic if we might re-add.
            // Since we removed tabs in UI, force 'all' via the state init.
            const data = await jobsApi.getAll();
            setJobs(data);
        } catch (error) {
            console.error('Failed to load jobs:', error);
        } finally {
            setLoading(false);
        }
    };

    const loadStats = async () => {
        try {
            const data = await jobsApi.getStats();
            setStats(data);
        } catch (error) {
            console.error('Failed to load stats:', error);
        }
    };

    const handleApply = async (jobId: number) => {
        try {
            await jobsApi.apply(jobId);
            // Refresh jobs to update status
            await loadJobs();
            await loadStats();
        } catch (error) {
            console.error('Failed to apply:', error);
            alert('Failed to apply to job. Please try again.');
        }
    };

    const handleStartAssessment = async (jobId: number) => {
        try {
            const result = await jobsApi.startAssessment(jobId);
            if (result && result.test_id) {
                navigate(`/test/${result.test_id}`);
            }
        } catch (error) {
            console.error('Failed to start assessment:', error);
            alert('Failed to start assessment. Please ensure you have applied first.');
        }
    };

    const getOfferTypeClass = (type: string) => {
        switch (type) {
            case 'dream_core': return 'dream-core';
            case 'super_dream': return 'super-dream';
            default: return 'regular';
        }
    };

    const formatOfferType = (type: string) => {
        switch (type) {
            case 'dream_core': return 'Dream Core';
            case 'super_dream': return 'Super Dream';
            default: return 'Regular';
        }
    };

    return (
        <div className="jobs-page fade-in">
            <div className="jobs-header-section">
                <div>
                    <h1 className="jobs-title">Explore Opportunities</h1>
                    <p className="jobs-subtitle">Find your dream role</p>
                </div>
            </div>

            <div className="jobs-layout">
                {/* Main List */}
                <div className="jobs-main">
                    <div className="jobs-toolbar glass-panel">
                        <div className="search-wrapper">
                            <span className="search-icon">🔍</span>
                            <input type="text" placeholder="Search opportunities..." className="job-search-input" />
                        </div>
                        <div className="filter-actions">
                            <select className="jobs-sort">
                                <option>Latest First</option>
                                <option>Highest CTC</option>
                            </select>
                            <button className="btn-filter">Filters</button>
                        </div>
                    </div>

                    {loading ? (
                        <div className="loading-state">Loading opportunities...</div>
                    ) : jobs.length === 0 ? (
                        <div className="empty-state glass-panel">
                            <div className="empty-icon">📂</div>
                            <h3>No opportunities found</h3>
                            <p>Try adjusting your search filters</p>
                        </div>
                    ) : (
                        <div className="jobs-grid">
                            {jobs.map(job => (
                                <div key={job.id} className="job-card glass-panel">
                                    <div className="job-card-top">
                                        <div className="company-logo-box">
                                            {job.company_name.charAt(0)}
                                        </div>
                                        <div className="job-header-info">
                                            <h3 className="job-role">{job.role}</h3>
                                            <p className="job-company">{job.company_name}</p>
                                        </div>
                                        <span className={`status-badge ${job.application_status === 'applied' ? 'applied' : 'new'}`}>
                                            {job.application_status === 'applied' ? 'Applied' : 'New'}
                                        </span>
                                    </div>

                                    <div className="job-tags-row">
                                        <span className="j-tag location">
                                            📍 {job.location || 'Bangalore'}
                                        </span>
                                        <span className="j-tag type">
                                            💼 {job.job_type}
                                        </span>
                                    </div>

                                    <div className="job-card-footer">
                                        <div className="ctc-info">
                                            <span className="label">Package</span>
                                            <span className="value">₹{job.ctc} LPA</span>
                                        </div>
                                        <span className={`offer-badge ${getOfferTypeClass(job.offer_type)}`}>
                                            {formatOfferType(job.offer_type)}
                                        </span>
                                    </div>

                                    <div className="job-actions">
                                        {job.application_status === 'applied' || job.application_status === 'shortlisted' ? (
                                            job.test_id ? (
                                                job.test_completed ? (
                                                    <button className="btn-completed" disabled>
                                                        ✓ Completed
                                                    </button>
                                                ) : (
                                                    <button
                                                        className="btn-start-test"
                                                        onClick={() => handleStartAssessment(job.id)}
                                                    >
                                                        Start Assessment
                                                    </button>
                                                )
                                            ) : (
                                                <button className="btn-view-job" disabled>Applied</button>
                                            )
                                        ) : (
                                            <button
                                                className="btn-apply-job"
                                                onClick={() => handleApply(job.id)}
                                            >
                                                Apply Now
                                            </button>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Sidebar (Summary) */}
                <div className="jobs-sidebar">
                    <div className="sidebar-widget glass-panel">
                        <h3 className="widget-title">Summary</h3>

                        <div className="tracker-item">
                            <div className="tracker-icon total">📊</div>
                            <div className="tracker-info">
                                <span className="t-label">No. of Opportunities</span>
                                <span className="t-value">{stats?.total_jobs || jobs.length || 0}</span>
                            </div>
                        </div>

                        <div className="tracker-item">
                            <div className="tracker-icon applied">✅</div>
                            <div className="tracker-info">
                                <span className="t-label">Applied</span>
                                <span className="t-value">{stats?.applied || 0}</span>
                            </div>
                        </div>

                        <div className="tracker-item">
                            <div className="tracker-icon waiting">⏳</div>
                            <div className="tracker-info">
                                <span className="t-label">In progress</span>
                                <span className="t-value">{stats?.waiting || 0}</span>
                            </div>
                        </div>

                        <div className="tracker-item">
                            <div className="tracker-icon rejected">❌</div>
                            <div className="tracker-info">
                                <span className="t-label">Rejected</span>
                                <span className="t-value error">{stats?.rejected || 0}</span>
                            </div>
                        </div>

                        <div className="tracker-item activity-section">
                            <div className="tracker-info">
                                <span className="t-label">Recent Activity</span>
                                <span className="t-value">No recent activity</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
