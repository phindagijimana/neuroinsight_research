import React from 'react';

interface IconProps extends React.SVGProps<SVGSVGElement> {}

const Activity: React.FC<IconProps> = (props) => (
  <svg {...props} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <polyline points="22,12 18,12 15,21 9,3 6,12 2,12" />
  </svg>
);

export default Activity;



