"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  Activity,
  FileText,
  Sliders,
  LogOut,
  Menu,
  X,
  AudioLines,
  Users,
  Settings,
  DollarSign,
} from "lucide-react";

export function Navbar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  if (!user && (pathname === "/login" || pathname === "/register")) {
    return null;
  }

  const baseNavItems = [
    { name: "Dashboard", href: "/dashboard", icon: Activity },
    { name: "Templates", href: "/templates", icon: Sliders },
    { name: "Transcripts", href: "/transcripts", icon: FileText },
  ];

  const navItems =
    user?.role === "admin"
      ? [
          ...baseNavItems,
          { name: "Team", href: "/team", icon: Users },
          { name: "LLM Costs", href: "/llm-costs", icon: DollarSign },
        ]
      : baseNavItems;

  return (
    <header className="sticky top-0 z-50 w-full border-b border-slate-200 bg-white/90 backdrop-blur-md shadow-xs">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 sm:px-6 py-3.5">
        {/* Brand Logo - Company: Scribe, Product: Teal AI */}
        <Link href="/dashboard" className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-teal-600 via-emerald-500 to-teal-400 text-white shadow-sm shadow-teal-500/20">
            <AudioLines className="h-5 w-5 text-white" />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xl font-extrabold tracking-tight text-slate-900">
              Scribe
            </span>
            <span className="rounded-full bg-teal-50 px-2.5 py-0.5 text-[10px] font-bold text-teal-700 border border-teal-200">
              Teal AI
            </span>
          </div>
        </Link>

        {/* Desktop Navigation Links */}
        <nav className="hidden md:flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100/80 p-1.5 shadow-inner">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname.startsWith(item.href);
            return (
              <Link
                key={item.name}
                href={item.href}
                className={`flex items-center gap-2 rounded-full px-4 py-1.5 text-xs font-bold transition-all duration-200 ${
                  isActive
                    ? "bg-slate-900 text-white shadow-sm"
                    : "text-slate-600 hover:text-slate-900 hover:bg-white"
                }`}
              >
                <Icon className="h-3.5 w-3.5 text-teal-500" />
                {item.name}
              </Link>
            );
          })}
        </nav>

        {/* Right Action / Profile */}
        <div className="flex items-center gap-3">
          {user && (
            <div className="hidden sm:flex items-center gap-3">
              <div className="text-right">
                <p className="text-xs font-bold text-slate-900">
                  {user.full_name || user.email}
                </p>
                <p className="text-[10px] capitalize font-mono text-teal-600 font-semibold">
                  {user.role}
                </p>
              </div>

              <Link
                href="/settings"
                title="Account Settings"
                className="flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-600 hover:border-teal-400 hover:text-teal-600 hover:bg-teal-50 transition-all shadow-xs"
              >
                <Settings className="h-4 w-4" />
              </Link>

              <button
                onClick={logout}
                title="Sign Out"
                className="flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-500 transition-colors hover:border-rose-300 hover:bg-rose-50 hover:text-rose-600 shadow-xs"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          )}

          {/* Mobile Menu Toggle Button */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-900 md:hidden shadow-xs"
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Mobile Collapsible Navigation Menu */}
      {mobileMenuOpen && (
        <div className="border-b border-slate-200 bg-white px-6 py-4 md:hidden space-y-3 shadow-md">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname.startsWith(item.href);
            return (
              <Link
                key={item.name}
                href={item.href}
                onClick={() => setMobileMenuOpen(false)}
                className={`flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-bold transition-all ${
                  isActive
                    ? "bg-slate-900 text-white"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                <Icon className="h-4 w-4 text-teal-400" />
                {item.name}
              </Link>
            );
          })}

          <Link
            href="/settings"
            onClick={() => setMobileMenuOpen(false)}
            className="flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-bold text-slate-600 hover:bg-slate-100"
          >
            <Settings className="h-4 w-4 text-teal-500" />
            Account Settings
          </Link>

          {user && (
            <div className="pt-3 border-t border-slate-200 flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-900">{user.full_name || user.email}</p>
                <p className="text-[10px] text-teal-600 capitalize font-semibold">{user.role}</p>
              </div>
              <button
                onClick={logout}
                className="flex items-center gap-2 rounded-xl bg-rose-50 border border-rose-200 px-3 py-1.5 text-xs font-bold text-rose-600"
              >
                <LogOut className="h-3.5 w-3.5" /> Sign Out
              </button>
            </div>
          )}
        </div>
      )}
    </header>
  );
}
