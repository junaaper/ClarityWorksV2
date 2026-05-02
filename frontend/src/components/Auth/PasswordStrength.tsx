import React from 'react';
import { Check, X } from 'lucide-react';
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
    strong: 'Strong',
  };

  const requirementsList = [
    { key: 'minLength', label: 'At least 8 characters', met: requirements.minLength },
    { key: 'hasUppercase', label: 'One uppercase letter', met: requirements.hasUppercase },
    { key: 'hasLowercase', label: 'One lowercase letter', met: requirements.hasLowercase },
    { key: 'hasNumber', label: 'One number', met: requirements.hasNumber },
    { key: 'hasSpecialChar', label: 'One special character (!@#$%^&*)', met: requirements.hasSpecialChar },
  ];

  if (password.length === 0) {
    return null;
  }

  const barColor = strengthColors[strength];

  return (
    <div className="mt-3 space-y-3">
      {/* Strength Bar */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <span style={{ fontSize: 11, color: 'var(--text-3)', letterSpacing: 0.2, textTransform: 'uppercase', fontWeight: 600 }}>
            Password Strength
          </span>
          <span style={{ fontSize: 11, fontWeight: 600, color: barColor }}>
            {strengthLabels[strength]}
          </span>
        </div>
        <div
          className="rounded-full overflow-hidden"
          style={{ height: 5, background: 'var(--surface-sunk)', border: '1px solid var(--border)' }}
        >
          <div
            className="h-full transition-all duration-300 rounded-full"
            style={{ width: `${percentage}%`, background: barColor }}
          />
        </div>
      </div>

      {/* Requirements List */}
      <div className="space-y-1">
        {requirementsList.map((req) => (
          <div
            key={req.key}
            className="flex items-center gap-2"
            style={{ fontSize: 11.5, color: req.met ? 'var(--ok-500)' : 'var(--text-4)' }}
          >
            {req.met ? <Check className="w-3 h-3" /> : <X className="w-3 h-3" />}
            <span>{req.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default PasswordStrength;
