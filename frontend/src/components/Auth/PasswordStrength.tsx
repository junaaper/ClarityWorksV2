import React from 'react';
import { Check, Circle } from 'lucide-react';
import type { PasswordRequirements } from '../../types';

interface PasswordStrengthProps {
  password: string;
}

export const getPasswordRequirements = (password: string): PasswordRequirements => {
  return {
    minLength: password.length >= 8,
    hasUppercase: /[A-Z]/.test(password),
    hasLowercase: /[a-z]/.test(password),
    hasNumber: /[0-9]/.test(password),
    hasSpecialChar: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password),
  };
};

export const getPasswordStrength = (password: string): { strength: 'weak' | 'fair' | 'good' | 'strong'; percentage: number } => {
  const requirements = getPasswordRequirements(password);
  const metCount = Object.values(requirements).filter(Boolean).length;

  if (password.length === 0) {
    return { strength: 'weak', percentage: 0 };
  }

  if (metCount <= 2) {
    return { strength: 'weak', percentage: 25 };
  } else if (metCount === 3) {
    return { strength: 'fair', percentage: 50 };
  } else if (metCount === 4) {
    return { strength: 'good', percentage: 75 };
  } else {
    return { strength: 'strong', percentage: 100 };
  }
};

export const isPasswordValid = (password: string): boolean => {
  const requirements = getPasswordRequirements(password);
  return Object.values(requirements).every(Boolean);
};

const PasswordStrength: React.FC<PasswordStrengthProps> = ({ password }) => {
  const requirements = getPasswordRequirements(password);
  const { strength, percentage } = getPasswordStrength(password);

  const strengthColors: Record<string, string> = {
    weak: 'var(--err-500)',
    fair: 'var(--warn-500)',
    good: 'var(--p-500)',
    strong: 'var(--ok-500)',
  };

  const strengthLabels = {
    weak: 'Weak',
    fair: 'Fair',
    good: 'Good',
    strong: 'Optimal',
  };

  const requirementsList = [
    { key: 'minLength', label: '8+ Characters', met: requirements.minLength },
    { key: 'hasNumber', label: '1+ Number', met: requirements.hasNumber },
    { key: 'hasSpecialChar', label: 'Special Symbol', met: requirements.hasSpecialChar },
    { key: 'hasUppercase', label: 'Uppercase Char', met: requirements.hasUppercase },
    { key: 'hasLowercase', label: 'Lowercase Char', met: requirements.hasLowercase },
  ];

  if (password.length === 0) {
    return null;
  }

  const barColor = strengthColors[strength];

  return (
    <div
      className="rounded-lg"
      style={{
        padding: '14px 16px',
        background: 'var(--surface-alt)',
        border: '1px solid var(--border)',
      }}
    >
      {/* Header + Bar */}
      <div className="flex items-center justify-between mb-2.5">
        <span style={{
          fontSize: 10.5,
          fontWeight: 700,
          color: 'var(--text-2)',
          letterSpacing: 0.4,
          textTransform: 'uppercase',
        }}>
          Complexity Score
        </span>
        <span
          className="rounded-full"
          style={{
            fontSize: 10.5,
            fontWeight: 600,
            color: barColor,
            background: strength === 'strong'
              ? 'color-mix(in srgb, var(--ok-500) 12%, transparent)'
              : 'transparent',
            padding: strength === 'strong' ? '2px 10px' : '2px 0',
          }}
        >
          {strengthLabels[strength]}
        </span>
      </div>

      {/* Segmented bar */}
      <div className="flex gap-1 mb-3">
        {[25, 50, 75, 100].map((threshold) => (
          <div
            key={threshold}
            className="flex-1 rounded-full"
            style={{
              height: 5,
              background: percentage >= threshold ? barColor : 'var(--surface-highest)',
              transition: 'background 200ms ease',
            }}
          />
        ))}
      </div>

      {/* Requirements grid */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
        {requirementsList.map((req) => (
          <div
            key={req.key}
            className="flex items-center gap-1.5"
            style={{ fontSize: 11.5 }}
          >
            {req.met ? (
              <Check className="w-3 h-3 flex-shrink-0" style={{ color: 'var(--ok-500)' }} />
            ) : (
              <Circle className="w-3 h-3 flex-shrink-0" style={{ color: 'var(--text-4)' }} />
            )}
            <span style={{ color: req.met ? 'var(--ok-500)' : 'var(--text-4)' }}>
              {req.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default PasswordStrength;
