import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../../services/api';
import './AdminLogin.css';
import smallLogo from '../../assets/small-logo.jpeg';

interface AdminLoginProps {
    onLogin: () => void;
}

export default function AdminLogin({ onLogin }: AdminLoginProps) {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const navigate = useNavigate();

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError('');

        try {
            // Call real authentication API
            const response = await authApi.login({ username: email, password });

            // Store the token temporarily to check role
            localStorage.setItem('access_token', response.access_token);

            // CRITICAL: Verify user is actually an admin
            const userData = await authApi.getMe();

            if (userData.role?.toUpperCase() !== 'ADMIN') {
                // NOT an admin - clear token and show error
                localStorage.removeItem('access_token');
                setError('Access denied. Admin privileges required.');
                setLoading(false);
                return;
            }

            // User is verified admin - store admin token
            localStorage.setItem('admin_token', response.access_token);

            onLogin();
            navigate('/admin');
        } catch (err: any) {
            localStorage.removeItem('access_token');
            setError(err.response?.data?.detail || 'Invalid credentials');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="admin-login-page">
            <div className="admin-login-left">
                <img src={smallLogo} alt="Autonex" className="admin-login-logo" />
                <h2>Autonex AI</h2>
                <p>Admin Portal</p>
            </div>
            <div className="admin-login-right">
                <div className="admin-login-card">
                    <div className="admin-login-header">
                        <h1>Welcome back</h1>
                        <p>Sign in to your admin account</p>
                    </div>

                    {error && (
                        <div className="admin-error">
                            <svg viewBox="0 0 24 24" fill="currentColor">
                                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
                            </svg>
                            {error}
                        </div>
                    )}

                    <form className="admin-login-form" onSubmit={handleSubmit}>
                        <div className="form-group">
                            <label>Email Address</label>
                            <input
                                type="email"
                                placeholder="admin@autonex.com"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                required
                                autoFocus
                            />
                        </div>

                        <div className="form-group">
                            <label>Password</label>
                            <input
                                type="password"
                                placeholder="Enter password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                            />
                        </div>

                        <button type="submit" className="admin-login-btn" disabled={loading}>
                            {loading ? (
                                <>
                                    <span className="spinner"></span>
                                    Signing in...
                                </>
                            ) : (
                                'Sign In'
                            )}
                        </button>
                    </form>

                    <div className="admin-login-hint">
                        <p>Demo credentials:</p>
                        <code>admin@autonex.com / admin123</code>
                    </div>
                </div>
            </div>
        </div>
    );
}
