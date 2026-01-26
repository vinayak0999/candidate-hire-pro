import { useState, useEffect } from 'react';
import { Plus, Edit2, Trash2, Check, X, Layers } from 'lucide-react';
import { adminApiService } from '../../services/api';
import './DivisionManagement.css';

interface Division {
    id: number;
    name: string;
    description: string | null;
    is_active: boolean;
    created_at: string;
    test_count: number;
}

export default function DivisionManagement() {
    const [divisions, setDivisions] = useState<Division[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [editingId, setEditingId] = useState<number | null>(null);
    const [formData, setFormData] = useState({ name: '', description: '' });
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    useEffect(() => {
        fetchDivisions();
    }, []);

    const fetchDivisions = async () => {
        try {
            setLoading(true);
            const data = await adminApiService.getDivisions();
            setDivisions(data);
        } catch (err) {
            console.error('Failed to fetch divisions:', err);
            setError('Failed to load divisions');
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!formData.name.trim()) {
            setError('Division name is required');
            return;
        }

        try {
            setError(null);
            if (editingId) {
                await adminApiService.updateDivision(editingId, {
                    name: formData.name,
                    description: formData.description || undefined
                });
                setSuccess('Division updated successfully');
            } else {
                await adminApiService.createDivision({
                    name: formData.name,
                    description: formData.description || undefined
                });
                setSuccess('Division created successfully');
            }
            setFormData({ name: '', description: '' });
            setShowForm(false);
            setEditingId(null);
            fetchDivisions();
            setTimeout(() => setSuccess(null), 3000);
        } catch (err) {
            console.error('Failed to save division:', err);
            setError('Failed to save division');
        }
    };

    const handleEdit = (division: Division) => {
        setEditingId(division.id);
        setFormData({
            name: division.name,
            description: division.description || ''
        });
        setShowForm(true);
    };

    const handleDelete = async (id: number, name: string) => {
        if (!confirm(`Are you sure you want to delete "${name}"? This cannot be undone.`)) return;

        try {
            await adminApiService.deleteDivision(id);
            setDivisions(prev => prev.filter(d => d.id !== id));
            setSuccess('Division deleted successfully');
            setTimeout(() => setSuccess(null), 3000);
        } catch (err: any) {
            console.error('Failed to delete division:', err);
            setError(err.response?.data?.detail || 'Failed to delete division');
        }
    };

    const handleToggleActive = async (division: Division) => {
        try {
            await adminApiService.updateDivision(division.id, {
                is_active: !division.is_active
            });
            setDivisions(prev => prev.map(d =>
                d.id === division.id ? { ...d, is_active: !d.is_active } : d
            ));
        } catch (err) {
            console.error('Failed to toggle division:', err);
        }
    };

    const cancelEdit = () => {
        setShowForm(false);
        setEditingId(null);
        setFormData({ name: '', description: '' });
    };

    return (
        <div className="division-management">
            <div className="division-header">
                <div>
                    <h1>
                        <Layers className="header-icon" />
                        Division Management
                    </h1>
                    <p className="subtitle">Create and manage test divisions/categories</p>
                </div>
                <button
                    className="add-btn"
                    onClick={() => { setShowForm(true); setEditingId(null); setFormData({ name: '', description: '' }); }}
                >
                    <Plus size={20} />
                    Add Division
                </button>
            </div>

            {error && (
                <div className="message error">
                    <span>⚠️ {error}</span>
                    <button onClick={() => setError(null)}>×</button>
                </div>
            )}

            {success && (
                <div className="message success">
                    <span>✅ {success}</span>
                </div>
            )}

            {showForm && (
                <div className="division-form-card">
                    <h3>{editingId ? 'Edit Division' : 'Create New Division'}</h3>
                    <form onSubmit={handleSubmit}>
                        <div className="form-group">
                            <label>Name *</label>
                            <input
                                type="text"
                                value={formData.name}
                                onChange={e => setFormData({ ...formData, name: e.target.value })}
                                placeholder="e.g., Data Annotation, QA Testing"
                                autoFocus
                            />
                        </div>
                        <div className="form-group">
                            <label>Description</label>
                            <textarea
                                value={formData.description}
                                onChange={e => setFormData({ ...formData, description: e.target.value })}
                                placeholder="Optional description of this division..."
                                rows={3}
                            />
                        </div>
                        <div className="form-actions">
                            <button type="button" className="cancel-btn" onClick={cancelEdit}>
                                <X size={18} />
                                Cancel
                            </button>
                            <button type="submit" className="submit-btn">
                                <Check size={18} />
                                {editingId ? 'Update' : 'Create'}
                            </button>
                        </div>
                    </form>
                </div>
            )}

            <div className="divisions-grid">
                {loading ? (
                    <div className="loading">Loading divisions...</div>
                ) : divisions.length === 0 ? (
                    <div className="empty-state">
                        <Layers size={48} className="empty-icon" />
                        <h3>No Divisions Yet</h3>
                        <p>Create your first division to organize tests</p>
                        <button
                            className="add-btn"
                            onClick={() => setShowForm(true)}
                        >
                            <Plus size={20} />
                            Create First Division
                        </button>
                    </div>
                ) : (
                    divisions.map(division => (
                        <div
                            key={division.id}
                            className={`division-card ${!division.is_active ? 'inactive' : ''}`}
                        >
                            <div className="division-info">
                                <h4>{division.name}</h4>
                                {division.description && (
                                    <p className="description">{division.description}</p>
                                )}
                                <div className="meta">
                                    <span className="test-count">
                                        📋 {division.test_count} {division.test_count === 1 ? 'test' : 'tests'}
                                    </span>
                                    <span className={`status ${division.is_active ? 'active' : 'inactive'}`}>
                                        {division.is_active ? '✓ Active' : '○ Inactive'}
                                    </span>
                                </div>
                            </div>
                            <div className="division-actions">
                                <button
                                    className="action-btn toggle"
                                    onClick={() => handleToggleActive(division)}
                                    title={division.is_active ? 'Deactivate' : 'Activate'}
                                >
                                    {division.is_active ? '🔓' : '🔒'}
                                </button>
                                <button
                                    className="action-btn edit"
                                    onClick={() => handleEdit(division)}
                                    title="Edit"
                                >
                                    <Edit2 size={16} />
                                </button>
                                <button
                                    className="action-btn delete"
                                    onClick={() => handleDelete(division.id, division.name)}
                                    title="Delete"
                                    disabled={division.test_count > 0}
                                >
                                    <Trash2 size={16} />
                                </button>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}
