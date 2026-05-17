import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { BookOpen, Mail, Lock, User, AlertCircle, Eye, EyeOff, BarChart3, FileText, Sparkles, ArrowRight } from 'lucide-react';
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
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

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
    fontSize: 12,
    fontWeight: 600,
    color: 'var(--text-2)',
    letterSpacing: 0.4,
    textTransform: 'uppercase',
  };

  return (
    <div className="min-h-screen flex" style={{ background: 'var(--surface)' }}>
      {/* Left Panel */}
      <div
        className="hidden lg:flex flex-col justify-between"
        style={{
          width: '45%',
          background: 'linear-gradient(160deg, #0d1217 0%, #001f3d 40%, #003461 100%)',
          padding: '52px 60px 48px',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {/* Decorative grid */}
        <div style={{
          position: 'absolute', inset: 0,
          backgroundImage: `linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
                           linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)`,
          backgroundSize: '48px 48px',
          pointerEvents: 'none',
        }} />
        <div style={{
          position: 'absolute', bottom: '10%', right: '-15%', width: '70%', height: '70%',
          background: 'radial-gradient(circle, rgba(40,96,157,0.12) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />

        {/* Top: Giant logo */}
        <div style={{ position: 'relative', zIndex: 1 }}>
          <div className="flex items-center gap-7">
            <div
              className="flex items-center justify-center"
              style={{
                width: 110,
                height: 110,
                borderRadius: 24,
                background: 'rgba(255,255,255,0.08)',
                border: '1px solid rgba(255,255,255,0.12)',
                boxShadow: '0 16px 48px rgba(0,0,0,0.4), 0 0 80px rgba(40,96,157,0.15)',
              }}
            >
              <BookOpen style={{ width: 56, height: 56, color: '#fff' }} />
            </div>
            <span style={{
              fontFamily: 'var(--font-display)',
              fontSize: 52,
              fontWeight: 800,
              color: '#fff',
              letterSpacing: -2,
            }}>
              ClarityWorks
            </span>
          </div>
        </div>

        {/* Middle: Headline + features */}
        <div style={{ position: 'relative', zIndex: 1, flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
          <h1 style={{
            fontFamily: 'var(--font-display)',
            fontSize: 50,
            fontWeight: 800,
            lineHeight: 1.05,
            letterSpacing: -1.8,
            color: '#fff',
            marginBottom: 20,
          }}>
            Start analyzing<br />text today.
          </h1>

          <p style={{
            fontSize: 16.5,
            lineHeight: 1.65,
            color: 'rgba(255,255,255,0.5)',
            maxWidth: 420,
            marginBottom: 44,
          }}>
            Grade-level predictions, readability scoring, and intelligent text simplification — all in one platform.
          </p>

          <div className="space-y-3">
            {[
              { icon: BarChart3, title: 'ML Grade Prediction', desc: '3-model ensemble trained on 5,000+ reading passages.' },
              { icon: FileText, title: 'Text Simplification', desc: 'Rewrite text to any grade level with NLP-powered analysis.' },
              { icon: Sparkles, title: 'RAG Textbook Search', desc: 'Upload textbooks and query them with AI-powered answers.' },
            ].map(({ icon: Icon, title, desc }) => (
              <div
                key={title}
                className="flex items-start gap-4"
                style={{
                  padding: '16px 20px',
                  borderRadius: 14,
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.07)',
                }}
              >
                <div
                  className="flex items-center justify-center flex-shrink-0"
                  style={{ width: 38, height: 38, borderRadius: 10, background: 'rgba(255,255,255,0.07)', marginTop: 1 }}
                >
                  <Icon className="w-[18px] h-[18px]" style={{ color: 'rgba(255,255,255,0.6)' }} />
                </div>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 14, color: '#fff', marginBottom: 3 }}>{title}</div>
                  <div style={{ fontSize: 12.5, color: 'rgba(255,255,255,0.4)', lineHeight: 1.5 }}>{desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom */}
        <div style={{ position: 'relative', zIndex: 1 }}>
          <div className="flex items-center gap-3">
            <div className="flex -space-x-2">
              {['#3d6562', '#28609d', '#d08a22'].map((bg, i) => (
                <div
                  key={i}
                  className="flex items-center justify-center rounded-full"
                  style={{
                    width: 30, height: 30, background: bg,
                    border: '2px solid #001f3d',
                    fontSize: 10, fontWeight: 700, color: '#fff',
                  }}
                >
                  {['G3', 'G8', 'C'][i]}
                </div>
              ))}
            </div>
            <span style={{ fontSize: 13, color: 'rgba(255,255,255,0.4)' }}>
              Covering <strong style={{ color: 'rgba(255,255,255,0.65)' }}>Grade 3 through College</strong> reading levels
            </span>
          </div>
        </div>
      </div>

      {/* Right Panel */}
      <div
        className="flex-1 flex items-center justify-center p-8"
        style={{ background: 'var(--surface-raised)', overflowY: 'auto' }}
      >
        <div style={{ width: '100%', maxWidth: 480 }}>
          {/* Heading */}
          <div className="mb-8">
            <h2 style={{
              fontFamily: 'var(--font-display)',
              fontSize: 30,
              fontWeight: 700,
              color: 'var(--text-1)',
              letterSpacing: -0.5,
              marginBottom: 8,
            }}>
              Create Your Account
            </h2>
            <p style={{ color: 'var(--text-3)', fontSize: 15 }}>
              Start analyzing readability in minutes.
            </p>
          </div>

          {/* Error alert */}
          {error && (
            <div
              className="mb-6 rounded-lg flex items-start gap-3"
              style={{
                padding: '16px 18px',
                background: 'var(--err-50)',
                border: '1px solid color-mix(in srgb, var(--err-500) 25%, transparent)',
                color: 'var(--err-700)',
                fontSize: 14,
              }}
            >
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            {/* Full Name */}
            <div>
              <label className="block mb-2.5" style={fieldLabel}>Full Name</label>
              <div className="relative">
                <User className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5" style={{ color: 'var(--text-4)' }} />
                <input
                  type="text"
                  {...register('fullName', {
                    required: 'Full name is required',
                    validate: {
                      minTrimmedLength: (value) =>
                        value.trim().length >= 2 || 'Name must be at least 2 characters',
                      startsWithLetter: (value) =>
                        /^\p{L}/u.test(value.trim()) || 'Name must start with a letter',
                    },
                  })}
                  className="cw-input"
                  style={{ paddingLeft: 46, height: 52, fontSize: 15, borderRadius: 'var(--r-lg)' }}
                  placeholder="John Doe"
                />
              </div>
              {errors.fullName && (
                <p className="mt-2" style={{ color: 'var(--err-500)', fontSize: 13 }}>{errors.fullName.message}</p>
              )}
            </div>

            {/* Email */}
            <div>
              <label className="block mb-2.5" style={fieldLabel}>Email</label>
              <div className="relative">
                <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5" style={{ color: 'var(--text-4)' }} />
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
                  style={{ paddingLeft: 46, height: 52, fontSize: 15, borderRadius: 'var(--r-lg)' }}
                  placeholder="you@example.com"
                />
              </div>
              {errors.email && (
                <p className="mt-2" style={{ color: 'var(--err-500)', fontSize: 13 }}>{errors.email.message}</p>
              )}
            </div>

            {/* Password + Confirm side by side */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block mb-2.5" style={fieldLabel}>Password</label>
                <div className="relative">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5" style={{ color: 'var(--text-4)' }} />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    {...register('password', {
                      required: 'Password is required',
                      validate: (value) =>
                        isPasswordValid(value) || 'Password does not meet all requirements',
                    })}
                    className="cw-input"
                    style={{ paddingLeft: 46, paddingRight: 42, height: 52, fontSize: 15, borderRadius: 'var(--r-lg)' }}
                    placeholder="••••••••"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded"
                    style={{ color: 'var(--text-4)', background: 'transparent', border: 'none', cursor: 'pointer' }}
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {errors.password && (
                  <p className="mt-2" style={{ color: 'var(--err-500)', fontSize: 13 }}>{errors.password.message}</p>
                )}
              </div>

              <div>
                <label className="block mb-2.5" style={fieldLabel}>Confirm</label>
                <div className="relative">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5" style={{ color: 'var(--text-4)' }} />
                  <input
                    type={showConfirm ? 'text' : 'password'}
                    {...register('confirmPassword', {
                      required: 'Please confirm your password',
                      validate: (value) => value === password || 'Passwords do not match',
                    })}
                    className="cw-input"
                    style={{ paddingLeft: 46, paddingRight: 42, height: 52, fontSize: 15, borderRadius: 'var(--r-lg)' }}
                    placeholder="••••••••"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirm(!showConfirm)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded"
                    style={{ color: 'var(--text-4)', background: 'transparent', border: 'none', cursor: 'pointer' }}
                  >
                    {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {errors.confirmPassword && (
                  <p className="mt-2" style={{ color: 'var(--err-500)', fontSize: 13 }}>{errors.confirmPassword.message}</p>
                )}
              </div>
            </div>

            {/* Password Strength */}
            <PasswordStrength password={password || ''} />

            {/* Submit */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2"
              style={{
                height: 54,
                borderRadius: 'var(--r-lg)',
                background: 'var(--g-scholar)',
                color: '#fff',
                border: '1px solid var(--p-900)',
                fontFamily: 'var(--font-sans)',
                fontSize: 15.5,
                fontWeight: 600,
                cursor: isLoading ? 'not-allowed' : 'pointer',
                opacity: isLoading ? 0.6 : 1,
                transition: 'filter 140ms ease',
                letterSpacing: -0.01,
              }}
              onMouseEnter={e => { if (!isLoading) (e.target as HTMLElement).style.filter = 'brightness(1.1)'; }}
              onMouseLeave={e => { (e.target as HTMLElement).style.filter = 'none'; }}
            >
              {isLoading ? (
                'Creating account…'
              ) : (
                <>
                  Create Account
                  <ArrowRight className="w-5 h-5" />
                </>
              )}
            </button>
          </form>

          {/* Footer link */}
          <p className="mt-8 text-center" style={{ color: 'var(--text-3)', fontSize: 14.5 }}>
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
