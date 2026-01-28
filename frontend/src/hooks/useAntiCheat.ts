/**
 * Anti-Cheating Hooks for Test Taking
 * Detects tab switches, fullscreen exits, copy/paste attempts
 */
import { useEffect, useCallback, useRef, useState } from 'react';

interface AntiCheatState {
    tabSwitches: number;
    fullscreenExits: number;
    copyAttempts: number;
    isFullscreen: boolean;
    isFlagged: boolean;
}

interface UseAntiCheatOptions {
    onViolation?: (type: string, count: number) => void;
    maxTabSwitches?: number;
    maxFullscreenExits?: number;
    enableCopyProtection?: boolean;
    enableFullscreenMode?: boolean;
    enableTabDetection?: boolean;
}

export function useAntiCheat(options: UseAntiCheatOptions = {}) {
    const {
        onViolation,
        maxTabSwitches = 3,
        maxFullscreenExits = 2,
        enableCopyProtection = true,
        enableFullscreenMode = true,
        enableTabDetection = true
    } = options;

    const [state, setState] = useState<AntiCheatState>({
        tabSwitches: 0,
        fullscreenExits: 0,
        copyAttempts: 0,
        isFullscreen: false,
        isFlagged: false
    });

    const stateRef = useRef(state);
    stateRef.current = state;

    // Tab visibility detection
    useEffect(() => {
        if (!enableTabDetection) return;

        const handleVisibilityChange = () => {
            if (document.hidden) {
                const newCount = stateRef.current.tabSwitches + 1;
                const isFlagged = newCount >= maxTabSwitches;

                setState(prev => ({
                    ...prev,
                    tabSwitches: newCount,
                    isFlagged: prev.isFlagged || isFlagged
                }));

                onViolation?.('tab_switch', newCount);
            }
        };

        document.addEventListener('visibilitychange', handleVisibilityChange);
        return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
    }, [onViolation, maxTabSwitches, enableTabDetection]);

    // Fullscreen detection
    useEffect(() => {
        if (!enableFullscreenMode) return;

        const handleFullscreenChange = () => {
            const isNowFullscreen = !!document.fullscreenElement;

            if (!isNowFullscreen && stateRef.current.isFullscreen) {
                // Exited fullscreen
                const newCount = stateRef.current.fullscreenExits + 1;
                const isFlagged = newCount >= maxFullscreenExits;

                setState(prev => ({
                    ...prev,
                    fullscreenExits: newCount,
                    isFullscreen: false,
                    isFlagged: prev.isFlagged || isFlagged
                }));

                onViolation?.('fullscreen_exit', newCount);
            } else {
                setState(prev => ({ ...prev, isFullscreen: isNowFullscreen }));
            }
        };

        document.addEventListener('fullscreenchange', handleFullscreenChange);
        return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
    }, [enableFullscreenMode, onViolation, maxFullscreenExits]);

    // Copy/Paste protection
    useEffect(() => {
        if (!enableCopyProtection) return;

        const handleCopy = (e: ClipboardEvent) => {
            e.preventDefault();
            const newCount = stateRef.current.copyAttempts + 1;

            setState(prev => ({
                ...prev,
                copyAttempts: newCount
            }));

            onViolation?.('copy_attempt', newCount);
        };

        const handlePaste = (e: ClipboardEvent) => {
            e.preventDefault();
            onViolation?.('paste_attempt', 1);
        };

        const handleContextMenu = (e: MouseEvent) => {
            e.preventDefault();
        };

        document.addEventListener('copy', handleCopy);
        document.addEventListener('paste', handlePaste);
        document.addEventListener('contextmenu', handleContextMenu);

        return () => {
            document.removeEventListener('copy', handleCopy);
            document.removeEventListener('paste', handlePaste);
            document.removeEventListener('contextmenu', handleContextMenu);
        };
    }, [enableCopyProtection, onViolation]);

    // DevTools Detection (10K+ Security)
    useEffect(() => {
        const devToolsThreshold = 160;
        let devToolsOpen = false;

        const detectDevTools = () => {
            const widthThreshold = window.outerWidth - window.innerWidth > devToolsThreshold;
            const heightThreshold = window.outerHeight - window.innerHeight > devToolsThreshold;

            if ((widthThreshold || heightThreshold) && !devToolsOpen) {
                devToolsOpen = true;
                onViolation?.('devtools_open', 1);
            } else if (!widthThreshold && !heightThreshold) {
                devToolsOpen = false;
            }
        };

        const interval = setInterval(detectDevTools, 1000);
        return () => clearInterval(interval);
    }, [onViolation]);

    // Keyboard Shortcut Blocking (F12, Ctrl+Shift+I, etc.)
    useEffect(() => {
        const blockShortcuts = (e: KeyboardEvent) => {
            // F12
            if (e.key === 'F12') {
                e.preventDefault();
                onViolation?.('shortcut_blocked', 1);
                return;
            }
            // Ctrl/Cmd + Shift + I (DevTools)
            if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'i') {
                e.preventDefault();
                onViolation?.('shortcut_blocked', 1);
                return;
            }
            // Ctrl/Cmd + Shift + J (Console)
            if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'j') {
                e.preventDefault();
                onViolation?.('shortcut_blocked', 1);
                return;
            }
            // Ctrl/Cmd + U (View Source)
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'u') {
                e.preventDefault();
                onViolation?.('shortcut_blocked', 1);
                return;
            }
            // Ctrl/Cmd + S (Save Page)
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
                e.preventDefault();
                return;
            }
            // Ctrl/Cmd + P (Print)
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'p') {
                e.preventDefault();
                return;
            }
        };

        document.addEventListener('keydown', blockShortcuts);
        return () => document.removeEventListener('keydown', blockShortcuts);
    }, [onViolation]);

    // Window Blur Detection (Alt+Tab, etc.)
    useEffect(() => {
        const handleBlur = () => {
            const newCount = stateRef.current.tabSwitches + 1;
            setState(prev => ({
                ...prev,
                tabSwitches: newCount,
                isFlagged: prev.isFlagged || newCount >= maxTabSwitches
            }));
            onViolation?.('window_blur', newCount);
        };

        window.addEventListener('blur', handleBlur);
        return () => window.removeEventListener('blur', handleBlur);
    }, [onViolation, maxTabSwitches]);

    // Request fullscreen
    const requestFullscreen = useCallback(async () => {
        if (!enableFullscreenMode) return;

        try {
            await document.documentElement.requestFullscreen();
            setState(prev => ({ ...prev, isFullscreen: true }));
        } catch (error) {
            console.warn('Fullscreen request denied:', error);
        }
    }, [enableFullscreenMode]);

    // Exit fullscreen
    const exitFullscreen = useCallback(async () => {
        if (document.fullscreenElement) {
            await document.exitFullscreen();
            setState(prev => ({ ...prev, isFullscreen: false }));
        }
    }, []);

    return {
        ...state,
        requestFullscreen,
        exitFullscreen
    };
}


