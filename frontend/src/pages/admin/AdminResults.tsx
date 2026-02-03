import { useState, useEffect } from 'react';
import { adminApiService } from '../../services/api';
import { Search, Download, Eye, CheckCircle, Clock, FileText, Briefcase } from 'lucide-react';
import './AdminResults.css';

interface TestResult {
    id: number;
    user_id: number;
    user_name: string;
    user_email: string;
    test_id: number;
    test_title: string;
    job_id?: number;
    job_title?: string;
    company?: string;
    score: number;
    max_score: number;
    percentage: number;
    status: string;
    completed_at: string;
    tab_switches: number;
    file_answer?: string;
}

interface Job {
    id: number;
    role: string;
    company_name: string;
}

export default function AdminResults() {
    const [results, setResults] = useState<TestResult[]>([]);
    const [jobs, setJobs] = useState<Job[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedJob, setSelectedJob] = useState<number | null>(null);
    const [selectedResult, setSelectedResult] = useState<TestResult | null>(null);

    useEffect(() => {
        fetchJobs();
        fetchResults();
    }, []);

    const fetchJobs = async () => {
        try {
            const data = await adminApiService.getJobs();
            setJobs(data);
        } catch (error) {
            console.error('Failed to fetch jobs:', error);
        }
    };

    const fetchResults = async () => {
        try {
            const data = await adminApiService.getTestResults();
            setResults(data);
        } catch (error) {
            console.error('Failed to fetch results:', error);
        } finally {
            setLoading(false);
        }
    };

    const filteredResults = results.filter(r => {
        const matchesSearch =
            r.user_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            r.user_email.toLowerCase().includes(searchQuery.toLowerCase()) ||
            r.test_title.toLowerCase().includes(searchQuery.toLowerCase()) ||
            (r.job_title && r.job_title.toLowerCase().includes(searchQuery.toLowerCase()));

        const matchesJob = !selectedJob || r.job_id === selectedJob;

        return matchesSearch && matchesJob;
    });

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'passed': return { bg: '#dcfce7', color: '#16a34a' };
            case 'failed': return { bg: '#fee2e2', color: '#dc2626' };
            case 'pending': return { bg: '#fef3c7', color: '#d97706' };
            default: return { bg: '#f1f5f9', color: '#64748b' };
        }
    };

    const handleDownloadFile = async (resultId: number) => {
        try {
            const blob = await adminApiService.downloadAnswerFile(resultId);
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `answer_${resultId}.xlsx`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Download failed:', error);
            alert('Failed to download file');
        }
    };

    const handleExportExcel = async () => {
        try {
            const blob = await adminApiService.exportTestResultsExcel(selectedJob || undefined);
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const timestamp = new Date().toISOString().slice(0, 10);
            a.download = `test_results_${selectedJob ? `job${selectedJob}_` : ''}${timestamp}.xlsx`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Export failed:', error);
            alert('Failed to export results. Make sure there are results to export.');
        }
    };

    return (
        <div className="admin-results">
            <div className="page-header">
                <div>
                    <h1>Job Results</h1>
                    <p className="page-subtitle">View candidate submissions by job, download answers, and assign marks</p>
                </div>
                <button className="btn-export" onClick={handleExportExcel}>
                    <Download size={18} /> Export to Excel
                </button>
            </div>

            {/* Filter Bar */}
            <div className="filter-bar">
                <div className="search-bar">
                    <Search size={18} />
                    <input
                        type="text"
                        placeholder="Search by name, email, test, or job..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>

                <div className="job-filter">
                    <Briefcase size={16} />
                    <select
                        value={selectedJob || ''}
                        onChange={(e) => setSelectedJob(e.target.value ? parseInt(e.target.value) : null)}
                    >
                        <option value="">All Jobs</option>
                        {jobs.map(job => (
                            <option key={job.id} value={job.id}>
                                {job.role} - {job.company_name}
                            </option>
                        ))}
                    </select>
                </div>
            </div>

            {/* Stats */}
            <div className="results-stats">
                <div className="stat-card">
                    <span className="stat-value">{filteredResults.length}</span>
                    <span className="stat-label">Total Submissions</span>
                </div>
                <div className="stat-card">
                    <span className="stat-value green">{filteredResults.filter(r => r.status === 'passed').length}</span>
                    <span className="stat-label">Passed</span>
                </div>
                <div className="stat-card">
                    <span className="stat-value red">{filteredResults.filter(r => r.status === 'failed').length}</span>
                    <span className="stat-label">Failed</span>
                </div>
            </div>

            {/* Results Table */}
            {loading ? (
                <div className="loading-state">Loading results...</div>
            ) : filteredResults.length === 0 ? (
                <div className="empty-state">
                    <FileText size={48} />
                    <h3>No Results Found</h3>
                    <p>No test submissions match your search criteria</p>
                </div>
            ) : (
                <div className="results-table">
                    <table>
                        <thead>
                            <tr>
                                <th>Candidate</th>
                                <th>Job</th>
                                <th>Test</th>
                                <th>Score</th>
                                <th>Status</th>
                                <th>Submitted</th>
                                <th>Violations</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filteredResults.map(result => {
                                const statusStyle = getStatusColor(result.status);
                                return (
                                    <tr key={result.id}>
                                        <td>
                                            <div className="candidate-cell">
                                                <span className="candidate-name">{result.user_name}</span>
                                                <span className="candidate-email">{result.user_email}</span>
                                            </div>
                                        </td>
                                        <td>
                                            <div className="job-cell">
                                                <span className="job-title">{result.job_title || 'No Job'}</span>
                                                {result.company && <span className="job-company">{result.company}</span>}
                                            </div>
                                        </td>
                                        <td>{result.test_title}</td>
                                        <td>
                                            <span className="score-badge">
                                                {result.score}/{result.max_score} ({result.percentage.toFixed(0)}%)
                                            </span>
                                        </td>
                                        <td>
                                            <span
                                                className="status-badge"
                                                style={{ background: statusStyle.bg, color: statusStyle.color }}
                                            >
                                                {result.status === 'passed' && <CheckCircle size={12} />}
                                                {result.status === 'pending' && <Clock size={12} />}
                                                {result.status}
                                            </span>
                                        </td>
                                        <td>{new Date(result.completed_at).toLocaleDateString()}</td>
                                        <td>
                                            <span className={`violation-count ${result.tab_switches > 2 ? 'warning' : ''}`}>
                                                {result.tab_switches} switches
                                            </span>
                                        </td>
                                        <td>
                                            <div className="action-buttons">
                                                <button
                                                    className="btn-icon"
                                                    title="View Details"
                                                    onClick={() => setSelectedResult(result)}
                                                >
                                                    <Eye size={16} />
                                                </button>
                                                {result.file_answer && (
                                                    <button
                                                        className="btn-icon download"
                                                        title="Download Answer"
                                                        onClick={() => handleDownloadFile(result.id)}
                                                    >
                                                        <Download size={16} />
                                                    </button>
                                                )}
                                            </div>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Result Detail Modal */}
            {selectedResult && (
                <div className="modal-overlay" onClick={() => setSelectedResult(null)}>
                    <div className="modal" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <h2>Test Result Details</h2>
                            <button className="close-btn" onClick={() => setSelectedResult(null)}>×</button>
                        </div>
                        <div className="modal-body">
                            <div className="detail-row">
                                <span className="label">Candidate:</span>
                                <span className="value">{selectedResult.user_name}</span>
                            </div>
                            <div className="detail-row">
                                <span className="label">Email:</span>
                                <span className="value">{selectedResult.user_email}</span>
                            </div>
                            <div className="detail-row">
                                <span className="label">Test:</span>
                                <span className="value">{selectedResult.test_title}</span>
                            </div>
                            <div className="detail-row">
                                <span className="label">Score:</span>
                                <span className="value">{selectedResult.score}/{selectedResult.max_score} ({selectedResult.percentage.toFixed(1)}%)</span>
                            </div>
                            <div className="detail-row">
                                <span className="label">Tab Switches:</span>
                                <span className={`value ${selectedResult.tab_switches > 2 ? 'warning' : ''}`}>
                                    {selectedResult.tab_switches}
                                </span>
                            </div>
                        </div>
                        <div className="modal-footer">
                            {selectedResult.file_answer && (
                                <button
                                    className="btn-primary"
                                    onClick={() => handleDownloadFile(selectedResult.id)}
                                >
                                    <Download size={16} /> Download Answer File
                                </button>
                            )}
                            <button className="btn-secondary" onClick={() => setSelectedResult(null)}>
                                Close
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
