"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, type JobStatus } from "@/lib/api";

/**
 * Poll a job until it completes or fails.
 */
export function useJobPoller(jobId: string | null) {
  const [job, setJob] = useState<JobStatus | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval>>();

  const stop = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
  }, []);

  useEffect(() => {
    if (!jobId) return;
    let active = true;

    const poll = async () => {
      try {
        const status = await api.getJobStatus(jobId);
        if (!active) return;
        setJob(status);
        if (status.status === "complete" || status.status === "failed") {
          stop();
        }
      } catch {
        // Ignore transient errors
      }
    };

    poll();
    // 5s (not 2s): long-running jobs (whisperx + inference) can take minutes,
    // and 2s produced hundreds of redundant /jobs/{id} requests per run in dev logs.
    intervalRef.current = setInterval(poll, 5000);
    return () => {
      active = false;
      stop();
    };
  }, [jobId, stop]);

  return job;
}

/**
 * Animates the displayed progress value so the bar never appears frozen.
 *
 * - When `realProgress` increases (new value polled from backend), the
 *   displayed value snaps to it immediately (CSS transition handles the
 *   visual ease-in).
 * - While `isProcessing`, the bar slowly creeps forward at ~0.15 %/s,
 *   capped at `realProgress + 6 %` so it never jumps far ahead of reality.
 * - Hard-capped at 94 % to avoid falsely showing "almost done".
 */
export function useAnimatedProgress(
  realProgress: number,
  isProcessing: boolean,
): number {
  const [displayed, setDisplayed] = useState(realProgress);
  const displayedRef = useRef(realProgress);
  const realRef = useRef(realProgress);

  // Sync upward when the backend emits a higher value
  useEffect(() => {
    realRef.current = realProgress;
    if (realProgress > displayedRef.current) {
      displayedRef.current = realProgress;
      setDisplayed(realProgress);
    }
  }, [realProgress]);

  // Slow creep while the job is running
  useEffect(() => {
    if (!isProcessing) return;
    const id = setInterval(() => {
      const softCap = Math.min(realRef.current + 0.06, 0.94);
      if (displayedRef.current < softCap) {
        const next = Math.min(displayedRef.current + 0.0015, softCap);
        displayedRef.current = next;
        setDisplayed(next);
      }
    }, 1000);
    return () => clearInterval(id);
  }, [isProcessing]);

  return displayed;
}

export function usePlaybackSync(trSeconds: number = 1.5) {
  const [currentTime, setCurrentTime] = useState(0);

  const currentTimestep = Math.floor(currentTime / trSeconds);

  const seekTo = useCallback((timeSec: number) => {
    setCurrentTime(Math.max(0, timeSec));
  }, []);

  const seekToTimestep = useCallback(
    (ts: number) => setCurrentTime(ts * trSeconds),
    [trSeconds]
  );

  return { currentTime, currentTimestep, seekTo, seekToTimestep, setCurrentTime };
}
