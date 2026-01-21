import { useState, useEffect } from 'react';
import { adminApiService } from '../../services/api';
import { Plus, Briefcase, MapPin, Users, Check, X } from 'lucide-react';
import './JobManagement.css';

interface Job {
    id: number;
    company_name: string;
    role: string;
    location?: string;
    ctc?: number;
    job_type: string;
    is_active: boolean;
    created_at: string;
    applications: number;
}

interface Division {
    id: number;
    name: string;
    description?: string;
}

interface Assessment {
    id: number;
    title: string;
    division_id: number | null;
}

export default function JobManagement() {
    const [jobs, setJobs] = useState<Job[]>([]);
    const [showModal, setShowModal] = useState(false);
    const [divisions, setDivisions] = useState<Division[]>([]);
    const [tests, setTests] = useState<Assessment[]>([]);
    const [loading, setLoading] = useState(true);

    // Form state
    const [formData, setFormData] = useState({
        title: '',
        company: 'Autonex AI',
        location: '',
        type: 'Full Time',
        ctc: ''
    });
    const [selectedDivision, setSelectedDivision] = useState<number | null>(null);
    const [selectedAssessments, setSelectedAssessments] = useState<number[]>([]);

    // Fetch data on mount
    useEffect(() => {
        fetchJobs();
        fetchDivisions();
        fetchTests();
    }, []);

    const fetchJobs = async () => {
        try {
            const data = await adminApiService.getJobs();
            setJobs(data);
        } catch (error) {
            console.error('Failed to fetch jobs:', error);
        } finally {
            setLoading(false);
        }
    };

    const fetchDivisions = async () => {
        try {
            const data = await adminApiService.getDivisions();
            setDivisions(data);
        } catch (error) {
            console.error('Failed to fetch divisions:', error);
        }
    };

    const fetchTests = async () => {
        try {
            const data = await adminApiService.getTests({ is_published: true });
            setTests(data);
        } catch (error) {
            console.error('Failed to fetch tests:', error);
        }
    };

    // Filter tests by selected division
    const filteredAssessments = tests.filter(t => t.division_id === selectedDivision);

    const handleDivisionChange = (divisionId: number | null) => {
        setSelectedDivision(divisionId);
        setSelectedAssessments([]); // Reset assessments when division changes
    };

    const toggleAssessment = (assessmentId: number) => {
        setSelectedAssessments(prev =>
            prev.includes(assessmentId)
                ? prev.filter(id => id !== assessmentId)
                : [...prev, assessmentId]
        );
    };

    const handleCreateJob = async () => {
        if (!formData.title.trim()) {
            alert('Please enter a job title');
            return;
        }
        if (!selectedDivision) {
            alert('Please select a division');
            return;
        }
        if (selectedAssessments.length === 0) {
            alert('Please select at least one assessment');
            return;
        }

        try {
            await adminApiService.createJob({
                company_name: formData.company,
                role: formData.title,
                location: formData.location || undefined,
                ctc: formData.ctc ? parseFloat(formData.ctc) : undefined,
                job_type: formData.type
            });

            setShowModal(false);
            resetForm();
            fetchJobs();
        } catch (error: any) {
            alert(error.response?.data?.detail || 'Failed to create job');
        }
    };

    const resetForm = () => {
        setFormData({ title: '', company: 'Autonex AI', location: '', type: 'Full Time', ctc: '' });
        setSelectedDivision(null);
        setSelectedAssessments([]);
    };

    const handleDeleteJob = async (job: Job) => {
        if (!confirm(`Delete "${job.role}"?`)) return;
        try {
            await adminApiService.deleteJob(job.id);
            fetchJobs();
        } catch (error) {
            alert('Failed to delete job');
        }
    };

    // Calculate stats
    const totalApplications = jobs.reduce((sum, j) => sum + j.applications, 0);
    const activeJobs = jobs.filter(j => j.is_active).length;

    return (
        <div className="job-management">
            <div className="page-header">
                <div>
                    <h1>Job Management</h1>
                    <p className="page-subtitle">Create and manage annotation job postings</p>
                </div>
                <button className="btn-primary" onClick={() => setShowModal(true)}>
                    <Plus size={18} /> Create New Job
                </button>
            </div>

            {/* Stats Summary */}
            <div className="job-stats">
                <div className="job-stat-card">
                    <span className="stat-number">{jobs.length}</span>
                    <span className="stat-label">Total Jobs</span>
                </div>
                <div className="job-stat-card">
                    <span className="stat-number green">{activeJobs}</span>
                    <span className="stat-label">Active</span>
                </div>
                <div className="job-stat-card">
                    <span className="stat-number orange">{jobs.length - activeJobs}</span>
                    <span className="stat-label">Inactive</span>
                </div>
                <div className="job-stat-card">
                    <span className="stat-number">{totalApplications}</span>
                    <span className="stat-label">Total Applications</span>
                </div>
            </div>

            {/* Jobs Grid */}
            {loading ? (
                <div className="loading-state">Loading jobs...</div>
            ) : jobs.length === 0 ? (
                <div className="empty-state">
                    <Briefcase size={48} />
                    <h3>No Jobs Created</h3>
                    <p>Create your first job posting to start receiving applications</p>
                    <button className="btn-primary" onClick={() => setShowModal(true)}>
                        <Plus size={18} /> Create Job
                    </button>
                </div>
            ) : (
                <div className="jobs-grid">
                    {jobs.map(job => (
                        <div key={job.id} className="job-card">
                            <div className="job-card-header">
                                <div className="job-company-logo">
                                    {job.company_name.charAt(0)}
                                </div>
                                <span className={`job-status ${job.is_active ? 'active' : 'closed'}`}>
                                    {job.is_active ? 'Active' : 'Closed'}
                                </span>
                            </div>
                            <h3 className="job-title">{job.role}</h3>
                            <p className="job-company">{job.company_name}</p>
                            <span className="job-type-badge">{job.job_type}</span>

                            <div className="job-meta">
                                <span className="job-meta-item">
                                    <MapPin size={14} />
                                    {job.location || 'Remote'}
                                </span>
                                <span className="job-meta-item">
                                    <Users size={14} />
                                    {job.applications} applications
                                </span>
                            </div>

                            {job.ctc && (
                                <div className="job-ctc">₹{job.ctc} LPA</div>
                            )}

                            <div className="job-card-actions">
                                <button className="btn-outline" onClick={() => handleDeleteJob(job)}>
                                    Delete
                                </button>
                                <button className="btn-primary-sm">View Details</button>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Create Job Modal */}
            {showModal && (
                <div className="modal-overlay" onClick={() => setShowModal(false)}>
                    <div className="modal modal-large" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <h2>Create New Job</h2>
                            <button className="close-btn" onClick={() => setShowModal(false)}>
                                <X size={20} />
                            </button>
                        </div>
                        <div className="modal-body">
                            {/* Step 1: Basic Info */}
                            <div className="form-section">
                                <h3>1. Basic Details</h3>
                                <div className="form-row">
                                    <div className="form-group">
                                        <label>Job Title *</label>
                                        <input
                                            value={formData.title}
                                            onChange={e => setFormData(p => ({ ...p, title: e.target.value }))}
                                            placeholder="e.g. Data Annotator - Text"
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label>Company</label>
                                        <input
                                            value={formData.company}
                                            onChange={e => setFormData(p => ({ ...p, company: e.target.value }))}
                                        />
                                    </div>
                                </div>
                                <div className="form-row">
                                    <div className="form-group">
                                        <label>Location</label>
                                        <input
                                            value={formData.location}
                                            onChange={e => setFormData(p => ({ ...p, location: e.target.value }))}
                                            placeholder="e.g. Remote, Bangalore"
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label>Job Type</label>
                                        <select
                                            value={formData.type}
                                            onChange={e => setFormData(p => ({ ...p, type: e.target.value }))}
                                        >
                                            <option value="Full Time">Full Time</option>
                                            <option value="Part Time">Part Time</option>
                                            <option value="Contract">Contract</option>
                                            <option value="Internship">Internship</option>
                                        </select>
                                    </div>
                                </div>
                            </div>

                            {/* Step 2: Select Division */}
                            <div className="form-section">
                                <h3>2. Select Division *</h3>
                                <p className="form-hint">Choose a division to see available assessments</p>
                                <div className="division-grid">
                                    {divisions.map(div => (
                                        <button
                                            key={div.id}
                                            className={`division-card ${selectedDivision === div.id ? 'selected' : ''}`}
                                            onClick={() => handleDivisionChange(div.id)}
                                        >
                                            <span className="division-name">{div.name}</span>
                                            {selectedDivision === div.id && <Check size={18} className="check-icon" />}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Step 3: Select Assessments */}
                            {selectedDivision && (
                                <div className="form-section">
                                    <h3>3. Select Assessments *</h3>
                                    <p className="form-hint">Choose tests that candidates must complete</p>
                                    {filteredAssessments.length === 0 ? (
                                        <div className="no-assessments">
                                            No published assessments for this division. Create tests in Test Management first.
                                        </div>
                                    ) : (
                                        <div className="assessment-grid">
                                            {filteredAssessments.map(test => (
                                                <button
                                                    key={test.id}
                                                    className={`assessment-card ${selectedAssessments.includes(test.id) ? 'selected' : ''}`}
                                                    onClick={() => toggleAssessment(test.id)}
                                                >
                                                    <span className="assessment-title">{test.title}</span>
                                                    {selectedAssessments.includes(test.id) && <Check size={18} className="check-icon" />}
                                                </button>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                        <div className="modal-footer">
                            <button className="btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
                            <button className="btn-primary" onClick={handleCreateJob}>
                                Create Job
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
