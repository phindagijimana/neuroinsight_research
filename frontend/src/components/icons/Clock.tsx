import React from 'react';

interface IconProps extends React.SVGProps<SVGSVGElement> {}

const Clock: React.FC<IconProps> = (props) => (
  <svg {...props} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <circle cx={12} cy={12} r={10} />
    <polyline points="12,6 12,12 16,14" />
  </svg>
);

export default Clock;



