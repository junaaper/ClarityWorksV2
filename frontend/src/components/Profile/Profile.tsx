import React, { useState, useRef } from 'react';
import { useForm } from 'react-hook-form';
import { User, Mail, Lock, AlertCircle, CheckCircle, Save, Camera, Trash2 } from 'lucide-react';
import { useAuth } from '../../utils/auth';
import { authApi } from '../../services/api';
import PasswordStrength, { isPasswordValid } from '../Auth/PasswordStrength';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

interface ProfileForm {
  fullName: string;
  email: string;
}

interface PasswordForm {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}

const Profile: React.FC = () => {
  const { user, refreshUser } = useAuth();
  const [activeTab, setActiveTab] = useState<'profile' | 'password'>('profile');
  const [isLoading, setIsLoading] = useState(false);
  const [isUploadingPicture, setIsUploadingPicture] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const {
    register: registerProfile,
    handleSubmit: handleProfileSubmit,
    formState: { errors: profileErrors },
  } = useForm<ProfileForm>({
    defaultValues: {
      fullName: user?.fullName || '',
      email: user?.email || '',
    },
  });

  const {
    register: registerPassword,
    handleSubmit: handlePasswordSubmit,
    watch,
    reset: resetPassword,
    formState: { errors: passwordErrors },
  } = useForm<PasswordForm>();

  const newPassword = watch('newPassword');

  const handleProfilePictureClick = () => {
    fileInputRef.current?.click();
  };

  const handleProfilePictureChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file size (5MB max)
    if (file.size > 5 * 1024 * 1024) {
      setError('File size must be less than 5MB');
      return;
    }

    // Validate file type
    const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'];
    if (!allowedTypes.includes(file.type)) {
      setError('Invalid file type. Only JPEG, PNG, GIF, and WebP are allowed.');
      return;
    }

    setError(null);
    setSuccess(null);
    setIsUploadingPicture(true);

    try {
      const result = await authApi.uploadProfilePicture(file);
      localStorage.setItem('user', JSON.stringify(result.user));
      if (refreshUser) refreshUser();
      setSuccess('Profile picture updated successfully');
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'An error occurred';
      if (typeof err === 'object' && err !== null && 'response' in err) {
        const axiosError = err as { response?: { data?: { error?: string } } };
        setError(axiosError.response?.data?.error || errorMessage);
      } else {
        setError(errorMessage);
      }
    } finally {
      setIsUploadingPicture(false);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDeleteProfilePicture = async () => {
    setError(null);
    setSuccess(null);
    setIsUploadingPicture(true);

    try {
      const result = await authApi.deleteProfilePicture();
      localStorage.setItem('user', JSON.stringify(result.user));
      if (refreshUser) refreshUser();
      setSuccess('Profile picture removed successfully');
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'An error occurred';
      if (typeof err === 'object' && err !== null && 'response' in err) {
        const axiosError = err as { response?: { data?: { error?: string } } };
        setError(axiosError.response?.data?.error || errorMessage);
      } else {
        setError(errorMessage);
      }
    } finally {
      setIsUploadingPicture(false);
    }
  };

  const onProfileSubmit = async (data: ProfileForm) => {
    setError(null);
    setSuccess(null);
    setIsLoading(true);

    try {
      const result = await authApi.updateProfile(data.fullName, data.email);
      // Update local storage and context
      localStorage.setItem('user', JSON.stringify(result.user));
      if (refreshUser) refreshUser();
      setSuccess('Profile updated successfully');
      // Re-login to refresh the token if email changed
      if (data.email !== user?.email) {
        window.location.reload();
      }
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'An error occurred';
      if (typeof err === 'object' && err !== null && 'response' in err) {
        const axiosError = err as { response?: { data?: { error?: string } } };
        setError(axiosError.response?.data?.error || errorMessage);
      } else {
        setError(errorMessage);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const onPasswordSubmit = async (data: PasswordForm) => {
    setError(null);
    setSuccess(null);
    setIsLoading(true);

    try {
      await authApi.updatePassword(data.currentPassword, data.newPassword);
      setSuccess('Password updated successfully');
      resetPassword();
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'An error occurred';
      if (typeof err === 'object' && err !== null && 'response' in err) {
        const axiosError = err as { response?: { data?: { error?: string; details?: string[] } } };
        const details = axiosError.response?.data?.details;
        if (details && details.length > 0) {
          setError(details.join(', '));
        } else {
          setError(axiosError.response?.data?.error || errorMessage);
        }
      } else {
        setError(errorMessage);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const fieldLabel: React.CSSProperties = {
    fontSize: 11.5,
    fontWeight: 600,
    color: 'var(--text-2)',
    letterSpacing: 0.2,
    textTransform: 'uppercase',
  };

  const TabButton: React.FC<{ active: boolean; onClick: () => void; icon: React.ReactNode; children: React.ReactNode }> = ({ active, onClick, icon, children }) => (
    <button
      onClick={onClick}
      className="flex-1 flex items-center justify-center gap-2 px-4 py-3.5 transition-colors"
      style={{
        fontSize: 12.5,
        fontWeight: active ? 600 : 500,
        color: active ? 'var(--p-900)' : 'var(--text-3)',
        background: active ? 'var(--surface-raised)' : 'transparent',
        borderBottom: active ? '2px solid var(--p-700)' : '2px solid transparent',
      }}
    >
      {icon}
      {children}
    </button>
  );

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-8">
        <div className="cw-eyebrow mb-2">Account</div>
        <h1 className="cw-hero" style={{ fontSize: 28 }}>Profile Settings</h1>
        <p className="mt-2" style={{ color: 'var(--text-3)', fontSize: 12.5 }}>
          Manage your account details and password.
        </p>
      </div>

      {/* Tabs */}
      <div className="cw-card overflow-hidden">
        <div className="flex" style={{ borderBottom: '1px solid var(--border)', background: 'var(--surface-sunk)' }}>
          <TabButton
            active={activeTab === 'profile'}
            onClick={() => { setActiveTab('profile'); setError(null); setSuccess(null); }}
            icon={<User className="w-4 h-4" />}
          >
            Profile
          </TabButton>
          <TabButton
            active={activeTab === 'password'}
            onClick={() => { setActiveTab('password'); setError(null); setSuccess(null); }}
            icon={<Lock className="w-4 h-4" />}
          >
            Password
          </TabButton>
        </div>

        <div className="cw-card-pad-lg">
          {/* Alerts */}
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
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div
              className="mb-4 rounded-md flex items-center gap-2"
              style={{
                padding: '10px 14px',
                background: 'color-mix(in srgb, var(--ok-500) 8%, var(--surface-raised))',
                border: '1px solid color-mix(in srgb, var(--ok-500) 25%, transparent)',
                color: 'var(--ok-500)',
                fontSize: 12.5,
              }}
            >
              <CheckCircle className="w-4 h-4 flex-shrink-0" />
              <span>{success}</span>
            </div>
          )}

          {/* Profile Form */}
          {activeTab === 'profile' && (
            <form onSubmit={handleProfileSubmit(onProfileSubmit)} className="space-y-5">
              {/* Profile Picture Section */}
              <div className="flex items-center gap-5 pb-5" style={{ borderBottom: '1px solid var(--border)' }}>
                <div className="relative">
                  <div
                    className="flex items-center justify-center overflow-hidden rounded-full"
                    style={{
                      width: 84,
                      height: 84,
                      background: 'var(--surface-sunk)',
                      border: '1px solid var(--border)',
                    }}
                  >
                    {user?.profilePicture ? (
                      <img
                        src={`${API_URL}${user.profilePicture}`}
                        alt="Profile"
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <User className="w-10 h-10" style={{ color: 'var(--text-4)' }} />
                    )}
                  </div>
                  {isUploadingPicture && (
                    <div
                      className="absolute inset-0 rounded-full flex items-center justify-center"
                      style={{ background: 'color-mix(in srgb, var(--ink-900) 55%, transparent)' }}
                    >
                      <div className="animate-spin rounded-full h-7 w-7 border-b-2 border-white"></div>
                    </div>
                  )}
                </div>
                <div className="flex-1">
                  <div className="cw-eyebrow" style={{ marginBottom: 4 }}>Profile Picture</div>
                  <p className="mb-3" style={{ fontSize: 11.5, color: 'var(--text-3)' }}>
                    JPG, PNG, GIF or WebP. Max size 5&nbsp;MB.
                  </p>
                  <div className="flex items-center gap-2 flex-wrap">
                    <input
                      type="file"
                      ref={fileInputRef}
                      onChange={handleProfilePictureChange}
                      accept="image/jpeg,image/jpg,image/png,image/gif,image/webp"
                      className="hidden"
                    />
                    <button
                      type="button"
                      onClick={handleProfilePictureClick}
                      disabled={isUploadingPicture}
                      className="cw-btn cw-btn-sm cw-btn-secondary"
                    >
                      <Camera className="w-3.5 h-3.5" />
                      Upload
                    </button>
                    {user?.profilePicture && (
                      <button
                        type="button"
                        onClick={handleDeleteProfilePicture}
                        disabled={isUploadingPicture}
                        className="cw-btn cw-btn-sm cw-btn-ghost"
                        style={{ color: 'var(--err-500)' }}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        Remove
                      </button>
                    )}
                  </div>
                </div>
              </div>

              <div>
                <label className="block mb-1.5" style={fieldLabel}>Full Name</label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-4)' }} />
                  <input
                    type="text"
                    {...registerProfile('fullName', {
                      required: 'Full name is required',
                      minLength: { value: 2, message: 'Name must be at least 2 characters' },
                    })}
                    className="cw-input"
                    style={{ paddingLeft: 36 }}
                  />
                </div>
                {profileErrors.fullName && (
                  <p className="mt-1" style={{ color: 'var(--err-500)', fontSize: 11.5 }}>{profileErrors.fullName.message}</p>
                )}
              </div>

              <div>
                <label className="block mb-1.5" style={fieldLabel}>Email</label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-4)' }} />
                  <input
                    type="email"
                    {...registerProfile('email', {
                      required: 'Email is required',
                      pattern: { value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/, message: 'Invalid email format' },
                    })}
                    className="cw-input"
                    style={{ paddingLeft: 36 }}
                  />
                </div>
                {profileErrors.email && (
                  <p className="mt-1" style={{ color: 'var(--err-500)', fontSize: 11.5 }}>{profileErrors.email.message}</p>
                )}
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="cw-btn cw-btn-primary cw-btn-lg w-full"
              >
                {isLoading ? 'Saving…' : <><Save className="w-4 h-4" />Save Changes</>}
              </button>
            </form>
          )}

          {/* Password Form */}
          {activeTab === 'password' && (
            <form onSubmit={handlePasswordSubmit(onPasswordSubmit)} className="space-y-4">
              <div>
                <label className="block mb-1.5" style={fieldLabel}>Current Password</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-4)' }} />
                  <input
                    type="password"
                    {...registerPassword('currentPassword', { required: 'Current password is required' })}
                    className="cw-input"
                    style={{ paddingLeft: 36 }}
                    placeholder="Enter current password"
                  />
                </div>
                {passwordErrors.currentPassword && (
                  <p className="mt-1" style={{ color: 'var(--err-500)', fontSize: 11.5 }}>{passwordErrors.currentPassword.message}</p>
                )}
              </div>

              <div>
                <label className="block mb-1.5" style={fieldLabel}>New Password</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-4)' }} />
                  <input
                    type="password"
                    {...registerPassword('newPassword', {
                      required: 'New password is required',
                      validate: (value) => isPasswordValid(value) || 'Password does not meet all requirements',
                    })}
                    className="cw-input"
                    style={{ paddingLeft: 36 }}
                    placeholder="Enter new password"
                  />
                </div>
                {passwordErrors.newPassword && (
                  <p className="mt-1" style={{ color: 'var(--err-500)', fontSize: 11.5 }}>{passwordErrors.newPassword.message}</p>
                )}
                <PasswordStrength password={newPassword || ''} />
              </div>

              <div>
                <label className="block mb-1.5" style={fieldLabel}>Confirm New Password</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-4)' }} />
                  <input
                    type="password"
                    {...registerPassword('confirmPassword', {
                      required: 'Please confirm your new password',
                      validate: (value) => value === newPassword || 'Passwords do not match',
                    })}
                    className="cw-input"
                    style={{ paddingLeft: 36 }}
                    placeholder="Confirm new password"
                  />
                </div>
                {passwordErrors.confirmPassword && (
                  <p className="mt-1" style={{ color: 'var(--err-500)', fontSize: 11.5 }}>{passwordErrors.confirmPassword.message}</p>
                )}
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="cw-btn cw-btn-primary cw-btn-lg w-full"
              >
                {isLoading ? 'Updating…' : <><Lock className="w-4 h-4" />Update Password</>}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};

export default Profile;
