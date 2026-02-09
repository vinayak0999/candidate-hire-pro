import { useState, useEffect } from 'react';
import { leaderboardApi } from '../services/api';
import { Trophy, Medal, Clock, Users, ChevronDown, Crown, Star, Zap } from 'lucide-react';
import './Leaderboard.css';

interface LeaderboardEntry {
    rank: number;
    user_id: number;
    display_name: string;
    profile_image: string | null;
    is_current_user: boolean;
    assessment_id: number;
    assessment_title: string;
    category: string | null;
    score: number;
    total_marks: number;
    percentage: number;
    time_taken_seconds: number;
    completed_at: string | null;
}

interface CurrentUserRank {
    rank: number;
    percentage: number;
    score: number;
    total_marks: number;
}

interface LeaderboardData {
    leaderboard: LeaderboardEntry[];
    total_participants: number;
    current_user_rank: CurrentUserRank | null;
}

const Leaderboard = () => {
    const [data, setData] = useState<LeaderboardData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [showAll, setShowAll] = useState(false);

    useEffect(() => {
        fetchLeaderboard();
    }, []);

    const fetchLeaderboard = async () => {
        try {
            setLoading(true);
            const response = await leaderboardApi.getLeaderboard();
            setData(response);
            setError(null);
        } catch (err) {
            setError('Failed to load leaderboard');
            console.error('Leaderboard error:', err);
        } finally {
            setLoading(false);
        }
    };

    const formatTime = (seconds: number | null | undefined): string => {
        if (!seconds || seconds <= 0) return '-';
        const hrs = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;

        if (hrs > 0) {
            return `${hrs}h ${mins}m`;
        }
        return `${mins}m ${secs}s`;
    };

    // Generate fallback avatar URL (same as Dashboard/Profile)
    const getFallbackAvatar = (name: string | null | undefined): string => {
        return `https://ui-avatars.com/api/?name=${encodeURIComponent(name || 'User')}&size=128&background=1E3A8A&color=fff`;
    };

    // Get avatar URL - uses Google profile pic if available, otherwise generated
    const getAvatar = (profileImage: string | null | undefined, name: string | null | undefined): string => {
        return profileImage || getFallbackAvatar(name);
    };

    // Safe percentage display (cap at 100)
    const formatPercentage = (pct: number | null | undefined): string => {
        if (pct === null || pct === undefined) return '0';
        return Math.min(pct, 100).toFixed(1).replace(/\.0$/, '');
    };

    const getRankIcon = (rank: number) => {
        switch (rank) {
            case 1:
                return <Crown className="rank-icon gold" size={24} />;
            case 2:
                return <Medal className="rank-icon silver" size={22} />;
            case 3:
                return <Medal className="rank-icon bronze" size={22} />;
            default:
                return <span className="rank-number">{rank}</span>;
        }
    };

    const getRankClass = (rank: number): string => {
        if (rank === 1) return 'rank-gold';
        if (rank === 2) return 'rank-silver';
        if (rank === 3) return 'rank-bronze';
        return '';
    };

    if (loading) {
        return (
            <div className="leaderboard-loading">
                <div className="loading-spinner"></div>
                <p>Loading leaderboard...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="leaderboard-error">
                <Trophy size={48} className="empty-icon" />
                <p>{error}</p>
                <button onClick={fetchLeaderboard} disabled={loading}>
                    {loading ? 'Retrying...' : 'Retry'}
                </button>
            </div>
        );
    }

    if (!data || data.leaderboard.length === 0) {
        return (
            <div className="leaderboard-empty">
                <Trophy size={64} className="empty-icon" />
                <h3>No Results Yet</h3>
                <p>Complete an assessment to appear on the leaderboard!</p>
            </div>
        );
    }

    const displayedEntries = showAll ? data.leaderboard : data.leaderboard.slice(0, 10);

    return (
        <div className="leaderboard-container">
            {/* Header */}
            <div className="leaderboard-header">
                <div className="header-left">
                    <Trophy className="header-icon" size={32} />
                    <div>
                        <h2>Assessment Leaderboard</h2>
                        <p className="subtitle">
                            <Users size={16} />
                            {data.total_participants} participants
                        </p>
                    </div>
                </div>
            </div>

            {/* Current User Rank Banner (if not in top results) */}
            {data.current_user_rank && data.current_user_rank.rank > 0 && (
                <div className="your-rank-banner">
                    <Star className="banner-icon" size={20} />
                    <span className="banner-text">
                        Your Rank: <strong>#{data.current_user_rank.rank}</strong>
                        <span className="divider">•</span>
                        Score: <strong>{data.current_user_rank.score ?? 0}/{data.current_user_rank.total_marks ?? 0}</strong>
                        <span className="divider">•</span>
                        <strong>{formatPercentage(data.current_user_rank.percentage)}%</strong>
                    </span>
                </div>
            )}

            {/* Top 3 Podium - Only show if there are entries */}
            {data.leaderboard.length > 0 && (
                <div className="podium-section">
                    {data.leaderboard.slice(0, Math.min(3, data.leaderboard.length)).map((entry, idx) => (
                        <div
                            key={`podium-${entry.user_id}-${entry.assessment_id}`}
                            className={`podium-card ${getRankClass(entry.rank)} ${entry.is_current_user ? 'is-you' : ''}`}
                            style={{ order: data.leaderboard.length >= 3 ? (idx === 0 ? 1 : idx === 1 ? 0 : 2) : idx }}
                        >
                            <div className="podium-rank">{getRankIcon(entry.rank)}</div>
                            <div className="podium-avatar">
                                <img
                                    src={getAvatar(entry.profile_image, entry.display_name)}
                                    alt={entry.display_name || 'User'}
                                    className="avatar-img"
                                    onError={(e) => {
                                        (e.target as HTMLImageElement).src = getFallbackAvatar(entry.display_name);
                                    }}
                                />
                            </div>
                            <div className="podium-name">
                                {entry.display_name || 'Anonymous'}
                                {entry.is_current_user && <span className="you-badge">You</span>}
                            </div>
                            <div className="podium-score">
                                <Zap size={14} />
                                {formatPercentage(entry.percentage)}%
                            </div>
                            <div className="podium-details">
                                <span>{entry.score ?? 0}/{entry.total_marks ?? 0}</span>
                                <span className="time">
                                    <Clock size={12} />
                                    {formatTime(entry.time_taken_seconds)}
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Full Leaderboard Table */}
            <div className="leaderboard-table-container">
                <table className="leaderboard-table">
                    <thead>
                        <tr>
                            <th className="col-rank">Rank</th>
                            <th className="col-name">Candidate</th>
                            <th className="col-assessment">Assessment</th>
                            <th className="col-score">Score</th>
                            <th className="col-percentage">%</th>
                            <th className="col-time">Time</th>
                        </tr>
                    </thead>
                    <tbody>
                        {displayedEntries.map((entry) => (
                            <tr
                                key={`${entry.user_id}-${entry.assessment_id}`}
                                className={`${entry.is_current_user ? 'current-user-row' : ''} ${getRankClass(entry.rank)}`}
                            >
                                <td className="col-rank">
                                    <div className="rank-cell">{getRankIcon(entry.rank)}</div>
                                </td>
                                <td className="col-name">
                                    <div className="name-cell">
                                        <div className="avatar-small">
                                            <img
                                                src={getAvatar(entry.profile_image, entry.display_name)}
                                                alt={entry.display_name || 'User'}
                                                className="avatar-img"
                                                onError={(e) => {
                                                    (e.target as HTMLImageElement).src = getFallbackAvatar(entry.display_name);
                                                }}
                                            />
                                        </div>
                                        <span className="name-text">
                                            {entry.display_name || 'Anonymous'}
                                            {entry.is_current_user && <span className="you-tag">You</span>}
                                        </span>
                                    </div>
                                </td>
                                <td className="col-assessment">
                                    <div className="assessment-cell">
                                        <span className="assessment-title">{entry.assessment_title || 'Unknown Assessment'}</span>
                                        {entry.category && (
                                            <span className="category-tag">{entry.category}</span>
                                        )}
                                    </div>
                                </td>
                                <td className="col-score">
                                    <span className="score-value">{entry.score ?? 0}/{entry.total_marks ?? 0}</span>
                                </td>
                                <td className="col-percentage">
                                    <div className="percentage-cell">
                                        <div
                                            className="percentage-bar"
                                            style={{ width: `${Math.min(entry.percentage ?? 0, 100)}%` }}
                                        ></div>
                                        <span className="percentage-text">{formatPercentage(entry.percentage)}%</span>
                                    </div>
                                </td>
                                <td className="col-time">
                                    <span className="time-value">
                                        <Clock size={14} />
                                        {formatTime(entry.time_taken_seconds)}
                                    </span>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>

                {/* Show More Button */}
                {data.leaderboard.length > 10 && (
                    <button
                        className="show-more-btn"
                        onClick={() => setShowAll(!showAll)}
                    >
                        <ChevronDown
                            size={18}
                            className={showAll ? 'rotated' : ''}
                        />
                        {showAll ? 'Show Less' : `Show All (${data.leaderboard.length})`}
                    </button>
                )}
            </div>
        </div>
    );
};

export default Leaderboard;
