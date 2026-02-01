// User types
export interface User {
    id: number;
    email: string;
    name: string;
    registration_number: string;
    degree?: string;       // Optional - may not be set yet
    branch?: string;       // Optional - may not be set yet
    batch?: string;        // Optional - may not be set yet
    college?: string;      // Optional - may not be set yet
    phone?: string;
    avatar_url?: string;
    role: 'student' | 'admin';
    neo_pat_score: number;
    solved_easy: number;
    solved_medium: number;
    solved_hard: number;
    badges_count: number;
    super_badges_count: number;
    total_badges?: number;
    total_certificates?: number;
    created_at: string;
    profile_complete?: boolean;  // True if resume has been uploaded
}

export interface LoginCredentials {
    username: string;
    password: string;
}

export interface AuthToken {
    access_token: string;
    token_type: string;
    profile_complete?: boolean;
}

// Job types
export type JobStatus = 'not_applied' | 'applied' | 'shortlisted' | 'rejected' | 'selected';
export type OfferType = 'dream_core' | 'regular' | 'super_dream';

export interface Job {
    id: number;
    company_name: string;
    company_logo?: string;
    role: string;
    location?: string;
    ctc?: number;
    job_type: string;
    offer_type: OfferType;
    round_date?: string;
    is_active: boolean;
    created_at: string;
    application_status?: JobStatus;
    test_id?: number;
}

export interface JobStats {
    total_jobs: number;
    placed: number;
    waiting: number;
    applied: number;
    rejected: number;
}

// Course types
export interface Course {
    id: number;
    title: string;
    description?: string;
    cover_image?: string;
    duration_hours: number;
    is_active: boolean;
    created_at: string;
}

export interface CourseEnrollment {
    id: number;
    course_id: number;
    progress: number;
    completed: boolean;
    enrolled_at: string;
    completed_at?: string;
    course: Course;
}

export interface CourseStats {
    courses_enrolled: number;
    completion_percentage: number;
    completed: number;
    expired: number;
}

// Assessment types
export interface Assessment {
    id: number;
    title: string;
    description?: string;
    company_name?: string;
    duration_minutes: number;
    total_questions: number;
    is_active: boolean;
    created_at: string;
}

export interface Badge {
    id: number;
    title: string;
    description?: string;
    icon_url?: string;
    is_super_badge: boolean;
    earned_at: string;
}

export interface AssessmentStats {
    tests_enrolled: number;
    tests_completed: number;
    badges: number;
    super_badges: number;
}
