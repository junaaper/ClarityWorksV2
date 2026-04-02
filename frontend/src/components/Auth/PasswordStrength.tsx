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

  const strengthColors = {
    weak: 'bg-red-500',
    fair: 'bg-yellow-500',
    good: 'bg-blue-500',
    strong: 'bg-green-500',
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

  return (
    <div className="mt-2 space-y-3">
      {/* Strength Bar */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-gray-600">Password Strength</span>
          <span className={`text-xs font-medium ${
            strength === 'weak' ? 'text-red-600' :
            strength === 'fair' ? 'text-yellow-600' :
            strength === 'good' ? 'text-blue-600' :
            'text-green-600'
          }`}>
            {strengthLabels[strength]}
          </span>
        </div>
        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all duration-300 ${strengthColors[strength]}`}
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>

      {/* Requirements List */}
      <div className="space-y-1">
        {requirementsList.map((req) => (
          <div
            key={req.key}
            className={`flex items-center gap-2 text-xs ${
              req.met ? 'text-green-600' : 'text-gray-500'
            }`}
          >
            {req.met ? (
              <Check className="w-3 h-3" />
            ) : (
              <X className="w-3 h-3" />
            )}
            <span>{req.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default PasswordStrength;
