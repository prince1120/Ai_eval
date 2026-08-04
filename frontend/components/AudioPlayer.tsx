"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Play,
  Pause,
  Volume2,
  VolumeX,
  Download,
  Loader2,
  AlertCircle,
  Globe,
  Clock,
  Mic,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

interface AudioPlayerProps {
  transcriptId: string;
  detectedLanguage?: string | null;
  durationSeconds?: number | null;
}

const audioUrlCache = new Map<string, string>();

export function AudioPlayer({
  transcriptId,
  detectedLanguage,
  durationSeconds,
}: AudioPlayerProps) {
  const cachedUrl = audioUrlCache.get(transcriptId) || null;
  const [audioUrl, setAudioUrl] = useState<string | null>(cachedUrl);
  const [isLoading, setIsLoading] = useState(!cachedUrl);
  const [error, setError] = useState<string | null>(null);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(durationSeconds || 0);
  const [isMuted, setIsMuted] = useState(false);

  useEffect(() => {
    let isMounted = true;

    if (audioUrlCache.has(transcriptId)) {
      setAudioUrl(audioUrlCache.get(transcriptId)!);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    apiFetch<{ url: string }>(`/transcripts/${transcriptId}/audio`)
      .then((data) => {
        if (isMounted) {
          audioUrlCache.set(transcriptId, data.url);
          setAudioUrl(data.url);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || "No audio recording file found.");
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [transcriptId]);


  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
  };

  const handleTimeUpdate = () => {
    if (!audioRef.current) return;
    setCurrentTime(audioRef.current.currentTime);
    if (!duration && audioRef.current.duration) {
      setDuration(audioRef.current.duration);
    }
  };

  const handleLoadedMetadata = () => {
    if (!audioRef.current) return;
    if (audioRef.current.duration) {
      setDuration(audioRef.current.duration);
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!audioRef.current) return;
    const seekTime = parseFloat(e.target.value);
    audioRef.current.currentTime = seekTime;
    setCurrentTime(seekTime);
  };

  const toggleMute = () => {
    if (!audioRef.current) return;
    audioRef.current.muted = !isMuted;
    setIsMuted(!isMuted);
  };

  const formatTime = (secs: number) => {
    if (!secs || isNaN(secs)) return "00:00";
    const mins = Math.floor(secs / 60);
    const remainder = Math.floor(secs % 60);
    return `${mins.toString().padStart(2, "0")}:${remainder.toString().padStart(2, "0")}`;
  };

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-4 flex items-center justify-center gap-3 text-xs font-semibold text-slate-500 shadow-2xs print:hidden">
        <Loader2 className="h-4 w-4 animate-spin text-teal-600" />
        Fetching call audio stream from storage...
      </div>
    );
  }

  if (error || !audioUrl) {
    return null; // Gracefully hide player if no audio recording attached
  }

  return (
    <div className="rounded-2xl border border-teal-200 bg-gradient-to-r from-teal-50/80 via-indigo-50/40 to-slate-50 p-4 shadow-sm print:hidden">
      <audio
        ref={audioRef}
        src={audioUrl}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => setIsPlaying(false)}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
      />

      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
        {/* Play/Pause & Audio Label */}
        <div className="flex items-center gap-3">
          <button
            onClick={togglePlay}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-teal-600 text-white shadow-md hover:bg-teal-700 transition-all hover:scale-105 active:scale-95"
            title={isPlaying ? "Pause audio" : "Play call recording"}
          >
            {isPlaying ? (
              <Pause className="h-5 w-5 fill-current" />
            ) : (
              <Play className="h-5 w-5 fill-current ml-0.5" />
            )}
          </button>

          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-bold text-slate-900 flex items-center gap-1">
                <Mic className="h-3.5 w-3.5 text-teal-600" /> Call Audio Recording
              </span>

              {detectedLanguage &&
                detectedLanguage
                  .split(",")
                  .map((lang) => lang.trim())
                  .filter(Boolean)
                  .map((lang, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center gap-1 rounded-md bg-teal-100/80 border border-teal-200 px-2 py-0.5 text-[10px] font-bold text-teal-800 capitalize"
                    >
                      <Globe className="h-3 w-3 text-teal-600" /> {lang}
                    </span>
                  ))}
            </div>
            <p className="text-[10px] text-slate-500 font-mono mt-0.5">
              {formatTime(currentTime)} / {formatTime(duration)}
            </p>
          </div>
        </div>

        {/* Scrubber Progress Bar */}
        <div className="flex-1 flex items-center gap-3">
          <span className="text-[10px] font-mono font-bold text-slate-500 shrink-0">
            {formatTime(currentTime)}
          </span>
          <input
            type="range"
            min={0}
            max={duration || 100}
            step={0.1}
            value={currentTime}
            onChange={handleSeek}
            className="w-full h-2 rounded-lg bg-slate-200 accent-teal-600 cursor-pointer"
          />
          <span className="text-[10px] font-mono font-bold text-slate-500 shrink-0">
            {formatTime(duration)}
          </span>
        </div>

        {/* Volume & Download controls */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={toggleMute}
            className="p-2 rounded-xl text-slate-600 hover:bg-slate-200/60 transition-colors"
            title={isMuted ? "Unmute" : "Mute"}
          >
            {isMuted ? (
              <VolumeX className="h-4 w-4 text-rose-500" />
            ) : (
              <Volume2 className="h-4 w-4 text-slate-700" />
            )}
          </button>
          <a
            href={audioUrl}
            download="call_recording.mp3"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-700 hover:border-teal-400 hover:text-teal-700 transition-all shadow-2xs"
            title="Download original audio file"
          >
            <Download className="h-3.5 w-3.5" /> Audio
          </a>
        </div>
      </div>
    </div>
  );
}
