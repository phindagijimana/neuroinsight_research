import React from 'react';

interface IconProps extends React.SVGProps<SVGSVGElement> {}

const ChevronLeft: React.FC<IconProps> = (props) => (
  <svg {...props} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
  </svg>
);

export default ChevronLeft;



