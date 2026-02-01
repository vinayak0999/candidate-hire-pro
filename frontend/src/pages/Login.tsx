import { useState, type FormEvent } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useGoogleLogin } from '@react-oauth/google';
import { authApi, API_BASE_URL } from '../services/api';
import loginHero from '../assets/Login-1.avif';
import logoImg from '../assets/autonex_ai_cover.png';
import './Login.css';

interface LoginProps {
    onLogin: () => void;
}

export default function Login({ onLogin }: LoginProps) {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [step, setStep] = useState<'email' | 'password'>('email');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const navigate = useNavigate();

    const handleEmailSubmit = (e: FormEvent) => {
        e.preventDefault();
        if (email) {
            setStep('password');
        }
    };

    const handleLogin = async (e: FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError('');

        try {
            const response = await authApi.login({ username: email, password });
            localStorage.setItem('access_token', response.access_token);
            localStorage.setItem('user_email', email.toLowerCase().trim());

            // Check if profile is complete
            if (response.profile_complete === false) {
                onLogin();
                navigate('/complete-profile');
            } else {
                onLogin();
                navigate('/dashboard');
            }
        } catch (err: any) {
            const detail = err.response?.data?.detail || 'Invalid email or password';
            setError(detail);
        } finally {
            setLoading(false);
        }
    };

    // Google Sign-In Handler
    const handleGoogleAuth = async (accessToken: string) => {
        setLoading(true);
        setError('');

        try {
            // First get user info from Google using access token
            const userInfoResponse = await fetch('https://www.googleapis.com/oauth2/v3/userinfo', {
                headers: { Authorization: `Bearer ${accessToken}` }
            });

            if (!userInfoResponse.ok) {
                throw new Error('Failed to get user info from Google');
            }

            const userInfo = await userInfoResponse.json();

            // Send to our backend
            const response = await fetch(`${API_BASE_URL}/auth/google`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id_token: accessToken,
                    email: userInfo.email,
                    name: userInfo.name,
                    picture: userInfo.picture
                })
            });

            const data = await response.json();

            if (!response.ok) {
                setError(data.detail || 'Google sign-in failed');
                return;
            }

            // Save token and email
            localStorage.setItem('access_token', data.access_token);
            if (data.user?.email) {
                localStorage.setItem('user_email', data.user.email.toLowerCase());
            }

            // Check next step
            if (data.next_step === 'upload_resume') {
                onLogin();
                navigate('/complete-profile');
            } else {
                onLogin();
                navigate('/dashboard');
            }
        } catch (err) {
            console.error('Google auth error:', err);
            setError('Google sign-in failed. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    const googleLogin = useGoogleLogin({
        onSuccess: (tokenResponse) => handleGoogleAuth(tokenResponse.access_token),
        onError: () => setError('Google sign-in failed'),
    });

    return (
        <div className="login-page">
            <div className="login-card">
                <div className="login-hero">
                    <img src={loginHero} alt="Welcome" />
                    <div className="hero-overlay">
                        <div className="hero-content">
                            <h2 className="hero-title">Welcome to the Future</h2>
                            <p className="hero-subtitle">Your gateway to endless opportunities</p>
                        </div>
                    </div>
                </div>

                <div className="login-form-section">
                    <div className="login-logo-container">
                        <img src={logoImg} alt="Autonex" className="login-logo" />
                    </div>

                    <h1 className="login-title">Candidate Portal</h1>
                    <p className="login-subtitle">Sign in to continue your journey</p>

                    {error && (
                        <div className="login-error">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
                            </svg>
                            {error}
                        </div>
                    )}

                    {step === 'email' ? (
                        <form className="login-form" onSubmit={handleEmailSubmit}>
                            <div className="form-group">
                                <label className="form-label">Email Address</label>
                                <div className="input-wrapper">
                                    <svg className="input-icon" viewBox="0 0 24 24" fill="currentColor">
                                        <path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z" />
                                    </svg>
                                    <input
                                        type="email"
                                        className="form-input"
                                        placeholder="Enter your email"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        required
                                        autoFocus
                                    />
                                </div>
                            </div>

                            <button type="submit" className="login-btn">
                                <span>Continue</span>
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                                    <path d="M12 4l-1.41 1.41L16.17 11H4v2h12.17l-5.58 5.59L12 20l8-8z" />
                                </svg>
                            </button>

                            <div className="login-footer">
                                <span className="footer-text">New here?</span>
                                <Link to="/signup" className="footer-link">Create your account</Link>
                            </div>

                            {/* Divider */}
                            <div className="login-or-divider">
                                <span>or</span>
                            </div>

                            {/* Google Sign-In - Custom Styled Button */}
                            <button
                                type="button"
                                className="login-btn google-btn"
                                onClick={() => googleLogin()}
                                disabled={loading}
                            >
                                <svg width="20" height="20" viewBox="0 0 24 24">
                                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                                </svg>
                                <span>Sign in with Google</span>
                            </button>
                        </form>
                    ) : (
                        <form className="login-form" onSubmit={handleLogin}>
                            <div className="form-group">
                                <label className="form-label">Email Address</label>
                                <div className="input-wrapper disabled">
                                    <svg className="input-icon" viewBox="0 0 24 24" fill="currentColor">
                                        <path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z" />
                                    </svg>
                                    <input
                                        type="email"
                                        className="form-input"
                                        value={email}
                                        disabled
                                    />
                                    <button
                                        type="button"
                                        className="change-email-btn"
                                        onClick={() => setStep('email')}
                                    >
                                        Change
                                    </button>
                                </div>
                            </div>

                            <div className="form-group">
                                <div className="form-label-row">
                                    <label className="form-label">Password</label>
                                    <Link to="/forgot-password" className="forgot-link">Forgot password?</Link>
                                </div>
                                <div className="input-wrapper">
                                    <svg className="input-icon" viewBox="0 0 24 24" fill="currentColor">
                                        <path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z" />
                                    </svg>
                                    <input
                                        type="password"
                                        className="form-input"
                                        placeholder="Enter your password"
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        required
                                        autoFocus
                                    />
                                </div>
                            </div>

                            <button type="submit" className="login-btn" disabled={loading}>
                                {loading ? (
                                    <>
                                        <span className="spinner"></span>
                                        <span>Signing in...</span>
                                    </>
                                ) : (
                                    <>
                                        <span>Sign In</span>
                                        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                                            <path d="M12 4l-1.41 1.41L16.17 11H4v2h12.17l-5.58 5.59L12 20l8-8z" />
                                        </svg>
                                    </>
                                )}
                            </button>

                            {/* Divider */}
                            <div className="login-or-divider">
                                <span>or</span>
                            </div>

                            {/* Google Sign-In - Custom Styled Button */}
                            <button
                                type="button"
                                className="login-btn google-btn"
                                onClick={() => googleLogin()}
                                disabled={loading}
                            >
                                <svg width="20" height="20" viewBox="0 0 24 24">
                                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                                </svg>
                                <span>Sign in with Google</span>
                            </button>
                        </form>
                    )}

                    <div className="login-divider">
                        <span>Crafted with excellence</span>
                    </div>
                </div>
            </div>
        </div>
    );
}
