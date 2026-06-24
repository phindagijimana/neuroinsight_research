/**
 * Spinner + LoadingState — one consistent loading treatment for the whole app.
 *
 * Replaces the mix of hand-rolled CSS spinners, varied sizes, and inconsistent
 * loading copy. Use <LoadingState message="Loading jobs…" /> for a centred
 * block, or <Spinner /> inline (e.g. inside a button).
 */
import React from 'react';

const SIZE = { sm: 'h-4 w-4 border-2', md: 'h-6 w-6 border-2', lg: 'h-8 w-8 border-[3px]' };

export const Spinner: React.FC<{ size?: keyof typeof SIZE; className?: string }> = ({
  size = 'md',
  className = '',
}) => (
  <span
    role="status"
    aria-label="Loading"
    className={`inline-block animate-spin rounded-full border-navy-600 border-t-transparent ${SIZE[size]} ${className}`}
  />
);

export const LoadingState: React.FC<{ message?: string; className?: string }> = ({
  message = 'Loading…',
  className = '',
}) => (
  <div className={`flex flex-col items-center justify-center py-12 text-center ${className}`}>
    <Spinner size="lg" />
    <p className="text-gray-500 mt-4 text-sm">{message}</p>
  </div>
);

export default LoadingState;
