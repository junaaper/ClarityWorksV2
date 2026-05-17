import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { BookOpen, Mail, Lock, AlertCircle, Eye, EyeOff, BarChart3, TrendingUp, BookOpenCheck, ArrowRight } from 'lucide-react';
import { useAuth } from '../../utils/auth';

interface LoginForm {
  email: string;
  password: string;
}

const Login: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const { register, handleSubmit, formState: { errors } } = useForm<LoginForm>();

  const onSubmit = async (data: LoginForm) => {
    setError(null);
    setIsLoading(true);

    try {
      await login(data.email, data.password);
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
          position: 'absolute', top: '15%', left: '-10%', width: '70%', height: '70%',
          background: 'radial-gradient(circle, rgba(40,96,157,0.15) 0%, transparent 70%)',
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

        {/* Middle: Headline + description + features */}
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
            Analyze and rewrite<br />text with precision.
          </h1>

          <p style={{
            fontSize: 16.5,
            lineHeight: 1.65,
            color: 'rgba(255,255,255,0.5)',
            maxWidth: 420,
            marginBottom: 44,
          }}>
            Readability scoring, ML-powered grade predictions, and intelligent text simplification for grades 3 through college.
          </p>

          <div className="space-y-3">
            {[
              { icon: BarChart3, title: '8 Readability Formulas', desc: 'Flesch, SMOG, ARI, Coleman-Liau and more — instant results.' },
              { icon: TrendingUp, title: 'Grade Prediction', desc: '3-model ensemble trained on 5,000+ reading passages.' },
              { icon: BookOpenCheck, title: 'Smart Simplification', desc: 'Rewrite text to any target grade level with NLP analysis.' },
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

      </div>

      {/* Right Panel */}
      <div
        className="flex-1 flex items-center justify-center p-8"
        style={{ background: 'var(--surface-raised)' }}
      >
        <div style={{ width: '100%', maxWidth: 480 }}>
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

          {/* Heading */}
          <div className="mb-10">
            <h2 style={{
              fontFamily: 'var(--font-display)',
              fontSize: 30,
              fontWeight: 700,
              color: 'var(--text-1)',
              letterSpacing: -0.5,
              marginBottom: 8,
            }}>
              Welcome back
            </h2>
            <p style={{ color: 'var(--text-3)', fontSize: 15 }}>
              Sign in to continue your readability analysis.
            </p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-7">
            {/* Email */}
            <div>
              <label className="block mb-2.5" style={{
                fontSize: 12,
                fontWeight: 600,
                color: 'var(--text-2)',
                letterSpacing: 0.4,
                textTransform: 'uppercase',
              }}>
                Email
              </label>
              <div className="relative">
                <Mail
                  className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5"
                  style={{ color: 'var(--text-4)' }}
                />
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

            {/* Password */}
            <div>
              <label className="block mb-2.5" style={{
                fontSize: 12,
                fontWeight: 600,
                color: 'var(--text-2)',
                letterSpacing: 0.4,
                textTransform: 'uppercase',
              }}>
                Password
              </label>
              <div className="relative">
                <Lock
                  className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5"
                  style={{ color: 'var(--text-4)' }}
                />
                <input
                  type={showPassword ? 'text' : 'password'}
                  {...register('password', {
                    required: 'Password is required',
                    minLength: {
                      value: 6,
                      message: 'Password must be at least 6 characters',
                    },
                  })}
                  className="cw-input"
                  style={{ paddingLeft: 46, paddingRight: 50, height: 52, fontSize: 15, borderRadius: 'var(--r-lg)' }}
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 p-1 rounded"
                  style={{ color: 'var(--text-4)', background: 'transparent', border: 'none', cursor: 'pointer' }}
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
              {errors.password && (
                <p className="mt-2" style={{ color: 'var(--err-500)', fontSize: 13 }}>{errors.password.message}</p>
              )}
            </div>

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
                'Signing in…'
              ) : (
                <>
                  <ArrowRight className="w-5 h-5" />
                  Sign In
                </>
              )}
            </button>
          </form>

          {/* Footer link */}
          <p className="mt-10 text-center" style={{ color: 'var(--text-3)', fontSize: 14.5 }}>
            New to ClarityWorks?{' '}
            <Link
              to="/register"
              style={{ color: 'var(--p-700)', fontWeight: 600 }}
              className="hover:underline"
            >
              Create an Account
            </Link>
          </p>

        </div>
      </div>
    </div>
  );
};

export default Login;
