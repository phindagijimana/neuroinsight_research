import React from 'react';

interface IconProps extends React.SVGProps<SVGSVGElement> {}

const ZoomIn: React.FC<IconProps> = (props) => (
  <svg {...props} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <circle cx={11} cy={11} r={8} />
    <path d="M21 21l-4.35-4.35" />
    <path d="M11 8v6m-3-3h6" />
  </svg>
);

export default ZoomIn;



