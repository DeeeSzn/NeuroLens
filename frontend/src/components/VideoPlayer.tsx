"use client";

import { useCallback, useEffect, useRef } from "react";

interface VideoPlayerProps {
  /** URL to the video file served by the backend */
  src: string;
  currentTime: number;
  onTimeUpdate: (timeSec: number) => void;
}

/**
 * Content preview that stays two-way synced with the analysis: seeking the
 * native video controls moves the brain/timeline, and seeking elsewhere
 * (timeline click, insight jump) moves the video.
 */
export default function VideoPlayer({
  src,
  currentTime,
  onTimeUpdate,
}: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const isSeeking = useRef(false);

  // Sync playback position FROM external state (e.g. timeline click)
  useEffect(() => {
    const video = videoRef.current;
    if (!video || isSeeking.current) return;
    if (Math.abs(video.currentTime - currentTime) > 0.3) {
      video.currentTime = currentTime;
    }
  }, [currentTime]);

  const handleTimeUpdate = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    isSeeking.current = false;
    onTimeUpdate(video.currentTime);
  }, [onTimeUpdate]);

  const handleSeeking = useCallback(() => {
    isSeeking.current = true;
  }, []);

  const handleSeeked = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    isSeeking.current = false;
    onTimeUpdate(video.currentTime);
  }, [onTimeUpdate]);

  return (
    <div className="nl-card overflow-hidden">
      <div className="nl-card-header">
        <h3 className="text-xs font-semibold text-ink">Content preview</h3>
        <span className="text-[10px] text-dim">Synced to timeline</span>
      </div>
      <div className="p-3">
        <video
          ref={videoRef}
          src={src}
          controls
          preload="metadata"
          className="mx-auto max-h-[38vh] w-full rounded-lg bg-black object-contain"
          onTimeUpdate={handleTimeUpdate}
          onSeeking={handleSeeking}
          onSeeked={handleSeeked}
        />
      </div>
    </div>
  );
}
