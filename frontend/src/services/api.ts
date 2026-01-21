import axios from 'axios';
import type { AuthToken, LoginCredentials, User, Job, JobStats, Course, CourseEnrollment, CourseStats, Assessment, AssessmentStats, Badge } from '../types';

const API_BASE_URL = 'http://localhost:8000/api';

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// Auth API
export const authApi = {
    login: async (credentials: LoginCredentials): Promise<AuthToken> => {
        const formData = new URLSearchParams();
        formData.append('username', credentials.username);
        formData.append('password', credentials.password);

        const response = await api.post('/auth/login', formData, {
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        });
        return response.data;
    },

    register: async (data: { email: string; phone: string; password: string }): Promise<User> => {
        const response = await api.post('/auth/register', {
            email: data.email,
            phone: data.phone,
            password: data.password,
            name: data.email.split('@')[0], // Temporary name from email
            registration_number: `REG${Date.now()}` // Temporary reg number
        });
        return response.data;
    },

    getMe: async (): Promise<User> => {
        const response = await api.get('/auth/me');
        return response.data;
    },
};

// Jobs API
export const jobsApi = {
    getAll: async (): Promise<Job[]> => {
        const response = await api.get('/jobs');
        return response.data;
    },

    getMy: async (): Promise<Job[]> => {
        const response = await api.get('/jobs/my');
        return response.data;
    },

    apply: async (jobId: number): Promise<Job> => {
        const response = await api.post(`/jobs/${jobId}/apply`);
        return response.data;
    },

    getStats: async (): Promise<JobStats> => {
        const response = await api.get('/jobs/stats');
        return response.data;
    },
};

// Courses API
export const coursesApi = {
    getAll: async (): Promise<Course[]> => {
        const response = await api.get('/courses');
        return response.data;
    },

    getEnrolled: async (): Promise<CourseEnrollment[]> => {
        const response = await api.get('/courses/enrolled');
        return response.data;
    },

    getStats: async (): Promise<CourseStats> => {
        const response = await api.get('/courses/stats');
        return response.data;
    },
};

// Assessments API
export const assessmentsApi = {
    getAll: async (): Promise<Assessment[]> => {
        const response = await api.get('/assessments');
        return response.data;
    },

    getCompany: async (): Promise<Assessment[]> => {
        const response = await api.get('/assessments/company');
        return response.data;
    },

    getBadges: async (): Promise<Badge[]> => {
        const response = await api.get('/assessments/badges');
        return response.data;
    },

    getStats: async (): Promise<AssessmentStats> => {
        const response = await api.get('/assessments/stats');
        return response.data;
    },
};

// Admin API
const adminApi = axios.create({
    baseURL: 'http://localhost:8000/api/admin',
    headers: {
        'Content-Type': 'application/json',
    },
});

adminApi.interceptors.request.use((config) => {
    const token = localStorage.getItem('access_token') || localStorage.getItem('admin_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

export const adminApiService = {
    // Dashboard
    getStats: async () => {
        const response = await adminApi.get('/stats');
        return response.data;
    },

    // Divisions
    getDivisions: async () => {
        const response = await adminApi.get('/divisions');
        return response.data;
    },
    createDivision: async (data: { name: string; description?: string }) => {
        const response = await adminApi.post('/divisions', data);
        return response.data;
    },
    updateDivision: async (id: number, data: { name?: string; description?: string; is_active?: boolean }) => {
        const response = await adminApi.put(`/divisions/${id}`, data);
        return response.data;
    },
    deleteDivision: async (id: number) => {
        const response = await adminApi.delete(`/divisions/${id}`);
        return response.data;
    },

    // Questions
    getQuestions: async (filters?: { question_type?: string; difficulty?: string; division_id?: number }) => {
        const response = await adminApi.get('/questions', { params: filters });
        return response.data;
    },
    createQuestion: async (data: {
        question_type: string;
        question_text: string;
        division_id?: number;
        options?: string[];
        correct_answer?: string;
        media_url?: string;
        passage?: string;
        sentences?: string[];
        marks?: number;
        difficulty?: string;
    }) => {
        const response = await adminApi.post('/questions', data);
        return response.data;
    },
    deleteQuestion: async (questionId: number) => {
        const response = await adminApi.delete(`/questions/${questionId}`);
        return response.data;
    },

    // Tests
    getTests: async (filters?: { division_id?: number; is_published?: boolean }) => {
        const response = await adminApi.get('/tests', { params: filters });
        return response.data;
    },
    generateTest: async (data: {
        title: string;
        description?: string;
        division_id?: number;
        duration_minutes: number;
        sections?: Record<string, {
            enabled: boolean;
            marks_per_question: number;
            hard: number;
            medium: number;
            easy: number;
        }>;
        // Legacy format support
        mcq?: { enabled: boolean; count: number; marks_per_question: number };
        text_annotation?: { enabled: boolean; count: number; marks_per_question: number };
        image_annotation?: { enabled: boolean; count: number; marks_per_question: number };
        video_annotation?: { enabled: boolean; count: number; marks_per_question: number };
    }) => {
        const response = await adminApi.post('/tests/generate', data);
        return response.data;
    },
    publishTest: async (testId: number) => {
        const response = await adminApi.post(`/tests/${testId}/publish`);
        return response.data;
    },

    // Candidates
    getCandidates: async (status?: string) => {
        const response = await adminApi.get('/candidates', { params: { status } });
        return response.data;
    },
    approveCandidate: async (candidateId: number) => {
        const response = await adminApi.post(`/candidates/${candidateId}/approve`);
        return response.data;
    },
    rejectCandidate: async (candidateId: number) => {
        const response = await adminApi.post(`/candidates/${candidateId}/reject`);
        return response.data;
    },
    getCandidateProfile: async (candidateId: number) => {
        const response = await adminApi.get(`/candidates/${candidateId}/profile`);
        return response.data;
    },
    sendMessage: async (data: { recipient_id: number; subject: string; content: string; reason?: string }) => {
        const response = await adminApi.post('/messages', null, { params: data });
        return response.data;
    },

    // Test Attempts
    getAttempts: async (flaggedOnly?: boolean) => {
        const response = await adminApi.get('/attempts', { params: { flagged_only: flaggedOnly } });
        return response.data;
    },

    // File Upload
    uploadFile: async (file: File, fileType: 'video' | 'image') => {
        const formData = new FormData();
        formData.append('file', file);
        const response = await adminApi.post(`/upload?file_type=${fileType}`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });
        return response.data;
    },

    // Excel Import
    importQuestionsExcel: async (file: File) => {
        const formData = new FormData();
        formData.append('file', file);
        const response = await adminApi.post('/questions/import-excel', formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });
        return response.data;
    },

    // Jobs
    getJobs: async (includeInactive?: boolean) => {
        const response = await adminApi.get('/jobs', { params: { include_inactive: includeInactive } });
        return response.data;
    },
    createJob: async (data: {
        company_name: string;
        role: string;
        location?: string;
        ctc?: number;
        job_type?: string;
        round_date?: string;
    }) => {
        const response = await adminApi.post('/jobs', null, { params: data });
        return response.data;
    },
    updateJob: async (jobId: number, data: {
        company_name?: string;
        role?: string;
        location?: string;
        ctc?: number;
        job_type?: string;
        is_active?: boolean;
        round_date?: string;
    }) => {
        const response = await adminApi.put(`/jobs/${jobId}`, null, { params: data });
        return response.data;
    },
    deleteJob: async (jobId: number) => {
        const response = await adminApi.delete(`/jobs/${jobId}`);
        return response.data;
    },
};

export default api;