/**
 * Timer Hook for test duration
 */
export function useTestTimer(durationMinutes: number, onTimeUp?: () => void, startTime?: string) {
    const [timeRemaining, setTimeRemaining] = useState(durationMinutes * 60);
    const [isRunning, setIsRunning] = useState(false);

    // Calculate remaining time relative to server start time
    const calculateRemaining = useCallback(() => {
        if (!startTime) return durationMinutes * 60;

        const start = new Date(startTime).getTime();
        const now = new Date().getTime();
        const elapsedSeconds = Math.floor((now - start) / 1000);
        const totalSeconds = durationMinutes * 60;

        return Math.max(0, totalSeconds - elapsedSeconds);
    }, [durationMinutes, startTime]);

    // Initialize/Sync timer
    useEffect(() => {
        setTimeRemaining(calculateRemaining());
    }, [calculateRemaining]);

    useEffect(() => {
        if (isRunning && timeRemaining > 0) {
            const interval = setInterval(() => {
                // Recalculate from start time every tick to avoid drift and handle backgrounding
                if (startTime) {
                    const remaining = calculateRemaining();
                    setTimeRemaining(remaining);
                    if (remaining <= 0) {
                        setIsRunning(false);
                        onTimeUp?.();
                    }
                } else {
                    setTimeRemaining(prev => {
                        if (prev <= 1) {
                            setIsRunning(false);
                            onTimeUp?.();
                            return 0;
                        }
                        return prev - 1;
                    });
                }
            }, 1000);
            return () => clearInterval(interval);
        }
    }, [isRunning, timeRemaining, onTimeUp, startTime, calculateRemaining]);

    const start = useCallback(() => setIsRunning(true), []);
    const pause = useCallback(() => setIsRunning(false), []);
    // Reset not really applicable for strict server exams, but keeping for compatibility
    const reset = useCallback(() => {
        setTimeRemaining(durationMinutes * 60);
        setIsRunning(false);
    }, [durationMinutes]);

    const formatTime = useCallback(() => {
        const hours = Math.floor(timeRemaining / 3600);
        const minutes = Math.floor((timeRemaining % 3600) / 60);
        const seconds = timeRemaining % 60;

        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        }
        return `${minutes}:${seconds.toString().padStart(2, '0')}`;
    }, [timeRemaining]);

    return {
        timeRemaining,
        formattedTime: formatTime(),
        isRunning,
        isTimeUp: timeRemaining === 0,
        start,
        pause,
        reset
    };
}
