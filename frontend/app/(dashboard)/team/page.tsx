"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Modal } from "@/components/Modal";
import { TeamSkeleton } from "@/components/TeamSkeleton";
import { formatToUserLocalTime } from "@/lib/date-utils";
import {
  Users,
  UserPlus,
  Shield,
  Trash2,
  AlertTriangle,
  Mail,
  User as UserIcon,
  Lock,
  CheckCircle2,
  Search,
  ShieldAlert,
  Ban,
  PlayCircle,
  PauseCircle,
  UserCheck,
  Check,
} from "lucide-react";

export default function TeamPage() {
  const queryClient = useQueryClient();
  const { user: currentUser } = useAuth();

  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const [userToDelete, setUserToDelete] = useState<any | null>(null);
  const [userToStatusToggle, setUserToStatusToggle] = useState<any | null>(null);
  const [userToAssignEvaluators, setUserToAssignEvaluators] = useState<any | null>(null);
  const [selectedEvaluatorIds, setSelectedEvaluatorIds] = useState<string[]>([]);
  const [isLoadingAssignments, setIsLoadingAssignments] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [actionError, setActionError] = useState("");

  // Invite Form State
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"admin" | "evaluator" | "viewer">("evaluator");
  const [errorMsg, setErrorMsg] = useState("");

  const { data: users = [], isLoading } = useQuery<any[]>({
    queryKey: ["users"],
    queryFn: () => apiFetch("/users"),
    enabled: currentUser?.role === "admin",
  });

  const handleOpenAssignModal = async (targetUser: any) => {
    setUserToAssignEvaluators(targetUser);
    setSelectedEvaluatorIds([]);
    setIsLoadingAssignments(true);
    try {
      const res: any[] = await apiFetch(`/assignments/viewers/${targetUser.id}/evaluators`);
      if (Array.isArray(res)) {
        setSelectedEvaluatorIds(res.map((a) => a.evaluator_id));
      }
    } catch {
      setSelectedEvaluatorIds([]);
    } finally {
      setIsLoadingAssignments(false);
    }
  };

  const inviteMutation = useMutation({
    mutationFn: (data: any) =>
      apiFetch("/users/invite", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      closeInviteModal();
    },
    onError: (err: any) => {
      setErrorMsg(err.message || "Failed to invite user");
    },
  });

  const updateRoleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      apiFetch(`/users/${userId}/role`, {
        method: "PATCH",
        body: JSON.stringify({ role }),
      }),
    onSuccess: () => {
      setActionError("");
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
    onError: (err: any) => {
      setActionError(err.message || "Failed to update user role");
    },
  });

  const updateStatusMutation = useMutation({
    mutationFn: ({ userId, is_active }: { userId: string; is_active: boolean }) =>
      apiFetch(`/users/${userId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ is_active }),
      }),
    onSuccess: () => {
      setActionError("");
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setUserToStatusToggle(null);
    },
    onError: (err: any) => {
      setActionError(err.message || "Failed to update user account status");
      setUserToStatusToggle(null);
    },
  });

  const assignEvaluatorsMutation = useMutation({
    mutationFn: ({ viewerId, evaluatorIds }: { viewerId: string; evaluatorIds: string[] }) =>
      apiFetch(`/assignments/viewers/${viewerId}/evaluators`, {
        method: "POST",
        body: JSON.stringify({ evaluator_ids: evaluatorIds }),
      }),
    onSuccess: () => {
      setActionError("");
      setUserToAssignEvaluators(null);
    },
    onError: (err: any) => {
      setActionError(err.message || "Failed to update evaluator assignments");
    },
  });

  const deleteUserMutation = useMutation({
    mutationFn: (userId: string) =>
      apiFetch(`/users/${userId}`, { method: "DELETE" }),
    onSuccess: () => {
      setActionError("");
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setUserToDelete(null);
    },
    onError: (err: any) => {
      setActionError(err.message || "Failed to delete user account");
      setUserToDelete(null);
    },
  });

  const closeInviteModal = () => {
    setIsInviteModalOpen(false);
    setEmail("");
    setFullName("");
    setPassword("");
    setRole("evaluator");
    setErrorMsg("");
  };

  const allEvaluators = users.filter((u) => u.role === "evaluator" || u.role === "admin");
  const filteredUsers = users.filter(
    (u) =>
      (u.email || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      (u.full_name || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      (u.role || "").toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (currentUser?.role !== "admin") {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16 text-center">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-rose-50 border border-rose-200 text-rose-600 mb-4">
          <ShieldAlert className="h-8 w-8" />
        </div>
        <h2 className="text-2xl font-extrabold text-slate-900">Access Restricted</h2>
        <p className="mt-2 text-xs text-slate-500 max-w-md mx-auto">
          Team Member Management is restricted to System Administrators (`admin` role). Please contact your workspace administrator for access.
        </p>
      </div>
    );
  }

  const getRoleBadgeStyle = (userRole: string) => {
    switch (userRole) {
      case "admin":
        return "bg-teal-50 text-teal-700 border-teal-200";
      case "evaluator":
        return "bg-indigo-50 text-indigo-700 border-indigo-200";
      case "viewer":
      default:
        return "bg-slate-100 text-slate-700 border-slate-200";
    }
  };

  return (
    <div className="page-transition mx-auto max-w-7xl px-4 sm:px-6 py-8 space-y-8">
      {/* Header Banner */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-slate-200 pb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 flex items-center gap-3">
            <Users className="h-8 w-8 text-teal-600" /> Organization Team Management
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-slate-500">
            Invite members, assign Evaluator reports to Viewers, manage RBAC permissions, or suspend user access
          </p>
        </div>

        <button
          onClick={() => setIsInviteModalOpen(true)}
          className="flex items-center justify-center gap-2 rounded-xl bg-slate-900 px-4.5 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-slate-800 transition-all"
        >
          <UserPlus className="h-4 w-4" /> Invite Team Member
        </button>
      </div>

      {actionError && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-3.5 text-xs font-semibold text-rose-700">
          {actionError}
        </div>
      )}

      {/* Filter & Count Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-slate-700">
            Total Team Members:
          </span>
          <span className="rounded-full bg-teal-50 px-2.5 py-0.5 text-xs font-bold text-teal-700 border border-teal-200">
            {users.length}
          </span>
        </div>

        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
          <input
            type="text"
            placeholder="Search by name, email or role..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-xl border border-slate-200 bg-slate-50 pl-9 pr-3 py-1.5 text-xs text-slate-900 placeholder-slate-400 focus:border-teal-500 focus:outline-none"
          />
        </div>
      </div>

      {/* Assign Evaluators Modal */}
      <Modal isOpen={!!userToAssignEvaluators} onClose={() => setUserToAssignEvaluators(null)}>
        <div className="mx-auto max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl space-y-4">
          <div className="flex items-center gap-3 text-indigo-600 border-b border-slate-100 pb-3">
            <UserCheck className="h-6 w-6 shrink-0 text-teal-600" />
            <div>
              <h3 className="text-base font-bold text-slate-900">
                Assign Evaluators to {userToAssignEvaluators?.full_name || userToAssignEvaluators?.email}
              </h3>
              <p className="text-xs text-slate-500">
                Select which Evaluators&apos; call reports this user can view
              </p>
            </div>
          </div>

          <p className="text-xs text-slate-600 leading-relaxed">
            This user will automatically gain read-only access to all current and future call evaluations uploaded by the checked Evaluators.
          </p>

          <div className="max-h-60 overflow-y-auto space-y-2 py-2">
            {isLoadingAssignments ? (
              <p className="text-xs text-slate-500 font-bold text-center py-4">Loading assigned evaluators...</p>
            ) : allEvaluators.length === 0 ? (
              <p className="text-xs text-slate-400 italic text-center py-4">No Evaluators available in workspace</p>
            ) : (
              allEvaluators.map((evalUser) => {
                const isSelected = selectedEvaluatorIds.includes(evalUser.id);
                return (
                  <button
                    type="button"
                    key={evalUser.id}
                    onClick={() => {
                      if (isSelected) {
                        setSelectedEvaluatorIds(selectedEvaluatorIds.filter((id) => id !== evalUser.id));
                      } else {
                        setSelectedEvaluatorIds([...selectedEvaluatorIds, evalUser.id]);
                      }
                    }}
                    className={`flex items-center justify-between w-full p-3 rounded-xl border transition-all text-left ${
                      isSelected
                        ? "border-teal-500 bg-teal-50/50 text-slate-900 font-bold"
                        : "border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100"
                    }`}
                  >
                    <div>
                      <p className="text-xs font-bold text-slate-900">{evalUser.full_name || evalUser.email.split("@")[0]}</p>
                      <p className="text-[10px] text-slate-500">{evalUser.email}</p>
                    </div>
                    <div
                      className={`flex h-5 w-5 items-center justify-center rounded-lg border transition-all ${
                        isSelected ? "border-teal-600 bg-teal-600 text-white" : "border-slate-300 bg-white"
                      }`}
                    >
                      {isSelected && <Check className="h-3.5 w-3.5 stroke-[3]" />}
                    </div>
                  </button>
                );
              })
            )}
          </div>

          <div className="flex justify-end gap-3 pt-3 border-t border-slate-200">
            <button
              onClick={() => setUserToAssignEvaluators(null)}
              className="rounded-xl px-4 py-2 text-xs font-bold text-slate-600 hover:text-slate-900"
            >
              Cancel
            </button>
            <button
              disabled={assignEvaluatorsMutation.isPending}
              onClick={() =>
                assignEvaluatorsMutation.mutate({
                  viewerId: userToAssignEvaluators.id,
                  evaluatorIds: selectedEvaluatorIds,
                })
              }
              className="rounded-xl bg-teal-600 px-5 py-2 text-xs font-bold text-white hover:bg-teal-700 shadow-xs disabled:opacity-50"
            >
              {assignEvaluatorsMutation.isPending ? "Saving..." : "Save Assignments"}
            </button>
          </div>
        </div>
      </Modal>

      {/* Suspend / Reactivate Confirmation Modal */}
      <Modal isOpen={!!userToStatusToggle} onClose={() => setUserToStatusToggle(null)}>
        <div className="mx-auto max-w-md rounded-2xl border border-amber-200 bg-white p-6 shadow-2xl space-y-4">
          <div className="flex items-center gap-3 text-amber-600">
            <Ban className="h-6 w-6 shrink-0" />
            <h3 className="text-lg font-bold text-slate-900">
              {userToStatusToggle?.is_active !== false ? "Suspend User Access?" : "Reactivate User Access?"}
            </h3>
          </div>

          <p className="text-xs text-slate-600 leading-relaxed">
            {userToStatusToggle?.is_active !== false ? (
              <>
                Are you sure you want to suspend and block <strong className="text-slate-900">{userToStatusToggle?.full_name || userToStatusToggle?.email}</strong>? They will be immediately logged out and blocked from logging in.
              </>
            ) : (
              <>
                Are you sure you want to reactivate access for <strong className="text-slate-900">{userToStatusToggle?.full_name || userToStatusToggle?.email}</strong>? They will regain access to your workspace.
              </>
            )}
          </p>

          <div className="flex justify-end gap-3 pt-3 border-t border-slate-200">
            <button
              onClick={() => setUserToStatusToggle(null)}
              className="rounded-xl px-4 py-2 text-xs font-bold text-slate-600 hover:text-slate-900"
            >
              Cancel
            </button>
            <button
              disabled={updateStatusMutation.isPending}
              onClick={() =>
                updateStatusMutation.mutate({
                  userId: userToStatusToggle.id,
                  is_active: userToStatusToggle.is_active === false,
                })
              }
              className={`rounded-xl px-4 py-2 text-xs font-bold text-white shadow-xs disabled:opacity-50 ${
                userToStatusToggle?.is_active !== false
                  ? "bg-amber-600 hover:bg-amber-700"
                  : "bg-teal-600 hover:bg-teal-700"
              }`}
            >
              {updateStatusMutation.isPending
                ? "Updating..."
                : userToStatusToggle?.is_active !== false
                ? "Suspend Access"
                : "Reactivate Access"}
            </button>
          </div>
        </div>
      </Modal>

      {/* Delete User Modal using Portal */}
      <Modal isOpen={!!userToDelete} onClose={() => setUserToDelete(null)}>
        <div className="mx-auto max-w-md rounded-2xl border border-rose-200 bg-white p-6 shadow-2xl space-y-4">
          <div className="flex items-center gap-3 text-rose-600">
            <AlertTriangle className="h-6 w-6 shrink-0" />
            <h3 className="text-lg font-bold text-slate-900">Revoke & Delete User Account?</h3>
          </div>

          <p className="text-xs text-slate-600 leading-relaxed">
            Are you sure you want to delete and permanently revoke access for{" "}
            <strong className="text-slate-900">
              {userToDelete?.full_name || userToDelete?.email}
            </strong>
            ? This action cannot be undone.
          </p>

          <div className="flex justify-end gap-3 pt-3 border-t border-slate-200">
            <button
              onClick={() => setUserToDelete(null)}
              className="rounded-xl px-4 py-2 text-xs font-bold text-slate-600 hover:text-slate-900"
            >
              Cancel
            </button>
            <button
              disabled={deleteUserMutation.isPending}
              onClick={() => deleteUserMutation.mutate(userToDelete.id)}
              className="rounded-xl bg-rose-600 px-4 py-2 text-xs font-bold text-white hover:bg-rose-700 shadow-xs disabled:opacity-50"
            >
              {deleteUserMutation.isPending ? "Revoking..." : "Revoke Access"}
            </button>
          </div>
        </div>
      </Modal>

      {/* Invite Member Modal using Portal */}
      <Modal isOpen={isInviteModalOpen} onClose={closeInviteModal}>
        <div className="mx-auto w-full max-w-md rounded-3xl border border-slate-200 bg-white p-6 sm:p-8 shadow-2xl space-y-6">
          <div className="border-b border-slate-100 pb-4">
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <UserPlus className="h-5 w-5 text-teal-600" /> Invite Team Member
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Add a new member to your workspace and assign their permission role
            </p>
          </div>

          {errorMsg && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs font-semibold text-rose-700">
              {errorMsg}
            </div>
          )}

          <form
            onSubmit={(e) => {
              e.preventDefault();
              inviteMutation.mutate({
                email,
                full_name: fullName || undefined,
                password,
                role,
              });
            }}
            className="space-y-4"
          >
            <div>
              <label className="block text-xs font-bold text-slate-700">
                Full Name (Optional)
              </label>
              <div className="relative mt-1">
                <UserIcon className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="John Doe"
                  className="w-full rounded-xl border border-slate-200 bg-slate-50 pl-10 pr-3 py-2 text-xs text-slate-900 placeholder-slate-400 focus:border-teal-500 focus:outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700">
                Email Address
              </label>
              <div className="relative mt-1">
                <Mail className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="member@company.com"
                  className="w-full rounded-xl border border-slate-200 bg-slate-50 pl-10 pr-3 py-2 text-xs text-slate-900 placeholder-slate-400 focus:border-teal-500 focus:outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700">
                Initial Password
              </label>
              <div className="relative mt-1">
                <Lock className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <input
                  type="password"
                  required
                  minLength={6}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full rounded-xl border border-slate-200 bg-slate-50 pl-10 pr-3 py-2 text-xs text-slate-900 placeholder-slate-400 focus:border-teal-500 focus:outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                Assign RBAC Role
              </label>
              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => setRole("evaluator")}
                  className={`rounded-xl border p-2.5 text-center transition-all ${
                    role === "evaluator"
                      ? "border-teal-500 bg-teal-50 text-teal-900 font-bold"
                      : "border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  <p className="text-xs">Evaluator</p>
                  <p className="text-[9px] text-slate-500 font-normal mt-0.5">Upload & Score</p>
                </button>

                <button
                  type="button"
                  onClick={() => setRole("viewer")}
                  className={`rounded-xl border p-2.5 text-center transition-all ${
                    role === "viewer"
                      ? "border-teal-500 bg-teal-50 text-teal-900 font-bold"
                      : "border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  <p className="text-xs">Viewer</p>
                  <p className="text-[9px] text-slate-500 font-normal mt-0.5">Read-Only</p>
                </button>

                <button
                  type="button"
                  onClick={() => setRole("admin")}
                  className={`rounded-xl border p-2.5 text-center transition-all ${
                    role === "admin"
                      ? "border-teal-500 bg-teal-50 text-teal-900 font-bold"
                      : "border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  <p className="text-xs">Admin</p>
                  <p className="text-[9px] text-slate-500 font-normal mt-0.5">Full Access</p>
                </button>
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-3">
              <button
                type="button"
                onClick={closeInviteModal}
                className="rounded-xl px-4 py-2 text-xs font-bold text-slate-600 hover:text-slate-900"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={inviteMutation.isPending}
                className="rounded-xl bg-teal-600 px-5 py-2 text-xs font-bold text-white hover:bg-teal-700 shadow-xs disabled:opacity-50"
              >
                {inviteMutation.isPending ? "Inviting..." : "Send Invite"}
              </button>
            </div>
          </form>
        </div>
      </Modal>

      {/* Users Grid / Table */}
      {isLoading ? (
        <TeamSkeleton />
      ) : filteredUsers.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-12 text-center shadow-xs">
          <Users className="mx-auto h-12 w-12 text-slate-400" />
          <h3 className="mt-4 text-base font-bold text-slate-900">No Team Members Found</h3>
          <p className="mt-1 text-xs text-slate-500">
            Invite colleagues into your organization workspace to collaborate on call evaluations.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredUsers.map((u) => {
            const isSelf = u.id === currentUser?.id;
            const isSuspended = u.is_active === false;

            return (
              <div
                key={u.id}
                className={`flex flex-col justify-between rounded-2xl border p-6 shadow-xs transition-all ${
                  isSuspended
                    ? "border-amber-200 bg-amber-50/20"
                    : "border-slate-200 bg-white hover:border-slate-300"
                }`}
              >
                <div>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div
                        className={`flex h-10 w-10 items-center justify-center rounded-xl font-bold border ${
                          isSuspended
                            ? "bg-amber-100 text-amber-800 border-amber-200"
                            : "bg-slate-100 text-slate-700 border-slate-200"
                        }`}
                      >
                        {(u.full_name || u.email).substring(0, 2).toUpperCase()}
                      </div>

                      <div>
                        <h3 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                          {u.full_name || u.email.split("@")[0]}
                          {isSelf && (
                            <span className="text-[10px] text-teal-600 bg-teal-50 px-1.5 py-0.2 rounded font-mono font-bold">
                              You
                            </span>
                          )}
                          {isSuspended && (
                            <span className="text-[10px] text-amber-700 bg-amber-100 px-1.5 py-0.2 rounded font-mono font-bold border border-amber-200">
                              Suspended
                            </span>
                          )}
                        </h3>
                        <p className="text-xs text-slate-500 truncate max-w-[180px]">
                          {u.email}
                        </p>
                      </div>
                    </div>

                    <span
                      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-bold border capitalize ${getRoleBadgeStyle(
                        u.role
                      )}`}
                    >
                      <Shield className="h-3 w-3" />
                      {u.role}
                    </span>
                  </div>
                </div>

                <div className="mt-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-t border-slate-100 pt-4">
                  <p className="text-[10px] text-slate-400 font-medium whitespace-nowrap">
                    Joined: {formatToUserLocalTime(u.created_at)}
                  </p>

                  {!isSelf && (
                    <div className="flex items-center gap-2">
                      {u.role !== "admin" && (
                        <button
                          onClick={() => handleOpenAssignModal(u)}
                          className="flex h-7 w-7 items-center justify-center rounded-lg border border-teal-200 bg-teal-50 text-teal-700 hover:bg-teal-100 transition-all"
                          title="Assign Evaluators to View Call Reports"
                        >
                          <UserCheck className="h-3.5 w-3.5" />
                        </button>
                      )}

                      <select
                        value={u.role}
                        onChange={(e) =>
                          updateRoleMutation.mutate({
                            userId: u.id,
                            role: e.target.value,
                          })
                        }
                        className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] font-bold text-slate-700 focus:border-teal-500 focus:outline-none cursor-pointer"
                      >
                        <option value="admin">Admin</option>
                        <option value="evaluator">Evaluator</option>
                        <option value="viewer">Viewer</option>
                      </select>

                      <button
                        onClick={() => setUserToStatusToggle(u)}
                        className={`flex h-7 w-7 items-center justify-center rounded-lg border transition-all ${
                          isSuspended
                            ? "border-teal-200 bg-teal-50 text-teal-600 hover:bg-teal-100"
                            : "border-amber-200 bg-amber-50 text-amber-600 hover:bg-amber-100"
                        }`}
                        title={isSuspended ? "Reactivate Account" : "Suspend / Block Account"}
                      >
                        {isSuspended ? (
                          <PlayCircle className="h-3.5 w-3.5" />
                        ) : (
                          <PauseCircle className="h-3.5 w-3.5" />
                        )}
                      </button>

                      <button
                        onClick={() => setUserToDelete(u)}
                        className="flex h-7 w-7 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-400 hover:border-rose-300 hover:bg-rose-50 hover:text-rose-600 transition-all"
                        title="Delete User Account"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
