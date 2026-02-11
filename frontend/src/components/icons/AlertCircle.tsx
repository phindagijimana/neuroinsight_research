import React from 'react';

interface IconProps extends React.SVGProps<SVGSVGElement> {}

const AlertCircle: React.FC<IconProps> = (props) => (
  <svg {...props} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <circle cx={12} cy={12} r={10} />
    <path d="M12 8v4m0 4h.01" />
  </svg>
);

export default AlertCircle;



