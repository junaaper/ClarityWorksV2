import React, { useState, useEffect, useCallback } from 'react';
import {
  Search, UserCheck, UserX, Shield, ShieldOff, Trash2, AlertCircle, ChevronLeft, ChevronRight
} from 'lucide-react';
import { adminApi } from '../../services/api';
import type { AdminUser, Pagination } from '../../types';

const UserManagement: React.FC = () => {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [pagination, setPagination] = useState<Pagination>({ page: 1, limit: 10, totalCount: 0, totalPages: 0 });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  const fetchUsers = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await adminApi.getUsers({
        page: pagination.page,
        limit: pagination.limit,
        search,
        role: roleFilter,
        status: statusFilter,
      });
      setUsers(data.users);
      setPagination(data.pagination);
    } catch (err) {
      setError('Failed to load users');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, [pagination.page, pagination.limit, search, roleFilter, statusFilter]);

  useEffect(() => {
    const debounceTimer = setTimeout(() => {
      fetchUsers();
    }, 300);
    return () => clearTimeout(debounceTimer);
  }, [fetchUsers]);

  const handleToggleRole = async (userId: number, currentRole: string) => {
    try {
      setActionLoading(userId);
      const newRole = currentRole === 'admin' ? 'user' : 'admin';
      await adminApi.updateUserRole(userId, newRole);
      setUsers(users.map(u => u.id === userId ? { ...u, role: newRole } : u));
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to update role';
      if (typeof err === 'object' && err !== null && 'response' in err) {
        const axiosError = err as { response?: { data?: { error?: string } } };
        alert(axiosError.response?.data?.error || errorMessage);
      } else {
        alert(errorMessage);
      }
    } finally {
      setActionLoading(null);
    }
  };

  const handleToggleStatus = async (userId: number) => {
    try {
      setActionLoading(userId);
      const result = await adminApi.toggleUserStatus(userId);
      setUsers(users.map(u => u.id === userId ? { ...u, isActive: result.user.isActive } : u));
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to update status';
      if (typeof err === 'object' && err !== null && 'response' in err) {
        const axiosError = err as { response?: { data?: { error?: string } } };
        alert(axiosError.response?.data?.error || errorMessage);
      } else {
        alert(errorMessage);
      }
    } finally {
      setActionLoading(null);
    }
  };

  const handleDelete = async (userId: number) => {
    try {
      setActionLoading(userId);
      await adminApi.deleteUser(userId);
      setUsers(users.filter(u => u.id !== userId));
      setDeleteConfirm(null);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete user';
      if (typeof err === 'object' && err !== null && 'response' in err) {
        const axiosError = err as { response?: { data?: { error?: string } } };
        alert(axiosError.response?.data?.error || errorMessage);
      } else {
        alert(errorMessage);
      }
    } finally {
      setActionLoading(null);
    }
  };

  const iconBtnStyle = (hoverBg: string, hoverColor: string) => ({
    onMouseEnter: (e: React.MouseEvent<HTMLButtonElement>) => {
      e.currentTarget.style.background = hoverBg;
      e.currentTarget.style.color = hoverColor;
    },
    onMouseLeave: (e: React.MouseEvent<HTMLButtonElement>) => {
      e.currentTarget.style.background = 'transparent';
      e.currentTarget.style.color = 'var(--text-3)';
    },
  });

  return (
    <div>
      <div className="mb-8">
        <div className="cw-eyebrow mb-2">Administration</div>
        <h1 className="cw-hero" style={{ fontSize: 28 }}>User Management</h1>
        <p className="mt-2" style={{ color: 'var(--text-3)', fontSize: 12.5 }}>
          Manage user accounts, roles, and permissions.
        </p>
      </div>

      {/* Filters */}
      <div className="cw-card cw-card-pad mb-5">
        <div className="flex flex-wrap gap-3">
          <div className="flex-1 min-w-[200px] relative">
            <Search
              className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4"
              style={{ color: 'var(--text-4)' }}
            />
            <input
              type="text"
              placeholder="Search by name or email…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPagination(p => ({ ...p, page: 1 }));
              }}
              className="cw-input"
              style={{ paddingLeft: 36 }}
            />
          </div>
          <select
            value={roleFilter}
            onChange={(e) => {
              setRoleFilter(e.target.value);
              setPagination(p => ({ ...p, page: 1 }));
            }}
            className="cw-select"
            style={{ maxWidth: 180 }}
          >
            <option value="all">All Roles</option>
            <option value="user">Users</option>
            <option value="admin">Admins</option>
          </select>
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPagination(p => ({ ...p, page: 1 }));
            }}
            className="cw-select"
            style={{ maxWidth: 180 }}
          >
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
      </div>

      {error && (
        <div
          className="mb-4 rounded-md flex items-center gap-2"
          style={{
            padding: '10px 14px',
            background: 'var(--err-50)',
            border: '1px solid color-mix(in srgb, var(--err-500) 22%, transparent)',
            color: 'var(--err-700)',
            fontSize: 12.5,
          }}
        >
          <AlertCircle className="w-4 h-4" />
          <span>{error}</span>
        </div>
      )}

      {/* Users Table */}
      <div className="cw-card overflow-hidden">
        <div className="cw-scroll-x">
          <table className="cw-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Role</th>
                <th>Status</th>
                <th>Analyses</th>
                <th>Joined</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="text-center py-12">
                    <div
                      className="animate-spin rounded-full h-8 w-8 border-b-2 mx-auto"
                      style={{ borderColor: 'var(--p-700)' }}
                    />
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-12" style={{ color: 'var(--text-4)', fontSize: 12.5 }}>
                    No users found
                  </td>
                </tr>
              ) : (
                users.map((user) => (
                  <tr key={user.id}>
                    <td>
                      <p style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-1)' }}>
                        {user.fullName}
                      </p>
                      <p style={{ fontSize: 11, color: 'var(--text-3)' }}>{user.email}</p>
                    </td>
                    <td>
                      <span className={user.role === 'admin' ? 'cw-badge cw-badge-teal' : 'cw-badge cw-badge-neutral'}>
                        {user.role === 'admin' && <Shield className="w-3 h-3 mr-1 inline" />}
                        {user.role.charAt(0).toUpperCase() + user.role.slice(1)}
                      </span>
                    </td>
                    <td>
                      <span className={user.isActive ? 'cw-badge cw-badge-ok' : 'cw-badge cw-badge-err'}>
                        {user.isActive ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-2)' }}>
                      {user.analysisCount}
                    </td>
                    <td style={{ color: 'var(--text-3)', fontSize: 11.5 }}>
                      {new Date(user.createdAt).toLocaleDateString()}
                    </td>
                    <td>
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => handleToggleRole(user.id, user.role)}
                          disabled={actionLoading === user.id}
                          className="p-1.5 rounded transition-colors"
                          style={{ color: 'var(--text-3)' }}
                          {...iconBtnStyle('color-mix(in srgb, var(--s-500) 12%, transparent)', 'var(--s-700)')}
                          title={user.role === 'admin' ? 'Remove admin' : 'Make admin'}
                        >
                          {user.role === 'admin' ? <ShieldOff className="w-4 h-4" /> : <Shield className="w-4 h-4" />}
                        </button>
                        <button
                          onClick={() => handleToggleStatus(user.id)}
                          disabled={actionLoading === user.id}
                          className="p-1.5 rounded transition-colors"
                          style={{ color: 'var(--text-3)' }}
                          {...iconBtnStyle(
                            user.isActive ? 'var(--err-50)' : 'color-mix(in srgb, var(--ok-500) 12%, transparent)',
                            user.isActive ? 'var(--err-500)' : 'var(--ok-500)'
                          )}
                          title={user.isActive ? 'Deactivate user' : 'Activate user'}
                        >
                          {user.isActive ? <UserX className="w-4 h-4" /> : <UserCheck className="w-4 h-4" />}
                        </button>
                        <button
                          onClick={() => setDeleteConfirm(user.id)}
                          disabled={actionLoading === user.id}
                          className="p-1.5 rounded transition-colors"
                          style={{ color: 'var(--text-3)' }}
                          {...iconBtnStyle('var(--err-50)', 'var(--err-500)')}
                          title="Delete user"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {pagination.totalPages > 1 && (
          <div
            className="flex items-center justify-between px-5 py-3"
            style={{ borderTop: '1px solid var(--border)', background: 'var(--surface-sunk)' }}
          >
            <p style={{ fontSize: 11.5, color: 'var(--text-3)' }}>
              Showing {(pagination.page - 1) * pagination.limit + 1} to {Math.min(pagination.page * pagination.limit, pagination.totalCount)} of {pagination.totalCount} users
            </p>
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setPagination(p => ({ ...p, page: p.page - 1 }))}
                disabled={pagination.page === 1}
                className="cw-btn cw-btn-sm cw-btn-secondary"
                style={{ padding: '0 8px' }}
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span
                className="px-3"
                style={{ fontSize: 11.5, color: 'var(--text-2)', fontFamily: 'var(--font-mono)' }}
              >
                {pagination.page} / {pagination.totalPages}
              </span>
              <button
                onClick={() => setPagination(p => ({ ...p, page: p.page + 1 }))}
                disabled={pagination.page === pagination.totalPages}
                className="cw-btn cw-btn-sm cw-btn-secondary"
                style={{ padding: '0 8px' }}
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div
          className="fixed inset-0 flex items-center justify-center z-50"
          style={{ background: 'color-mix(in srgb, var(--ink-900) 55%, transparent)' }}
        >
          <div className="cw-card cw-card-pad-lg max-w-md w-full mx-4">
            <div className="flex items-center gap-3 mb-4">
              <div
                className="p-2 rounded-full"
                style={{ background: 'var(--err-50)' }}
              >
                <AlertCircle className="w-5 h-5" style={{ color: 'var(--err-500)' }} />
              </div>
              <h3 className="cw-section-title">Delete User</h3>
            </div>
            <p style={{ color: 'var(--text-2)', fontSize: 13, marginBottom: 20, lineHeight: 1.55 }}>
              Are you sure you want to delete this user? This action cannot be undone and will also delete all their analyses.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setDeleteConfirm(null)} className="cw-btn cw-btn-secondary">
                Cancel
              </button>
              <button
                onClick={() => handleDelete(deleteConfirm)}
                disabled={actionLoading === deleteConfirm}
                className="cw-btn cw-btn-danger"
              >
                {actionLoading === deleteConfirm ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserManagement;
