import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { BookOpen, Mail, Lock, User, AlertCircle } from 'lucide-react';
import { useAuth } from '../../utils/auth';
import PasswordStrength, { isPasswordValid } from './PasswordStrength';

interface RegisterForm {
  fullName: string;
  email: string;
  password: string;
  confirmPassword: string;
}

const Register: React.FC = () => {
  const { register: registerUser } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const { register, handleSubmit, watch, formState: { errors } } = useForm<RegisterForm>();
  const password = watch('password');

  const onSubmit = async (data: RegisterForm) => {
    setError(null);
    setIsLoading(true);

    try {
      await registerUser(data.email, data.password, data.fullName);
      navigate('/dashboard');
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

  const fieldLabel: React.CSSProperties = {
    fontSize: 11.5,
    fontWeight: 600,
    color: 'var(--text-2)',
    letterSpacing: 0.2,
    textTransform: 'uppercase',
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4"
      style={{
        background: 'radial-gradient(ellipse at top, color-mix(in srgb, var(--p-700) 14%, var(--surface)) 0%, var(--surface) 55%)',
      }}
    >
      <div className="w-full max-w-md">
        {/* Brand */}
        <div className="flex items-center justify-center gap-3 mb-6">
          <div
            className="flex items-center justify-center rounded-md"
            style={{
              width: 40,
              height: 40,
              background: 'var(--gradient-scholar)',
              boxShadow: 'var(--sh-2)',
            }}
          >
            <BookOpen className="w-5 h-5" style={{ color: '#fff' }} />
          </div>
          <div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, fontWeight: 700, color: 'var(--p-900)', letterSpacing: -0.2 }}>
              ClarityWorks
            </div>
            <div className="cw-eyebrow" style={{ marginBottom: 0 }}>Digital Scholar</div>
          </div>
        </div>

        <div className="cw-card cw-card-pad-lg" style={{ padding: 36 }}>
          <div className="mb-6 text-center">
            <h2 className="cw-section-title" style={{ fontSize: 20, marginBottom: 4 }}>Create your account</h2>
            <p style={{ color: 'var(--text-3)', fontSize: 12.5 }}>
              Start analyzing readability in minutes.
            </p>
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
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label className="block mb-1.5" style={fieldLabel}>Full Name</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-4)' }} />
                <input
                  type="text"
                  {...register('fullName', {
                    required: 'Full name is required',
                    minLength: { value: 2, message: 'Name must be at least 2 characters' },
                  })}
                  className="cw-input"
                  style={{ paddingLeft: 36 }}
                  placeholder="John Doe"
                />
              </div>
              {errors.fullName && (
                <p className="mt-1" style={{ color: 'var(--err-500)', fontSize: 11.5 }}>{errors.fullName.message}</p>
              )}
            </div>

            <div>
              <label className="block mb-1.5" style={fieldLabel}>Email</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-4)' }} />
                <input
                  type="email"
                  {...register('email', {
                    required: 'Email is required',
                    pattern: {
                      value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
                      message: 'Invalid email format',
                    },
                  })}
                  className="cw-input"
                  style={{ paddingLeft: 36 }}
                  placeholder="you@example.com"
                />
              </div>
              {errors.email && (
                <p className="mt-1" style={{ color: 'var(--err-500)', fontSize: 11.5 }}>{errors.email.message}</p>
              )}
            </div>

            <div>
              <label className="block mb-1.5" style={fieldLabel}>Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-4)' }} />
                <input
                  type="password"
                  {...register('password', {
                    required: 'Password is required',
                    validate: (value) =>
                      isPasswordValid(value) || 'Password does not meet all requirements',
                  })}
                  className="cw-input"
                  style={{ paddingLeft: 36 }}
                  placeholder="••••••••"
                />
              </div>
              {errors.password && (
                <p className="mt-1" style={{ color: 'var(--err-500)', fontSize: 11.5 }}>{errors.password.message}</p>
              )}
              <PasswordStrength password={password || ''} />
            </div>

            <div>
              <label className="block mb-1.5" style={fieldLabel}>Confirm Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-4)' }} />
                <input
                  type="password"
                  {...register('confirmPassword', {
                    required: 'Please confirm your password',
                    validate: (value) => value === password || 'Passwords do not match',
                  })}
                  className="cw-input"
                  style={{ paddingLeft: 36 }}
                  placeholder="••••••••"
                />
              </div>
              {errors.confirmPassword && (
                <p className="mt-1" style={{ color: 'var(--err-500)', fontSize: 11.5 }}>{errors.confirmPassword.message}</p>
              )}
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="cw-btn cw-btn-primary cw-btn-lg w-full mt-2"
            >
              {isLoading ? 'Creating account…' : 'Create Account'}
            </button>
          </form>

          <p className="mt-6 text-center" style={{ color: 'var(--text-3)', fontSize: 12.5 }}>
            Already have an account?{' '}
            <Link to="/login" style={{ color: 'var(--p-700)', fontWeight: 600 }} className="hover:underline">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default Register;
