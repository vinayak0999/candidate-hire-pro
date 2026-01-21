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
}

export function useAntiCheat(options: UseAntiCheatOptions = {}) {
    const {
        onViolation,
        maxTabSwitches = 3,
        maxFullscreenExits = 2,
        enableCopyProtection = true,
        enableFullscreenMode = true
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
    }, [onViolation, maxTabSwitches]);

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
export function useTestTimer(durationMinutes: number, onTimeUp?: () => void) {
    const [timeRemaining, setTimeRemaining] = useState(durationMinutes * 60);
    const [isRunning, setIsRunning] = useState(false);
    const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

    useEffect(() => {
        if (isRunning && timeRemaining > 0) {
            intervalRef.current = setInterval(() => {
                setTimeRemaining(prev => {
                    if (prev <= 1) {
                        setIsRunning(false);
                        onTimeUp?.();
                        return 0;
                    }
                    return prev - 1;
                });
            }, 1000);
        }

        return () => {
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
            }
        };
    }, [isRunning, timeRemaining, onTimeUp]);

    const start = useCallback(() => setIsRunning(true), []);
    const pause = useCallback(() => setIsRunning(false), []);
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
