"use client";

import React, { useState, useEffect } from "react";
import { ArrowUp } from "lucide-react";

export function ScrollToTop() {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const toggleVisibility = () => {
      // Only show when page is scrolled down > 400px on long pages
      if (window.scrollY > 400) {
        setIsVisible(true);
      } else {
        setIsVisible(false);
      }
    };

    window.addEventListener("scroll", toggleVisibility);
    return () => window.removeEventListener("scroll", toggleVisibility);
  }, []);

  const scrollToTop = () => {
    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  if (!isVisible) return null;

  return (
    <div className="fixed bottom-6 right-5 z-40 animate-in fade-in slide-in-from-bottom-4 duration-300 print:hidden">
      <button
        onClick={scrollToTop}
        className="flex items-center gap-1.5 rounded-full bg-slate-900 px-4 py-2.5 text-xs font-bold text-white shadow-xl shadow-slate-900/20 hover:bg-teal-600 transition-all active:scale-95 border border-slate-700"
        title="Scroll smooth to top of page"
      >
        <ArrowUp className="h-4 w-4 text-teal-400" /> Top
      </button>
    </div>
  );
}
