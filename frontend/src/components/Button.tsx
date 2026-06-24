/**
 * Button — the one button in the app.
 *
 * Collapses the dozens of inline `bg-[#003d7a] … rounded-md hover:…` variants
 * (and their drifting sizes/disabled styles) into a single, consistent control.
 * Extra layout utilities (w-full, gap, etc.) can still be passed via className.
 *
 *   <Button onClick={...}>Save</Button>
 *   <Button variant="secondary" size="sm">Cancel</Button>
 *   <Button variant="danger">Delete</Button>
 */
import React from 'react';

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost';
type Size = 'sm' | 'md' | 'lg';

const VARIANT: Record<Variant, string> = {
  primary: 'bg-[#003d7a] text-white border border-transparent hover:bg-[#002b55]',
  secondary: 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50',
  danger: 'bg-red-600 text-white border border-transparent hover:bg-red-700',
  ghost: 'bg-transparent text-gray-600 border border-transparent hover:bg-gray-100',
};

const SIZE: Record<Size, string> = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-sm',
  lg: 'px-5 py-2.5 text-base',
};

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', className = '', type = 'button', children, ...rest }, ref) => (
    <button
      ref={ref}
      type={type}
      className={`inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#003d7a]/40 disabled:opacity-50 disabled:cursor-not-allowed ${VARIANT[variant]} ${SIZE[size]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  )
);
Button.displayName = 'Button';

export default Button;
